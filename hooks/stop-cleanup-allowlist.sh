#!/usr/bin/env bash
# Stop Hook: Wipe any unconsumed /allow grant at turn end.
# Registered LAST in Stop hooks array so earlier hook failures do not block cleanup.
# Exits 0 always (cleanup is best-effort; never blocks agent stop).
# NOTE: NO `set -e` — missing flag file is expected and must not error out.
set -u

INPUT=$(cat)
SID=$(echo "$INPUT" | python3 -c \
  "import json,sys,os; d=json.load(sys.stdin); print(d.get('session_id','') or os.environ.get('CLAUDE_SESSION_ID','default'))" \
  2>/dev/null)
[ -z "$SID" ] && SID="default"

# DEFECT 1 fix (task-id 20260509-113838): hoist CONSENT_LOG above both
# cleanup branches. Previously CONSENT_LOG was bound only inside the /allow
# branch; under `set -u` the /do branch aborted with "unbound variable"
# whenever the /allow branch did not run, leaving /do consent flags on disk
# across turns. Hoisting binds the variable unconditionally.
CONSENT_LOG="$HOME/.claude/logs/bash-consent.log"
mkdir -p "$(dirname "$CONSENT_LOG")"

FLAG="/tmp/claude-bash-allowlist-${SID}.json"
if [ -f "$FLAG" ]; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) sid=$SID EXPIRED (turn ended without consumption)" >> "$CONSENT_LOG"
  rm -f "$FLAG"
fi

# Also clear /do consent flag - single-turn scope per 2026-04-28 boundary update.
# /do unlocks tool combinations the main agent normally avoids (context-saving);
# it must be re-granted explicitly each turn.
DO_FLAG="/tmp/claude-orchestrator-consent-${SID}.flag"
if [ -f "$DO_FLAG" ]; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) sid=$SID DO_CONSENT_EXPIRED (turn ended)" >> "$CONSENT_LOG"
  rm -f "$DO_FLAG"
fi
rm -f "/tmp/claude-tool-streak-${SID}.json"
exit 0
