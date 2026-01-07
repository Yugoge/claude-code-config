#!/bin/bash
# install-protection-all.sh - Automatically install protection for all git repos
# Location: ~/.claude/hooks/install-protection-all.sh
# Usage: bash ~/.claude/hooks/install-protection-all.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_TEMPLATE="$SCRIPT_DIR/git-hooks/post-commit-auto-push"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 Git Protection Installer"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🔍 Scanning for git repositories..."
echo ""

create_combined_hook() {
    local repo_dir=$1
    local hook_file="$repo_dir/.git/hooks/post-commit"

    cat > "$hook_file" <<'EOF'
#!/bin/bash
# post-commit - Combined hook: Git LFS + Auto-Push

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 1: Git LFS Post-Commit Hook
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if command -v git-lfs >/dev/null 2>&1; then
    git lfs post-commit "$@"
fi

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PART 2: Auto-Push Hook
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BRANCH=$(git branch --show-current 2>/dev/null)

if [ -z "$BRANCH" ]; then
  exit 0
fi

if [ "${GIT_AUTO_PUSH:-1}" = "0" ]; then
  exit 0
fi

nohup git push origin "$BRANCH" >/dev/null 2>&1 &

exit 0
EOF

    chmod +x "$hook_file"
}

installed_count=0
skipped_count=0

find ~ -maxdepth 3 -type d -name ".git" 2>/dev/null | sort | while read git_dir; do
    repo_dir=$(dirname "$git_dir")
    repo_name=$(basename "$repo_dir")

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📦 Repository: $repo_name"
    echo "   Path: $repo_dir"
    echo ""

    # Check Layer 1 (Settings)
    if [ -f "$repo_dir/.claude/settings.json" ]; then
        if grep -q "smart-checkpoint" "$repo_dir/.claude/settings.json" 2>/dev/null; then
            echo "   ✅ Layer 1: Smart Checkpoint configured"
        else
            echo "   ⚠️  Layer 1: Has custom settings (needs manual review)"
            echo "       Add this to PostToolUse hooks:"
            echo "       {\"command\": \"bash ~/.claude/hooks/smart-checkpoint.sh\"}"
        fi
    else
        echo "   ✅ Layer 1: Using global settings (auto-protected)"
    fi

    # Install Layer 2 (Post-Commit Hook)
    hook_file="$repo_dir/.git/hooks/post-commit"

    if [ -f "$hook_file" ]; then
        if grep -q "auto-push\|GIT_AUTO_PUSH" "$hook_file" 2>/dev/null; then
            echo "   ✅ Layer 2: Auto-push already installed"
        elif grep -q "git-lfs\|git lfs" "$hook_file" 2>/dev/null; then
            echo "   📝 Layer 2: Git LFS detected, creating combined hook"
            create_combined_hook "$repo_dir"
            echo "   ✅ Layer 2: Combined hook installed"
            ((installed_count++))
        else
            echo "   ⚠️  Layer 2: Custom hook exists, skipping"
            echo "       Manual review needed: $hook_file"
            ((skipped_count++))
        fi
    else
        echo "   📝 Layer 2: Installing auto-push hook..."
        if [ -f "$HOOK_TEMPLATE" ]; then
            cp "$HOOK_TEMPLATE" "$hook_file"
            chmod +x "$hook_file"
            echo "   ✅ Layer 2: Installed"
            ((installed_count++))
        else
            echo "   ❌ Layer 2: Template not found at $HOOK_TEMPLATE"
        fi
    fi

    # Check Layer 3 (FSWatch)
    if ps aux | grep -q "[g]it-fswatch.sh $repo_dir"; then
        echo "   ✅ Layer 3: FSWatch monitoring"
    else
        echo "   ❌ Layer 3: Not monitored"
        echo "       Start with: bash ~/.claude/hooks/start-fswatch-all.sh"
    fi

    echo ""
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Installation complete!"
echo ""
echo "Summary:"
echo "  - Hooks installed: $installed_count"
echo "  - Hooks skipped:   $skipped_count"
echo ""
echo "Next steps:"
echo "1. Review repositories with custom settings"
echo "2. Start FSWatch: bash ~/.claude/hooks/start-fswatch-all.sh"
echo "3. Check status:  bash ~/.claude/hooks/protection-status.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
