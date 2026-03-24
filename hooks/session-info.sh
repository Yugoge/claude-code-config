#!/bin/bash
# s-info.sh — SessionStart: display environment info + tool quick reference

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Claude Code Session Started"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Dir: $(pwd)"

# Git info
if [ -d .git ]; then
    branch=$(git branch --show-current 2>/dev/null || echo "detached")
    modified=$(git status --porcelain 2>/dev/null | wc -l)
    if [ "$modified" -gt 0 ]; then
        echo "  Git: $branch  (! $modified uncommitted files)"
    else
        echo "  Git: $branch  (clean)"
    fi
fi

# Project metadata
[ -f .claude/CLAUDE.md ] && echo "  CLAUDE.md: project instructions loaded"
cmd_count=$(find .claude/commands -name "*.md" 2>/dev/null | wc -l)
agent_count=$(find .claude/agents -name "*.md" 2>/dev/null | wc -l)
[ "$cmd_count" -gt 0 ] && echo "  Commands:  $cmd_count available"
[ "$agent_count" -gt 0 ] && echo "  Agents:    $agent_count available"

echo ""
