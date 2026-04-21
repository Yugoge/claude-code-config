#!/bin/bash
# ============================================================================
# stop-git-commit.sh - Stop hook: snapshot on conversation end (chain #1)
# ----------------------------------------------------------------------------
# Writes a checkpoint to refs/checkpoints/<branch> via the shared library.
# The working branch HEAD is never moved.
#
# Note: This hook runs BEFORE auto-commit.sh in the Stop chain. The first
# hook to fire creates a checkpoint; the second one sees TREE == PARENT_TREE
# (idempotency short-circuit in checkpoint-core.sh) and returns 0 silently.
# ============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if this is a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
  echo -e "${YELLOW}⚠️  Not a git repository. Skipping checkpoint.${NC}"
  exit 0
fi

# Fast exit if there are no changes (tracked modifications + untracked)
UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null | wc -l)
if git diff --quiet && git diff --cached --quiet && [ "$UNTRACKED" -eq 0 ]; then
  echo -e "${GREEN}✅ No changes to checkpoint.${NC}"
  exit 0
fi

# Source and delegate to the shared library
# shellcheck source=lib/checkpoint-core.sh
. "$HOME/.claude/hooks/lib/checkpoint-core.sh"

if write_checkpoint "" "stop hook: stop-git-commit.sh"; then
  TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
  BRANCH=$(git branch --show-current 2>/dev/null)
  if [ -n "$BRANCH" ]; then
    SANITIZED=$(printf '%s' "$BRANCH" | tr '/' '-')
  else
    SHORT=$(git rev-parse --short HEAD 2>/dev/null)
    SANITIZED="detached-${SHORT:-empty}"
  fi
  REF="refs/checkpoints/${SANITIZED}"
  TIP=$(git rev-parse --short "$REF" 2>/dev/null)
  echo -e "${GREEN}✅ Checkpoint saved at $TIMESTAMP${NC}"
  echo -e "${GREEN}   Ref: ${REF}${NC}"
  if [ -n "$TIP" ]; then
    echo -e "${GREEN}   Tip: ${TIP}${NC}"
  fi
else
  echo -e "${RED}❌ Checkpoint failed. See ~/.claude/logs/checkpoint.log${NC}"
  exit 1
fi

exit 0
