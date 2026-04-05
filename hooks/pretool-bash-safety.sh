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

# Block: docker-compose down and restart (destructive)
if echo "$COMMAND" | grep -qE 'docker.compose\s+(down|restart)'; then
  echo "BLOCKED: docker-compose down/restart is forbidden" >&2
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

# Block: kill -9 targeting unknown PIDs (warn on any kill -9)
if echo "$COMMAND" | grep -qE 'kill\s+-9'; then
  echo "BLOCKED: kill -9 is forbidden — use graceful shutdown methods" >&2
  echo "Command: $COMMAND" >&2
  exit 2
fi

# Block: systemctl stop/restart (unless ALL targets are dev-whitelisted)
if echo "$COMMAND" | grep -qE 'systemctl\s+(stop|restart)\s+'; then
  if ! check_systemctl_targets_all_dev "$COMMAND" "$DEV_SYSTEMD"; then
    echo "BLOCKED: systemctl stop/restart is forbidden for production services" >&2
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

# ── ABSOLUTE ISOLATION: happy-dev must NEVER touch production happy ──────────

# Block: npm install -g (strip comments first to avoid false positives)
CMD_NO_COMMENTS=$(echo "$COMMAND" | sed 's/#.*$//')
if echo "$CMD_NO_COMMENTS" | grep -qE 'npm\s+install\s+-g' || echo "$CMD_NO_COMMENTS" | grep -qE 'npm\s+install\s+--global'; then
  echo "BLOCKED: npm install -g is FORBIDDEN from this environment" >&2
  echo "Command: $COMMAND" >&2
  echo "REASON: On 2026-04-04, npm install -g from a worktree replaced the global happy binary," >&2
  echo "triggered auto-upgrade, and killed ALL production sessions. NEVER do this again." >&2
  echo "The global CLI must only be installed from /root/happy by the user manually." >&2
  exit 2
fi

# Block: direct invocation of /usr/bin/happy or bare 'happy' CLI command
# (prevents triggering auto-upgrade version mismatch detection)
if echo "$COMMAND" | grep -qE '(^|[;&|]\s*)/usr/bin/happy\b' || echo "$COMMAND" | grep -qE '(^|[;&|]\s*)happy\s+(daemon|--version|auth)\b'; then
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
if echo "$COMMAND" | grep -qE '(ln|cp|mv|unlink|tee)\s.*(/usr/lib/node_modules/happy|/usr/bin/happy)'; then
  echo "BLOCKED: Modifying global happy binary/modules is FORBIDDEN" >&2
  echo "Command: $COMMAND" >&2
  exit 2
fi

# Warn: force push
if echo "$COMMAND" | grep -qE 'git push\s+(--force|-f)\b'; then
  echo "WARNING: Force push will rewrite remote history" >&2
  echo "Command: $COMMAND" >&2
fi

exit 0
