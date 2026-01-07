#!/bin/bash
# checkpoint.sh - Manual checkpoint command
# Manual checkpoint command: immediately save all current changes
# Location: ~/.claude/hooks/checkpoint.sh
# Usage: bash ~/.claude/hooks/checkpoint.sh

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}💾 Creating checkpoint...${NC}"
echo ""

# Check for changes
STAGED=$(git diff --cached --name-only 2>/dev/null | wc -l)
MODIFIED=$(git diff --name-only 2>/dev/null | wc -l)
UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null | wc -l)
TOTAL=$((STAGED + MODIFIED + UNTRACKED))

if [ "$TOTAL" -eq 0 ]; then
  echo -e "${GREEN}✓ No changes to checkpoint${NC}"
  exit 0
fi

echo "Found $TOTAL file(s) with changes"
echo ""

# Stage all
echo "📦 Staging all changes..."
git add .

# Get current branch
BRANCH=$(git branch --show-current)
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
MESSAGE_PREFIX=${GIT_CHECKPOINT_MESSAGE:-"checkpoint"}

# Create commit
echo "📝 Creating checkpoint commit..."
git commit -q -m "$MESSAGE_PREFIX: Manual save at $TIMESTAMP

Files: $TOTAL modified/added
Triggered by: Manual checkpoint command

🤖 Generated with [Claude Code](https://claude.com/claude-code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>"

if [ $? -ne 0 ]; then
  echo -e "${RED}❌ Failed to create checkpoint${NC}"
  exit 1
fi

COMMIT_HASH=$(git rev-parse --short HEAD)
echo -e "${GREEN}✅ Checkpoint created: $COMMIT_HASH${NC}"
echo ""

# Push
echo "🌐 Pushing to remote..."
git push origin "$BRANCH"

if [ $? -eq 0 ]; then
  echo ""
  echo -e "${GREEN}✅ Checkpoint successfully saved and pushed${NC}"
  echo ""
  echo "Summary:"
  echo "  • Branch: $BRANCH"
  echo "  • Commit: $COMMIT_HASH"
  echo "  • Files: $TOTAL"
else
  echo ""
  echo -e "${YELLOW}⚠️  Checkpoint saved locally but push failed${NC}"
  echo "Retry push manually: git push origin $BRANCH"
fi
