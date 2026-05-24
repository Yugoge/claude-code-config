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
  "/allow "*|"/allow") ;;
  *) exit 0 ;;
esac

# ── Step 2: parse flags + optional comment (flag-style aligned with /close) ──
# Syntax:
#   /allow                                  -> wildcard, no comment
#   /allow --tool rm                        -> literal pattern "rm"
#   /allow --tool rm 删冗余文件             -> literal "rm" + comment
#   /allow --regex ^git\s+stash             -> regex pattern
#   /allow --regex ^git cleanup             -> regex + comment
# Backward-compat: /allow rm and /allow re:^git still parse as legacy bare pattern.
# Resolution: --tool/--regex WINS (all bare tokens become comment); else first bare
# token is the pattern; else wildcard.
PARSED=$(PROMPT="$PROMPT" python3 -c "
import os, shlex
p = os.environ.get('PROMPT','')
body = ''
if p.startswith('/allow '):
    body = p[len('/allow '):]
elif p == '/allow':
    body = ''
try:
    raw_tokens = shlex.split(body, posix=False) if body else []
except ValueError:
    raw_tokens = body.split() if body else []
tokens = []
for t in raw_tokens:
    if len(t) >= 2 and t[0] == t[-1] and t[0] in (chr(0x22), chr(0x27)):
        t = t[1:-1]
    tokens.append(t)
flag_pattern, flag_is_regex = None, None
bare = []
i = 0
while i < len(tokens):
    t = tokens[i]
    if t == '--tool' and i+1 < len(tokens):
        flag_pattern, flag_is_regex = tokens[i+1], False
        i += 2
    # --regex flag intentionally removed: hook auto-detects regex from
    # presence of regex metacharacters in the pattern.
    else:
        bare.append(t)
        i += 1
import re as _re
def _looks_regex(s):
    # Heuristic: contains regex metacharacter (excluding plain alphanumerics + space + - / .)
    return bool(_re.search(r'[\^$\\.*+?\[\]\(\){}|]', s))

if flag_pattern is not None:
    pattern = flag_pattern
    # --tool declares an explicit literal pattern; force is_regex=False
    # unconditionally regardless of _looks_regex() output. Dotted filenames
    # (e.g. /tmp/file.json) must not be misclassified as regex. (CRITICAL-2 fix)
    is_regex = False
    comment = ' '.join(bare)
elif bare:
    first = bare[0]
    if first.startswith('re:'):
        pattern, is_regex = first[3:], True
        comment = ' '.join(bare[1:])
    elif first == 'Write' and len(bare) >= 2 and bare[1].startswith('/'):
        # Bare /allow Write /path form: treat second token as path argument,
        # not as a comment. Emit scoped sentinel with target=path. (CRITICAL-1 fix)
        pattern = 'Write ' + bare[1]
        is_regex = False
        comment = ' '.join(bare[2:])
    else:
        pattern = first
        is_regex = _looks_regex(first)
        comment = ' '.join(bare[1:])
else:
    pattern, is_regex = '.*', True
    comment = ''
print(pattern)
print('true' if is_regex else 'false')
print(comment.strip())
" 2>/dev/null)
PATTERN=$(echo "$PARSED" | sed -n '1p')
PARSED_IS_REGEX=$(echo "$PARSED" | sed -n '2p')
COMMENT=$(echo "$PARSED" | sed -n '3p')

# Python parser already resolved PATTERN + IS_REGEX. Just adopt them.
IS_REGEX="$PARSED_IS_REGEX"
if [ -z "$PATTERN" ]; then
  PATTERN=".*"
  IS_REGEX="true"
fi

# ── V1b: structural rejection of catastrophic-backtracking regex shapes ──
# Defense-in-depth for V1 (SIGALRM consumer-side timeout). Reject nested-quantifier
# patterns like (a+)+, (a*)*, (a|b)+ at WRITE time so they never reach the consumer.
# Heuristic: body contains '(...)' with '+' or '*' inside the group AND the group is
# followed by '+' or '*' — structural shape of catastrophic backtracking.
if [ "$IS_REGEX" = "true" ]; then
  STRUCT_CHECK=$(ALLOW_PATTERN="$PATTERN" python3 -c "
import os, re, sys
p = os.environ['ALLOW_PATTERN']
# Nested-quantifier detector: group containing + or *, followed by + or *
if re.search(r'\([^)]*[+*][^)]*\)[+*]', p):
    print('REJECT')
else:
    print('OK')
" 2>/dev/null)
  if [ "$STRUCT_CHECK" = "REJECT" ]; then
    echo "[allow] ERROR: pattern rejected — contains nested quantifier (e.g., (a+)+, (a*)*) which risks catastrophic backtracking." >&2
    echo "[allow] Use a more specific literal pattern or a bounded-quantifier regex instead." >&2
    exit 0
  fi
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
if [ -n "$COMMENT" ]; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) sid=$SID GRANTED pattern='$PATTERN' is_regex=$IS_REGEX comment='$COMMENT'" >> "$CONSENT_LOG"
else
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) sid=$SID GRANTED pattern='$PATTERN' is_regex=$IS_REGEX" >> "$CONSENT_LOG"
fi

if [ -n "$COMMENT" ]; then
  echo "[allow] Grant recorded: pattern='$PATTERN' is_regex=$IS_REGEX comment='$COMMENT'. Valid for ONE matching bash call this turn."
else
  echo "[allow] Grant recorded: pattern='$PATTERN' is_regex=$IS_REGEX. Valid for ONE matching bash call this turn."
fi

# ── Step 4: write sentinel grant (task 20260519-211515 R2 / AC2) ──
# Sentinel-file grant lifecycle: /tmp/claude-grants/<task_id>.json contains
# {task_id, session_id, allowed_operations[], created_at, expires_at}.
# The legacy pattern-string grant (above) remains for back-compat; the new
# sentinel is a STRUCTURED grant that hooks/lib/allowlist.py reads via
# load_sentinel_grant_for_task() — predicate never substring-matches against
# the command line. allowed_operations[] is bootstrapped from the legacy
# pattern as a single {op,target,args_contain} entry when the pattern is
# literal.
# S1 (task 20260521-090200): skip sentinel write for is_regex=true grants.
# Rationale: a regex sentinel writes op:"*" which never structurally matches
# (structured predicate requires op equality), causing CF-1 to fire and
# suppress the legacy /allow path — defeating the user's regex grant. By not
# writing a sentinel for regex grants, the legacy path is consulted as
# expected. Atomic write-temp+rename so partial files never appear.
if [ "$IS_REGEX" = "true" ]; then
  exit 0
fi
TASK_ID="${CLAUDE_TASK_ID:-${SID}}"
SENTINEL_DIR="/tmp/claude-grants"
mkdir -p "$SENTINEL_DIR" 2>/dev/null
SENTINEL_FILE="${SENTINEL_DIR}/${TASK_ID}.json"
SENTINEL_TMP="${SENTINEL_FILE}.tmp.$$"
ALLOW_PATTERN="$PATTERN" \
  SENTINEL_TMP="$SENTINEL_TMP" \
  SID="$SID" \
  TASK_ID="$TASK_ID" \
  python3 -c "
import json, os, time
pattern = os.environ['ALLOW_PATTERN']
now = time.time()
# Default sentinel TTL: 300s. Aligns with bash-safety grant window.
ttl = 300
# Literal patterns produce a single structured op entry.
parts = pattern.split(None, 1)
op = parts[0] if parts else pattern
rest = parts[1] if len(parts) >= 2 else ''
entry = {'op': op}
if op == 'Write' and rest:
    # Write ops use 'target' for exact-path scoping (not args_contain).
    # Matcher key-presence logic requires this field name. (ORIGINAL fix)
    entry['target'] = rest
elif rest:
    entry['args_contain'] = [rest]
ops = [entry]
grant = {
    'task_id': os.environ['TASK_ID'],
    'session_id': os.environ['SID'],
    'allowed_operations': ops,
    'created_at': now,
    'expires_at': now + ttl,
}
with open(os.environ['SENTINEL_TMP'], 'w') as f:
    json.dump(grant, f)
" 2>/dev/null && mv -f "$SENTINEL_TMP" "$SENTINEL_FILE" 2>/dev/null

exit 0
