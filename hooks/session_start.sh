#!/bin/bash
# SessionStart Hook - Display working environment info
# ~/.claude/hooks/session_start.sh

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Claude Code Session Started"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📁 Working Directory: $(pwd)"
echo ""

# Git info
if [ -d .git ]; then
    branch=$(git branch --show-current 2>/dev/null || echo "detached")
    echo "🔀 Git Branch: $branch"

    # Show uncommitted changes count
    modified=$(git status --porcelain 2>/dev/null | wc -l)
    if [ "$modified" -gt 0 ]; then
        echo "   ⚠️  Uncommitted changes: $modified files"
    else
        echo "   ✅ Working tree clean"
    fi
    echo ""
fi

# Check for project CLAUDE.md
if [ -f .claude/CLAUDE.md ]; then
    echo "📝 Project CLAUDE.md found"
else
    echo "💡 Tip: Create .claude/CLAUDE.md for project-specific instructions"
fi

# List available custom commands
if [ -d .claude/commands ] && [ "$(ls -A .claude/commands 2>/dev/null)" ]; then
    cmd_count=$(find .claude/commands -name "*.md" 2>/dev/null | wc -l)
    echo "⚡ Custom Commands: $cmd_count available (type / to see)"
fi

# List available agents
if [ -d .claude/agents ] && [ "$(ls -A .claude/agents 2>/dev/null)" ]; then
    agent_count=$(find .claude/agents -name "*.md" 2>/dev/null | wc -l)
    echo "🤖 Custom Agents: $agent_count available (use /agents)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
