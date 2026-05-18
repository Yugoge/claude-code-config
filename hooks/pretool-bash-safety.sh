#!/bin/bash
# PreToolUse Safety Hook - Warn or block before dangerous operations
# Reads tool input from stdin as JSON (Claude Code hook protocol)

# Read full JSON from stdin
INPUT=$(cat)

CLAUDE_HOME="${CLAUDE_HOME:-${HOME}/.claude}"
CLAUDE_TMPDIR="${CLAUDE_TMPDIR:-${TMPDIR:-/tmp}}"
PYTHON_BIN="${CLAUDE_PYTHON_BIN:-${CLAUDE_HOME}/venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="${CLAUDE_PYTHON_FALLBACK:-python}"
fi
DAEMON_RESTART_GRANT_DIR="${CLAUDE_DAEMON_RESTART_GRANT_DIR:-${CLAUDE_TMPDIR}}"
DAEMON_RESTART_SENTINEL_RE="$(printf '%s' "${DAEMON_RESTART_GRANT_DIR%/}/claude-allow-daemon-restart-" | sed 's/[][\\.^$*+?{}|()]/\\&/g')"

# IS_SUBAGENT: set once here at the top of the script (after PYTHON_BIN resolution).
# $INPUT is assigned once at line 6 and never reassigned, so this read is safe regardless of position.
# Used by check_and_consume_allowlist (subagent firewall) and the /do bypass block below.
IS_SUBAGENT=$(echo "$INPUT" | "$PYTHON_BIN" -c "import json,sys; d=json.load(sys.stdin); print('1' if d.get('agent_id') else '0')" 2>/dev/null)

# Codex compatibility: hook payloads may pass a multi-line shell snippet with
# strict-mode preludes such as `set -euo pipefail` before the actual command.
# Docker compose service detection must examine compose invocations, not the
# first shell token in the whole snippet; otherwise dev-only operations like
# `set -euo pipefail; cd /root/deploy; docker compose up -d happy-web-dev`
# are misclassified as service `set`.
strip_shell_prelude_for_compose() {
  local command="$1"
  command="$(printf '%s\n' "$command" | sed -E \
    -e '/^[[:space:]]*set([[:space:]]+[^;&|]+)*[[:space:]]*$/d' \
    -e '/^[[:space:]]*cd[[:space:]]+[^;&|]+[[:space:]]*$/d')"
  printf '%s\n' "$command"
}

# Extract tool name and command
TOOL_NAME=$(echo "$INPUT" | "$PYTHON_BIN" -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)
COMMAND=$(echo "$INPUT" | "$PYTHON_BIN" -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null)
COMPOSE_COMMAND=$(strip_shell_prelude_for_compose "$COMMAND")

# Only act on Bash tool
if [ "$TOOL_NAME" != "Bash" ]; then
  exit 0
fi

# ── Dev whitelist (exact names only) ──────────────────────────────
# These are the ONLY dev resources that can be freely managed.
DEV_CONTAINERS="happy-web-dev"
# Per c3-20260504-223115 R1: happy-daemon-dev is REMOVED from the systemctl whitelist.
# All happy-daemon-* targets are gated by Layer 1.A (daemon-restart-prohibition) which
# requires an explicit user grant via /root/bin/claude-allow-restart. The systemctl block
# at line ~700 skips happy-daemon commands entirely (Layer 1.A already adjudicated).
DEV_SYSTEMD=""

# ── Helper: split compound command into subcommands ───────────────
# Splits on && || ; and checks each subcommand independently.
# Returns 0 (true) if ANY subcommand matches the pattern.
any_subcmd_matches() {
  local cmd="$1"
  local pattern="$2"
  # Replace && || ; with newlines, then check each line
  echo "$cmd" | sed 's/&&/\n/g; s/||/\n/g; s/;/\n/g' | while IFS= read -r subcmd; do
    if echo "$subcmd" | grep -qE "$pattern"; then
      return 0
    fi
  done
}

# Returns 0 if ALL container/service args in a docker/systemctl subcommand
# are in the whitelist. Returns 1 if any non-whitelisted target is found.
check_docker_targets_all_dev() {
  local cmd="$1"
  local whitelist="$2"
  # Split on && || ;
  echo "$cmd" | sed 's/&&/\n/g; s/||/\n/g; s/;/\n/g' | while IFS= read -r subcmd; do
    # Check if this subcommand is a docker stop/restart/rm/kill
    if echo "$subcmd" | grep -qE 'docker\s+(stop|restart|rm|kill)\s'; then
      # Extract all args after the docker action word
      local args
      args=$(echo "$subcmd" | sed -E 's/.*docker\s+(stop|restart|rm|kill)\s+//')
      # Check each arg that looks like a container name (skip flags like -f)
      for arg in $args; do
        [[ "$arg" == -* ]] && continue
        local found=0
        for dev in $whitelist; do
          if [ "$arg" = "$dev" ]; then
            found=1
            break
          fi
        done
        if [ "$found" = "0" ]; then
          return 1  # Non-dev target found
        fi
      done
    fi
  done
}

check_systemctl_targets_all_dev() {
  local cmd="$1"
  local whitelist="$2"
  echo "$cmd" | sed 's/&&/\n/g; s/||/\n/g; s/;/\n/g' | while IFS= read -r subcmd; do
    if echo "$subcmd" | grep -qE 'systemctl\s+(stop|restart)\s'; then
      local args
      args=$(echo "$subcmd" | sed -E 's/.*systemctl\s+(stop|restart)\s+//')
      for arg in $args; do
        [[ "$arg" == -* ]] && continue
        # Strip .service suffix for comparison
        local bare="${arg%.service}"
        local found=0
        for dev in $whitelist; do
          if [ "$bare" = "$dev" ]; then
            found=1
            break
          fi
        done
        if [ "$found" = "0" ]; then
          return 1
        fi
      done
    fi
  done
}

# ── One-shot allowlist bypass (single-shot /allow consume) ────────────────────
# Reads /tmp/claude-bash-allowlist-<sid>.json (written by userprompt-consent-allowlist.sh).
# On match: atomically deletes the flag (single-use), audit-logs, emits canonical
# Claude Code PreToolUse approval JSON to stdout, returns 0.
# Per task-id 20260509-113838 (R11 relaxation): this helper is invoked from the
# global /allow short-circuit at line 555, which runs BEFORE all four absolute-ban
# categories (Layer 1.A daemon-restart prohibition + session_dirs/happy-recovery/
# happy-restart). The user-binding directive (verbatim text preserved in
# docs/dev/ticket-20260509-113838.md) authorizes /allow to bypass any command
# including dangerous ones when the user explicitly grants the pattern; consume
# covers ANY safety block when the user-granted pattern matches.
# NEVER bypasses subagent calls (IS_SUBAGENT inline fresh parse first; lines 121-131).
CONSENT_LOG="$HOME/.claude/logs/bash-consent.log"

check_and_consume_allowlist() {
  local cmd="$1"

  # IS_SUBAGENT check: references the script-global IS_SUBAGENT variable set at the top
  # of the script (after PYTHON_BIN resolution). $INPUT is assigned once at line 6 and
  # never reassigned, so IS_SUBAGENT is valid for the entire script lifetime.
  if [ "$IS_SUBAGENT" = "1" ]; then
    return 1
  fi

  local sid
  sid=$(echo "$INPUT" | "$PYTHON_BIN" -c \
    "import json,sys,os; d=json.load(sys.stdin); print(d.get('session_id','') or os.environ.get('CLAUDE_SESSION_ID','default'))" \
    2>/dev/null)
  [ -z "$sid" ] && sid="default"

  local flag_file="/tmp/claude-bash-allowlist-${sid}.json"
  [ ! -f "$flag_file" ] && return 1

  # Consolidated consume path: V1 (SIGALRM regex timeout) + V2 (flock atomic read-match-unlink) +
  # V3 (compound-command split on && || ; | with per-subcommand match + block-rule cross-check).
  # Pattern and command passed via environment variables — never shell-interpolated into Python.
  local lock_file="${flag_file}.lock"
  local consume_result
  consume_result=$(FLAG_FILE="$flag_file" LOCK_FILE="$lock_file" CMD_INPUT="$cmd" SID_VAL="$sid" "$PYTHON_BIN" - <<'PYEOF'
# V1: SIGALRM-only timeout (1s) around re.search to stop catastrophic-backtracking DoS.
#     ThreadPoolExecutor fallback is PROHIBITED — it does not interrupt a running C regex.
# V2: flock(LOCK_EX | LOCK_NB) with 3x 100ms retry; atomic unlink while lock held; finally-unlock.
# V3: split cmd on &&, ||, ;, | (single pipe). Process || BEFORE | via sentinel placeholder.
#     Match per-subcommand AND cross-check against embedded block-rule list. Bypass fires only
#     when the same subcommand matches both the user's allow-pattern and a dev-class block rule.
# NOTE: backtick substitution, $(...), <(...) process substitution, << heredoc are OUT OF SCOPE
#       — full shell parser required. Documented limitation.
import fcntl, json, os, re, signal, sys, time

flag_file = os.environ['FLAG_FILE']
lock_file = os.environ['LOCK_FILE']
cmd = os.environ['CMD_INPUT']

# Block rules embedded here (must be kept in sync with the outer shell block list).
# Each entry is a Python regex string. Historically used for cross-check between
# /allow-pattern and embedded block rules; the cross-check was removed 2026-04-28
# (see comment near matched_subcmd loop below). After task-id 20260509-113838
# R11 relaxation, /allow is a true break-glass over ALL safety blocks; the
# BLOCK_RULES list is retained for potential future use but is not consulted by
# the consume path.
BLOCK_RULES = [
    # V4 stash forms
    r'git\s+stash\s+(push|save|create|store|-u|--include-untracked|-a|--all)\b',
    r'git\s+stash\s+-[ua]+\b',
    r'git\s+stash\s*($|[;&|])',
    # Wide-path checkout
    r'git\s+checkout\s+\S+\s+--\s+(\.|\*|[^ ]+/)',
    # V6 restore wide-path (two-condition joined for subcommand match).
    # Wide-path alternative '[^ /]+/' = bare dir-segment ending in '/' — excludes src/index.ts (interior '/').
    # Trailing boundary '\s*($|[;&|])' required only when --source/-s precedes the wide-path,
    # so that 'src/' at end-of-token is flagged but 'src/index.ts' is not.
    r'git\s+restore\b.*(--source\b|-s\b).*--\s+(\.|\*|[^ /]+/)\s*($|[;&|])',
    r'git\s+restore\b.*--\s+(\.|\*|[^ /]+/)\s*($|[;&|]).*(--source\b|-s\b)',
    # reset --hard to non-HEAD
    r'git\s+reset\s+--hard\s+(?!HEAD(\s|$))\S+',
    # V5 revert forms (no \b after ^/~/} — non-word chars, \b would fail at boundary)
    r'git\s+revert\s+(\S+\s+)*[0-9a-f]{7,40}\b',
    r'git\s+revert\s+(\S+\s+)*\S+\^+',
    r'git\s+revert\s+(\S+\s+)*\S+~[0-9]*',
    r'git\s+revert\s+(\S+\s+)*\S+@\{[0-9]+\}',
]


def _alarm_handler(signum, frame):
    raise TimeoutError('regex timeout')


def safe_search(pattern, text, is_regex, timeout_sec=1):
    """Match pattern against text. Literal substring or regex with SIGALRM timeout."""
    if not is_regex:
        return pattern in text
    old_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.alarm(timeout_sec)
    try:
        return bool(re.search(pattern, text))
    except (re.error, TimeoutError):
        return False
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def split_subcommands(raw_cmd):
    """Split on && || ; | . Order matters: || before | so || becomes \\n\\n not \\n|\\n."""
    s = raw_cmd.replace('||', '\n').replace('&&', '\n').replace(';', '\n').replace('|', '\n')
    return [t.strip() for t in s.split('\n') if t.strip()]


def matches_any_block_rule(subcmd):
    """True iff subcmd matches at least one dev-class block rule."""
    for rule in BLOCK_RULES:
        try:
            if re.search(rule, subcmd):
                return True
        except re.error:
            continue
    return False


# V2: acquire exclusive lock with bounded retry (3x 100ms). Block on failure (no deadlock).
lock_fd = None
try:
    lock_fd = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o600)
    attempts = 0
    while True:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            attempts += 1
            if attempts >= 3:
                print('BLOCKED_LOCK')
                sys.exit(0)
            time.sleep(0.1)

    # Lock held. Read-match-unlink sequence is now atomic.
    if not os.path.exists(flag_file):
        print('NO_FLAG')
        sys.exit(0)
    try:
        with open(flag_file) as f:
            data = json.load(f)
    except Exception:
        print('NO_FLAG')
        sys.exit(0)

    pattern = data.get('pattern', '')
    is_regex = bool(data.get('is_regex', False))
    if not pattern:
        print('NO_MATCH')
        sys.exit(0)

    # V3: split compound command into subcommands.
    subcmds = split_subcommands(cmd)
    if not subcmds:
        subcmds = [cmd]

    matched_subcmd = None
    for sub in subcmds:
        # Match the user's allow-pattern against each subcommand.
        # Historic note: until 2026-04-28 the consume path also cross-checked the
        # subcommand against BLOCK_RULES above and required BOTH conditions to
        # hold; that gate was removed so /allow is a true break-glass over ALL
        # safety blocks. Task-id 20260509-113838 reinforces this: per the
        # user-binding directive (verbatim text preserved in
        # docs/dev/ticket-20260509-113838.md) authorizing /allow to bypass any
        # command including dangerous ones when the user explicitly grants the
        # pattern, the consume covers any safety block when the granted pattern
        # matches.
        if safe_search(pattern, sub, is_regex):
            matched_subcmd = sub
            break

    if matched_subcmd is None:
        print('NO_MATCH')
        sys.exit(0)

    # Emit structured result for shell wrapper to parse and log.
    # Consume is deferred to posttool-allowlist-consume.py (PostToolUse).
    # Escape single quotes in matched_subcmd for safe shell consumption.
    print('CONSUMED\t{}\t{}\t{}'.format(
        pattern,
        '1' if is_regex else '0',
        matched_subcmd,
    ))
except Exception as e:
    print('ERROR: {}'.format(e))
    sys.exit(0)
finally:
    if lock_fd is not None:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            os.close(lock_fd)
        except Exception:
            pass
PYEOF
)

  # Parse structured result.
  case "$consume_result" in
    CONSUMED$'\t'*)
      local rest pattern is_regex matched_sub
      rest="${consume_result#CONSUMED$'\t'}"
      pattern="${rest%%$'\t'*}"
      rest="${rest#*$'\t'}"
      is_regex="${rest%%$'\t'*}"
      matched_sub="${rest#*$'\t'}"
      mkdir -p "$(dirname "$CONSENT_LOG")"
      echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) sid=$sid CONSUMED pattern='$pattern' is_regex=$is_regex matched_subcmd='$matched_sub' full_cmd='$cmd'" >> "$CONSENT_LOG"
      echo "[allow] Grant matched for pattern='$pattern' (matched subcommand: '$matched_sub'). consume deferred to PostToolUse. Command will proceed." >&2
      # DEFECT 3a fix iter-2 (task-id 20260509-113838): emit the canonical Claude
      # Code PreToolUse approval JSON to stdout. Field shape verified locally at
      # /root/.claude-cold.backup/2026-05-06/projects/-dev-shm-dev-workspace-dot-claude/
      # 314848b6-214f-4302-845f-dc5d3d5975be/tool-results/b7goje9q2.txt:18702,19028
      # (Anthropic Claude Code release notes); cross-verified by codex consultation
      # of https://code.claude.com/docs/en/hooks. This produces a valid permissions-
      # ledger entry for every consumed /allow. NOTE per D3b refutation: this
      # canonical "allow" does NOT cross-block-short-circuit a sibling project-local
      # deny — the docs specify "All matching hooks run in parallel" and PreToolUse
      # precedence is "deny > defer > ask > allow". Cross-block override of
      # /root/<repo>/.claude/settings.json deny rules requires a separate cycle
      # (Plan B/C/D/E per dev-report plan_a_blocker_d3b).
      #
      # iter-2 fix per qa-report finding 1: pass pattern + matched_sub via env vars
      # so the Python source itself is static. Shell-interpolating user-supplied
      # patterns (which may contain literal single quotes, backslashes, or newlines)
      # into a Python source string causes SyntaxError. json.dumps escapes any
      # internal quote/backslash/newline correctly. This mirrors the env-var passing
      # idiom used at userprompt-consent-allowlist.sh:140-148 for the same class of
      # user-supplied strings.
      PATTERN_VAL="$pattern" SUBCMD_VAL="$matched_sub" "$PYTHON_BIN" -c '
import json, os
reason = "/allow consumed for pattern=" + repr(os.environ["PATTERN_VAL"]) + " matched_subcmd=" + repr(os.environ["SUBCMD_VAL"])
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow", "permissionDecisionReason": reason}}))
'
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

# ── C3: daemon-restart prohibition helper (consume_daemon_restart_grant) ───
# TASK-ID: c3-20260504-223115 (introduced) + 20260509-113838 (R11 relaxed)
# Per BA spec docs/dev/ticket-c3-20260504-223115.md (original) +
# docs/dev/ticket-20260509-113838.md (R11 supersession).
#
# Note: as of task-id 20260509-113838 the global /allow short-circuit at
# line 555 runs BEFORE Layer 1.A daemon-restart prohibition. R11's narrower
# invariant ("daemon-restart NOT bypassable by generic /allow") is RELAXED
# per the user-binding directive (verbatim text preserved in
# docs/dev/ticket-20260509-113838.md) authorizing /allow to bypass any command
# including dangerous ones. The dedicated
# ${DAEMON_RESTART_GRANT_DIR}/claude-allow-daemon-restart-<target>.flag sentinel created by
# /root/bin/claude-allow-restart is preserved per W6 as the precise-grant
# alternative for users who prefer not to type generic /allow. The function
# below is still invoked from Layer 1.A; it remains the consume mechanism
# for the dedicated channel and is unaffected by the /allow short-circuit
# relocation.

DAEMON_RESTART_AUDIT_LOG="${CLAUDE_DAEMON_RESTART_AUDIT_LOG:-$HOME/.claude/logs/claude-daemon-restart-grants.log}"

# Atomic consume of ${DAEMON_RESTART_GRANT_DIR}/claude-allow-daemon-restart-<target>.flag.
# Reuses the same flock+SIGALRM atomic-consume design as check_and_consume_allowlist.
# Args: $1 = bare unit name (e.g. "happy-daemon-dev"), $2 = the verb being attempted.
# Returns 0 if a valid grant existed and was consumed (caller may proceed);
# returns 1 otherwise (caller must block).
check_and_consume_daemon_restart_grant() {
  local unit="$1"
  local verb="$2"

  # Derive target suffix: strip "happy-daemon-" or "happy-daemon" prefix.
  # happy-daemon-dev → dev; happy-daemon → default; happy-daemon-jade → jade
  local target
  case "$unit" in
    happy-daemon-dev) target="dev" ;;
    happy-daemon-jade) target="jade" ;;
    happy-daemon-qijie) target="qijie" ;;
    happy-daemon) target="default" ;;
    *) target="" ;;
  esac
  [ -z "$target" ] && return 1

  local sid
  sid=$(echo "$INPUT" | "$PYTHON_BIN" -c \
    "import json,sys,os; d=json.load(sys.stdin); print(d.get('session_id','') or os.environ.get('CLAUDE_SESSION_ID','default'))" \
    2>/dev/null)
  [ -z "$sid" ] && sid="default"

  mkdir -p "$(dirname "$DAEMON_RESTART_AUDIT_LOG")" 2>/dev/null || true

  local flag_file="${DAEMON_RESTART_GRANT_DIR%/}/claude-allow-daemon-restart-${target}.flag"
  local flag_all="${DAEMON_RESTART_GRANT_DIR%/}/claude-allow-daemon-restart-all.flag"
  local lock_file="${flag_file}.lock"

  # Try target-specific flag first; if absent, try the "all" flag.
  if [ ! -f "$flag_file" ] && [ -f "$flag_all" ]; then
    flag_file="$flag_all"
    lock_file="${flag_all}.lock"
  fi
  [ ! -f "$flag_file" ] && return 1

  local consume_result
  consume_result=$(FLAG_FILE="$flag_file" LOCK_FILE="$lock_file" UNIT_VAL="$unit" SID_VAL="$sid" TARGET_VAL="$target" "$PYTHON_BIN" - <<'PYEOF'
# Atomic flock+SIGALRM consume for daemon-restart grant.
# Reuses the design from check_and_consume_allowlist (lines 114-298).
import fcntl, json, os, signal, sys, time
from datetime import datetime, timezone

flag_file = os.environ['FLAG_FILE']
lock_file = os.environ['LOCK_FILE']
unit_val  = os.environ['UNIT_VAL']
sid_val   = os.environ['SID_VAL']
target    = os.environ['TARGET_VAL']

def _alarm(signum, frame):
    raise TimeoutError('parse timeout')

lock_fd = None
try:
    lock_fd = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o600)
    attempts = 0
    while True:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            attempts += 1
            if attempts >= 3:
                print('BLOCKED_LOCK')
                sys.exit(0)
            time.sleep(0.1)

    if not os.path.exists(flag_file):
        print('NO_FLAG')
        sys.exit(0)

    old = signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(1)
    try:
        with open(flag_file) as fh:
            data = json.load(fh)
    except Exception:
        signal.alarm(0); signal.signal(signal.SIGALRM, old)
        print('NO_FLAG')
        sys.exit(0)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)

    grant_target = data.get('target', '')
    expires_at   = data.get('expires_at', '')
    grant_sid    = data.get('session_id', '')
    single_shot  = bool(data.get('single_shot', True))

    # Target match: either exact, or grant target is "all"
    if grant_target != target and grant_target != 'all':
        print('TARGET_MISMATCH\t{}\t{}'.format(grant_target, target))
        sys.exit(0)

    # Expiry check
    try:
        # Accept both "Z" and "+00:00" suffixes
        norm = expires_at.replace('Z', '+00:00')
        exp = datetime.fromisoformat(norm)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if exp <= now:
            print('EXPIRED\t{}'.format(expires_at))
            sys.exit(0)
    except Exception:
        print('EXPIRED\t{}'.format(expires_at))
        sys.exit(0)

    # Session match: grant_sid must equal sid_val (no-active-session never matches a real sid).
    if grant_sid and grant_sid != 'no-active-session' and grant_sid != sid_val:
        print('SESSION_MISMATCH\t{}\t{}'.format(grant_sid, sid_val))
        sys.exit(0)

    # All checks pass. Single-shot consume: unlink atomically while holding lock.
    try:
        os.unlink(flag_file)
    except FileNotFoundError:
        pass
    print('CONSUMED\t{}\t{}\t{}'.format(grant_target, expires_at, grant_sid))
except Exception as e:
    print('ERROR\t{}'.format(e))
    sys.exit(0)
finally:
    if lock_fd is not None:
        try: fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except Exception: pass
        try: os.close(lock_fd)
        except Exception: pass
PYEOF
)

  case "$consume_result" in
    CONSUMED$'\t'*)
      local rest grant_target expires grant_sid
      rest="${consume_result#CONSUMED$'\t'}"
      grant_target="${rest%%$'\t'*}"
      rest="${rest#*$'\t'}"
      expires="${rest%%$'\t'*}"
      grant_sid="${rest#*$'\t'}"
      "$PYTHON_BIN" - "$DAEMON_RESTART_AUDIT_LOG" "$sid" "$target" "$unit" "$verb" "$grant_target" "$expires" "$grant_sid" <<'PYAUDIT' >> "$DAEMON_RESTART_AUDIT_LOG"
import json, sys
from datetime import datetime, timezone
log_path, sid, target, unit, verb, grant_target, expires, grant_sid = sys.argv[1:9]
print(json.dumps({
    "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "sid": sid,
    "target": target,
    "unit": unit,
    "verb": verb,
    "outcome": "consumed",
    "grant_target": grant_target,
    "grant_session_id": grant_sid,
    "grant_expires_at": expires,
    "source": "pretool-bash-safety",
}, separators=(",", ":")))
PYAUDIT
      echo "[daemon-restart-grant] consumed grant for target=$target unit=$unit verb=$verb" >&2
      return 0
      ;;
    EXPIRED$'\t'*|TARGET_MISMATCH$'\t'*|SESSION_MISMATCH$'\t'*|NO_FLAG|BLOCKED_LOCK|ERROR$'\t'*)
      local outcome="${consume_result%%$'\t'*}"
      "$PYTHON_BIN" - "$DAEMON_RESTART_AUDIT_LOG" "$sid" "$target" "$unit" "$verb" "$outcome" <<'PYAUDIT2' >> "$DAEMON_RESTART_AUDIT_LOG"
import json, sys
from datetime import datetime, timezone
log_path, sid, target, unit, verb, outcome = sys.argv[1:7]
print(json.dumps({
    "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "sid": sid,
    "target": target,
    "unit": unit,
    "verb": verb,
    "outcome": outcome.lower(),
    "source": "pretool-bash-safety",
}, separators=(",", ":")))
PYAUDIT2
      return 1
      ;;
    *)
      return 1
      ;;
  esac
}

# ── Global /allow short-circuit ─────────────────────────────────────────────
# RELOCATED 2026-05-09 (task-id 20260509-113838) to run BEFORE all four
# absolute-ban categories (Layer 1.A-E daemon-restart prohibition + the three
# session/recovery/restart blocks below). The user-binding directive (verbatim
# text preserved in docs/dev/ticket-20260509-113838.md) authorizing /allow to
# bypass any command including dangerous ones when the user explicitly grants
# the pattern supersedes c3-20260504-223115 R11.
# R11's narrower invariant ("daemon-restart NOT bypassable by generic /allow")
# is RELAXED for users who type generic /allow. The dedicated
# /root/bin/claude-allow-restart channel and its check_and_consume_daemon_restart_grant
# function are UNTOUCHED (W6) and remain the precise-grant alternative for
# users who prefer R11's tighter band.
# Single-shot consume semantics, V1 SIGALRM regex timeout, V1b structural
# rejection, flock atomic-unlink, and the IS_SUBAGENT firewall (inside
# check_and_consume_allowlist) are all preserved unchanged.
# On consume-match: emits canonical Claude Code PreToolUse approval JSON to
# stdout (DEFECT 3a) for permissions-ledger value; sibling project-local
# settings.json hooks still run in parallel and a project-local deny still
# wins per documented "deny > defer > ask > allow" precedence (D3b is a
# Plan-A-blocker; see dev-report plan_a_blocker_d3b for alternatives).
# ── Main-agent /do bypass ────────────────────────────────────────────────────
_DO_IS_SUB=$(echo "$INPUT" | "$PYTHON_BIN" -c \
  "import json,sys; d=json.load(sys.stdin); print('1' if d.get('agent_id') else '0')" \
  2>/dev/null)
if [ "$_DO_IS_SUB" != "1" ]; then
  _DO_SID=$(echo "$INPUT" | "$PYTHON_BIN" -c \
    "import json,sys,os; d=json.load(sys.stdin); \
print(d.get('session_id','') or os.environ.get('CLAUDE_SESSION_ID','default'))" \
    2>/dev/null)
  [ -z "$_DO_SID" ] && _DO_SID="default"
  _DO_FLAG="/tmp/claude-orchestrator-consent-${_DO_SID}.flag"
  if [ -f "$_DO_FLAG" ] && [ "$(cat "$_DO_FLAG" 2>/dev/null)" = "true" ]; then
    exit 0
  fi
fi
# ────────────────────────────────────────────────────────────────────────────
check_and_consume_allowlist "$COMMAND" && exit 0

# Layer 1.A — daemon-restart prohibition: systemctl verb gate against happy-daemon-*.
# Verb set: stop|restart|disable|enable|reload|kill|try-restart|reload-or-restart.
# Anchor `(\s+|\b)` so `systemctl kill -s SIGTERM happy-daemon-dev` matches (verb
# followed by `-s` flag, not whitespace-then-target). Stable label: daemon-restart-prohibition.
if echo "$COMMAND" | grep -qE 'systemctl\s+(stop|restart|disable|enable|reload|kill|try-restart|reload-or-restart)(\s+|\b)' \
   && echo "$COMMAND" | grep -qE 'happy-daemon'; then
  # Identify the bare unit name in the command. We look for happy-daemon[suffix]
  # tokens; if multiple targets, the consume rejects unless grant covers all.
  HAPPY_UNIT=$(echo "$COMMAND" | grep -oE 'happy-daemon(-(dev|jade|qijie))?' | head -1 | sed 's/\.service$//')
  HAPPY_VERB=$(echo "$COMMAND" | grep -oE 'systemctl\s+(stop|restart|disable|enable|reload|kill|try-restart|reload-or-restart)' | head -1 | awk '{print $2}')
  if [ -n "$HAPPY_UNIT" ] && check_and_consume_daemon_restart_grant "$HAPPY_UNIT" "$HAPPY_VERB"; then
    : # grant consumed — fall through to allow the command
  else
    echo "BLOCKED: daemon-restart-prohibition — systemctl ${HAPPY_VERB:-<verb>} on ${HAPPY_UNIT:-happy-daemon-*} is FORBIDDEN" >&2
    echo "Command: $COMMAND" >&2
    echo "REASON: per c3-20260504-223115, Claude must NEVER restart any happy-daemon-* by any path." >&2
    echo "Hint: user must run /root/bin/claude-allow-restart <target> from a real TTY first." >&2
    exit 2
  fi
fi

# Layer 1.B — wrapper-class block: any wrapper invocation co-occurring with
# happy-daemon vocabulary AND daemon-state-disrupting verb. Stable label:
# daemon-restart-wrapper.
if echo "$COMMAND" | grep -qE 'happy-daemon' \
   && echo "$COMMAND" | grep -qE '(restart|stop|disable|enable|reload|kill|try-restart|reload-or-restart|kick|cycle|bounce|hup|HUP)' \
   && echo "$COMMAND" | grep -qE '(systemd-run|^|[[:space:]])((at|batch)\s|crontab\s|nohup\s|disown\s|watch\s|timeout\s|dbus-send|busctl|nc\s|ncat\s|eval\s|bash\s+-c|sh\s+-c|zsh\s+-c|python3?\s+-c|node\s+-[ce]|perl\s+-e|ruby\s+-e)'; then
  echo "BLOCKED: daemon-restart-wrapper — wrapper invocation co-occurring with daemon-restart vocabulary is FORBIDDEN" >&2
  echo "Command: $COMMAND" >&2
  echo "REASON: per c3-20260504-223115, indirect daemon-restart paths (systemd-run/at/crontab/nohup/" >&2
  echo "        timeout/dbus-send/nc/eval/bash -c/python -c) are all forbidden. Use the user-only" >&2
  echo "        /root/bin/claude-allow-restart grant channel instead." >&2
  exit 2
fi

# Layer 1.C — wrapper script on disk: bash /tmp/*.sh, /var/tmp/*.sh, /dev/shm/*.sh
# are blocked outright regardless of body content (orchestrator AND subagents).
# Stable label: daemon-restart-wrapper.
if echo "$COMMAND" | grep -qE '(^|[;&|]\s*)(bash|sh|zsh)\s+(/tmp/|/var/tmp/|/dev/shm/)[^[:space:];&|]+\.sh'; then
  echo "BLOCKED: daemon-restart-wrapper — bash invocation of disposable wrapper script is FORBIDDEN" >&2
  echo "Command: $COMMAND" >&2
  echo "REASON: per c3-20260504-223115, wrapper scripts under /tmp/, /var/tmp/, /dev/shm/ can be a" >&2
  echo "        durable bypass surface for daemon-restart. Run commands inline or via tracked scripts." >&2
  exit 2
fi

# Layer 1.D — daemon HTTP /stop UNCONDITIONAL block. Trigger: any
# (curl|wget|nc|ncat|http.client|aiohttp|requests) invocation referencing
# (localhost|127.0.0.1):PORT/stop, regardless of surrounding text. Stable
# label: daemon-restart-http-stop. Per BA AC4 / OBJ-3-F: there is no
# legitimate Claude reason to POST/GET to `/stop` on a localhost service.
if echo "$COMMAND" | grep -qE '(curl|wget|nc[[:space:]]|ncat|http\.client|aiohttp|requests)' \
   && echo "$COMMAND" | grep -qE '(localhost|127\.0\.0\.1):[0-9]+/stop'; then
  echo "BLOCKED: daemon-restart-http-stop — HTTP /stop on a localhost port is FORBIDDEN" >&2
  echo "Command: $COMMAND" >&2
  echo "REASON: per c3-20260504-223115, the daemon HTTP /stop endpoint is the only documented" >&2
  echo "        use of /stop on a localhost port; Claude must never trigger it. False-positive risk" >&2
  echo "        on other localhost services is accepted by design." >&2
  exit 2
fi

# Layer 1.E — sentinel-write block: any Bash that creates/edits the grant
# sentinel is forbidden (only /root/bin/claude-allow-restart may write it).
# Stable label: daemon-restart-sentinel-write.
if echo "$COMMAND" | grep -qE "${DAEMON_RESTART_SENTINEL_RE}[A-Za-z0-9_-]+\.flag" \
   && echo "$COMMAND" | grep -qE '(>|>>|tee|cp|mv|ln|touch|cat\s)'; then
  echo "BLOCKED: daemon-restart-sentinel-write — writing to grant sentinel is FORBIDDEN" >&2
  echo "Command: $COMMAND" >&2
  echo "REASON: per c3-20260504-223115, only /root/bin/claude-allow-restart (run by user from TTY)" >&2
  echo "        may create the grant sentinel." >&2
  exit 2
fi

# ── Global /allow short-circuit RELOCATED ──────────────────────────────────
# As of task-id 20260509-113838 the /allow short-circuit runs BEFORE Layer 1.A
# (and before the three absolute-ban blocks below). The original callsite at
# this position is intentionally removed; the secondary check_and_consume_allowlist
# callsites further below in the git-rule blocks (around lines 889/900/912/932/
# 946/1002 of the original file) are now defense-in-depth-only and harmless
# (no command can reach them with the /allow flag still present).

# ── ABSOLUTE BAN: session_dirs.txt, happy-session-recovery.sh, happy-restart.sh ──
# On 2026-04-09, editing session_dirs.txt triggered full restore and killed all sessions.
# These files must NEVER be touched by Claude under any circumstances.

if echo "$COMMAND" | grep -qE 'session_dirs\.txt'; then
  echo "BLOCKED: session_dirs.txt is PERMANENTLY FORBIDDEN — never read, write, or reference this file" >&2
  echo "Command: $COMMAND" >&2
  echo "REASON: On 2026-04-09, editing session_dirs.txt triggered session-watcher full restore and killed ALL production sessions." >&2
  exit 2
fi

if echo "$COMMAND" | grep -qE 'happy-session-recovery'; then
  echo "BLOCKED: happy-session-recovery.sh is PERMANENTLY FORBIDDEN" >&2
  echo "Command: $COMMAND" >&2
  echo "REASON: This script manages critical session state. Only the user may run it manually." >&2
  exit 2
fi

if echo "$COMMAND" | grep -qE 'happy-restart'; then
  echo "BLOCKED: happy-restart.sh is PERMANENTLY FORBIDDEN" >&2
  echo "Command: $COMMAND" >&2
  echo "REASON: This script restarts daemons and can kill all sessions. Only the user may run it manually." >&2
  exit 2
fi

# ── Rules ─────────────────────────────────────────────────────────

# Block: sensitive file write via Bash redirect or as target
if echo "$COMMAND" | grep -qE '(>|>>)\s*\S*(\.env|credentials|secret|password)'; then
  echo "BLOCKED: Attempting to write to sensitive file via Bash" >&2
  echo "Command: $COMMAND" >&2
  echo "Edit sensitive files manually — never via AI-driven Bash redirection." >&2
  exit 2
fi
if echo "$COMMAND" | grep -qE '(\.env|credentials|secret|password)\S*\s*(>|>>)'; then
  echo "BLOCKED: Attempting to redirect from/to sensitive file via Bash" >&2
  echo "Command: $COMMAND" >&2
  echo "Edit sensitive files manually — never via AI-driven Bash redirection." >&2
  exit 2
fi

# Block: destructive disk operations
if echo "$COMMAND" | grep -qE '^\s*(dd |mkfs|fdisk|shred )'; then
  echo "BLOCKED: Destructive disk operation detected" >&2
  echo "Command: $COMMAND" >&2
  exit 2
fi

# Block: Docker daemon operations
if echo "$COMMAND" | grep -qE 'systemctl\s+(restart|stop|disable)\s+docker'; then
  echo "BLOCKED: Docker daemon operations are forbidden" >&2
  echo "Command: $COMMAND" >&2
  exit 2
fi

# Block: modifying Docker daemon config
if echo "$COMMAND" | grep -qE '(>|>>|tee|cp|mv|sed|awk)\s.*/etc/docker/daemon\.json'; then
  echo "BLOCKED: Modifying Docker daemon config is forbidden" >&2
  echo "Command: $COMMAND" >&2
  exit 2
fi

# Block: docker stop/restart/rm/kill on happy containers (unless ALL targets are dev-whitelisted)
if echo "$COMMAND" | grep -qE 'docker\s+(stop|restart|rm|kill)\s+.*happy'; then
  if ! check_docker_targets_all_dev "$COMMAND" "$DEV_CONTAINERS"; then
    echo "BLOCKED: Stopping/restarting production happy containers is forbidden" >&2
    echo "Command: $COMMAND" >&2
    echo "Hint: only $DEV_CONTAINERS is allowed." >&2
    exit 2
  fi
fi

# Block: docker-compose down, stop, and restart (destructive)
if echo "$COMMAND" | grep -qE 'docker.compose\s+(down|restart|stop)'; then
  echo "BLOCKED: docker-compose down/stop/restart is forbidden" >&2
  echo "Command: $COMMAND" >&2
  exit 2
fi

# Block: docker system prune -a (removes everything)
if echo "$COMMAND" | grep -qE 'docker\s+system\s+prune\s+-a'; then
  echo "BLOCKED: docker system prune -a is forbidden" >&2
  echo "Command: $COMMAND" >&2
  exit 2
fi

# Block: generic process killers targeting services
if echo "$COMMAND" | grep -qE '(killall|pkill)\s+.*(happy|claude|docker)'; then
  echo "BLOCKED: Killing happy/claude/docker processes is forbidden" >&2
  echo "Command: $COMMAND" >&2
  exit 2
fi

# Block: kill with ANY signal targeting PIDs (kill -9, kill -TERM, kill -15, kill -HUP, etc.)
if echo "$COMMAND" | grep -qE 'kill\s+-'; then
  echo "BLOCKED: kill with signals is forbidden — use graceful shutdown methods" >&2
  echo "Command: $COMMAND" >&2
  exit 2
fi

# Block: systemctl stop/restart/disable/enable/reload/kill/try-restart/reload-or-restart
# Verb set extended per c3-20260504-223115 R1 (8 verbs covering all daemon-state-disrupting
# systemctl operations). Targets covering `happy-daemon` are handled by Layer 1.A above
# (with the dedicated grant channel); this block fires for non-happy systemctl targets.
if echo "$COMMAND" | grep -qE 'systemctl\s+(stop|restart|disable|enable|reload|kill|try-restart|reload-or-restart)(\s+|\b)' \
   && ! echo "$COMMAND" | grep -qE 'happy-daemon'; then
  if ! check_systemctl_targets_all_dev "$COMMAND" "$DEV_SYSTEMD"; then
    check_and_consume_allowlist "$COMMAND" && exit 0
    echo "BLOCKED: systemctl stop/restart/disable/enable/reload/kill/try-restart/reload-or-restart is forbidden for production services" >&2
    echo "Command: $COMMAND" >&2
    echo "Hint: only $DEV_SYSTEMD is allowed (and happy-daemon-* is gated by Layer 1.A)." >&2
    exit 2
  fi
fi

# Block: rm/mv targeting workflow enforcement files (AF3+AF4 security fix)
if echo "$COMMAND" | grep -qE '(rm|mv)\s' && echo "$COMMAND" | grep -qE '(workflow-[^/]*\.json|\.claude/todos/)'; then
  echo "BLOCKED: Deleting/moving workflow state files is forbidden" >&2
  echo "Command: $COMMAND" >&2
  echo "These files are required by the workflow enforcement system." >&2
  exit 2
fi

# Block: filesystem rm (but NOT docker rm, which is handled above)
if echo "$COMMAND" | grep -qE '(^|[;|&]\s*)rm\s' && ! echo "$COMMAND" | grep -qE 'docker\s+rm\s'; then
  echo "BLOCKED: rm is forbidden — delete files manually or ask the user" >&2
  echo "Command: $COMMAND" >&2
  exit 2
fi

# Block: source contamination — rsync/cp from external paths into /root/happy/packages/
# Only git (merge/cherry-pick) should bring code into production source
if echo "$COMMAND" | grep -qE '(rsync|cp)\s' && echo "$COMMAND" | grep -q '/root/happy/packages/'; then
  # Allow operations WITHIN /root/happy (e.g. cp within the repo)
  # Block operations FROM external paths (happy-dev, worktrees, /dev/shm, /tmp)
  if echo "$COMMAND" | grep -qE '(/root/happy-dev/|/dev/shm/|/tmp/|worktree).*(/root/happy/packages/)'; then
    echo "BLOCKED: Writing external code into /root/happy/packages/ is forbidden" >&2
    echo "Command: $COMMAND" >&2
    echo "Hint: Use git merge/cherry-pick to bring code into production. NEVER rsync/cp from dev branches or worktrees." >&2
    echo "Bug #59: A dev-overnight agent rsynced worktree code into /root/happy, causing 6 days of broken sidechain rendering." >&2
    exit 2
  fi
fi

# Block: docker build of Dockerfile.webapp without HAPPY_SERVER_URL
if echo "$COMMAND" | grep -qE 'docker\s+build' && echo "$COMMAND" | grep -q "Dockerfile.webapp"; then
  if ! echo "$COMMAND" | grep -q "HAPPY_SERVER_URL"; then
    echo "BLOCKED: docker build for Dockerfile.webapp MUST include --build-arg HAPPY_SERVER_URL=https://api.life-ai.app" >&2
    echo "Without this, the web app defaults to api.cluster-fluster.com (WRONG)." >&2
    echo "Command: $COMMAND" >&2
    exit 2
  fi
  if echo "$COMMAND" | grep -qE '\-\-build-arg.*cluster-fluster|HAPPY_SERVER_URL=.*cluster-fluster'; then
    echo "BLOCKED: HAPPY_SERVER_URL must NOT be api.cluster-fluster.com" >&2
    echo "Command: $COMMAND" >&2
    exit 2
  fi
fi

# Block: direct SQL writes to production happy DB (INSERT/UPDATE/DELETE on Session, Account, etc.)
if echo "$COMMAND" | grep -qE 'docker\s+exec\s+happy-postgres\b' && echo "$COMMAND" | grep -qiE '\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER)\b'; then
  echo "BLOCKED: Direct SQL writes to production happy-postgres are forbidden" >&2
  echo "Command: $COMMAND" >&2
  echo "Hint: Only SELECT queries allowed. Use the app/API to modify data." >&2
  exit 2
fi
if echo "$COMMAND" | grep -qE 'psql.*happydb' && echo "$COMMAND" | grep -qiE '\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER)\b'; then
  echo "BLOCKED: Direct SQL writes to production happydb are forbidden" >&2
  echo "Command: $COMMAND" >&2
  echo "Hint: Only SELECT queries allowed. Use the app/API to modify data." >&2
  exit 2
fi

# Block: docker compose up/build (recreates containers, causes downtime)
# Exception: applio-* and happy-*-dev services are allowed IF no prod services mixed in
# Whitelist approach: extract ALL service names, every one must be dev/applio
if echo "$COMPOSE_COMMAND" | grep -qE 'docker.compose\s+(up|build)\s'; then
  compose_lines=$(echo "$COMPOSE_COMMAND" | grep -E 'docker.compose\s+(up|build)\s')
  # Extract service names (everything after up/build and flags like -d --no-deps)
  services=$(echo "$compose_lines" | sed -E 's/.*docker.compose\s+(up|build)\s+//' | tr ' ' '\n' | grep -v '^-' | grep -v '^$')
  if [ -z "$services" ]; then
    # No specific services = ALL services = forbidden
    echo "BLOCKED: docker compose up/build without specific service names is forbidden" >&2
    echo "Command: $COMMAND" >&2
    echo "Hint: specify services explicitly: docker compose up -d happy-web-dev happy-server-dev" >&2
    exit 2
  fi
  # Check every service name is in the whitelist
  blocked_service=""
  while IFS= read -r svc; do
    case "$svc" in
      applio-*|happy-web-dev|happy-server-dev|happy-server-dev:*|postgres-dev|redis-dev) ;; # allowed
      *) blocked_service="$svc" ; break ;;
    esac
  done <<< "$services"
  if [ -n "$blocked_service" ]; then
    echo "BLOCKED: service '$blocked_service' is not a dev service — cannot compose up/build production services" >&2
    echo "Command: $COMMAND" >&2
    echo "Hint: only these services allowed: applio-*, happy-web-dev, happy-server-dev, postgres-dev, redis-dev" >&2
    exit 2
  fi
fi

# Block: curl/wget POST to happy-server API that creates/modifies sessions
if echo "$COMMAND" | grep -qE '(curl|wget).*(/v1/sessions|/v1/machines|/session-started|/spawn-session)' && echo "$COMMAND" | grep -qiE '(-X\s*POST|-X\s*PUT|-X\s*PATCH|-X\s*DELETE|-d\s|--data)'; then
  echo "BLOCKED: 必须使用正常的UI流程创建session，永远不允许使用代码创建session！" >&2
  echo "Command: $COMMAND" >&2
  echo "Hint: Open https://dev.life-ai.app -> click Start New Session -> type message -> send. NEVER use curl/API to create sessions." >&2
  exit 2
fi

# Block: curl/wget to production API (localhost:3000 or api.life-ai.app) — all methods
if echo "$COMMAND" | grep -qE '(curl|wget).*(localhost:3000|127\.0\.0\.1:3000|api\.life-ai\.app)' && \
   ! echo "$COMMAND" | grep -qE 'api-dev\.life-ai\.app'; then
  echo "BLOCKED: Accessing production API is FORBIDDEN from dev environment" >&2
  echo "Command: $COMMAND" >&2
  echo "Hint: Use localhost:3005 (dev API) or api-dev.life-ai.app instead." >&2
  exit 2
fi

# ── ABSOLUTE ISOLATION: happy-dev must NEVER touch production happy ──────────

# Block: npm install -g (strip comments first to avoid false positives)
CMD_NO_COMMENTS=$(echo "$COMMAND" | sed 's/#.*$//')
if echo "$CMD_NO_COMMENTS" | grep -qE 'npm\s+(install|i)\s+.*(-g|--global)' || echo "$CMD_NO_COMMENTS" | grep -qE 'npm\s+(install|i)\s+-g'; then
  echo "BLOCKED: npm install -g is FORBIDDEN from this environment" >&2
  echo "Command: $COMMAND" >&2
  echo "REASON: On 2026-04-04, npm install -g from a worktree replaced the global happy binary," >&2
  echo "triggered auto-upgrade, and killed ALL production sessions. NEVER do this again." >&2
  echo "The global CLI must only be installed from /root/happy by the user manually." >&2
  exit 2
fi

# Block: direct invocation of /usr/bin/happy or bare 'happy' CLI command
# (prevents triggering auto-upgrade version mismatch detection)
if echo "$COMMAND" | grep -qE '(^|[;&|]\s*)/usr/bin/happy([^-]|$)' || echo "$COMMAND" | grep -qE '(^|[;&|]\s*)happy\s+(daemon|--version|auth)\b'; then
  echo "BLOCKED: Direct invocation of the global happy CLI is FORBIDDEN" >&2
  echo "Command: $COMMAND" >&2
  echo "REASON: The global /usr/bin/happy is shared by ALL daemons. Invoking it can trigger" >&2
  echo "auto-upgrade and kill production sessions. Use node with full path to dist instead." >&2
  exit 2
fi

# Block: kill on PIDs that aren't verified dev processes
# (prevents accidentally killing production session processes)
if echo "$COMMAND" | grep -qE '(^|[;&|]\s*)kill\s+[0-9]'; then
  echo "BLOCKED: kill with PIDs is FORBIDDEN — verify target is dev before killing" >&2
  echo "Command: $COMMAND" >&2
  echo "REASON: On 2026-04-04, killing dev session processes cascaded to production." >&2
  echo "Use systemctl restart happy-daemon-dev or daemon HTTP /stop instead." >&2
  exit 2
fi

# Block: WRITING to /usr/lib/node_modules/happy or /usr/bin/happy (reading is OK)
# Allow /usr/bin/happy-dev (dev binary) but block /usr/bin/happy (production binary)
if echo "$COMMAND" | grep -qE '(ln|cp|mv|unlink|tee)\s.*(/usr/lib/node_modules/happy|/usr/bin/happy)' && \
   ! echo "$COMMAND" | grep -qE '/usr/bin/happy-dev'; then
  echo "BLOCKED: Modifying global happy binary/modules is FORBIDDEN" >&2
  echo "Command: $COMMAND" >&2
  exit 2
fi

# Block: happy-daemon-dev service must NEVER use /usr/bin/happy (production binary)
# Allow /usr/bin/happy-dev but block /usr/bin/happy
if echo "$COMMAND" | grep -q 'happy-daemon-dev' && echo "$COMMAND" | grep -qE '/usr/bin/happy([^-]|$)'; then
  echo "BLOCKED: happy-daemon-dev must NEVER reference /usr/bin/happy (production binary)" >&2
  echo "Command: $COMMAND" >&2
  echo "REASON: Dev daemon must use /root/happy-dev/packages/happy-cli/dist/index.mjs directly." >&2
  echo "Using /usr/bin/happy causes dev daemon to run production code, ignoring all dev fixes." >&2
  exit 2
fi

# ── Dangerous git operations (2026-04-19 incident prevention) ──────────────
# On 2026-04-19 23:02:22, a dev subagent ran:
#     git stash && cd packages/happy-app && git checkout 925f5960 -- .
# The `-- .` wide-path checkout overwrote the entire happy-app directory with
# 3-27 baseline content, erasing 17 days of UI work. The stash was treated as
# a throwaway buffer but then failed to pop cleanly, leaving the worktree in a
# silently-regressed state. The subagent reported "something happened" as if
# it were an accident, concealing that it ran the destructive command itself.
# Block these three patterns globally — main agent AND subagents.

# Block: git stash (destructive forms only — list/show/pop/apply/drop/clear/branch are safe)
# V4: extended to also cover -u/--include-untracked/-a/--all variants (which include untracked/ignored files)
if echo "$COMMAND" | grep -qE 'git\s+stash\s+(push|save|create|store|-u|--include-untracked|-a|--all)\b' || \
   echo "$COMMAND" | grep -qE 'git\s+stash\s+-[ua]+\b'; then
  check_and_consume_allowlist "$COMMAND" && exit 0
  echo "BLOCKED: 'git stash push/save/create/store/-u/--all' requires explicit user approval" >&2
  echo "Command: $COMMAND" >&2
  echo "REASON: On 2026-04-19, a dev subagent used 'git stash' as a throwaway buffer" >&2
  echo "before running a destructive 'git checkout <hash> -- .', silently erasing 17 days" >&2
  echo "of UI work. Stash+checkout is a known-dangerous combo in subagent hands." >&2
  echo "-u/--include-untracked/-a/--all forms include untracked/ignored files — more destructive." >&2
  echo "Tell the user what you want to do and ask them to run it, or use commit/branch." >&2
  exit 2
fi
if echo "$COMMAND" | grep -qE 'git\s+stash\s*($|[;&|])'; then
  check_and_consume_allowlist "$COMMAND" && exit 0
  echo "BLOCKED: bare 'git stash' (implicit push) requires explicit user approval" >&2
  echo "Command: $COMMAND" >&2
  echo "REASON: See 2026-04-19 incident — stash is often paired with destructive checkout." >&2
  echo "Safe stash subcommands are exempt: list, show, pop, apply, drop, clear, branch." >&2
  exit 2
fi

# Block: git checkout <ref> -- . or -- * or -- <dir>/
# Wide-path checkout from a ref overwrites the entire subtree with historical content.
# Allowed: 'git checkout <ref> -- path/to/specific-file.ts' (single file), 'git checkout <branch>' (branch switch).
if echo "$COMMAND" | grep -qE 'git\s+checkout\s+\S+\s+--\s+(\.|\*|[^ ]+/)\s*($|[;&|])'; then
  check_and_consume_allowlist "$COMMAND" && exit 0
  echo "BLOCKED: 'git checkout <ref> -- .' / '-- *' / '-- dir/' requires explicit user approval" >&2
  echo "Command: $COMMAND" >&2
  echo "REASON: On 2026-04-19, a dev subagent ran 'git checkout 925f5960 -- .' inside" >&2
  echo "packages/happy-app/, overwriting 17 days of UI development with 3-27 baseline." >&2
  echo "Wide-path checkout from a commit is a blunt-force destructive operation." >&2
  echo "Allowed: 'git checkout <ref> -- path/to/specific-file.ts' (single file)." >&2
  echo "If you genuinely need a subtree restore, tell the user what you need and why." >&2
  exit 2
fi

# Block: git restore --source=<ref> -- . / -- */ -- <dir>/  (V6)
# Modern equivalent of 'git checkout <ref> -- .' (git 2.23+) — overwrites working tree with historical content.
# Two-condition approach (order-independent): command must contain BOTH a source flag AND a wide-path.
# Covers all four syntaxes: --source=X, --source X, -s=X, -s X.
# Allowed: 'git restore -- myfile.ts' (no --source, no overwrite), 'git restore --staged -- file' (index-only),
#          'git restore --source=HEAD -- specific-file.ts' (specific file, not wide-path).
if echo "$COMMAND" | grep -qE 'git\s+restore\b' && \
   echo "$COMMAND" | grep -qE -- '(--source\b|-s\b)' && \
   echo "$COMMAND" | grep -qE -- '--\s+(\.|\*|[^ /]+/)\s*($|[;&|])'; then
  check_and_consume_allowlist "$COMMAND" && exit 0
  echo "BLOCKED: 'git restore --source=<ref> -- .' / '-- *' / '-- dir/' requires explicit user approval" >&2
  echo "Command: $COMMAND" >&2
  echo "REASON: 'git restore --source=<ref> -- .' is the modern equivalent of" >&2
  echo "'git checkout <ref> -- .' (git 2.23+). It overwrites the working tree with historical" >&2
  echo "content — same blunt-force destructive operation that erased 17 days of UI work on 2026-04-19." >&2
  echo "Allowed: 'git restore -- path/to/specific-file.ts' (no --source, or specific file)." >&2
  echo "If you genuinely need a subtree restore, tell the user what you need and why." >&2
  exit 2
fi

# Block: every git reset --hard form. Shared-repo policy forbids reset-like cleanup in agent flow.
GIT_GLOBAL_OPT_RE='([[:space:]]+(-[Cc][[:space:]]+[^[:space:];|&]+|-[Cc][^[:space:];|&]+|--(git-dir|work-tree|namespace|exec-path|super-prefix|config-env)(=[^[:space:];|&]+|[[:space:]]+[^[:space:];|&]+)|--(bare|no-pager|paginate|no-replace-objects|literal-pathspecs|glob-pathspecs|noglob-pathspecs|icase-pathspecs|no-optional-locks)|-[pP]))*'
GIT_CMD_RE='(^|[[:space:];&|()`])git'"$GIT_GLOBAL_OPT_RE"'[[:space:]]+'
if echo "$COMMAND" | grep -qE "${GIT_CMD_RE}reset[[:space:]]+([^;|&]*[[:space:]]+)?--hard\b"; then
  echo "BLOCKED: 'git reset --hard' is forbidden in agent flow" >&2
  echo "Command: $COMMAND" >&2
  echo "REASON: shared-repo policy requires non-destructive recovery; hard reset can discard another session's work or index state." >&2
  echo "Use semantic commits, backup recovery refs, or ask the user for a human-run recovery operation." >&2
  exit 2
fi

# Block: force/delete branch publication and direct ref mutation surfaces.
if echo "$COMMAND" | grep -qE "${GIT_CMD_RE}push\b" && \
   echo "$COMMAND" | grep -qE '(^|[[:space:]])(--force|-f|--force-with-lease(=[^[:space:]]+)?|--delete|-d|--mirror)([[:space:]]|$)|[[:space:]]\+[^[:space:]]|[[:space:]]:[^[:space:]]'; then
  echo "BLOCKED: force/delete/ref-rewrite push is forbidden in agent flow" >&2
  echo "Command: $COMMAND" >&2
  echo "REASON: policy allows normal /push branch publication and backup-only recovery refs; force/delete/ref-rewrite pushes can lose remote work." >&2
  exit 2
fi
if echo "$COMMAND" | grep -qE "${GIT_CMD_RE}(update-ref\b|branch[[:space:]]+(-[fDdMm]+|--delete|--force|--move)\b|symbolic-ref([[:space:]]+-m([[:space:]]+[^[:space:];|&]+|[^[:space:];|&]*))*[[:space:]]+HEAD[[:space:]]+refs/)"; then
  echo "BLOCKED: direct git ref mutation is forbidden in agent flow" >&2
  echo "Command: $COMMAND" >&2
  echo "REASON: branch movement must go through the expected-parent CAS wrapper; branch delete/force/update-ref is not agent-accessible." >&2
  exit 2
fi

# Block: subagent-initiated git history mutation (2026-04-23 incident)
# Subagents have weak context and cannot reliably know whether the user has consented.
# All git history changes by subagents must be surfaced to the user instead.
# Detection: parse stdin JSON for agent_id (matches pretool-orchestrator-gate.py mechanism).
IS_SUBAGENT=$(echo "$INPUT" | "$PYTHON_BIN" -c "import json,sys; d=json.load(sys.stdin); print('1' if d.get('agent_id') else '0')" 2>/dev/null)
if [ "$IS_SUBAGENT" = "1" ]; then
  # /do bypass (2026-04-25): user has explicitly consented via /do — allow subagent history mutation
  SID=$(echo "$INPUT" | "$PYTHON_BIN" -c "import json,sys; d=json.load(sys.stdin); print(d.get('session_id',''))" 2>/dev/null)
  if [ -n "$SID" ] && [ -e "/tmp/claude-orchestrator-consent-${SID}.flag" ]; then
    exit 0
  fi
  # Narrowed (2026-05-14): commit|merge|push are fully covered by
  # pretool-git-privilege-guard.py (canonical layer). revert|cherry-pick|rebase
  # are NOT covered there, so they remain in this layer.
  if echo "$COMMAND" | grep -qE 'git[[:space:]]+(revert|cherry-pick|rebase)([[:space:]]|$)'; then
    echo "BLOCKED: Subagent-initiated git history mutation is FORBIDDEN (revert|cherry-pick|rebase)" >&2
    echo "Command: $COMMAND" >&2
    echo "Subagents must NEVER mutate git history. Tell the user what you want done" >&2
    echo "and ask them to run the command themselves." >&2
    echo "Allowed git verbs for subagents: status, log, show, diff, blame, ls-tree, ls-files, branch (read-only), worktree list." >&2
    echo "(commit|merge|push are blocked by pretool-git-privilege-guard.py)" >&2
    exit 2
  fi
  # Branch -D / -d deletion is covered by the canonical block at line ~1046
  # (regex -[fDdMm]+) AND by pretool-git-privilege-guard.py:287. The previous
  # 'git branch -D ' substring check here was a duplicate and has been removed.
fi

# Block: git revert <commit-hash> or git revert <ref>^ or git revert <ref>~N or git revert <ref>@{N}
# V5: broadened from HEAD-only anchor to \S+ so any ref (HEAD, master, main, branch, tag)
# with a modifier (caret, tilde, reflog, hash) is blocked.
# Reverting a non-bare-HEAD commit can undo deliberate user work.
# Safe: 'git revert HEAD' ONLY (bare — no caret, no tilde, no reflog, no branch-ref modifier).
# All other revert forms are blocked.
if echo "$COMMAND" | grep -qE 'git\s+revert\s+'; then
  # Block hex hashes (7+ chars)
  # Block caret form: <ref>^ or <ref>^^ (e.g., HEAD^, master^, HEAD^^)
  # Block tilde form: <ref>~ or <ref>~N (e.g., HEAD~, HEAD~1, master~2)
  # Block reflog form: <ref>@{N} (e.g., HEAD@{1})
  # Intermediate group (\S+\s+)* allows flags-before-ref (e.g., git revert --no-edit HEAD^)
  # Note: \b after ^/~/} is omitted because those characters are non-word — \b requires
  # a word-char transition and would fail to match at end-of-string or before whitespace.
  if echo "$COMMAND" | grep -qE 'git\s+revert\s+(\S+\s+)*[0-9a-f]{7,40}\b' || \
     echo "$COMMAND" | grep -qE 'git\s+revert\s+(\S+\s+)*\S+\^+' || \
     echo "$COMMAND" | grep -qE 'git\s+revert\s+(\S+\s+)*\S+~[0-9]*' || \
     echo "$COMMAND" | grep -qE 'git\s+revert\s+(\S+\s+)*\S+@\{[0-9]+\}'; then
    check_and_consume_allowlist "$COMMAND" && exit 0
    echo "BLOCKED: 'git revert' with any ref modifier (caret/tilde/reflog/hash) requires explicit user approval" >&2
    echo "Command: $COMMAND" >&2
    echo "REASON: On 2026-04-23, a dev subagent ran 'git revert 1204d62' which undid a user-approved" >&2
    echo "feature commit (the /spec simplification the user had explicitly endorsed), restoring an" >&2
    echo "unwanted 5-step interview state. The user had explicitly forbidden full revert in chat." >&2
    echo "Reverting historical commits without user authorization is destructive — it overrides" >&2
    echo "deliberate work that may have been thoroughly reviewed and accepted." >&2
    # V5 comment fix: Only bare 'git revert HEAD' (no suffix) is safe. All other forms blocked.
    echo "Safe: 'git revert HEAD' only (bare — no caret, no tilde, no reflog, no branch-ref)." >&2
    echo "All other revert forms (HEAD^, HEAD~N, HEAD@{N}, master^, <hash>) are blocked." >&2
    echo "If you genuinely need to revert a historical commit, tell the user the hash and the" >&2
    echo "rationale, and ask them to run it manually." >&2
    exit 2
  fi
fi

exit 0
