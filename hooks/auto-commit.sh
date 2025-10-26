#!/bin/bash
# ============================================================================
# Auto-Commit Hook for Claude Code
# 自动提交 Claude Code 的修改
# ============================================================================
# 用途：在 Claude Code 完成响应后自动提交所有更改
# 触发：Stop Hook
# ============================================================================

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 可配置的 Co-Authorship
# 设置环境变量 CLAUDE_CO_AUTHOR 来自定义
# 留空则不添加 co-author
CO_AUTHOR=${CLAUDE_CO_AUTHOR:-"Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>"}

# 检查是否为 git 仓库
if ! git rev-parse --git-dir > /dev/null 2>&1; then
  echo -e "${YELLOW}⚠️  Not a git repository. Skipping commit.${NC}"
  exit 0
fi

# 检查是否有更改
if git diff --quiet && git diff --cached --quiet; then
  echo -e "${GREEN}✅ No changes to commit.${NC}"
  exit 0
fi

# 获取当前时间戳
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

# 尝试从 Claude 会话获取最后的用户提示（可选功能）
# 需要访问 Claude 的会话数据，这里提供备用方案
LAST_PROMPT="Claude Code auto-commit"

# 如果有 git 暂存区的文件列表，添加到提交消息
CHANGED_FILES=$(git diff --cached --name-only 2>/dev/null || git diff --name-only)
FILE_COUNT=$(echo "$CHANGED_FILES" | wc -l | tr -d ' ')

# 构建提交消息
COMMIT_MSG="Auto-commit: $TIMESTAMP

Changed $FILE_COUNT file(s):
$(echo "$CHANGED_FILES" | head -n 10 | sed 's/^/- /')
$([ $FILE_COUNT -gt 10 ] && echo "... and $((FILE_COUNT - 10)) more")

🤖 Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

${CO_AUTHOR}"

# 添加所有更改
git add -A

# 提交
if git commit -m "$COMMIT_MSG" > /dev/null 2>&1; then
  echo -e "${GREEN}✅ Committed: Auto-commit at $TIMESTAMP${NC}"
  echo -e "${GREEN}   Files changed: $FILE_COUNT${NC}"

  # 自动 Push（如果不想自动 push，注释掉下面的代码）
  # ========================================
  # 检查是否配置了远程仓库
  if git remote get-url origin > /dev/null 2>&1; then
    echo -e "${YELLOW}📤 Pushing to remote...${NC}"

    # 获取当前分支
    CURRENT_BRANCH=$(git branch --show-current)

    # Push（如果失败不报错）
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
