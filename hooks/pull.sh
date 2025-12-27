#!/bin/bash
# pull.sh - Executable version of /pull command
# Location: ~/.claude/hooks/pull.sh
# Usage: bash ~/.claude/hooks/pull.sh

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔄 Starting safe pull...${NC}"
echo ""

# Step 1: Check for uncommitted changes
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  HAS_CHANGES=1
else
  HAS_CHANGES=0
fi

# Step 2: Stash if necessary
if [ "$HAS_CHANGES" = "1" ]; then
  echo -e "${YELLOW}📦 Uncommitted changes detected${NC}"
  echo "Stashing changes before pull..."
  TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
  git stash push -m "Auto-stash before pull ($TIMESTAMP)"
  if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Error: Failed to stash changes${NC}"
    exit 1
  fi
  echo -e "${GREEN}✅ Stashed as: stash@{0}${NC}"
  echo ""
  STASHED=1
else
  STASHED=0
  echo "Working directory clean, no stash needed"
  echo ""
fi

# Step 3: Get current branch
BRANCH=$(git branch --show-current)
if [ -z "$BRANCH" ]; then
  echo -e "${RED}❌ Error: Not on a branch (detached HEAD)${NC}"
  if [ "$STASHED" = "1" ]; then
    echo "Restoring stashed changes..."
    git stash pop
  fi
  exit 1
fi

echo "Pulling from origin/$BRANCH with rebase..."

# Step 4: Check for git lock file before pulling
LOCK_FILE=".git/index.lock"
if [ -f "$LOCK_FILE" ]; then
  echo ""
  echo -e "${YELLOW}⚠️  Warning: Git lock file detected${NC}"
  echo ""
  echo "A lock file exists at: $LOCK_FILE"
  echo "This usually means:"
  echo "  • Another git process is running"
  echo "  • A previous git process crashed"
  echo ""

  # Check if any git process is running
  GIT_PROCESSES=$(ps aux | grep -i '[g]it' | grep -v grep || true)
  if [ -n "$GIT_PROCESSES" ]; then
    echo -e "${RED}Active git processes found:${NC}"
    echo "$GIT_PROCESSES"
    echo ""
    echo "Please wait for other git operations to complete."

    if [ "$STASHED" = "1" ]; then
      echo ""
      echo "Restoring stashed changes before exit..."
      git stash pop
    fi
    exit 1
  else
    echo "No active git processes detected."
    echo "The lock file appears to be stale (from a crashed process)."
    echo ""
    echo -e "${CYAN}Remove the lock file and continue? (y/n)${NC}"
    read -r RESPONSE

    if [ "$RESPONSE" = "y" ] || [ "$RESPONSE" = "Y" ] || [ "$RESPONSE" = "yes" ]; then
      rm -f "$LOCK_FILE"
      if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Lock file removed${NC}"
        echo ""
      else
        echo -e "${RED}❌ Failed to remove lock file${NC}"
        echo "You may need to remove it manually:"
        echo "  rm $LOCK_FILE"

        if [ "$STASHED" = "1" ]; then
          echo ""
          echo "Restoring stashed changes before exit..."
          git stash pop
        fi
        exit 1
      fi
    else
      echo "Operation cancelled."
      echo "To remove manually: rm $LOCK_FILE"

      if [ "$STASHED" = "1" ]; then
        echo ""
        echo "Restoring stashed changes before exit..."
        git stash pop
      fi
      exit 0
    fi
  fi
fi

# Step 5: Pull with rebase
git pull --rebase origin "$BRANCH"
PULL_STATUS=$?

# Step 6: Check for conflicts
if [ $PULL_STATUS -ne 0 ]; then
  echo ""
  echo -e "${RED}⚠️  Conflicts detected during rebase!${NC}"
  echo ""

  # List conflicted files
  CONFLICTED=$(git diff --name-only --diff-filter=U 2>/dev/null)
  if [ -n "$CONFLICTED" ]; then
    echo "Conflicted files:"
    echo "$CONFLICTED" | sed 's/^/   - /'
    echo ""
  fi

  echo "Resolution steps:"
  echo "  1. Edit conflicted files to resolve conflicts"
  echo "  2. Stage resolved files: git add <file>"
  echo "  3. Continue rebase: git rebase --continue"
  echo ""
  echo "Or abort the rebase: git rebase --abort"
  echo ""

  if [ "$STASHED" = "1" ]; then
    echo -e "${YELLOW}⚠️  Note: Stashed changes not yet restored${NC}"
    echo "After resolving rebase, restore with: git stash pop"
    echo ""
  fi

  exit 1
fi

echo -e "${GREEN}✅ Pull completed successfully${NC}"
echo ""

# Step 7: Pop stash if created
if [ "$STASHED" = "1" ]; then
  echo "📦 Restoring stashed changes..."
  git stash pop
  POP_STATUS=$?

  if [ $POP_STATUS -ne 0 ]; then
    echo ""
    echo -e "${YELLOW}⚠️  Stash conflicts detected${NC}"
    echo ""
    echo "Resolution steps:"
    echo "  1. Check status: git status"
    echo "  2. Edit conflicted files to resolve"
    echo "  3. Stage resolved files: git add <file>"
    echo "  4. Drop stash after resolution: git stash drop"
    echo ""
    echo "Or keep changes in stash: (no action needed)"
    exit 1
  fi

  echo -e "${GREEN}✅ Stashed changes restored${NC}"
  echo ""
fi

# Step 8: Show summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Pull complete!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Count new commits
COMMITS_BEHIND=$(git rev-list --count HEAD@{1}..HEAD 2>/dev/null || echo "0")

echo "Summary:"
echo "  • Branch: $BRANCH"
echo "  • New commits: $COMMITS_BEHIND"
if [ "$STASHED" = "1" ]; then
  echo "  • Stashed changes: Restored"
fi
echo ""

# Show recent commits if any were pulled
if [ "$COMMITS_BEHIND" != "0" ] && [ "$COMMITS_BEHIND" != "" ]; then
  echo "Recent commits:"
  git log --oneline -5
  echo ""
fi

echo "Next steps:"
echo "  • Review changes: git log --oneline -5"
echo "  • Check status: git status"
