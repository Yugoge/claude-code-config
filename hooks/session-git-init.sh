#!/bin/bash
# ============================================================================
# Ensure Git Repository Hook for Claude Code
# Ensure project has Git repository (auto-create if none exists)
# ============================================================================
# Purpose: Check and initialize Git repository when Claude Code session starts
# Trigger: SessionStart Hook
# ============================================================================

set -e

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configurable Co-Authorship
CO_AUTHOR=${CLAUDE_CO_AUTHOR:-"Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>"}

# Check if already a git repository
if git rev-parse --git-dir > /dev/null 2>&1; then
  echo -e "${GREEN}✅ Git repository already exists.${NC}"
  exit 0
fi

# Get current directory name as repository name
REPO_NAME=$(basename "$PWD")

echo -e "${BLUE}🚀 No Git repository found. Initializing...${NC}"

# Initialize git
git init > /dev/null 2>&1

# Create .gitignore (if doesn't exist)
if [ ! -f .gitignore ]; then
  cat > .gitignore << 'EOF'
# Dependencies
node_modules/
venv/
__pycache__/
*.pyc
.Python
env/
build/
dist/
*.egg-info/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Environment variables
.env
.env.local
.env.*.local

# Logs
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Claude Code local settings
.claude/settings.local.json
EOF
  echo -e "${GREEN}✅ Created .gitignore${NC}"
fi

# Initial commit
git add .
git commit -m "Initial commit

🤖 Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

${CO_AUTHOR}" > /dev/null 2>&1

echo -e "${GREEN}✅ Git repository initialized with initial commit${NC}"

# Check if GitHub CLI is installed
if ! command -v gh &> /dev/null; then
  echo -e "${YELLOW}⚠️  GitHub CLI (gh) not found.${NC}"
  echo -e "${YELLOW}   Install it to auto-create remote repositories:${NC}"
  echo -e "${YELLOW}   https://cli.github.com/${NC}"
  exit 0
fi

# Check if authenticated with GitHub CLI
if ! gh auth status > /dev/null 2>&1; then
  echo -e "${YELLOW}⚠️  GitHub CLI not authenticated.${NC}"
  echo -e "${YELLOW}   Run: gh auth login${NC}"
  exit 0
fi

# Ask whether to create remote repository (controlled by environment variable)
# Set CLAUDE_AUTO_CREATE_REPO=true to auto-create
# Set CLAUDE_AUTO_CREATE_REPO=false to skip
AUTO_CREATE=${CLAUDE_AUTO_CREATE_REPO:-ask}

if [ "$AUTO_CREATE" = "false" ]; then
  echo -e "${YELLOW}⚠️  Auto-create disabled. Skipping GitHub repository creation.${NC}"
  exit 0
fi

if [ "$AUTO_CREATE" = "ask" ]; then
  echo -e "${BLUE}❓ Create GitHub repository '$REPO_NAME'? (set CLAUDE_AUTO_CREATE_REPO env var to automate)${NC}"
  echo -e "${YELLOW}   Skipping for now. Run manually: gh repo create \"$REPO_NAME\" --private --source=. --remote=origin --push${NC}"
  exit 0
fi

# Auto-create GitHub repository
echo -e "${BLUE}🌐 Creating GitHub repository: $REPO_NAME${NC}"

# Create private repository and push
if gh repo create "$REPO_NAME" --private --source=. --remote=origin --push > /dev/null 2>&1; then
  USERNAME=$(gh api user -q .login)
  echo -e "${GREEN}✅ Repository created: https://github.com/$USERNAME/$REPO_NAME${NC}"
else
  echo -e "${RED}❌ Failed to create GitHub repository.${NC}"
  echo -e "${YELLOW}   You can create it manually: gh repo create \"$REPO_NAME\" --private --source=. --remote=origin --push${NC}"
  exit 1
fi

exit 0
