#!/bin/bash
# PreToolUse Safety Hook - Warn before dangerous operations
# ~/.claude/hooks/pre_tool_use_safety.sh

# This hook is triggered before dangerous operations
# It should be configured in settings.json with specific matchers

# Example: For rm -rf operations
if [[ "$1" == *"rm -rf"* ]] || [[ "$1" == *"rm -r"* ]]; then
    echo ""
    echo "⚠️  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "⚠️  DANGER: About to delete files/directories recursively"
    echo "⚠️  Command: $1"
    echo "⚠️  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "⚠️  Please confirm this action is intentional."
    echo "⚠️  Deleted files CANNOT be recovered!"
    echo "⚠️  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
fi

# Example: For git push --force
if [[ "$1" == *"git push --force"* ]] || [[ "$1" == *"git push -f"* ]]; then
    echo ""
    echo "⚠️  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "⚠️  WARNING: Force push will rewrite remote history"
    echo "⚠️  Command: $1"
    echo "⚠️  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "⚠️  This affects other developers!"
    echo "⚠️  Are you sure you want to proceed?"
    echo "⚠️  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
fi

# Example: For package.json modifications
if [[ "$1" == *"package.json"* ]]; then
    echo ""
    echo "📦 Modifying package.json"
    echo "💡 Remember to run: npm install"
    echo ""
fi

# Example: For .env file modifications (BLOCK instead of warn)
if [[ "$1" == *".env"* ]] || [[ "$1" == *"credentials"* ]] || [[ "$1" == *"secret"* ]]; then
    echo ""
    echo "🔒 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔒 BLOCKED: Attempting to modify sensitive file"
    echo "🔒 File: $1"
    echo "🔒 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔒 This file contains secrets and should NEVER be edited by AI"
    echo "🔒 Please modify this file manually"
    echo "🔒 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    exit 2  # Exit code 2 blocks the operation
fi
