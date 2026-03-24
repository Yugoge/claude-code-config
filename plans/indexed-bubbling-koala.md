# Hook 系统清理计划

## 背景
设置了 `ENABLE_TOOL_SEARCH=false` 后，所有内置工具 schema 直接加载，不再需要 ToolSearch。因此：
- `pretool-todowrite-validate.py` 失去存在意义（schema 验证已在参数解析阶段拦截 string）
- session-info.sh 中关于 ToolSearch 的提示不再需要
- prompt-workflow.py 中的 WRONG/RIGHT TodoWrite 提示不再需要
- CLAUDE.md 中 "NEVER use ToolSearch" 规则需要更新

## 当前状态
- 全局 `/root/.claude/hooks/`：31 个文件（13 hook + 8 工具 + 4 遗留 + 6 文档/配置）
- 10 个项目各有 14 个文件（13 hook + README）

## 清理计划

### 第1步：删除 pretool-todowrite-validate.py（全局 + 10个项目）
**原因**：`ENABLE_TOOL_SEARCH=false` → TodoWrite schema 直接加载 → 参数类型验证在 schema 层完成 → hook 永远不会被触发

删除文件：
- `/root/.claude/hooks/pretool-todowrite-validate.py`
- 10个项目的 `.claude/hooks/pretool-todowrite-validate.py`

同时从 10个项目的 `settings.json` 中移除对应的 PreToolUse 注册。

### 第2步：清理全局遗留/工具文件
删除以下未注册、未使用的文件：
- `checkpoint.sh` — 被 `posttool-git-checkpoint.sh` 取代
- `pre-commit-check.sh` — 被 `pretool-bash-safety.sh` 取代
- `git-fswatch.sh` / `start-fswatch-all.sh` / `git-fswatch@.service` / `fswatch-manager.sh` — fswatch 系统
- `install.sh` / `install-git-hooks.sh` / `install-auto-sync.sh` / `install-protection-all.sh` — 安装脚本
- `protection-status.sh` — 保护状态检查
- `push.sh` / `pull.sh` — 部署脚本
- `project-settings-template.json` — 模板
- `QUICKSTART.md` / `README-TODO-INJECTION.md` / `INDEX.md` — 冗余文档

共删除 **16 个文件**，仅保留 13 个 hook 脚本 + README.md

### 第3步：简化 session-info.sh 中的 ToolSearch 提示
- 删除 "do NOT ToolSearch these" 的 header
- 删除 WRONG/RIGHT TodoWrite 示例
- 保留工具 schema 列表（仍有参考价值）

### 第4步：简化 prompt-workflow.py 中的 TodoWrite 提示
- 删除 Phase A 和 Phase B 中的 WRONG/RIGHT 对比
- 删除 "If schema errors persist, call ToolSearch" 提示

### 第5步：更新 CLAUDE.md
- 删除或简化 "NEVER use ToolSearch for documented tools" 规则
- 更新 Tool Reference 部分，移除 ToolSearch 相关说明

### 第6步：同步到所有项目
- 将修改后的 session-info.sh、prompt-workflow.py 同步到 10 个项目

## 最终保留的 hook 清单（12个）

| # | 文件 | 事件 | 功能 |
|---|------|------|------|
| 1 | session-info.sh | SessionStart | 环境信息 + 工具参考 |
| 2 | session-git-init.sh | SessionStart | Git 初始化 |
| 3 | prompt-workflow.py | UserPromptSubmit | 工作流 checklist 注入 |
| 4 | pretool-workflow-gate.py | PreToolUse | 要求先确认 todo |
| 5 | pretool-bash-safety.sh | PreToolUse (Bash) | 危险命令拦截 |
| 6 | posttool-git-checkpoint.sh | PostToolUse (Write/Edit) | 自动 checkpoint |
| 7 | posttool-git-warn.sh | PostToolUse (git commit) | 提醒 untracked 文件 |
| 8 | posttool-todo-tracker.py | PostToolUse (TodoWrite) | 进度输出 |
| 9 | posttool-todo-count.py | PostToolUse (TodoWrite) | 强制 todo 数量 |
| 10 | posttool-todo-sequence.py | PostToolUse (TodoWrite) | 强制逐步推进 |
| 11 | stop-workflow-enforce.py | Stop | 工作流完成验证 |
| 12 | stop-git-commit.sh | Stop | 结束时 git commit |

## 验证
- 新会话中测试 TodoWrite 直接使用（无需 ToolSearch）
- 确认 pretool-todowrite-validate.py 已从所有项目删除
- 确认 settings.json 中无残留注册
