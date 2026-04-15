#!/bin/bash
# PreToolUse hook: Block Playwright navigation to production URLs
# Prevents any agent from accessing production web/API via browser
# Created: 2026-04-04 after QA agent polluted production session

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)

# Act on Playwright navigation/code tools and WebFetch
case "$TOOL_NAME" in
  mcp__playwright__browser_navigate|mcp__playwright__browser_click|mcp__playwright__browser_run_code|WebFetch) ;;
  *) exit 0 ;;
esac

# Extract URL for navigate, or ref text for click
TOOL_INPUT=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d.get('tool_input',{})))" 2>/dev/null)

# Check for production URLs
if echo "$TOOL_INPUT" | grep -qE 'life-ai\.app' && ! echo "$TOOL_INPUT" | grep -qE 'dev\.life-ai\.app|api-dev\.life-ai\.app'; then
  echo "BLOCKED: Navigating to production life-ai.app is FORBIDDEN" >&2
  echo "Only dev.life-ai.app and api-dev.life-ai.app are allowed." >&2
  echo "Tool input: $TOOL_INPUT" >&2
  exit 2
fi

if echo "$TOOL_INPUT" | grep -qE 'localhost:8090|localhost:3000'; then
  echo "BLOCKED: Navigating to production ports (8090/3000) is FORBIDDEN" >&2
  echo "Only localhost:8097 (dev web) and localhost:3005 (dev API) are allowed." >&2
  echo "Tool input: $TOOL_INPUT" >&2
  exit 2
fi

exit 0
