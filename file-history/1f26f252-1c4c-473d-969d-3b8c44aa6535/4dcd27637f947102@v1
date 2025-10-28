#!/bin/bash
# ============================================================================
# Ensure Git Repository Hook for Claude Code
# 确保项目有 Git 仓库（没有则自动创建）
# ============================================================================
# 用途：在 Claude Code 会话开始时检查并初始化 Git 仓库
# 触发：SessionStart Hook
# ============================================================================

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查是否已经是 git 仓库
if git rev-parse --git-dir > /dev/null 2>&1; then
  echo -e "${GREEN}✅ Git repository already exists.${NC}"
  exit 0
fi

# 获取当前目录名作为仓库名
REPO_NAME=$(basename "$PWD")

echo -e "${BLUE}🚀 No Git repository found. Initializing...${NC}"

# 初始化 git
git init > /dev/null 2>&1

# 创建 .gitignore（如果不存在）
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

# 初始提交
git add .
git commit -m "Initial commit

🤖 Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>" > /dev/null 2>&1

echo -e "${GREEN}✅ Git repository initialized with initial commit${NC}"

# 检查是否安装了 GitHub CLI
if ! command -v gh &> /dev/null; then
  echo -e "${YELLOW}⚠️  GitHub CLI (gh) not found.${NC}"
  echo -e "${YELLOW}   Install it to auto-create remote repositories:${NC}"
  echo -e "${YELLOW}   https://cli.github.com/${NC}"
  exit 0
fi

# 检查是否已登录 GitHub CLI
if ! gh auth status > /dev/null 2>&1; then
  echo -e "${YELLOW}⚠️  GitHub CLI not authenticated.${NC}"
  echo -e "${YELLOW}   Run: gh auth login${NC}"
  exit 0
fi

# 询问是否创建远程仓库（通过环境变量控制）
# 设置 CLAUDE_AUTO_CREATE_REPO=true 来自动创建
# 设置 CLAUDE_AUTO_CREATE_REPO=false 来跳过
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

# 自动创建 GitHub 仓库
echo -e "${BLUE}🌐 Creating GitHub repository: $REPO_NAME${NC}"

# 创建私有仓库并推送
if gh repo create "$REPO_NAME" --private --source=. --remote=origin --push > /dev/null 2>&1; then
  USERNAME=$(gh api user -q .login)
  echo -e "${GREEN}✅ Repository created: https://github.com/$USERNAME/$REPO_NAME${NC}"
else
  echo -e "${RED}❌ Failed to create GitHub repository.${NC}"
  echo -e "${YELLOW}   You can create it manually: gh repo create \"$REPO_NAME\" --private --source=. --remote=origin --push${NC}"
  exit 1
fi

exit 0
