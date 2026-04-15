#!/bin/bash
# PreToolUse hook: Block EnterWorktree tool
# EnterWorktree always bases worktree on origin/main (remote upstream), NOT local HEAD.
# For forked repos this silently replaces local code with upstream code.
# Use ~/.claude/scripts/create-worktree.sh instead.
# Exit 2 = block

TOOL_NAME="${CLAUDE_TOOL_NAME:-}"

if [ "$TOOL_NAME" = "EnterWorktree" ]; then
    cat >&2 << 'EOF'
BLOCKED: EnterWorktree uses origin/main as start point, not local HEAD.
This causes worktrees to contain upstream code instead of local changes.

Use this instead:
  bash ~/.claude/scripts/create-worktree.sh <name>

It creates a worktree from HEAD and prints the path.
EOF
    exit 2
fi

exit 0
