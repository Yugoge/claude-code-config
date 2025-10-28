#!/bin/bash
# pre-commit-check.sh - Detect untracked files before commit
# Part of Claude Code git tracking solution
# Location: ~/.claude/hooks/pre-commit-check.sh

# Configuration (from environment variables)
AUTO_STAGE=${GIT_AUTO_STAGE_ALL:-0}
BLOCK_MODE=${GIT_BLOCK_ON_UNTRACKED:-0}
WARN_MODE=${GIT_WARN_UNTRACKED:-1}

# Colors for terminal output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect untracked files (respecting .gitignore)
UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null)

# Exit early if no untracked files
if [ -z "$UNTRACKED" ]; then
  exit 0
fi

# Count untracked files (more robust method)
COUNT=$(echo "$UNTRACKED" | grep -c '^' || echo "1")

# Auto-stage mode - automatically add all files
if [ "$AUTO_STAGE" = "1" ]; then
  echo -e "${BLUE}🔄 Auto-staging all files...${NC}"
  echo ""
  echo "Adding:"
  echo "$UNTRACKED" | sed 's/^/   - /'
  echo ""
  git add .
  if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ All files staged automatically${NC}"
    echo ""
    echo "Note: Auto-staged all files (GIT_AUTO_STAGE_ALL=1)"
  else
    echo -e "${RED}❌ Error staging files${NC}"
    exit 2
  fi
  exit 0
fi

# Block mode - prevent commit if untracked files exist
if [ "$BLOCK_MODE" = "1" ]; then
  echo -e "${RED}❌ ERROR: Untracked files detected!${NC}"
  echo ""
  echo "The following $COUNT file(s) are not tracked by git:"
  echo "$UNTRACKED" | sed 's/^/   - /'
  echo ""
  echo "Commit blocked. Please:"
  echo "  1. Add files: git add <file>"
  echo "  2. Or ignore: echo 'filename' >> .gitignore"
  echo "  3. Or stage all: git add ."
  echo ""
  echo "To bypass: git commit --no-verify"
  exit 1
fi

# Warn mode (default) - show warning but allow commit
if [ "$WARN_MODE" = "1" ]; then
  echo -e "${YELLOW}⚠️  Warning: $COUNT untracked file(s) detected:${NC}"
  echo "$UNTRACKED" | sed 's/^/   - /'
  echo ""
  echo "Commit will proceed without these files."
  echo "Run 'git add .' to include them, or use /push command."
  echo ""
fi

exit 0
