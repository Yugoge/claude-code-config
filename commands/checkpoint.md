# Checkpoint Command

Quick save current progress with automatic commit and push.

快速保存当前进度，自动 commit 并推送。

## Usage

```bash
bash ~/.claude/hooks/checkpoint.sh
```

This command will:
1. Check for any uncommitted changes
2. Stage all files (git add .)
3. Create a checkpoint commit with timestamp
4. Push to remote automatically

该命令会：
1. 检查未提交的修改
2. 暂存所有文件
3. 创建带时间戳的检查点 commit
4. 自动推送到远程

## When to use

- Before taking a break
- After completing a significant change
- When you want to ensure everything is backed up
- As a safety checkpoint during long sessions

## Environment Variables

- `GIT_CHECKPOINT_MESSAGE`: Custom message prefix (default: "checkpoint")

## Examples

```bash
# Quick checkpoint
bash ~/.claude/hooks/checkpoint.sh

# With custom message
GIT_CHECKPOINT_MESSAGE="Before refactoring" bash ~/.claude/hooks/checkpoint.sh
```
