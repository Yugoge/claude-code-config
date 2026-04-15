#!/bin/bash
# smart-checkpoint.sh - Intelligent auto-checkpoint system
# Smart checkpoint system: automatically save code at appropriate times
# Location: ~/.claude/hooks/posttool-git-checkpoint.sh
#
# Worktree awareness: detects when edited file is inside a .claude/worktrees/
# directory and uses git -C <worktree_root> so commits land on the worktree
# branch instead of polluting the main repo branch.

# Configuration
CHECKPOINT_THRESHOLD=${GIT_CHECKPOINT_THRESHOLD:-10}  # Default: 10 files accumulated
SILENT_MODE=${GIT_CHECKPOINT_SILENT:-0}  # Silent mode flag

# Worktree detection: parse TOOL_INPUT to find file_path, detect worktree context
GIT_DIR=""
if [ -n "$TOOL_INPUT" ]; then
  # Extract file_path from JSON (handles both Write and Edit tools)
  FILE_PATH=$(echo "$TOOL_INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"//;s/"$//')

  if [ -n "$FILE_PATH" ]; then
    # Check if path contains .claude/worktrees/<session-name>/
    if echo "$FILE_PATH" | grep -q '/.claude/worktrees/[^/]\+/'; then
      # Extract worktree root: everything up to and including .claude/worktrees/<name>/
      WORKTREE_ROOT=$(echo "$FILE_PATH" | sed 's|\(.*/.claude/worktrees/[^/]*/\).*|\1|')
      # Verify the directory exists before using it
      if [ -d "$WORKTREE_ROOT" ]; then
        GIT_DIR="$WORKTREE_ROOT"
        if [ "$SILENT_MODE" != "1" ]; then
          echo "📂 Worktree detected: $GIT_DIR"
        fi
      fi
    fi
  fi
fi

# Allow explicit override via environment variable
GIT_DIR="${GIT_CHECKPOINT_DIR:-$GIT_DIR}"

# Build git command: use -C flag when targeting a worktree, bare git otherwise
if [ -n "$GIT_DIR" ]; then
  GIT_CMD="git -C $GIT_DIR"
else
  GIT_CMD="git"
fi

# Count changes
STAGED=$($GIT_CMD diff --cached --name-only 2>/dev/null | wc -l)
MODIFIED=$($GIT_CMD diff --name-only 2>/dev/null | wc -l)
UNTRACKED=$($GIT_CMD ls-files --others --exclude-standard 2>/dev/null | wc -l)
TOTAL=$((STAGED + MODIFIED + UNTRACKED))

# Exit if no changes
if [ "$TOTAL" -eq 0 ]; then
  exit 0
fi

# Check if threshold reached
if [ "$TOTAL" -ge "$CHECKPOINT_THRESHOLD" ]; then
  TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

  if [ "$SILENT_MODE" != "1" ]; then
    echo "💾 Auto-checkpoint triggered: $TOTAL files pending"
  fi

  # Stage all changes
  $GIT_CMD add . 2>/dev/null

  # Create checkpoint commit
  $GIT_CMD commit -q -m "checkpoint: Auto-save at $TIMESTAMP

Files: $TOTAL modified/added
Triggered by: Smart checkpoint system (threshold: $CHECKPOINT_THRESHOLD)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>" 2>/dev/null

  if [ $? -eq 0 ]; then
    # Push in background (won't block workflow) -- use worktree's current branch
    $GIT_CMD push origin $($GIT_CMD branch --show-current) >/dev/null 2>&1 &

    if [ "$SILENT_MODE" != "1" ]; then
      COMMIT_HASH=$($GIT_CMD rev-parse --short HEAD)
      echo "✅ Checkpoint saved: $COMMIT_HASH ($TOTAL files)"
    fi
  fi
fi

exit 0
