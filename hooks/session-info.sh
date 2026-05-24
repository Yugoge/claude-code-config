#!/bin/bash
# s-info.sh — SessionStart: display environment info + tool quick reference
# All output redirected to stderr per spec-20260518-225715 Cycle 3 Debt 9
# (AC-09): SessionStart hooks must not emit on stdout because stdout is the
# protocol channel for hook<->harness JSON; informational messages belong on
# stderr.

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2
echo "  Claude Code Session Started" >&2
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2
echo "" >&2
echo "  Dir: $(pwd)" >&2

# Git info
if [ -d .git ]; then
    branch=$(git branch --show-current 2>/dev/null || echo "detached")
    modified=$(git status --porcelain 2>/dev/null | wc -l)
    if [ "$modified" -gt 0 ]; then
        echo "  Git: $branch  (! $modified uncommitted files)" >&2
    else
        echo "  Git: $branch  (clean)" >&2
    fi
fi

# Project metadata
[ -f .claude/CLAUDE.md ] && echo "  CLAUDE.md: project instructions loaded" >&2
cmd_count=$(find .claude/commands -name "*.md" 2>/dev/null | wc -l)
agent_count=$(find .claude/agents -name "*.md" 2>/dev/null | wc -l)
[ "$cmd_count" -gt 0 ] && echo "  Commands:  $cmd_count available" >&2
[ "$agent_count" -gt 0 ] && echo "  Agents:    $agent_count available" >&2

echo "" >&2
