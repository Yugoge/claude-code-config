# Plan: 直接注入官方 Todo 文件，移除 PostToolUse Hook

## Context

当前三 hook 架构存在冗余：PostToolUse/TodoWrite hook 负责把 Claude Code 原生维护的 todo 状态"转存"到 `/tmp/`，再由 Stop hook 读取。实际上 Claude Code 自己已经把 TodoWrite 状态写入了 `~/.claude/todos/{session_id}-agent-{session_id}.json`。

目标：直接读官方文件，移除 PostToolUse hook，简化整体架构。

---

## 官方 Todo 文件结构（已验证）

**路径**：`~/.claude/todos/{session_id}-agent-{session_id}.json`
- 主 session（非 subagent）时 session_id == agent_id
- 每次 TodoWrite 后 Claude Code 自动更新此文件
- 内容：`[{"content": "...", "activeForm": "...", "status": "pending|in_progress|completed"}]`

---

## 新架构（零自定义文件）

| Hook | 职责 |
|---|---|
| UserPromptSubmit | 阶段A：直接写官方文件 + 告知 Claude 已就绪；阶段B：读官方文件注入当前进度 |
| PostToolUse/TodoWrite | **移除** |
| Stop | 读官方文件，检查所有 todos 是否全部 completed |
| SessionStart | `clear_stale_workflow_state()` 删除，无自定义文件需清理 |

不写任何自定义文件。`blocking_count` 废弃——要求所有 todos 全部 completed。

---

## 变更细节

### 1. `hook-checklist-userprompt.py` — 两阶段，阶段A直接写官方文件

**阶段 A（命令起点）**：检测到 `/command` → 运行 todo 脚本 → **直接写入官方文件** → 打印"checklist 已创建，直接使用"。

```python
official_todos = Path.home() / '.claude' / 'todos' / f'{session_id}-agent-{session_id}.json'
official_todos.parent.mkdir(parents=True, exist_ok=True)
official_todos.write_text(json.dumps(todos, ensure_ascii=False))

print(f"CHECKLIST PRE-INITIALIZED: /{cmd_name} workflow checklist has been created.")
print(f"Use TodoRead to view it. Begin immediately with Step 1: {todos[0]['content']}")
```

Claude 无需自己调用 TodoWrite 初始化——checklist 已就位，直接 mark in_progress/completed 即可。

**阶段 B（后续 prompt）**：无 slash command → 读官方文件。有未完成 todos → 注入进度提醒。
```python
official_todos = Path.home() / '.claude' / 'todos' / f'{session_id}-agent-{session_id}.json'
if official_todos.exists():
    todos = json.loads(official_todos.read_text())
    incomplete = [t for t in todos if t.get('status') != 'completed']
    if incomplete:
        print(format_progress(todos))
```

**注意**：需验证 Claude Code 的 TodoRead 是从磁盘读还是从内存缓存读。若从内存读，阶段 A 的文件写入对 Claude 不可见，但阶段 B 的注入仍然有效（Stop hook 也直接读文件）。

### 2. `hook-enforce-workflow.py` — 只读官方文件，按数量判断

```python
official_todos = Path.home() / '.claude' / 'todos' / f'{session_id}-agent-{session_id}.json'
```

- 文件不存在或为空 → exit(0)
- `completed_count = len([t for t in todos if t['status'] == 'completed'])`
- `total_steps = len(todos)` — 等于脚本步骤数（Phase A 从脚本写入）
- `completed_count < total_steps` → exit(2)，提示还差几步
- `completed_count == total_steps` → exit(0)

不检查 status 字段是否为 in_progress，不删除任何文件。

### 3. `hook-todo-state-tracker.py` — 从 settings.json 注销

从所有项目的 `.claude/settings.json` 删除 PostToolUse/TodoWrite hook 条目。

### 4. `hook-session-start.py` — 移除 clear_stale_workflow_state()

没有自定义文件需要清理，删除该函数。

---

## 文件修改清单

| 文件 | 操作 |
|------|------|
| `scripts/hooks/hook-checklist-userprompt.py` | 移除所有文件写入；添加阶段 B（读官方文件注入进度） |
| `scripts/hooks/hook-enforce-workflow.py` | 改读官方文件；移除所有自定义文件读写 |
| `scripts/hooks/hook-session-start.py` | 移除 `clear_stale_workflow_state()` 和 `is_pid_alive()` |
| `.claude/settings.json`（所有 7 个项目）| 删除 PostToolUse/TodoWrite hook 条目 |

**彻底消除**：所有 /tmp 文件、所有自定义状态文件。纯读官方文件。

---

## 边界情况

- **官方文件不存在**（TodoWrite 从未调用）：Stop hook 仍按"工作流未开始"逻辑处理
- **Subagent 的 agent_id ≠ session_id**：只读主 session 文件，subagent todos 忽略（符合预期）
- **多开 session**：每个 session 有独立官方文件（`{session_id}-agent-{session_id}.json`），天然隔离，无需 /tmp 文件

---

## 验证方法

1. 执行 `/ask` 命令 → UserPromptSubmit 注入初始 checklist
2. Claude 调用 TodoWrite → 官方文件更新
3. 用户继续输入 → UserPromptSubmit 注入当前进度（从官方文件读取）
4. 不完成 blocking steps → Stop hook 阻止并提示
5. 完成所有 blocking steps → Stop hook 放行
