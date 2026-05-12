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

# ── C3: daemon-restart-edit — block any Edit/Write to systemd unit files,
# admin-script siblings, hook files themselves, and the grant sentinel.
# TASK-ID: c3-20260504-223115
# Per BA spec docs/dev/ticket-c3-20260504-223115.md (R4, AC5, AC6).
# Stable substring: daemon-restart-edit (or daemon-restart-sentinel-write).

# Block: any file under /etc/systemd/system/happy-daemon-*.service or its drop-in dir
# Covers happy-daemon.service, happy-daemon-jade.service, happy-daemon-dev.service,
# happy-daemon-qijie.service, plus all .service.d/*.conf overrides.
case "$FILE_PATH" in
  /etc/systemd/system/happy-daemon*.service|/etc/systemd/system/happy-daemon*.service.d/*)
    echo "BLOCKED: daemon-restart-edit — Edit/Write to happy-daemon systemd unit/drop-in is FORBIDDEN" >&2
    echo "Path: $FILE_PATH" >&2
    echo "REASON: per c3-20260504-223115, only the user may edit happy-daemon-* units." >&2
    exit 2 ;;
esac

# Block: admin scripts in /root/bin that orchestrate daemon restarts.
# Bash invocation already blocked at /root/.claude/hooks/pretool-bash-safety.sh:345
# but Edit/Write to the script body is a separate bypass surface.
case "$FILE_PATH" in
  /root/bin/happy-restart.sh|\
  /root/bin/happy-session-recovery.sh|\
  /root/bin/safe-swap-drain.sh|\
  /root/bin/auto-safe-swap-drain.sh|\
  /root/bin/safe-daemon-restart.sh|\
  /root/bin/claude-allow-restart)
    echo "BLOCKED: daemon-restart-edit — Edit/Write to admin script is FORBIDDEN" >&2
    echo "Path: $FILE_PATH" >&2
    echo "REASON: per c3-20260504-223115, these scripts orchestrate or gate daemon restarts;" >&2
    echo "        only the user may modify them." >&2
    exit 2 ;;
esac

# Block: Edit/Write to the hook files themselves — defense in depth on top of
# settings.json `permissions.ask` (lines 237-238). Subagent edits to hook files
# would be a self-modification bypass; this rule fail-closes regardless of
# whether the user is currently prompted via the ask layer.
case "$FILE_PATH" in
  /root/.claude/hooks/pretool-bash-safety.sh|\
  /root/.claude/hooks/pretool-block-production-files.sh|\
  /root/.claude/hooks/pretool-orchestrator-prompt-purity.py)
    # Detect subagent vs orchestrator: only block subagent edits here.
    # Orchestrator edits remain gated by settings.json permissions.ask which
    # prompts the user. Subagents have no user prompt — block outright.
    # Exception: .hook-refactor-allow sentinel (the same convention used by
    # pretool-claude-config-guard.py) signals an explicit user-authorized
    # refactor session — honor that here too.
    IS_SUBAGENT_EDIT=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print('1' if d.get('agent_id') else '0')" 2>/dev/null)
    if [ "$IS_SUBAGENT_EDIT" = "1" ]; then
      PROJECT_DIR_FOR_SENTINEL="${CLAUDE_PROJECT_DIR:-$(pwd)}"
      if [ -f "$PROJECT_DIR_FOR_SENTINEL/.claude/.hook-refactor-allow" ] || [ -f "$HOME/.claude/.hook-refactor-allow" ]; then
        : # user has authorized hook refactor — fall through (still subject to other rules)
      else
        echo "BLOCKED: hook-self-modification — subagent Edit/Write to hook file is FORBIDDEN" >&2
        echo "Path: $FILE_PATH" >&2
        echo "REASON: per c3-20260504-223115, hooks are the daemon-restart prohibition floor;" >&2
        echo "        only the orchestrator (with user prompt) may modify them." >&2
        echo "        To override: create .claude/.hook-refactor-allow at project root" >&2
        echo "        (the same sentinel used by pretool-claude-config-guard.py)." >&2
        exit 2
      fi
    fi
    ;;
esac

# Block: Edit/Write to the grant sentinel file. Only /root/bin/claude-allow-restart
# may write the sentinel; Claude (orchestrator AND subagents) must never create or
# alter it via the Edit/Write tools.
case "$FILE_PATH" in
  /tmp/claude-allow-daemon-restart-*.flag)
    echo "BLOCKED: daemon-restart-sentinel-write — Edit/Write to grant sentinel is FORBIDDEN" >&2
    echo "Path: $FILE_PATH" >&2
    echo "REASON: per c3-20260504-223115, only /root/bin/claude-allow-restart (run by user from TTY)" >&2
    echo "        may create the grant sentinel." >&2
    exit 2 ;;
esac

exit 0
