#!/bin/bash
# PreToolUse Hook - Block Write tool from overwriting existing files
# Forces agents to use Edit for modifying existing files.
# Reads tool input from stdin as JSON (Claude Code hook protocol)

# Read full JSON from stdin
INPUT=$(cat)

# Extract tool name
TOOL_NAME=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)

# Only act on Write tool
if [ "$TOOL_NAME" != "Write" ]; then
  exit 0
fi

# /do bypass (main-agent only)
_WG_IS_SUB=$(echo "$INPUT" | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print('1' if d.get('agent_id') else '0')" \
  2>/dev/null)
if [ "$_WG_IS_SUB" != "1" ]; then
  _WG_SID=$(echo "$INPUT" | python3 -c \
    "import json,sys,os; d=json.load(sys.stdin); \
print(d.get('session_id','') or os.environ.get('CLAUDE_SESSION_ID','default'))" \
    2>/dev/null)
  [ -z "$_WG_SID" ] && _WG_SID="default"
  _WG_DO_FLAG="/tmp/claude-orchestrator-consent-${_WG_SID}.flag"
  if [ -f "$_WG_DO_FLAG" ] && [ "$(cat "$_WG_DO_FLAG" 2>/dev/null)" = "true" ]; then
    exit 0
  fi
  # /allow bypass (main-agent only) — delegates to lib/allowlist.read_grant("Write", sid)
  _WG_HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  _WG_ALLOW_FILE="/tmp/claude-bash-allowlist-${_WG_SID}.json"
  if [ -f "$_WG_ALLOW_FILE" ]; then
    _WG_MATCHED=$(HOOKS_DIR="$_WG_HOOKS_DIR" WG_SID="$_WG_SID" python3 - <<'WGEOF'
import os, sys
sys.path.insert(0, os.environ["HOOKS_DIR"])
from lib.allowlist import read_grant
if read_grant("Write", os.environ["WG_SID"]):
    print("1")
WGEOF
)
    if [ "$_WG_MATCHED" = "1" ]; then
      exit 0
    fi
  fi
fi

# Extract file_path from tool_input
FILE_PATH=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null)

# If we couldn't extract a file path, allow (don't block on parse errors)
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Check if the file already exists
if [ -f "$FILE_PATH" ]; then
  echo "[Write Guard] BLOCKED: File already exists: $FILE_PATH"
  echo "Use the Edit tool to modify existing files. Write is only for creating NEW files."
  exit 2
fi

# File does not exist — allow creation
exit 0
