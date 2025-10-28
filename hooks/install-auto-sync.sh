#!/bin/bash
# install-auto-sync.sh - Quick installer for auto-sync features
# 自动同步功能快速安装脚本
# Location: ~/.claude/hooks/install-auto-sync.sh
# Usage: bash ~/.claude/hooks/install-auto-sync.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}🚀 Auto-Sync Installation Wizard${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Step 1: Choose installation type
echo "请选择安装类型 / Choose installation type:"
echo ""
echo "1) 智能检查点 (推荐) - Smart Checkpoint (Recommended)"
echo "   • 每10个文件自动保存"
echo "   • Token成本: +16%"
echo "   • 数据丢失风险: <0.1%"
echo ""
echo "2) 零成本方案 - Zero-Cost Solution"
echo "   • 仅使用 Git post-commit hook"
echo "   • Token成本: 0%"
echo "   • 手动commit时自动push"
echo ""
echo "3) 完整保护 - Full Protection"
echo "   • 智能检查点 + Post-commit hook + 手动命令"
echo "   • Token成本: +16%"
echo "   • 最高安全性"
echo ""
echo "4) 终极方案 - Ultimate (File Watcher)"
echo "   • 实时文件监控"
echo "   • Token成本: 0%"
echo "   • 需要后台运行"
echo ""

read -p "选择 (1-4): " CHOICE
echo ""

case $CHOICE in
  1)
    echo -e "${BLUE}安装智能检查点...${NC}"
    INSTALL_CHECKPOINT=1
    INSTALL_HOOK=0
    INSTALL_WATCHER=0
    ;;
  2)
    echo -e "${BLUE}安装零成本方案...${NC}"
    INSTALL_CHECKPOINT=0
    INSTALL_HOOK=1
    INSTALL_WATCHER=0
    ;;
  3)
    echo -e "${BLUE}安装完整保护...${NC}"
    INSTALL_CHECKPOINT=1
    INSTALL_HOOK=1
    INSTALL_WATCHER=0
    ;;
  4)
    echo -e "${BLUE}安装终极方案...${NC}"
    INSTALL_CHECKPOINT=0
    INSTALL_HOOK=1
    INSTALL_WATCHER=1
    ;;
  *)
    echo -e "${RED}无效选择${NC}"
    exit 1
    ;;
esac

# Step 2: Install Smart Checkpoint
if [ "$INSTALL_CHECKPOINT" = "1" ]; then
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "1️⃣  配置智能检查点"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  # Check if settings.json exists
  SETTINGS_FILE="$HOME/.claude/settings.json"

  if [ ! -f "$SETTINGS_FILE" ]; then
    echo -e "${YELLOW}⚠️  settings.json 不存在，创建新文件...${NC}"
    cp "$HOME/.claude/examples/settings-with-checkpoint.json" "$SETTINGS_FILE"
    echo -e "${GREEN}✓ 已创建 settings.json${NC}"
  else
    echo -e "${YELLOW}⚠️  settings.json 已存在${NC}"
    echo "请手动添加以下配置到 ~/.claude/settings.json："
    echo ""
    cat <<'EOF'
{
  "env": {
    "GIT_CHECKPOINT_THRESHOLD": "10",
    "GIT_CHECKPOINT_SILENT": "0"
  },
  "hooks": [
    {
      "matcher": "Edit|Write|NotebookEdit",
      "type": "PostToolUse",
      "hooks": [{
        "type": "command",
        "command": "~/.claude/hooks/smart-checkpoint.sh"
      }]
    }
  ]
}
EOF
    echo ""
    read -p "手动添加后按回车继续..."
  fi
  echo ""
fi

# Step 3: Install Post-Commit Hook
if [ "$INSTALL_HOOK" = "1" ]; then
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "2️⃣  安装 Post-Commit Hook"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  read -p "项目路径 (留空则在所有 git 仓库安装): " PROJECT_PATH
  echo ""

  if [ -z "$PROJECT_PATH" ]; then
    echo "搜索所有 git 仓库..."
    COUNT=0

    # Find all git repos in home directory (max depth 5)
    find ~ -maxdepth 5 -name ".git" -type d 2>/dev/null | while read gitdir; do
      repo=$(dirname "$gitdir")
      echo "  • 安装到: $repo"

      cp ~/.claude/hooks/git-hooks/post-commit-auto-push \
         "$gitdir/hooks/post-commit" 2>/dev/null || true
      chmod +x "$gitdir/hooks/post-commit" 2>/dev/null || true

      COUNT=$((COUNT + 1))
    done

    echo -e "${GREEN}✓ 已安装到所有 git 仓库${NC}"
  else
    if [ -d "$PROJECT_PATH/.git" ]; then
      cp ~/.claude/hooks/git-hooks/post-commit-auto-push \
         "$PROJECT_PATH/.git/hooks/post-commit"
      chmod +x "$PROJECT_PATH/.git/hooks/post-commit"
      echo -e "${GREEN}✓ 已安装到 $PROJECT_PATH${NC}"
    else
      echo -e "${RED}❌ 错误: $PROJECT_PATH 不是 git 仓库${NC}"
    fi
  fi
  echo ""
fi

# Step 4: Install File Watcher
if [ "$INSTALL_WATCHER" = "1" ]; then
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "3️⃣  安装 File Watcher"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  # Check OS
  if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "检测到 Linux 系统"
    if ! command -v inotifywait &> /dev/null; then
      echo "安装 inotify-tools..."
      sudo apt-get update && sudo apt-get install -y inotify-tools
    fi
    echo -e "${GREEN}✓ inotify-tools 已安装${NC}"
  elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "检测到 macOS 系统"
    if ! command -v fswatch &> /dev/null; then
      echo "安装 fswatch..."
      brew install fswatch
    fi
    echo -e "${GREEN}✓ fswatch 已安装${NC}"
  else
    echo -e "${RED}❌ 不支持的操作系统${NC}"
    exit 1
  fi
  echo ""

  read -p "要监控的项目路径: " WATCH_PATH

  if [ -z "$WATCH_PATH" ]; then
    echo -e "${RED}❌ 路径不能为空${NC}"
    exit 1
  fi

  if [ ! -d "$WATCH_PATH" ]; then
    echo -e "${RED}❌ 路径不存在${NC}"
    exit 1
  fi

  echo ""
  echo "启动 file watcher..."
  echo "提示：按 Ctrl+C 停止"
  echo ""

  # Create watcher script if not exists
  if [ ! -f ~/.claude/hooks/git-watcher.sh ]; then
    echo -e "${YELLOW}⚠️  git-watcher.sh 不存在，请先创建${NC}"
    exit 1
  fi

  # Start watcher in background
  nohup bash ~/.claude/hooks/git-watcher.sh "$WATCH_PATH" \
    > ~/.claude/logs/git-watcher.log 2>&1 &

  WATCHER_PID=$!
  echo -e "${GREEN}✓ File watcher 已启动 (PID: $WATCHER_PID)${NC}"
  echo "日志文件: ~/.claude/logs/git-watcher.log"
  echo ""
  echo "停止命令: kill $WATCHER_PID"
  echo ""
fi

# Step 5: Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ 安装完成${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$INSTALL_CHECKPOINT" = "1" ]; then
  echo "✓ 智能检查点已配置"
  echo "  • 阈值: 10个文件"
  echo "  • 调整: export GIT_CHECKPOINT_THRESHOLD=5"
  echo ""
fi

if [ "$INSTALL_HOOK" = "1" ]; then
  echo "✓ Post-commit hook 已安装"
  echo "  • 每次 commit 自动 push"
  echo "  • 禁用: export GIT_AUTO_PUSH=0"
  echo ""
fi

if [ "$INSTALL_WATCHER" = "1" ]; then
  echo "✓ File watcher 正在运行"
  echo "  • 监控路径: $WATCH_PATH"
  echo "  • 查看日志: tail -f ~/.claude/logs/git-watcher.log"
  echo ""
fi

echo "📚 相关文档："
echo "  • 完整分析: ~/.claude/docs/auto-sync-analysis.md"
echo "  • 快速命令: ~/.claude/commands/checkpoint.md"
echo ""

echo "🧪 测试方法："
echo "  1. 修改10个文件，观察自动checkpoint"
echo "  2. 手动运行: bash ~/.claude/hooks/checkpoint.sh"
echo "  3. 查看历史: git log --grep='checkpoint'"
echo ""

echo "需要帮助？运行："
echo "  cat ~/.claude/docs/auto-sync-analysis.md | less"
echo ""
