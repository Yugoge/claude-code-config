#!/bin/bash
# protection-status.sh - Display protection status for all git repositories
# Display protection status for all git repositories
# Location: ~/.claude/hooks/protection-status.sh
# Usage: bash ~/.claude/hooks/protection-status.sh

echo "┌─────────────────────────────────────────────────────────────────┐"
echo "│          Git Three-Layer Protection System - Status              │"
echo "└─────────────────────────────────────────────────────────────────┘"
echo ""

# Find all git repositories
find ~ -maxdepth 3 -type d -name ".git" 2>/dev/null | sort | while read git_dir; do
    repo_dir=$(dirname "$git_dir")
    repo_name=$(basename "$repo_dir")

    # Skip if not accessible
    if [ ! -d "$repo_dir" ]; then
        continue
    fi

    # Check each layer
    layer1="❌"
    layer2="❌"
    layer3="❌"
    status="🔴"

    # Layer 1: Smart Checkpoint
    if [ -f "$repo_dir/.claude/settings.json" ]; then
        if grep -q "smart-checkpoint" "$repo_dir/.claude/settings.json" 2>/dev/null; then
            layer1="✅"
        else
            layer1="⚠️"
        fi
    else
        # Uses global settings
        if grep -q "smart-checkpoint" ~/.claude/settings.json 2>/dev/null; then
            layer1="✅"
        fi
    fi

    # Layer 2: Post-Commit Auto-Push
    if [ -f "$repo_dir/.git/hooks/post-commit" ]; then
        if grep -q "auto-push\|GIT_AUTO_PUSH\|git push" "$repo_dir/.git/hooks/post-commit" 2>/dev/null; then
            layer2="✅"
        else
            layer2="⚠️"
        fi
    fi

    # Layer 3: FSWatch
    if ps aux | grep -q "[g]it-fswatch.sh $repo_dir"; then
        layer3="✅"
    fi

    # Overall status
    if [ "$layer1" = "✅" ] && [ "$layer2" = "✅" ] && [ "$layer3" = "✅" ]; then
        status="🟢"
    elif [ "$layer1" = "❌" ] && [ "$layer2" = "❌" ] && [ "$layer3" = "❌" ]; then
        status="🔴"
    else
        status="🟡"
    fi

    # Get git status
    cd "$repo_dir" 2>/dev/null
    uncommitted=$(git status --porcelain 2>/dev/null | wc -l)
    branch=$(git branch --show-current 2>/dev/null || echo "detached")

    # Print status line
    printf "%-25s %s  L1:%s L2:%s L3:%s  Branch:%s  Changes:%d\n" \
        "$repo_name" "$status" "$layer1" "$layer2" "$layer3" "$branch" "$uncommitted"
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Legend:"
echo "  Status: 🟢 Full Protection | 🟡 Partial Protection | 🔴 No Protection"
echo "  Layers: L1=Smart Checkpoint | L2=Auto-Push | L3=FSWatch"
echo "  Marks:  ✅ Enabled | ⚠️ Partially Enabled | ❌ Disabled"
echo ""
echo "Commands:"
echo "  Install protection: bash ~/.claude/hooks/install-protection-all.sh"
echo "  Start fswatch:      bash ~/.claude/hooks/start-fswatch-all.sh"
echo "  Stop fswatch:       pkill -f git-fswatch.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
