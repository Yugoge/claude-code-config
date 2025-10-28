#!/bin/bash
# push.sh - Executable version of /push command
# Location: ~/.claude/hooks/push.sh
# Usage: bash ~/.claude/hooks/push.sh

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}🚀 Starting validated push...${NC}"
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

# Step 4: Prompt for auto-staging (if enabled and files exist)
SHOULD_STAGE=0
if [ "${GIT_PUSH_AUTO_STAGE:-1}" = "1" ] && ([ "$MODIFIED_COUNT" != "0" ] || [ "$UNTRACKED_COUNT" != "0" ]); then
  TOTAL_UNSTAGED=$((MODIFIED_COUNT + UNTRACKED_COUNT))
  echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${YELLOW}Auto-Staging Available${NC}"
  echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  echo "Found $TOTAL_UNSTAGED file(s) not staged for commit."
  echo ""
  echo -e "${CYAN}Stage all files including untracked? (y/n)${NC}"
  read -r RESPONSE

  if [ "$RESPONSE" = "y" ] || [ "$RESPONSE" = "Y" ] || [ "$RESPONSE" = "yes" ]; then
    SHOULD_STAGE=1
  fi
  echo ""
fi

# Step 5: Stage files if requested
if [ "$SHOULD_STAGE" = "1" ]; then
  echo "📦 Staging all files..."
  git add .
  if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Error: Failed to stage files${NC}"
    exit 1
  fi

  # Recount staged files
  STAGED=$(git diff --cached --name-only 2>/dev/null)
  STAGED_COUNT=$(echo "$STAGED" | grep -c '^' 2>/dev/null || echo "0")

  echo -e "${GREEN}✅ Staged $STAGED_COUNT file(s)${NC}"
  echo ""
fi

# Step 6: Check if there are staged changes to commit
if [ "$STAGED_COUNT" = "0" ]; then
  echo -e "${YELLOW}⚠️  No staged changes to commit${NC}"
  echo ""

  # Check if there are commits to push
  COMMITS_AHEAD=$(git rev-list --count @{u}..HEAD 2>/dev/null || echo "0")
  if [ "$COMMITS_AHEAD" != "0" ] && [ "$COMMITS_AHEAD" != "" ]; then
    echo "However, you have $COMMITS_AHEAD commit(s) ahead of remote."
    echo "Proceeding with push..."
    echo ""
  else
    echo "Nothing to commit or push."
    echo ""
    if [ "$MODIFIED_COUNT" != "0" ] || [ "$UNTRACKED_COUNT" != "0" ]; then
      echo "Suggestions:"
      echo "  • Stage files: git add <file>"
      echo "  • Stage all: git add ."
      echo "  • Run this script again with auto-staging"
    fi
    exit 0
  fi
else
  # Step 7: Check for git lock file before committing
  LOCK_FILE=".git/index.lock"
  if [ -f "$LOCK_FILE" ]; then
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
          exit 1
        fi
      else
        echo "Operation cancelled."
        echo "To remove manually: rm $LOCK_FILE"
        exit 0
      fi
    fi
  fi

  # Step 8: Create commit with staged changes
  echo "📝 Creating commit..."

  # Generate commit message
  COMMIT_MSG="Update: Comprehensive changes via push script

🤖 Generated with [Claude Code](https://claude.com/claude-code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>"

  # Create commit
  git commit -m "$COMMIT_MSG"
  if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Error: Failed to create commit${NC}"
    exit 1
  fi

  COMMIT_HASH=$(git rev-parse --short HEAD)
  echo -e "${GREEN}✅ Commit created: $COMMIT_HASH${NC}"
  echo ""
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
