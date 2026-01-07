#!/bin/bash
# install-auto-sync.sh - Quick installer for auto-sync features
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
echo "Choose installation type:"
echo ""
echo "1) Smart Checkpoint (Recommended)"
echo "   • Auto-save every 10 files"
echo "   • Token cost: +16%"
echo "   • Data loss risk: <0.1%"
echo ""
echo "2) Zero-Cost Solution"
echo "   • Git post-commit hook only"
echo "   • Token cost: 0%"
echo "   • Auto-push on manual commit"
echo ""
echo "3) Full Protection"
echo "   • Smart Checkpoint + Post-commit hook + Manual commands"
echo "   • Token cost: +16%"
echo "   • Maximum security"
echo ""
echo "4) Ultimate (File Watcher)"
echo "   • Real-time file monitoring"
echo "   • Token cost: 0%"
echo "   • Requires background process"
echo ""

read -p "Choose (1-4): " CHOICE
echo ""

case $CHOICE in
  1)
    echo -e "${BLUE}Installing Smart Checkpoint...${NC}"
    INSTALL_CHECKPOINT=1
    INSTALL_HOOK=0
    INSTALL_WATCHER=0
    ;;
  2)
    echo -e "${BLUE}Installing Zero-Cost Solution...${NC}"
    INSTALL_CHECKPOINT=0
    INSTALL_HOOK=1
    INSTALL_WATCHER=0
    ;;
  3)
    echo -e "${BLUE}Installing Full Protection...${NC}"
    INSTALL_CHECKPOINT=1
    INSTALL_HOOK=1
    INSTALL_WATCHER=0
    ;;
  4)
    echo -e "${BLUE}Installing Ultimate Solution...${NC}"
    INSTALL_CHECKPOINT=0
    INSTALL_HOOK=1
    INSTALL_WATCHER=1
    ;;
  *)
    echo -e "${RED}Invalid choice${NC}"
    exit 1
    ;;
esac

# Step 2: Install Smart Checkpoint
if [ "$INSTALL_CHECKPOINT" = "1" ]; then
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "1️⃣  Configure Smart Checkpoint"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  # Check if settings.json exists
  SETTINGS_FILE="$HOME/.claude/settings.json"

  if [ ! -f "$SETTINGS_FILE" ]; then
    echo -e "${YELLOW}⚠️  settings.json does not exist, creating new file...${NC}"
    cp "$HOME/.claude/examples/settings-with-checkpoint.json" "$SETTINGS_FILE"
    echo -e "${GREEN}✓ Created settings.json${NC}"
  else
    echo -e "${YELLOW}⚠️  settings.json already exists${NC}"
    echo "Please manually add the following configuration to ~/.claude/settings.json:"
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
    read -p "Press Enter after manual addition to continue..."
  fi
  echo ""
fi

# Step 3: Install Post-Commit Hook
if [ "$INSTALL_HOOK" = "1" ]; then
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "2️⃣  Install Post-Commit Hook"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  read -p "Project path (leave empty to install in all git repos): " PROJECT_PATH
  echo ""

  if [ -z "$PROJECT_PATH" ]; then
    echo "Searching for all git repositories..."
    COUNT=0

    # Find all git repos in home directory (max depth 5)
    find ~ -maxdepth 5 -name ".git" -type d 2>/dev/null | while read gitdir; do
      repo=$(dirname "$gitdir")
      echo "  • Installing to: $repo"

      cp ~/.claude/hooks/git-hooks/post-commit-auto-push \
         "$gitdir/hooks/post-commit" 2>/dev/null || true
      chmod +x "$gitdir/hooks/post-commit" 2>/dev/null || true

      COUNT=$((COUNT + 1))
    done

    echo -e "${GREEN}✓ Installed to all git repositories${NC}"
  else
    if [ -d "$PROJECT_PATH/.git" ]; then
      cp ~/.claude/hooks/git-hooks/post-commit-auto-push \
         "$PROJECT_PATH/.git/hooks/post-commit"
      chmod +x "$PROJECT_PATH/.git/hooks/post-commit"
      echo -e "${GREEN}✓ Installed to $PROJECT_PATH${NC}"
    else
      echo -e "${RED}❌ Error: $PROJECT_PATH is not a git repository${NC}"
    fi
  fi
  echo ""
fi

# Step 4: Install File Watcher
if [ "$INSTALL_WATCHER" = "1" ]; then
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "3️⃣  Install File Watcher"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  # Check OS
  if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Detected Linux system"
    if ! command -v inotifywait &> /dev/null; then
      echo "Installing inotify-tools..."
      sudo apt-get update && sudo apt-get install -y inotify-tools
    fi
    echo -e "${GREEN}✓ inotify-tools installed${NC}"
  elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Detected macOS system"
    if ! command -v fswatch &> /dev/null; then
      echo "Installing fswatch..."
      brew install fswatch
    fi
    echo -e "${GREEN}✓ fswatch installed${NC}"
  else
    echo -e "${RED}❌ Unsupported operating system${NC}"
    exit 1
  fi
  echo ""

  read -p "Project path to monitor: " WATCH_PATH

  if [ -z "$WATCH_PATH" ]; then
    echo -e "${RED}❌ Path cannot be empty${NC}"
    exit 1
  fi

  if [ ! -d "$WATCH_PATH" ]; then
    echo -e "${RED}❌ Path does not exist${NC}"
    exit 1
  fi

  echo ""
  echo "Starting file watcher..."
  echo "Hint: Press Ctrl+C to stop"
  echo ""

  # Create watcher script if not exists
  if [ ! -f ~/.claude/hooks/git-watcher.sh ]; then
    echo -e "${YELLOW}⚠️  git-watcher.sh does not exist, please create it first${NC}"
    exit 1
  fi

  # Start watcher in background
  nohup bash ~/.claude/hooks/git-watcher.sh "$WATCH_PATH" \
    > ~/.claude/logs/git-watcher.log 2>&1 &

  WATCHER_PID=$!
  echo -e "${GREEN}✓ File watcher started (PID: $WATCHER_PID)${NC}"
  echo "Log file: ~/.claude/logs/git-watcher.log"
  echo ""
  echo "Stop command: kill $WATCHER_PID"
  echo ""
fi

# Step 5: Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Installation complete${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$INSTALL_CHECKPOINT" = "1" ]; then
  echo "✓ Smart checkpoint configured"
  echo "  • Threshold: 10 files"
  echo "  • Adjust: export GIT_CHECKPOINT_THRESHOLD=5"
  echo ""
fi

if [ "$INSTALL_HOOK" = "1" ]; then
  echo "✓ Post-commit hook installed"
  echo "  • Auto-push on every commit"
  echo "  • Disable: export GIT_AUTO_PUSH=0"
  echo ""
fi

if [ "$INSTALL_WATCHER" = "1" ]; then
  echo "✓ File watcher running"
  echo "  • Monitored path: $WATCH_PATH"
  echo "  • View logs: tail -f ~/.claude/logs/git-watcher.log"
  echo ""
fi

echo "📚 Related documentation:"
echo "  • Full analysis: ~/.claude/docs/auto-sync-analysis.md"
echo "  • Quick commands: ~/.claude/commands/checkpoint.md"
echo ""

echo "🧪 Testing method:"
echo "  1. Modify 10 files, observe auto-checkpoint"
echo "  2. Manual run: bash ~/.claude/hooks/checkpoint.sh"
echo "  3. View history: git log --grep='checkpoint'"
echo ""

echo "Need help? Run:"
echo "  cat ~/.claude/docs/auto-sync-analysis.md | less"
echo ""
