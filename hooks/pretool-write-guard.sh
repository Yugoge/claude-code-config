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
