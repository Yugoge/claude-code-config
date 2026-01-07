#!/bin/bash
# ============================================================================
# Auto-Commit Hook for Claude Code
# Automatically commit Claude Code changes
# ============================================================================
# Purpose: Auto-commit all changes after Claude Code completes a response
# Trigger: Stop Hook
# ============================================================================

set -e

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configurable Co-Authorship
# Set CLAUDE_CO_AUTHOR environment variable to customize
# Leave empty to skip co-author
CO_AUTHOR=${CLAUDE_CO_AUTHOR:-"Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>"}

# Check if this is a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
  echo -e "${YELLOW}⚠️  Not a git repository. Skipping commit.${NC}"
  exit 0
fi

# Check if there are changes
if git diff --quiet && git diff --cached --quiet; then
  echo -e "${GREEN}✅ No changes to commit.${NC}"
  exit 0
fi

# Get current timestamp
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

# Try to get last user prompt from Claude session (optional feature)
# Requires access to Claude's session data, fallback provided here
LAST_PROMPT="Claude Code auto-commit"

# Add staged file list to commit message if available
CHANGED_FILES=$(git diff --cached --name-only 2>/dev/null || git diff --name-only)
FILE_COUNT=$(echo "$CHANGED_FILES" | wc -l | tr -d ' ')

# Build commit message
COMMIT_MSG="Auto-commit: $TIMESTAMP

Changed $FILE_COUNT file(s):
$(echo "$CHANGED_FILES" | head -n 10 | sed 's/^/- /')
$([ $FILE_COUNT -gt 10 ] && echo "... and $((FILE_COUNT - 10)) more")

🤖 Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

${CO_AUTHOR}"

# Add all changes
git add -A

# Commit
if git commit -m "$COMMIT_MSG" > /dev/null 2>&1; then
  echo -e "${GREEN}✅ Committed: Auto-commit at $TIMESTAMP${NC}"
  echo -e "${GREEN}   Files changed: $FILE_COUNT${NC}"

  # Auto Push (comment out the code below if you don't want auto push)
  # ========================================
  # Check if remote repository is configured
  if git remote get-url origin > /dev/null 2>&1; then
    echo -e "${YELLOW}📤 Pushing to remote...${NC}"

    # Get current branch
    CURRENT_BRANCH=$(git branch --show-current)

    # Push (don't error on failure)
    if git push origin "$CURRENT_BRANCH" > /dev/null 2>&1; then
      echo -e "${GREEN}✅ Pushed to origin/$CURRENT_BRANCH${NC}"
    else
      echo -e "${YELLOW}⚠️  Push failed. You may need to pull first or check permissions.${NC}"
    fi
  else
    echo -e "${YELLOW}⚠️  No remote repository configured. Skipping push.${NC}"
  fi
  # ========================================

else
  echo -e "${RED}❌ Commit failed.${NC}"
  exit 1
fi

exit 0
