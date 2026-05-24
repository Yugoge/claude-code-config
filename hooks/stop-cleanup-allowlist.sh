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

# ── Sentinel-grant reap (task 20260519-211515 R2 / AC2) ──
# At session stop, sweep /tmp/claude-grants/*.json: unlink any sentinel
# whose expires_at has elapsed OR whose JSON is malformed. Bounded
# best-effort; never blocks agent stop. The reaper delegates to
# hooks/lib/allowlist.reap_expired_sentinel_grants().
HOOK_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
python3 -c "
import sys
sys.path.insert(0, '${HOOK_DIR}')
from lib.allowlist import reap_expired_sentinel_grants
print('[stop-cleanup] reaped', reap_expired_sentinel_grants(), '/tmp/claude-grants/* sentinel grants', file=sys.stderr)
" 2>>"$CONSENT_LOG" || true

# ── Bulk-commit sentinel reap ──
# /commit --bulk writes /tmp/claude-bulk-commit-sentinel-<sid>-<nonce>.json
# (30 min TTL, multi-use). Reap any that have expired at session end.
python3 -c "
import glob, json, os
from datetime import datetime, timezone
reaped = 0
for p in glob.glob('/tmp/claude-bulk-commit-sentinel-*.json'):
    try:
        d = json.loads(open(p).read())
        exp = d.get('expires_at', '')
        end = datetime.fromisoformat(exp.replace('Z', '+00:00'))
        if datetime.now(timezone.utc) > end:
            os.unlink(p)
            reaped += 1
    except Exception:
        pass
print('[stop-cleanup] reaped', reaped, 'bulk-commit sentinels', flush=True)
" 2>>"$CONSENT_LOG" || true

exit 0
