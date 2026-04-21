#!/bin/bash
# push.sh - Executable version of /push command
# Location: ~/.claude/hooks/push.sh
# Usage: bash ~/.claude/hooks/push.sh [--auto]
#
# Options:
#   --auto    Non-interactive mode (auto-remove stale locks only; does NOT
#             auto-commit — a dirty tree is ALWAYS rejected with a clear
#             "commit first" message. Automated snapshots now live on
#             refs/checkpoints/<branch> and must NOT be promoted to HEAD.)

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Check for --auto flag or if running in non-interactive environment
AUTO_MODE=0
if [ "$1" = "--auto" ] || [ ! -t 0 ]; then
  AUTO_MODE=1
fi

echo -e "${BLUE}🚀 Starting validated push...${NC}"
if [ "$AUTO_MODE" = "1" ]; then
  echo -e "${CYAN}(Non-interactive mode)${NC}"
fi
echo ""

# Step 1: Get current branch
BRANCH=$(git branch --show-current)
if [ -z "$BRANCH" ]; then
  echo -e "${RED}❌ Error: Not on a branch (detached HEAD)${NC}"
  echo "Checkout a branch first: git checkout <branch-name>"
  exit 1
fi

# Step 2: Check git status
echo "📊 Checking repository status..."
echo ""

# Get staged files
STAGED=$(git diff --cached --name-only 2>/dev/null)
STAGED_COUNT=$(echo "$STAGED" | grep -c '^' 2>/dev/null || echo "0")

# Get modified but unstaged files
MODIFIED=$(git diff --name-only 2>/dev/null)
MODIFIED_COUNT=$(echo "$MODIFIED" | grep -c '^' 2>/dev/null || echo "0")

# Get untracked files (respecting .gitignore)
UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null)
UNTRACKED_COUNT=$(echo "$UNTRACKED" | grep -c '^' 2>/dev/null || echo "0")

# Step 3: Display status summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${CYAN}Git Status Summary${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$STAGED_COUNT" != "0" ] && [ -n "$STAGED" ]; then
  echo -e "${GREEN}Staged files ($STAGED_COUNT):${NC}"
  echo "$STAGED" | sed 's/^/   ✓ /'
  echo ""
fi

if [ "$MODIFIED_COUNT" != "0" ] && [ -n "$MODIFIED" ]; then
  echo -e "${YELLOW}Modified but not staged ($MODIFIED_COUNT):${NC}"
  echo "$MODIFIED" | sed 's/^/   ⚠ /'
  echo ""
fi

if [ "$UNTRACKED_COUNT" != "0" ] && [ -n "$UNTRACKED" ]; then
  echo -e "${YELLOW}Untracked files ($UNTRACKED_COUNT):${NC}"
  echo "$UNTRACKED" | sed 's/^/   ? /'
  echo ""
fi

if [ "$STAGED_COUNT" = "0" ] && [ "$MODIFIED_COUNT" = "0" ] && [ "$UNTRACKED_COUNT" = "0" ]; then
  echo -e "${GREEN}✓ Working directory clean${NC}"
  echo ""
fi

# Step 4: Dirty-tree guard — /push must NOT create commits.
# If the working tree or index is dirty, reject with a clear "commit first"
# message. Automated snapshots live on refs/checkpoints/<branch> (written by
# the Stop hooks and /checkpoint) and must not be promoted to HEAD by /push.
DIRTY_STATUS=$(git status --porcelain 2>/dev/null)
if [ -n "$DIRTY_STATUS" ]; then
  echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${RED}❌ Refusing to push: working tree is dirty${NC}"
  echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  echo "commit first — /push no longer auto-commits."
  echo ""
  echo "Options to proceed:"
  echo "  • Create a real semantic commit:   git add <files> && git commit -m \"...\""
  echo "  • Discard changes:                 git checkout -- <files>"
  echo "  • Snapshot to checkpoint ref only: bash ~/.claude/hooks/checkpoint.sh"
  echo "      (checkpoint saves to refs/checkpoints/<branch>, does NOT move HEAD)"
  echo ""
  echo "Why? Automated snapshots belong on refs/checkpoints/<branch>, never on HEAD."
  echo "See CLAUDE.md → 'Auto-Commit Mechanism' for recovery commands."
  exit 1
fi

# Step 5: No staged/unstaged/untracked content at this point. Verify there is
# actually something to push; otherwise exit cleanly.
if [ "$STAGED_COUNT" = "0" ]; then
  COMMITS_AHEAD=$(git rev-list --count @{u}..HEAD 2>/dev/null || echo "0")
  if [ "$COMMITS_AHEAD" != "0" ] && [ "$COMMITS_AHEAD" != "" ]; then
    echo "Working tree clean. $COMMITS_AHEAD commit(s) ahead of remote — proceeding with push."
    echo ""
  else
    echo "Nothing to push (working tree clean, no commits ahead of remote)."
    echo ""
    exit 0
  fi
fi

# Step 9: Push to remote
echo "🌐 Pushing to remote..."
echo ""

# Check if upstream is set
UPSTREAM=$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null)

if [ -z "$UPSTREAM" ]; then
  # No upstream set, push with -u
  echo "Setting upstream to origin/$BRANCH..."
  git push -u origin "$BRANCH"
  PUSH_STATUS=$?
else
  # Upstream exists, normal push
  git push origin "$BRANCH"
  PUSH_STATUS=$?
fi

# Step 10: Handle push result
if [ $PUSH_STATUS -ne 0 ]; then
  echo ""
  echo -e "${RED}❌ Push failed${NC}"
  echo ""
  echo "Possible causes:"
  echo "  • Remote has changes you don't have (pull first)"
  echo "  • Network connectivity issues"
  echo "  • Authentication failure"
  echo ""
  echo "Suggestions:"
  echo "  • Pull first: git pull --rebase"
  echo "  • Check network connection"
  echo "  • Verify remote access: git remote -v"
  exit 1
fi

# Step 11: Success summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Successfully pushed to origin/$BRANCH${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Get latest commit info
LATEST_COMMIT=$(git log -1 --oneline)
FILES_CHANGED=$(git diff --stat HEAD~1 HEAD 2>/dev/null | tail -n 1)

echo "Summary:"
echo "  • Branch: $BRANCH"
echo "  • Latest commit: $LATEST_COMMIT"
if [ -n "$FILES_CHANGED" ]; then
  echo "  • Changes: $FILES_CHANGED"
fi
echo ""

# Get remote URL
REMOTE_URL=$(git remote get-url origin 2>/dev/null)
if [ -n "$REMOTE_URL" ]; then
  echo "Remote: $REMOTE_URL"
  echo ""
fi

echo "Next steps:"
echo "  • View commit: git show HEAD"
echo "  • Check status: git status"
