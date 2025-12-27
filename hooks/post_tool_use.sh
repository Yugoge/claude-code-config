#!/bin/bash
# PostToolUse Hook - Code quality hints after file modifications
# ~/.claude/hooks/post_tool_use.sh

# Get the tool name from environment variable (set by Claude Code)
# For demo purposes, we'll check if a file was modified

# This script is called after Write|Edit operations
# We provide helpful hints without auto-executing commands

# Check if we can detect the modified file
# (In real usage, Claude Code provides tool input context)

echo ""
echo "✅ File modification completed"

# Detect file type and suggest actions
if [ -n "$1" ]; then
    file="$1"
    ext="${file##*.}"

    case "$ext" in
        py)
            echo "💡 Python file modified. Consider:"
            echo "   - Run tests: pytest"
            echo "   - Format: black $file"
            echo "   - Type check: mypy $file"
            ;;
        js|ts|jsx|tsx)
            echo "💡 JavaScript/TypeScript file modified. Consider:"
            echo "   - Run tests: npm test"
            echo "   - Lint: npm run lint"
            echo "   - Format: prettier --write $file"
            ;;
        go)
            echo "💡 Go file modified. Consider:"
            echo "   - Format: gofmt -w $file"
            echo "   - Test: go test"
            ;;
        rs)
            echo "💡 Rust file modified. Consider:"
            echo "   - Format: rustfmt $file"
            echo "   - Check: cargo check"
            ;;
        java)
            echo "💡 Java file modified. Consider:"
            echo "   - Format: Check your IDE formatter"
            echo "   - Build: mvn compile or gradle build"
            ;;
    esac

    # Check file size
    if [ -f "$file" ]; then
        lines=$(wc -l < "$file" 2>/dev/null || echo "?")
        echo "   📊 File stats: $lines lines"
    fi
fi

echo ""
