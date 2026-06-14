#!/usr/bin/env bash
# UserPromptSubmit Hook: parse `/allow <pattern>` and write a single-use
# bypass flag for developer-class git blocks in pretool-bash-safety.sh.
#
# Step 0: if agent_id is present in the hook JSON input, exit 0 without writing
#         (subagent write-firewall — defense in depth with consume-path check).
# Step 1: extract prompt + session_id; detect `/allow ` prefix (case-sensitive).
# Step 2: derive an EXPLICIT, NARROWLY-scoped grant pattern from the argument.
#         REFUSE-BY-DEFAULT: when no explicit command pattern can be derived
#         (empty arg, no leading-ASCII command token, missing/empty flag operand,
#         empty/vacuous re: body) OR the derived regex is effectively universal
#         (matches commands unrelated to a named token), the hook writes NO grant
#         on EITHER channel, removes any stale grant, prints a usage error, and
#         exits 0 without wedging the session. There is NO wildcard fallback.
#         Pattern passed via env var — never shell-interpolated into Python source.
# Step 3: on an explicit narrow grant only: write the legacy flag
#         /tmp/claude-bash-allowlist-<sid>.json with {pattern, is_regex} AND the
#         structured per-task sentinel; log to ~/.claude/logs/bash-consent.log.
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

# ── Step 2: parse flags + optional comment; derive an EXPLICIT narrow grant ──
# REFUSE-BY-DEFAULT: there is NO wildcard fallback anywhere below. When an
# explicit, narrowly-scoped command pattern cannot be derived, the parser emits
# STATUS=REFUSE and the shell writes no grant, removes any stale grant, prints a
# usage error, and exits 0 (non-wedging).
#
# Syntax (explicit-command forms only — each must name a concrete command):
#   /allow --tool rm                        -> literal pattern "rm"
#   /allow --tool rm 删冗余文件             -> literal "rm" + CJK comment
#   /allow git stash                        -> literal pattern "git stash"
#   /allow re:^git\s+stash                  -> anchored narrow regex
#   /allow Write /abs/path                  -> path-scoped Write grant
#   /allow Write                            -> bare Write carve-out (any target)
# Refused (no grant written): /allow (no arg); /allow <CJK-only> (no leading
#   ASCII command token); /allow --tool (missing/empty operand); /allow re:
#   (empty/quote-only regex body); any effectively-universal regex (e.g. .*, ^,
#   a?, [\s\S]*, re:git unanchored) that would match commands unrelated to a
#   concrete named command token.
#
# Output protocol (5 lines): STATUS(GRANT|REFUSE) / PATTERN / IS_REGEX / COMMENT
#   / REFUSE_REASON. The pattern value is passed back via this protocol, never
#   shell-interpolated into Python source.
PARSED=$(PROMPT="$PROMPT" python3 -c "
import os, shlex
import re as _re
p = os.environ.get('PROMPT','')
body = ''
if p.startswith('/allow '):
    body = p[len('/allow '):]
elif p == '/allow':
    body = ''

REFUSE_REASON = ''

def emit(status, pattern='', is_regex=False, comment='', reason=''):
    print(status)
    print(pattern)
    print('true' if is_regex else 'false')
    print((comment or '').strip())
    print(reason or '')
    raise SystemExit(0)

def _looks_regex(s):
    # Heuristic: contains a regex metacharacter (excluding plain alphanumerics,
    # space, '-', '/', '.').
    return bool(_re.search(r'[\^\$\\\\.*+?\[\]\(\){}|]', s))

def is_forbidden_regex(pat):
    # Returns (forbidden: bool, reason: str). reason in {'vacuous','universal',''}.
    #
    # AC13 PART-2 — SUFFICIENT static anchor-and-bounded-literal rule. A regex
    # grant is allowed ONLY if it starts with ^ (or \\A), exposes a finite
    # literal command-head token immediately after the anchor, and that head is
    # terminated by a real boundary (\$ | \\s+ | \\s | (?:\\s|\$) | end) BEFORE
    # any wildcard / character-class / any-char-quantifier / lookaround /
    # empty-alternative. Otherwise it is refused as effectively universal /
    # over-broad. This is the consumer's own breadth contract: a grant is
    # forbidden iff its matcher would accept commands unrelated to a concrete
    # command token the user named. A literal denylist or corpus-only oracle is
    # insufficient — this is a structural rule.
    if pat is None or pat == '' or pat.strip() == '':
        return True, 'vacuous'
    if pat in (chr(0x27)*2, chr(0x22)*2):   # '' or \"\" — quote-only vacuous body
        return True, 'vacuous'
    if pat.startswith('\\\\A'):
        rest = pat[2:]
    elif pat.startswith('^'):
        rest = pat[1:]
    else:
        return True, 'universal'            # unanchored -> over-broad (KIND-B)
    META = set('.*+?[]()|{}^\$')
    i = 0
    head_len = 0
    n = len(rest)
    while i < n:
        c = rest[i]
        if c == '\\\\':
            if i + 1 >= n:
                break
            nxt = rest[i+1]
            if nxt in ('s','S','d','D','w','W','b','B','A','Z','n','r','t'):
                break                       # \\s \\d \\w \\b ... -> boundary/class
            head_len += 1                   # \\. \\- \\/ -> literal escaped char
            i += 2
            continue
        if c in META or c == ' ':
            break
        head_len += 1
        i += 1
    if head_len == 0:
        return True, 'universal'            # no concrete literal command-head
    tail = rest[i:]
    if tail == '':
        return False, ''                    # anchored literal, bounded by end
    if tail.startswith('\$') or tail.startswith('(?:\\\\s|\$)') or tail.startswith('(?:\\\\s'):
        return False, ''
    if tail.startswith('\\\\s'):
        if tail[2:3] == '*':                # \\s* is not a real boundary
            return True, 'universal'
        return False, ''
    return True, 'universal'                # something non-boundary follows head

try:
    raw_tokens = shlex.split(body, posix=False) if body else []
except ValueError:
    raw_tokens = body.split() if body else []
tokens = []
for t in raw_tokens:
    if len(t) >= 2 and t[0] == t[-1] and t[0] in (chr(0x22), chr(0x27)):
        t = t[1:-1]
    tokens.append(t)

flag_pattern = None
bare = []
i = 0
while i < len(tokens):
    t = tokens[i]
    if t == '--tool':
        # AC10: recognized flag with a missing operand -> REFUSE.
        if i + 1 >= len(tokens):
            emit('REFUSE', reason='missing_flag_operand')
        operand = tokens[i+1]
        # AC10: recognized flag with an empty/whitespace-only operand -> REFUSE.
        if operand == '' or operand.strip() == '':
            emit('REFUSE', reason='empty_flag_operand')
        flag_pattern = operand
        i += 2
    else:
        bare.append(t)
        i += 1

if flag_pattern is not None:
    # --tool declares an explicit literal pattern; force is_regex=False
    # unconditionally (dotted filenames must not be misclassified as regex).
    emit('GRANT', pattern=flag_pattern, is_regex=False, comment=' '.join(bare))
elif bare:
    first = bare[0]
    if first.startswith('re:'):
        pat = first[3:]
        # AC14: empty / vacuous re: body names no concrete command -> REFUSE
        # BEFORE any wildcard fallback could re-coerce it.
        forbidden, reason = is_forbidden_regex(pat)
        if forbidden:
            emit('REFUSE', reason=reason)
        emit('GRANT', pattern=pat, is_regex=True, comment=' '.join(bare[1:]))
    elif first == 'Write' and len(bare) >= 2 and bare[1].startswith('/'):
        # Bare /allow Write /path form: second token is a path argument, not a
        # comment. Emit a path-scoped grant (sentinel target=path).
        emit('GRANT', pattern='Write ' + bare[1], is_regex=False,
             comment=' '.join(bare[2:]))
    else:
        # Bare command form: take leading ASCII tokens as the command; the
        # first non-ASCII token (e.g. a CJK comment) ends the command.
        ascii_bare = []
        for t in bare:
            if any(ord(c) >= 128 for c in t):
                break
            ascii_bare.append(t)
        comment_bare = bare[len(ascii_bare):]
        # AC2/AC3: no leading-ASCII command token derivable -> REFUSE (no
        # wildcard fallback).
        if not ascii_bare:
            emit('REFUSE', reason='no_command_token')
        pattern = ' '.join(ascii_bare)
        is_regex = _looks_regex(pattern)
        if is_regex:
            # AC5/AC13 KIND-C: a bare auto-detected regex that is effectively
            # universal -> REFUSE.
            forbidden, reason = is_forbidden_regex(pattern)
            if forbidden:
                emit('REFUSE', reason=reason)
        emit('GRANT', pattern=pattern, is_regex=is_regex,
             comment=' '.join(comment_bare))
else:
    # AC1: bare /allow with no argument -> REFUSE (no wildcard fallback).
    emit('REFUSE', reason='no_argument')
" 2>/dev/null)
PARSED_STATUS=$(echo "$PARSED" | sed -n '1p')
PATTERN=$(echo "$PARSED" | sed -n '2p')
PARSED_IS_REGEX=$(echo "$PARSED" | sed -n '3p')
COMMENT=$(echo "$PARSED" | sed -n '4p')
IS_REGEX="$PARSED_IS_REGEX"

# ── Refuse gate (AC1-AC5, AC10, AC13, AC14): no explicit narrow command was
# derivable, OR the derived regex is effectively universal. Write NO grant on
# EITHER channel, remove any stale grant for this SID/TASK_ID across the full
# loader glob (AC15), print a usage error, and exit 0 (non-wedging). This runs
# BEFORE the nested-quantifier check, the audit log, and both grant writes. If
# the Python parser failed to emit a recognized status, fail closed (REFUSE).
if [ "$PARSED_STATUS" != "GRANT" ]; then
  REFUSE_TASK_ID="${CLAUDE_TASK_ID:-${SID}}"
  rm -f "/tmp/claude-bash-allowlist-${SID}.json" 2>/dev/null
  rm -f "/tmp/claude-grants/${REFUSE_TASK_ID}.json" 2>/dev/null
  rm -f "/tmp/claude-grants/${REFUSE_TASK_ID}"-*.json 2>/dev/null
  echo "[allow] ERROR: refused — you must name an explicit command to allow." >&2
  echo "[allow] /allow records a NARROW single-use bypass; it has no wildcard default." >&2
  echo "[allow] Examples: '/allow --tool rm', '/allow git stash', '/allow re:^git\\s+stash', '/allow Write /abs/path'." >&2
  echo "[allow] Refused because no explicit, narrowly-scoped command pattern could be derived (empty/under-specified argument or an effectively-universal regex)." >&2
  exit 0
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
# the command line.
#
# Literal patterns: single {op, target?, args_contain?} entry.
# Regex patterns: {op:"*", regex:<pattern>} entry. match_sentinel_grant_for_bash_command()
#   tests re.search(regex, subcommand) for op="*" entries, enabling regex grants to
#   reach subagents (which cannot use the legacy grant path).
#   S1 early-exit removed (task 20260524-133650 gap-1 fix): regex grants now write a
#   sentinel so subagents are covered. CF-1 (sentinel-exists-but-no-match suppresses
#   legacy path) no longer applies because the matcher now returns a match for regex.
#
# Atomic write-temp+rename so partial files never appear.
TASK_ID="${CLAUDE_TASK_ID:-${SID}}"
SENTINEL_DIR="/tmp/claude-grants"
mkdir -p "$SENTINEL_DIR" 2>/dev/null
SENTINEL_FILE="${SENTINEL_DIR}/${TASK_ID}.json"
SENTINEL_TMP="${SENTINEL_FILE}.tmp.$$"
ALLOW_PATTERN="$PATTERN" \
  ALLOW_IS_REGEX="$IS_REGEX" \
  SENTINEL_TMP="$SENTINEL_TMP" \
  SID="$SID" \
  TASK_ID="$TASK_ID" \
  python3 -c "
import json, os, time
pattern = os.environ['ALLOW_PATTERN']
is_regex = os.environ.get('ALLOW_IS_REGEX') == 'true'
now = time.time()
# Default sentinel TTL: 300s. Aligns with bash-safety grant window.
ttl = 300
if is_regex:
    # Regex sentinel: op='*' with 'regex' field. The matcher (allowlist.py
    # match_sentinel_grant_for_bash_command) runs re.search(regex, subcommand)
    # for op='*' entries, allowing regex grants to reach subagents.
    entry = {'op': '*', 'regex': pattern}
else:
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
        entry['args_contain'] = rest.split()
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
