#!/bin/bash
# PreToolUse hook: Block Write/Edit to production paths from dev environment
# Prevents dev agents from modifying production source, daemon state, or global binaries
# Created: 2026-04-04 after isolation audit

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)

# Only act on Write and Edit tools
case "$TOOL_NAME" in
  Write|Edit) ;;
  *) exit 0 ;;
esac

FILE_PATH=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null)

# Block production source tree
case "$FILE_PATH" in
  /root/happy/*)
    echo "BLOCKED: Write/Edit to production source /root/happy/ is FORBIDDEN from dev environment" >&2
    echo "Path: $FILE_PATH" >&2
    echo "Use git merge/cherry-pick to bring changes into production." >&2
    exit 2 ;;
esac

# Block production daemon homes
case "$FILE_PATH" in
  /root/.happy/*)
    echo "BLOCKED: Write/Edit to production daemon home /root/.happy/ is FORBIDDEN" >&2
    echo "Path: $FILE_PATH" >&2
    exit 2 ;;
esac

case "$FILE_PATH" in
  /root/.happy-jade/*)
    echo "BLOCKED: Write/Edit to jade daemon home /root/.happy-jade/ is FORBIDDEN" >&2
    echo "Path: $FILE_PATH" >&2
    exit 2 ;;
esac

case "$FILE_PATH" in
  /root/.happy-qijie/*)
    echo "BLOCKED: Write/Edit to qijie daemon home /root/.happy-qijie/ is FORBIDDEN" >&2
    echo "Path: $FILE_PATH" >&2
    exit 2 ;;
esac

# Block global binary paths
case "$FILE_PATH" in
  /usr/lib/node_modules/happy*)
    echo "BLOCKED: Write/Edit to global happy modules is FORBIDDEN" >&2
    echo "Path: $FILE_PATH" >&2
    exit 2 ;;
esac

# Block /usr/bin/happy but allow /usr/bin/happy-dev
if [[ "$FILE_PATH" =~ ^/usr/bin/happy ]] && [[ ! "$FILE_PATH" =~ ^/usr/bin/happy-dev ]]; then
  echo "BLOCKED: Write/Edit to global happy binary is FORBIDDEN" >&2
  echo "Path: $FILE_PATH" >&2
  exit 2
fi

# Block: happy-daemon-dev.service must NEVER contain /usr/bin/happy as ExecStart/ExecStop
# Dev daemon must always use /root/happy-dev/ binary directly
if [ "$FILE_PATH" = "/etc/systemd/system/happy-daemon-dev.service" ]; then
  NEW_CONTENT=$(echo "$INPUT" | python3 -c "
import json,sys
d=json.load(sys.stdin)
ti=d.get('tool_input',{})
print(ti.get('new_string','') + ti.get('content',''))
" 2>/dev/null)
  # Allow /usr/bin/happy-dev but block /usr/bin/happy (production binary)
  if echo "$NEW_CONTENT" | grep -qE 'Exec(Start|Stop)=.*/usr/bin/happy([^-]|$)'; then
    echo "BLOCKED: happy-daemon-dev.service must NEVER use /usr/bin/happy (production binary)" >&2
    echo "Path: $FILE_PATH" >&2
    echo "Dev daemon must use: /usr/bin/happy-dev (which resolves to /root/happy-dev/ binary)" >&2
    exit 2
  fi
fi

exit 0
