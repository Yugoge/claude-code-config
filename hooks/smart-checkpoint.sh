#!/bin/bash
# smart-checkpoint.sh - Intelligent auto-checkpoint system
# Smart checkpoint system: automatically save code at appropriate times
# Location: ~/.claude/hooks/smart-checkpoint.sh

# Configuration
CHECKPOINT_THRESHOLD=${GIT_CHECKPOINT_THRESHOLD:-10}  # Default: 10 files accumulated
SILENT_MODE=${GIT_CHECKPOINT_SILENT:-0}  # Silent mode flag

# Count changes
STAGED=$(git diff --cached --name-only 2>/dev/null | wc -l)
MODIFIED=$(git diff --name-only 2>/dev/null | wc -l)
UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null | wc -l)
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
  git add . 2>/dev/null

  # Create checkpoint commit
  git commit -q -m "checkpoint: Auto-save at $TIMESTAMP

Files: $TOTAL modified/added
Triggered by: Smart checkpoint system (threshold: $CHECKPOINT_THRESHOLD)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>" 2>/dev/null

  if [ $? -eq 0 ]; then
    # Push in background (won't block workflow)
    git push origin $(git branch --show-current) >/dev/null 2>&1 &

    if [ "$SILENT_MODE" != "1" ]; then
      COMMIT_HASH=$(git rev-parse --short HEAD)
      echo "✅ Checkpoint saved: $COMMIT_HASH ($TOTAL files)"
    fi
  fi
fi

exit 0
