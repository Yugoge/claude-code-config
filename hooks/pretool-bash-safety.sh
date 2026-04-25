#!/bin/bash
# PreToolUse Safety Hook - Warn or block before dangerous operations
# Reads tool input from stdin as JSON (Claude Code hook protocol)

# Read full JSON from stdin
INPUT=$(cat)

# Extract tool name and command
TOOL_NAME=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)
COMMAND=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null)

# Only act on Bash tool
if [ "$TOOL_NAME" != "Bash" ]; then
  exit 0
fi

# ── Dev whitelist (exact names only) ──────────────────────────────
# These are the ONLY dev resources that can be freely managed.
DEV_CONTAINERS="happy-web-dev"
DEV_SYSTEMD="happy-daemon-dev"

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

# ── One-shot allowlist bypass for developer-class blocks ─────────────────────
# Reads /tmp/claude-bash-allowlist-<sid>.json (written by userprompt-consent-allowlist.sh).
# On match: deletes the entry (single-use), logs, exits 0.
# NEVER called for asteroid-class blocks.
# NEVER bypasses subagent calls (agent_id check first, inline fresh parse).
CONSENT_LOG="$HOME/.claude/logs/bash-consent.log"

check_and_consume_allowlist() {
  local cmd="$1"

  # IS_SUBAGENT check: INLINE fresh parse from $INPUT.
  # The IS_SUBAGENT variable assigned at line ~499 is NOT yet set when this function is called
  # at upstream call sites (all before the IS_SUBAGENT assignment). Inline parse is the only
  # correct approach.
  local is_sub
  is_sub=$(echo "$INPUT" | python3 -c \
    "import json,sys; d=json.load(sys.stdin); print('1' if d.get('agent_id') else '0')" \
    2>/dev/null)
  if [ "$is_sub" = "1" ]; then
    return 1
  fi

  local sid
  sid=$(echo "$INPUT" | python3 -c \
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
  consume_result=$(FLAG_FILE="$flag_file" LOCK_FILE="$lock_file" CMD_INPUT="$cmd" SID_VAL="$sid" python3 - <<'PYEOF'
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

# Dev-class block rules embedded here (must be kept in sync with the outer shell block list).
# Each entry is a Python regex string. A subcommand is "dangerous" iff it matches ANY of these.
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
        # Both conditions must hold on the SAME subcommand:
        # (a) subcommand matches the user's allow-pattern
        # (b) subcommand matches at least one dev-class block rule
        if safe_search(pattern, sub, is_regex) and matches_any_block_rule(sub):
            matched_subcmd = sub
            break

    if matched_subcmd is None:
        print('NO_MATCH')
        sys.exit(0)

    # Atomic consume: unlink flag while still holding the lock.
    try:
        os.unlink(flag_file)
    except FileNotFoundError:
        print('NO_FLAG')
        sys.exit(0)

    # Emit structured result for shell wrapper to parse and log.
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
      echo "[allow] One-shot bypass consumed for pattern='$pattern' (matched subcommand: '$matched_sub'). Command will proceed." >&2
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

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

# Block: systemctl stop/restart/disable/enable (unless ALL targets are dev-whitelisted)
if echo "$COMMAND" | grep -qE 'systemctl\s+(stop|restart|disable|enable)\s+'; then
  if ! check_systemctl_targets_all_dev "$COMMAND" "$DEV_SYSTEMD"; then
    echo "BLOCKED: systemctl stop/restart/disable/enable is forbidden for production services" >&2
    echo "Command: $COMMAND" >&2
    echo "Hint: only $DEV_SYSTEMD is allowed." >&2
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
if echo "$COMMAND" | grep -qE 'docker.compose\s+(up|build)\s'; then
  # Extract service names (everything after up/build and flags like -d --no-deps)
  services=$(echo "$COMMAND" | sed -E 's/.*docker.compose\s+(up|build)\s+//' | tr ' ' '\n' | grep -v '^-' | grep -v '^$')
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

# Block: git reset --hard to a specific commit (HEAD or no-arg is fine — those are local safety reverts)
if echo "$COMMAND" | grep -qE 'git\s+reset\s+--hard\b' && \
   ! echo "$COMMAND" | grep -qE 'git\s+reset\s+--hard(\s+HEAD)?(\s*$|\s*[;&|])'; then
  check_and_consume_allowlist "$COMMAND" && exit 0
  echo "BLOCKED: 'git reset --hard <commit>' (non-HEAD) requires explicit user approval" >&2
  echo "Command: $COMMAND" >&2
  echo "REASON: reset --hard to an older commit rewrites branch history and discards work." >&2
  echo "Safe: 'git reset --hard' or 'git reset --hard HEAD' (no commit arg) — just resets working tree." >&2
  echo "For recovery, prefer 'git revert HEAD' (main agent only, with user consent) or 'git checkout -b recovery <ref>'. To revert older commits, ask the user." >&2
  exit 2
fi

# Block: subagent-initiated git history mutation (2026-04-23 incident)
# Subagents have weak context and cannot reliably know whether the user has consented.
# All git history changes by subagents must be surfaced to the user instead.
# Detection: parse stdin JSON for agent_id (matches pretool-orchestrator-gate.py mechanism).
IS_SUBAGENT=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print('1' if d.get('agent_id') else '0')" 2>/dev/null)
if [ "$IS_SUBAGENT" = "1" ]; then
  # /do bypass (2026-04-25): user has explicitly consented via /do — allow subagent history mutation
  SID=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('session_id',''))" 2>/dev/null)
  if [ -n "$SID" ] && [ -e "/tmp/claude-orchestrator-consent-${SID}.flag" ]; then
    exit 0
  fi
  if echo "$COMMAND" | grep -qE 'git[[:space:]]+(revert|commit|merge|cherry-pick|rebase|push)([[:space:]]|$)'; then
    echo "BLOCKED: Subagent-initiated git history mutation is FORBIDDEN" >&2
    echo "Command: $COMMAND" >&2
    echo "REASON: On 2026-04-23, a dev subagent ran 'git revert 1204d62 --no-edit' on the" >&2
    echo "nested .claude repo, undoing a user-approved feature commit. The user had stated" >&2
    echo "'禁止 full revert' but the subagent had no real-time access to that constraint." >&2
    echo "Subagents must NEVER mutate git history. Tell the user what you want done" >&2
    echo "and ask them to run the command themselves." >&2
    echo "Allowed git verbs for subagents: status, log, show, diff, blame, ls-tree, ls-files, branch (read-only), worktree list." >&2
    exit 2
  fi
  if echo "$COMMAND" | grep -qE 'git[[:space:]]+branch[[:space:]]+-D[[:space:]]'; then
    echo "BLOCKED: Subagent-initiated branch deletion is FORBIDDEN" >&2
    echo "Command: $COMMAND" >&2
    exit 2
  fi
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

# Warn: force push
if echo "$COMMAND" | grep -qE 'git push\s+(--force|-f)\b'; then
  echo "WARNING: Force push will rewrite remote history" >&2
  echo "Command: $COMMAND" >&2
fi

exit 0
