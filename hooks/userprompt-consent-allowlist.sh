#!/usr/bin/env bash
# UserPromptSubmit Hook: parse `/allow <pattern>` and write a single-use
# bypass flag for developer-class git blocks in pretool-bash-safety.sh.
#
# Step 0: if agent_id is present in the hook JSON input, exit 0 without writing
#         (subagent write-firewall — defense in depth with consume-path check).
# Step 1: extract prompt + session_id; detect `/allow ` prefix (case-sensitive).
# Step 2: write /tmp/claude-bash-allowlist-<sid>.json with {pattern, is_regex}.
#         Pattern passed via env var — never shell-interpolated into Python source.
# Step 3: log to ~/.claude/logs/bash-consent.log; echo status to stdout.
#
# Exit 0 always. Stop hook (stop-cleanup-allowlist.sh) wipes any unconsumed flag.
set -u

INPUT=$(cat)

# ── Step 0: subagent write firewall ─────────────────────────────────
IS_SUBAGENT=$(echo "$INPUT" | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print('1' if d.get('agent_id') else '0')" \
  2>/dev/null)
if [ "$IS_SUBAGENT" = "1" ]; then
  exit 0
fi

# ── Step 1: extract prompt + session_id ────────────────────────────
PROMPT=$(echo "$INPUT" | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(d.get('prompt',''))" \
  2>/dev/null)
SID=$(echo "$INPUT" | python3 -c \
  "import json,sys,os; d=json.load(sys.stdin); print(d.get('session_id','') or os.environ.get('CLAUDE_SESSION_ID','default'))" \
  2>/dev/null)
[ -z "$SID" ] && SID="default"

# Only fire on `/allow ` prefix (case-sensitive). Trailing space required so
# `/allow-something-else` does not trigger.
case "$PROMPT" in
  "/allow "*) ;;
  *) exit 0 ;;
esac

# ── Step 2: parse pattern ──────────────────────────────────────────
# Everything after the leading `/allow ` (python handles trim + re: prefix safely).
PATTERN=$(PROMPT="$PROMPT" python3 -c "
import os
p = os.environ.get('PROMPT','')
if p.startswith('/allow '):
    print(p[len('/allow '):].strip())
else:
    print('')
")

if [ -z "$PATTERN" ]; then
  echo "[allow] ERROR: empty pattern. Usage: /allow <substring> or /allow re:<regex>" >&2
  exit 0
fi

# Determine regex vs literal. If user typed `re:<body>`, strip the prefix.
IS_REGEX="false"
case "$PATTERN" in
  "re:"*)
    IS_REGEX="true"
    PATTERN="${PATTERN#re:}"
    ;;
esac

if [ -z "$PATTERN" ]; then
  echo "[allow] ERROR: empty regex body after 're:'. Usage: /allow re:<regex>" >&2
  exit 0
fi

# ── Step 3: write flag via env-var Python (no shell interpolation) ──
FLAG="/tmp/claude-bash-allowlist-${SID}.json"
ALLOW_PATTERN="$PATTERN" ALLOW_IS_REGEX="$IS_REGEX" FLAG_PATH="$FLAG" python3 -c "
import json, os
data = {
    'pattern': os.environ['ALLOW_PATTERN'],
    'is_regex': os.environ['ALLOW_IS_REGEX'] == 'true',
}
with open(os.environ['FLAG_PATH'], 'w') as f:
    json.dump(data, f)
" 2>/dev/null

# ── Audit log ───────────────────────────────────────────────────────
CONSENT_LOG="$HOME/.claude/logs/bash-consent.log"
mkdir -p "$(dirname "$CONSENT_LOG")"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) sid=$SID GRANTED pattern='$PATTERN' is_regex=$IS_REGEX" >> "$CONSENT_LOG"

echo "[allow] Grant recorded: pattern='$PATTERN' is_regex=$IS_REGEX. Valid for ONE matching developer-class bash call this turn."
exit 0
