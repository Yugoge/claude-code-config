# 分析：ask 脚本损坏原因

## Context

用户反映 /ask 命令近期被"严重损坏"，agent 质量明显下降。需要找出是什么变更造成的，谁改了，改了什么。

---

## 调查结论

### 损坏时间线

今天（2026-03-10）ask.md 被两次修改，两次都是 Auto-commit（自动提交），说明是 Claude Code session 中的 AI 操作所为。

| 提交 | 时间 | 变更内容 | 严重程度 |
|------|------|----------|----------|
| 6b6c116 | 09:46 | 添加 `disable-model-invocation: true` | **高危** |
| 6233996 | 16:10 | 删除 Step 0（自动 TodoWrite 初始化） | 中等 |

analyst.md 从未被修改（自 2026-01-23 初始创建后保持原样）。

---

## 损坏分析

### 问题 1：`disable-model-invocation: true`（高危）

**变更位置**：`.claude/commands/ask.md` frontmatter，commit 6b6c116

**添加前**：
```yaml
description: "Ask any question with automatic web research and comprehensive answers"
allowed-tools: Task, Read, TodoWrite
argument-hint: "<question>"
model: inherit
```

**添加后**：
```yaml
description: "Ask any question with automatic web research and comprehensive answers"
allowed-tools: Task, Read, TodoWrite
argument-hint: "<question>"
model: inherit
disable-model-invocation: true
```

**影响**：
- `disable-model-invocation: true` 让 /ask 命令以"纯工具执行模式"运行，不调用主模型生成回应
- ask 架构的核心是：**主 agent 作为 Teacher** 与用户对话，analyst 作为后端 JSON 顾问
- 关闭模型调用后，主 agent 无法执行自然对话、无法综合 analyst 的 JSON 结果、无法扮演教师角色
- 用户看到的将是工具输出的原始结果，而非自然教学对话
- 这与 ask.md 中三方架构设计完全矛盾

### 问题 2：删除 Step 0（中等）

**变更位置**：`.claude/commands/ask.md`，commit 6233996

**删除内容**：
```markdown
## Step 0: Initialize Workflow Checklist

**Load todos from**: `scripts/todo/ask.py`

Execute via venv:
`source venv/bin/activate && python scripts/todo/ask.py`

Use output to create TodoWrite with all workflow steps.

**Rules**: Mark `in_progress` before each step, `completed` after. NEVER skip steps.
```

**影响**：
- 移除了自动 TodoWrite 初始化，agent 不再强制按步骤执行
- hook-enforce-todo-count.py 仍在强制要求精确的 todo 数量，但 Step 0 消失后 agent 不知道怎么初始化
- 导致 hook 触发错误、工作流混乱

---

## 修复方案

### 修复 1：移除 `disable-model-invocation: true`

**文件**：`.claude/commands/ask.md`（第6行）

删除该行，恢复正常模型调用模式。这是主要修复，影响最大。

### 修复 2：恢复 Step 0

**文件**：`.claude/commands/ask.md`（在步骤列表最前）

恢复自动 TodoWrite 初始化步骤，使 hook 验证和工作流跟踪恢复正常工作。

---

## 验证

修复后，运行 `/ask 什么是量子纠缠` 验证：
1. 主 agent 正常启动对话（而非显示原始 JSON）
2. TodoWrite 显示 10 个步骤
3. analyst 被 Task 工具静默调用
4. 用户看到自然教学对话，不看到 JSON
