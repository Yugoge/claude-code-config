# Checkpoint Command

Quick save current progress with automatic commit and push.

## Usage

```bash
bash ~/.claude/hooks/checkpoint.sh
```

This command will:
1. Check for any uncommitted changes
2. Stage all files (git add .)
3. Create a checkpoint commit with timestamp
4. Push to remote automatically

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
