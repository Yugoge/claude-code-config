#!/bin/bash
# ============================================================================
# Claude Code Auto-Commit One-Click Installer
# Claude Code 自动提交一键安装脚本
# ============================================================================
# 用途：快速安装和配置 Claude Code 自动提交功能
# 使用：bash install.sh
# ============================================================================

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

# 打印标题
print_header() {
  echo -e "${BOLD}${BLUE}"
  echo "╔════════════════════════════════════════════════════════════════════════════╗"
  echo "║                                                                            ║"
  echo "║   Claude Code Auto-Commit Installer                                       ║"
  echo "║   Claude Code 自动提交安装程序                                              ║"
  echo "║                                                                            ║"
  echo "╚════════════════════════════════════════════════════════════════════════════╝"
  echo -e "${NC}"
}

# 打印步骤
print_step() {
  echo -e "${BOLD}${BLUE}➜ $1${NC}"
}

# 打印成功消息
print_success() {
  echo -e "${GREEN}✅ $1${NC}"
}

# 打印警告消息
print_warning() {
  echo -e "${YELLOW}⚠️  $1${NC}"
}

# 打印错误消息
print_error() {
  echo -e "${RED}❌ $1${NC}"
}

# 检查命令是否存在
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# 主安装流程
main() {
  print_header

  # 步骤 1: 创建目录
  print_step "创建 hooks 目录..."
  mkdir -p ~/.claude/hooks
  print_success "目录创建完成"

  # 步骤 2: 检查文件是否已存在
  if [ -f ~/.claude/hooks/auto-commit.sh ]; then
    print_warning "检测到已存在的配置文件"
    read -p "是否覆盖现有文件? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      print_warning "安装已取消"
      exit 0
    fi
  fi

  # 步骤 3: 下载或复制脚本文件
  # 注意：这个安装脚本假设你已经在 ~/.claude/hooks/ 目录
  # 如果要从网络下载，需要修改这部分
  print_step "检查脚本文件..."

  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

  if [ -f "$SCRIPT_DIR/auto-commit.sh" ]; then
    print_success "脚本文件已存在"
  else
    print_error "找不到脚本文件。请确保在正确的目录运行此脚本。"
    exit 1
  fi

  # 步骤 4: 设置执行权限
  print_step "设置脚本执行权限..."
  chmod +x ~/.claude/hooks/auto-commit.sh
  chmod +x ~/.claude/hooks/ensure-git-repo.sh
  print_success "权限设置完成"

  # 步骤 5: 备份现有 settings.json
  if [ -f ~/.claude/settings.json ]; then
    print_step "备份现有配置..."
    cp ~/.claude/settings.json ~/.claude/settings.json.backup.$(date +%Y%m%d_%H%M%S)
    print_success "配置已备份"
  fi

  # 步骤 6: 检查依赖
  print_step "检查依赖..."

  if ! command_exists git; then
    print_error "Git 未安装。请先安装 Git。"
    exit 1
  fi
  print_success "Git 已安装"

  if ! command_exists gh; then
    print_warning "GitHub CLI 未安装（可选）"
    echo -e "${YELLOW}  安装方法:${NC}"
    echo -e "${YELLOW}    macOS: brew install gh${NC}"
    echo -e "${YELLOW}    Linux: sudo apt install gh${NC}"
    echo -e "${YELLOW}    其他: https://cli.github.com/${NC}"
  else
    print_success "GitHub CLI 已安装"

    if ! gh auth status > /dev/null 2>&1; then
      print_warning "GitHub CLI 未登录"
      echo -e "${YELLOW}  运行: gh auth login${NC}"
    else
      print_success "GitHub CLI 已登录"
    fi
  fi

  # 步骤 7: 配置环境变量（可选）
  print_step "配置环境变量（可选）..."

  read -p "是否启用自动创建 GitHub 仓库? (y/N): " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    SHELL_RC=""
    if [ -f ~/.bashrc ]; then
      SHELL_RC=~/.bashrc
    elif [ -f ~/.zshrc ]; then
      SHELL_RC=~/.zshrc
    fi

    if [ -n "$SHELL_RC" ]; then
      if ! grep -q "CLAUDE_AUTO_CREATE_REPO" "$SHELL_RC"; then
        echo "" >> "$SHELL_RC"
        echo "# Claude Code Auto-Commit Configuration" >> "$SHELL_RC"
        echo "export CLAUDE_AUTO_CREATE_REPO=true" >> "$SHELL_RC"
        print_success "环境变量已添加到 $SHELL_RC"
        print_warning "请运行: source $SHELL_RC"
      else
        print_warning "环境变量已存在于 $SHELL_RC"
      fi
    fi
  fi

  # 步骤 8: 完成
  echo ""
  echo -e "${BOLD}${GREEN}"
  echo "╔════════════════════════════════════════════════════════════════════════════╗"
  echo "║                                                                            ║"
  echo "║   ✅ 安装完成！                                                             ║"
  echo "║                                                                            ║"
  echo "╚════════════════════════════════════════════════════════════════════════════╝"
  echo -e "${NC}"

  echo -e "${BOLD}下一步操作:${NC}"
  echo -e "  ${BLUE}1.${NC} 重启 Claude Code"
  echo -e "  ${BLUE}2.${NC} 查看文档: ${YELLOW}cat ~/.claude/hooks/README.md${NC}"
  echo -e "  ${BLUE}3.${NC} 快速开始: ${YELLOW}cat ~/.claude/hooks/QUICKSTART.md${NC}"
  echo ""
  echo -e "${BOLD}测试安装:${NC}"
  echo -e "  ${YELLOW}bash ~/.claude/hooks/auto-commit.sh${NC}"
  echo ""
}

# 运行安装
main

exit 0
