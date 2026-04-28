#!/bin/bash
#
# /commit wrapper — closed dev task one-shot commit (Scheme 6)
#
# Authority:
#   /root/docs/dev/close-report-20260425-push-commit-debate.md (CLOSE: YES on Scheme 6)
#   /root/docs/dev/ba-spec-20260425-redev2.md §4.3 (AC-C1..AC-C13)
#
# Flow:
#   1. Parse <task-id> argument (positional, required)
#   2. Closure detection (PRIMARY close-report → SECONDARY completion+qa-report; fail-closed)
#   3. Read dev-report; extract allowed_files (multi-schema union)
#   4. Generate deterministic commit message; compute sha256
#   5. Write single-use grant manifest /tmp/claude-commit-grant-<sid>-<nonce>.json
#   6. Stage exactly allowed_files; verify staged set matches
#   7. Export CLAUDE_COMMIT_COMMAND_ACTIVE=1; run blessed git commit
#   8. Append audit log line to /root/.claude/logs/git-privilege-grants.log
#
# Defense:
#   - Closure check is necessary but not sufficient — bulk-commit-detector remains an
#     independent downstream gate. A forged grant whose allowed_files spans 3+ subsystems
#     and whose message looks like 'chore(claude): sync ...' will still be blocked there.
#   - Grant single-use unlink is performed by THIS WRAPPER on the success path.
#     PreToolUse hooks (incl. the privilege-guard) DO NOT fire on subprocesses spawned
#     by a wrapper script, so the guard cannot observe the `git commit` subprocess and
#     cannot unlink the grant. The wrapper must clean up after itself (AC-iter2-9).
#   - On any wrapper failure path, the grant is left in place — the operator may want
#     to retry, and the grant has nonce binding so retries are safe. The EXIT trap
#     unlinks ONLY when the wrapper itself errors out before reaching the success path.

set -euo pipefail

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
# Smart fallback chain (redev7 P-CWD-FALLBACK):
#   1. CLAUDE_PROJECT_DIR set → use it (redev4 explicit override behavior preserved)
#   2. cwd inside a git repo → use repo toplevel (handles real-world cross-project use)
#   3. cwd not in a repo → use cwd (last resort; never blindly /root)
DOCS_DIR_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
DOCS_DIR="${DOCS_DIR_ROOT}/docs/dev"
# LOG_PATH is intentionally user-home-anchored (audit log lives where Claude
# infrastructure lives, not where the project lives). Do NOT parameterize via
# CLAUDE_PROJECT_DIR — this is by design (AC-DOCS-4).
LOG_PATH="/root/.claude/logs/git-privilege-grants.log"
GRANT_FILE=""

# AC-iter2-9: Wrapper-only grant lifecycle.
#   - Success path: Step 7 unlinks GRANT_FILE after `git commit` returns 0
#     (PreToolUse hooks do not fire on subprocesses, so the guard cannot do it).
#   - Failure path: leave the grant in place. The grant is nonce-bound and
#     single-use, so the operator may safely retry. No EXIT trap removal.
# (Earlier revisions removed the grant in an EXIT trap on rc!=0 — that was the
# wrong policy and is no longer in force.)

# -----------------------------------------------------------------------------
# Step 1 — argument parse
# -----------------------------------------------------------------------------
# Three modes:
#   commit.sh <task-id> -m "<msg>"          — closed-task commit (PRIMARY/SECONDARY)
#                                             -m REQUIRED non-empty (redev6 P-MSG / M-MSG-1).
#                                             Auto-derive from H1 title is REMOVED.
#   commit.sh --auto-bulk-bridge <branch>   — overnight per-cycle commit (P3 bridge mode)
#                                             -m FORBIDDEN (BLESSED_BRIDGE_RE locks message)
#   commit.sh --force -m "<msg>"            — irregular-path escape hatch (redev6 P-FORCE)
#                                             -m REQUIRED non-empty; bypasses closure /
#                                             task-id / dev-report / cross-repo / P-CLOSEHONOR
#                                             / H1 checks. The four always-on security layers
#                                             (disable-model-invocation on commit.md,
#                                             inline-env literal-substring rejection,
#                                             bulk-commit-detector, grant manifest emission)
#                                             remain engaged.
#
# --force and --auto-bulk-bridge are mutually exclusive; passing both -> exit 2.
#
# Bridge mode (AC-P3-2 in ba-spec-20260426-redev3.md):
#   Used by /dev-overnight per-cycle finalization. Stages from the already-cached
#   set (caller pre-stages with `git add`), emits commit message
#   `auto-bulk: end-of-cycle commit for <branch>` (matches BLESSED_BRIDGE_RE in
#   pretool-git-privilege-guard.py:92), AND writes a grant manifest so the guard
#   gains defense-in-depth visibility into staged-set / message-hash. Bridge
#   mode does NOT require close-report or dev-report — overnight cycles produce
#   bulk commits across many small fixes; closure evidence is per-issue, not
#   per-cycle.
#
# Force mode (ba-spec-20260426-redev6.md M-FORCE / AC-FORCE-1..4):
#   The irregular-path escape hatch for hand-written single-file commits, spec-only
#   commits, manual recovery commits — flows that have no closure ceremony but are
#   still legitimate. The closure / task-id / dev-report layers are demoted from
#   "gate" to "audit metadata" per feedback_commit_overengineering.md. Security
#   rests on the four always-on layers, all of which stay engaged in --force mode.
if [ $# -lt 1 ] || [ -z "${1:-}" ]; then
  echo "Usage:" >&2
  echo "  commit.sh <task-id> [-m \"<msg>\"]           # closed-task commit (-m optional, auto-fills from closure artifacts)" >&2
  echo "  commit.sh --auto-bulk-bridge <branch>      # overnight per-cycle commit (-m forbidden)" >&2
  echo "  commit.sh --force -m \"<msg>\"                # irregular-path escape hatch (-m required)" >&2
  echo "Example: commit.sh dev-20260425-145411 -m \"real session summary describing the fix\"" >&2
  echo "Example: commit.sh --auto-bulk-bridge cycle-2-redev" >&2
  echo "Example: commit.sh --force -m \"docs(notes): add foo notes — hand-written single-file\"" >&2
  exit 2
fi

MODE="closed-task"
TASK_ID=""
BRIDGE_BRANCH=""
CALLER_MESSAGE=""
HAS_CALLER_MESSAGE=0
MESSAGE_SOURCE="auto"   # "auto" | "caller" — recorded in audit log

# Pre-scan: extract `-m "<msg>"` (or `--message "<msg>"`) from anywhere in argv
# (M-MSG-5 / AC-MSG-6 — orchestrator may pass -m before or after the mode flag).
# The remaining (non--m) tokens are repacked into the positional argv for the
# first-pass dispatch + second-pass leftover loop.
PRESCAN_REMAINING=()
PRESCAN_I=0
while [ $PRESCAN_I -lt $# ]; do
  PRESCAN_I=$((PRESCAN_I + 1))
  PRESCAN_ARG="${!PRESCAN_I}"
  if [ "$PRESCAN_ARG" = "-m" ] || [ "$PRESCAN_ARG" = "--message" ]; then
    PRESCAN_I=$((PRESCAN_I + 1))
    if [ $PRESCAN_I -gt $# ]; then
      echo "commit.sh: -m requires a message argument" >&2
      exit 2
    fi
    if [ "$HAS_CALLER_MESSAGE" -eq 1 ]; then
      echo "commit.sh: -m specified more than once" >&2
      exit 2
    fi
    CALLER_MESSAGE="${!PRESCAN_I}"
    HAS_CALLER_MESSAGE=1
  else
    PRESCAN_REMAINING+=("$PRESCAN_ARG")
  fi
done
# Repack argv with -m / --message stripped out.
set -- "${PRESCAN_REMAINING[@]+"${PRESCAN_REMAINING[@]}"}"

# After pre-scan, at least one positional must remain (the mode flag or task-id).
if [ $# -lt 1 ] || [ -z "${1:-}" ]; then
  echo "commit.sh: no mode argument (task-id, --auto-bulk-bridge <branch>, or --force)" >&2
  exit 2
fi

# First-pass dispatch: identify the mode based on the first positional arg.
if [ "$1" = "--auto-bulk-bridge" ]; then
  if [ $# -lt 2 ] || [ -z "${2:-}" ]; then
    echo "commit.sh --auto-bulk-bridge: missing <branch> argument" >&2
    exit 2
  fi
  MODE="auto-bulk-bridge"
  BRIDGE_BRANCH="$2"
  if [[ "$BRIDGE_BRANCH" =~ [[:space:]\;\&\|\`\$\(\)\<\>\\\"\'\*\?\[\]] ]]; then
    echo "commit.sh: invalid branch (shell-metacharacters not allowed): $BRIDGE_BRANCH" >&2
    exit 2
  fi
  # Bridge mode uses the branch as the task-id surrogate for grant + audit.
  TASK_ID="$BRIDGE_BRANCH"
  shift 2
elif [ "$1" = "--force" ]; then
  MODE="force"
  shift 1
else
  TASK_ID="$1"
  if [[ "$TASK_ID" =~ [[:space:]\;\&\|\`\$\(\)\<\>\\\"\'\*\?\[\]] ]]; then
    echo "commit.sh: invalid task-id (shell-metacharacters not allowed): $TASK_ID" >&2
    exit 2
  fi
  shift 1
fi

# Second pass: parse trailing flags. Currently only -m "<msg>" is supported.
# Per-mode -m semantics:
#   closed-task: REQUIRED non-empty (M-MSG-1; auto-derive REMOVED in redev6)
#   force:       REQUIRED non-empty (empty/missing both reject)
#   bridge:      FORBIDDEN (would break BLESSED_BRIDGE_RE locked message format)
#
# Mutual exclusion: encountering --force or --auto-bulk-bridge in this loop
# means the caller passed BOTH mode flags (the first-pass dispatch already
# consumed exactly one). Reject with usage (ba-spec-20260426-redev6.md mutual-
# exclusion clause in user prompt).
while [ $# -gt 0 ]; do
  case "$1" in
    -m|--message)
      if [ $# -lt 2 ]; then
        echo "commit.sh: -m requires a message argument" >&2
        exit 2
      fi
      CALLER_MESSAGE="$2"
      HAS_CALLER_MESSAGE=1
      shift 2
      ;;
    --force|--auto-bulk-bridge)
      echo "commit.sh: --force and --auto-bulk-bridge are mutually exclusive" >&2
      echo "Usage:" >&2
      echo "  commit.sh <task-id> [-m \"<msg>\"]           # closed-task commit (-m optional, auto-fills from closure artifacts)" >&2
      echo "  commit.sh --auto-bulk-bridge <branch>      # overnight per-cycle commit (-m forbidden)" >&2
      echo "  commit.sh --force -m \"<msg>\"                # irregular-path escape hatch (-m required)" >&2
      exit 2
      ;;
    *)
      echo "commit.sh: unrecognized argument: $1" >&2
      exit 2
      ;;
  esac
done

# Per-mode -m policy enforcement (ba-spec-20260426-redev6.md M-MSG-1..3,
# AC-MSG-1, AC-MSG-3, AC-MSG-5).
#
# Verbatim exit-message contract (asserted by AC-MSG-1, AC-MSG-3, AC-MSG-5):
#   closed-task without -m  -> "commit message required (-m); agent must summarize session intent"
#   --force without -m      -> "commit message required (-m); agent must summarize session intent"
#   --force with -m ""      -> "commit message required (-m); agent must summarize session intent"
#   --auto-bulk-bridge -m   -> "commit.sh --auto-bulk-bridge: -m not allowed (bridge mode uses fixed BLESSED message format)"
if [ "$MODE" = "force" ]; then
  if [ "$HAS_CALLER_MESSAGE" -eq 0 ] || [ -z "$CALLER_MESSAGE" ]; then
    echo "commit message required (-m); agent must summarize session intent" >&2
    exit 2
  fi
  MESSAGE_SOURCE="caller"
elif [ "$MODE" = "auto-bulk-bridge" ]; then
  if [ "$HAS_CALLER_MESSAGE" -eq 1 ]; then
    echo "commit.sh --auto-bulk-bridge: -m not allowed (bridge mode uses fixed BLESSED message format)" >&2
    exit 2
  fi
elif [ "$MODE" = "closed-task" ]; then
  # 2026-04-28: -m is OPTIONAL in closed-task mode. If caller did not pass -m,
  # auto-generate from closure artifacts via helper script.
  if [ "$HAS_CALLER_MESSAGE" -eq 0 ] || [ -z "$CALLER_MESSAGE" ]; then
    HELPER="/root/.claude/scripts/auto-commit-message.sh"
    if [ -x "$HELPER" ]; then
      CALLER_MESSAGE="$("$HELPER" "$TASK_ID")"
      if [ -n "$CALLER_MESSAGE" ]; then
        HAS_CALLER_MESSAGE=1
        MESSAGE_SOURCE="auto"
      fi
    fi
  else
    MESSAGE_SOURCE="caller"
  fi
  if [ "$HAS_CALLER_MESSAGE" -eq 0 ] || [ -z "$CALLER_MESSAGE" ]; then
    echo "commit message could not be auto-generated (no closure artifacts for $TASK_ID); pass -m manually" >&2
    exit 2
  fi
fi

# S-FORCE-WARNING: emit a one-line stderr warning for --force mode so the
# operator is reminded that closure/task-id/dev-report layers are bypassed
# but the four always-on security layers remain engaged.
if [ "$MODE" = "force" ]; then
  echo "commit.sh: --force bypasses closure/task-id/dev-report checks; security relies on disable-model-invocation + inline-env rejection + bulk-detector + grant manifest" >&2
fi

# -----------------------------------------------------------------------------
# Step 1b — bridge-mode short-circuit
# -----------------------------------------------------------------------------
# When invoked as `commit.sh --auto-bulk-bridge <branch>`:
#   - Skip closure detection entirely (no close-report / completion / qa-report
#     required — overnight cycles produce bulk commits across many issues).
#   - Read pre-staged file set from `git diff --cached --name-only` (caller
#     stages files before invoking the bridge).
#   - Compute commit message of the form `auto-bulk: end-of-cycle commit for <branch>`
#     (matches BLESSED_BRIDGE_RE in pretool-git-privilege-guard.py:92).
#   - Write a per-nonce grant manifest with allowed_files + expected_message_sha256
#     + branch (defense-in-depth: the guard's defense-in-depth path validates
#     this manifest when it sees a bridge-mode commit with the env+grant pair).
#   - Export CLAUDE_COMMIT_COMMAND_ACTIVE=1; run blessed git commit.
#   - Wrapper unlinks grant on success (preserve iter3 fix).
#   - Audit log line carries `mode=auto-bulk-bridge branch=<branch>`.
if [ "$MODE" = "auto-bulk-bridge" ]; then
  # Pre-staged set required (caller is responsible for staging).
  STAGED_RAW="$(git diff --cached --name-only | sort -u)"
  if [ -z "$STAGED_RAW" ]; then
    echo "commit.sh --auto-bulk-bridge: no files staged for ${BRIDGE_BRANCH}" >&2
    echo "  Caller must run 'git add' before invoking bridge mode." >&2
    exit 2
  fi

  # Pack into a bash array.
  ALLOWED_FILES=()
  while IFS= read -r line; do
    [ -n "$line" ] && ALLOWED_FILES+=("$line")
  done <<< "$STAGED_RAW"

  # JSON-encode for the grant manifest.
  ALLOWED_JSON="$(python3 -c "
import json, sys
files = [l for l in sys.stdin.read().splitlines() if l.strip()]
print(json.dumps(sorted(set(files))))
" <<< "$STAGED_RAW")"

  # Bridge-mode commit message (matches BLESSED_BRIDGE_RE — preserves
  # backwards-compat with the existing privilege-guard early-return at line
  # 440-442 of pretool-git-privilege-guard.py).
  COMMIT_MSG="auto-bulk: end-of-cycle commit for ${BRIDGE_BRANCH}"

  MSG_SHA256="$(python3 -c "
import hashlib, sys
print(hashlib.sha256(sys.argv[1].encode('utf-8')).hexdigest())
" "$COMMIT_MSG")"

  # Grant manifest (per-nonce; mirrors the closed-task path).
  SID="${CLAUDE_SESSION_ID:-$$}"
  NONCE="$(python3 -c "import secrets; print(secrets.token_hex(16))")"
  GRANT_FILE="/tmp/claude-commit-grant-${SID}-${NONCE}.json"
  CREATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  PPID_VAL="$$"

  python3 - "$GRANT_FILE" "$NONCE" "$SID" "$BRIDGE_BRANCH" "$ALLOWED_JSON" "$MSG_SHA256" "$CREATED_AT" "$PPID_VAL" <<'PY'
import json, sys
path, nonce, sid, branch, allowed_json, msg_sha, created_at, ppid_val = sys.argv[1:9]
grant = {
    "nonce": nonce,
    "sid": sid,
    "mode": "auto-bulk-bridge",
    "branch": branch,
    "task_id": branch,
    "allowed_files": json.loads(allowed_json),
    "expected_message_sha256": msg_sha,
    "created_at": created_at,
    "ppid": int(ppid_val),
}
with open(path, "w") as fh:
    json.dump(grant, fh, indent=2, sort_keys=True)
PY

  # Bless the commit.  The privilege-guard's BLESSED_BRIDGE_RE early-return
  # admits this regardless of env/grant (AC-P3-4: in-flight overnight runs
  # without bridge-mode patches keep working).  Bridge mode ALSO sets the env
  # and writes the grant so the guard's defense-in-depth path (added in this
  # cycle) can observe and warn on staged-set / message-hash drift.
  export CLAUDE_COMMIT_COMMAND_ACTIVE=1

  git commit -m "$COMMIT_MSG"

  # Wrapper unlinks grant on success path (guard never fires on subprocess).
  rm -f "$GRANT_FILE"
  GRANT_FILE=""

  # Audit log line.
  mkdir -p "$(dirname "$LOG_PATH")"
  NEW_HEAD="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
  MSG_SHA_SHORT="${MSG_SHA256:0:12}"
  TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  python3 - "$LOG_PATH" "$TS" "$SID" "$BRIDGE_BRANCH" "$NONCE" "$PPID_VAL" "$MSG_SHA_SHORT" "$NEW_HEAD" <<'PY'
import json, sys
path, ts, sid, branch, nonce, ppid_val, msg_sha_short, head = sys.argv[1:9]
line = {
    "timestamp": ts,
    "sid": sid,
    "command_kind": "commit",
    "mode": "auto-bulk-bridge",
    "branch": branch,
    "task_id": branch,
    "sentinel_nonce": nonce,
    "ppid": int(ppid_val),
    "message_sha256_short": msg_sha_short,
    "head": head,
    "closure_kind": "bridge",
}
with open(path, "a") as fh:
    fh.write(json.dumps(line) + "\n")
PY

  echo "commit.sh: success — mode=auto-bulk-bridge branch=${BRIDGE_BRANCH} head=${NEW_HEAD} files=${#ALLOWED_FILES[@]}"
  exit 0
fi

# -----------------------------------------------------------------------------
# Step 1c — force-mode short-circuit (ba-spec-20260426-redev6.md M-FORCE / AC-FORCE-1..4)
# -----------------------------------------------------------------------------
# When invoked as `commit.sh --force -m "<msg>"`:
#   - Skip closure detection entirely (no PRIMARY/SECONDARY check; no close-report
#     / completion-md / qa-report / dev-report required).
#   - Skip task-id resolution (TASK_ID stays empty).
#   - Skip dev-report parsing (no allowed_files extraction from dev-report).
#   - Skip cross-repo filter (allowed_files == staged set, by definition).
#   - Skip P-CLOSEHONOR (no close-report consultation).
#   - Skip P-H1 / P-TASKID / P-NESTED / P-CROSSREPO checks.
#   - Read pre-staged file set via `git diff --cached --name-only` (caller stages
#     files before invoking).
#   - Use caller-supplied message verbatim (CALLER_MESSAGE, validated above).
#   - Write a per-nonce grant manifest with mode="force"; allowed_files = staged
#     set; expected_message_sha256 = sha256(CALLER_MESSAGE). The privilege-guard's
#     existing schema admits this without modification (it validates env +
#     sha256(message) + allowed_files = staged set; the `mode` field is
#     metadata-only).
#   - Export CLAUDE_COMMIT_COMMAND_ACTIVE=1; run blessed git commit.
#   - Wrapper unlinks grant on success (matches commit.sh:666 pattern).
#   - Audit log line carries `mode=force` for forensics, with
#     `message_source=caller` (--force requires caller-supplied -m).
#
# Security model: the FOUR ALWAYS-ON layers remain engaged in --force mode:
#   1. disable-model-invocation: true on commit.md (the slash command can only
#      be invoked by a human, never the model — AV-5 mitigation).
#   2. inline-env literal-substring rejection in privilege-guard
#      (CLAUDE_COMMIT_COMMAND_ACTIVE=1 prefix in the raw command text rejects).
#   3. bulk-commit-detector (independent gate; AC-FORCE-3: --force does NOT
#      bypass the b5d447e-shape detector).
#   4. grant manifest emission with sha256(message) + allowed_files binding +
#      single-use unlink on success (replay defense).
if [ "$MODE" = "force" ]; then
  # Pre-staged set required (caller is responsible for staging via `git add`).
  # M-FORCE-2 (ba-spec-20260426-redev6.md / orchestrator-prompt verbatim):
  # exit 2 with explicit no-staged message (mirrors bridge-mode behavior).
  STAGED_RAW="$(git diff --cached --name-only | sort -u)"
  if [ -z "$STAGED_RAW" ]; then
    echo "commit.sh --force: no files staged; run 'git add' first" >&2
    exit 2
  fi

  # Pack into a bash array (matches bridge-mode pattern at lines 129-132).
  ALLOWED_FILES=()
  while IFS= read -r line; do
    [ -n "$line" ] && ALLOWED_FILES+=("$line")
  done <<< "$STAGED_RAW"

  # JSON-encode for the grant manifest.
  ALLOWED_JSON="$(python3 -c "
import json, sys
files = [l for l in sys.stdin.read().splitlines() if l.strip()]
print(json.dumps(sorted(set(files))))
" <<< "$STAGED_RAW")"

  # Caller-supplied message verbatim (validated non-empty above at the
  # per-mode policy enforcement step).
  COMMIT_MSG="$CALLER_MESSAGE"

  MSG_SHA256="$(python3 -c "
import hashlib, sys
print(hashlib.sha256(sys.argv[1].encode('utf-8')).hexdigest())
" "$COMMIT_MSG")"

  # Grant manifest (per-nonce; mirrors the bridge-mode + closed-task pattern).
  SID="${CLAUDE_SESSION_ID:-$$}"
  NONCE="$(python3 -c "import secrets; print(secrets.token_hex(16))")"
  GRANT_FILE="/tmp/claude-commit-grant-${SID}-${NONCE}.json"
  CREATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  PPID_VAL="$$"

  # --force mode has no task-id; use the literal sentinel "__force__" as the
  # task_id field so audit-log readers can distinguish force-mode entries.
  FORCE_TASK_SENTINEL="__force__"

  python3 - "$GRANT_FILE" "$NONCE" "$SID" "$FORCE_TASK_SENTINEL" "$ALLOWED_JSON" "$MSG_SHA256" "$CREATED_AT" "$PPID_VAL" <<'PY'
import json, sys
path, nonce, sid, task_id, allowed_json, msg_sha, created_at, ppid_val = sys.argv[1:9]
grant = {
    "nonce": nonce,
    "sid": sid,
    "mode": "force",
    "task_id": task_id,
    "allowed_files": json.loads(allowed_json),
    "expected_message_sha256": msg_sha,
    "created_at": created_at,
    "ppid": int(ppid_val),
}
with open(path, "w") as fh:
    json.dump(grant, fh, indent=2, sort_keys=True)
PY

  # Bless the commit. The privilege-guard will validate env-var presence + grant
  # manifest + sha256(message) + allowed_files = staged set. The bulk-commit-
  # detector remains an independent downstream gate (AC-FORCE-3).
  export CLAUDE_COMMIT_COMMAND_ACTIVE=1

  git commit -m "$COMMIT_MSG"

  # Wrapper unlinks grant on success path (guard never fires on subprocess).
  rm -f "$GRANT_FILE"
  GRANT_FILE=""

  # Audit log line.
  mkdir -p "$(dirname "$LOG_PATH")"
  NEW_HEAD="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
  MSG_SHA_SHORT="${MSG_SHA256:0:12}"
  TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  python3 - "$LOG_PATH" "$TS" "$SID" "$FORCE_TASK_SENTINEL" "$NONCE" "$PPID_VAL" "$MSG_SHA_SHORT" "$NEW_HEAD" "$ALLOWED_JSON" <<'PY'
import json, sys
path, ts, sid, task_id, nonce, ppid_val, msg_sha_short, head, allowed_json = sys.argv[1:10]
line = {
    "timestamp": ts,
    "sid": sid,
    "command_kind": "commit",
    "mode": "force",
    "task_id": task_id,
    "sentinel_nonce": nonce,
    "ppid": int(ppid_val),
    "message_sha256_short": msg_sha_short,
    "head": head,
    "closure_kind": "force",
    "allowed_files": json.loads(allowed_json),
    "message_source": "caller",
}
with open(path, "a") as fh:
    fh.write(json.dumps(line) + "\n")
PY

  echo "commit.sh: success — mode=force head=${NEW_HEAD} files=${#ALLOWED_FILES[@]}"
  exit 0
fi

# -----------------------------------------------------------------------------
# Step 2 — closure detection (PRIMARY then SECONDARY, fail-closed)
# -----------------------------------------------------------------------------
CLOSE_REPORT="${DOCS_DIR}/close-report-${TASK_ID}.md"
COMPLETION_DOC="${DOCS_DIR}/completion-${TASK_ID}.md"
QA_REPORT="${DOCS_DIR}/qa-report-${TASK_ID}.json"

CLOSURE_PATH=""    # path of the file that satisfied the check (used for title extraction)
CLOSURE_KIND=""    # "primary" | "secondary"
CLOSE_VERDICT_OBSERVED="absent"   # "yes" | "no" | "absent" — for S2 audit log

# PRIMARY: close-report exists AND last non-empty line matches '^CLOSE:\s*YES\b'.
#
# P-CLOSEHONOR (ba-spec-20260426-redev5.md M5 / AC-CLOSEHONOR-1..4):
# When a close-report exists for the task-id, its verdict is AUTHORITATIVE.
#   CLOSE: YES → PRIMARY (current behavior preserved, AC-CLOSEHONOR-2)
#   CLOSE: NO  → REFUSE the commit (AC-CLOSEHONOR-1) — do NOT fall through to SECONDARY
#   neither   → REFUSE (defensive; AC-CLOSEHONOR-4) — do NOT fall through
# This closes the SECONDARY back-door that previously admitted commits even
# when /close had returned a deliberate negative verdict.
if [ -f "$CLOSE_REPORT" ]; then
  # Last non-empty line — strip CR, drop blank lines, take final survivor.
  LAST_NONEMPTY="$(tr -d '\r' < "$CLOSE_REPORT" | awk 'NF{line=$0} END{print line}')"
  if [[ "$LAST_NONEMPTY" =~ ^CLOSE:[[:space:]]*YES([[:space:]]|$|\b) ]]; then
    CLOSURE_PATH="$CLOSE_REPORT"
    CLOSURE_KIND="primary"
    CLOSE_VERDICT_OBSERVED="yes"
  elif [[ "$LAST_NONEMPTY" =~ ^CLOSE:[[:space:]]*NO([[:space:]]|$|\b) ]]; then
    CLOSE_VERDICT_OBSERVED="no"
    echo "task closed with verdict NO; cannot commit until /close passes" >&2
    echo "  close-report: ${CLOSE_REPORT}" >&2
    echo "  last non-empty line: ${LAST_NONEMPTY}" >&2
    exit 2
  else
    # close-report exists but last line is neither YES nor NO — fail closed.
    echo "close-report exists for ${TASK_ID} but verdict is unrecognized; expected CLOSE: YES or CLOSE: NO" >&2
    echo "  close-report: ${CLOSE_REPORT}" >&2
    echo "  last non-empty line: ${LAST_NONEMPTY}" >&2
    exit 2
  fi
fi

# SECONDARY: only if PRIMARY failed.
#
# F2 (close-report-20260425-push-commit-debate.md §3 — task-id content binding):
# the SECONDARY path was previously file-existence-only, which let an attacker
# steer /commit at an unrelated task by simply renaming dropped files.  We now
# require the task-id to appear (a) as the leading H1/title of the
# completion-md, and (b) inside the qa-report.json's task_id / request_id keys
# (UNION at top-level OR under .qa), and (c) inside the dev-report.json's
# task_id / request_id keys (UNION at top-level OR under .dev).  ALL three
# checks must pass; ANY missing -> exit 2 (fail closed).
if [ -z "$CLOSURE_KIND" ]; then
  if [ -f "$COMPLETION_DOC" ] && [ -f "$QA_REPORT" ]; then
    QA_STATUS_OK="$(python3 -c "
import json, sys
try:
    with open(sys.argv[1]) as fh:
        data = json.load(fh)
except Exception:
    sys.exit(1)
status = data.get('qa', {}).get('status') if isinstance(data, dict) else None
sys.exit(0 if status == 'pass' else 1)
" "$QA_REPORT" && echo yes || echo no)"
    if [ "$QA_STATUS_OK" = "yes" ]; then
      # F2 check 1 (P-H1, ba-spec-20260426-redev5.md M1 / AC-H1-1..3):
      # task_id evidence in the completion-md may come from ANY of three sources:
      #   (a) filename match — proven by the lookup at COMPLETION_DOC=
      #       "${DOCS_DIR}/completion-${TASK_ID}.md" already succeeding;
      #       this alone is sufficient (canonical proof — historically all 40
      #       completion files use generic H1 'Development Completion Report'
      #       with the task-id only in the filename + Request-ID body line).
      #   (b) Request-ID body line — case-insensitive, decoration-tolerant
      #       (e.g. '**Request ID**: dev-<task-id>', 'Request-ID: <task-id>').
      #   (c) H1 contains task-id — kept as legacy fallback (iter2 schema).
      # Pass if ANY one holds. The lookup path satisfies (a) by construction,
      # so this check is effectively a sanity confirmation; we still verify
      # explicitly so the audit trail records which source matched.
      H1_EVIDENCE_SOURCE=""
      # (a) filename match: COMPLETION_DOC ends with the task-id.
      if [[ "$COMPLETION_DOC" == *"completion-${TASK_ID}.md" ]]; then
        H1_EVIDENCE_SOURCE="filename"
      fi
      # (b) Request-ID body line: case-insensitive, allow markdown decoration
      # (asterisks/underscores) and tabs/spaces around the colon.
      if [ -z "$H1_EVIDENCE_SOURCE" ] && \
         grep -iE "[Rr]equest[[:space:]_*-]*[Ii][Dd][[:space:]*_]*:[[:space:]]*${TASK_ID}" \
              "$COMPLETION_DOC" > /dev/null 2>&1; then
        H1_EVIDENCE_SOURCE="request_id_body"
      fi
      # (c) H1 fallback: legacy iter2 behavior.
      if [ -z "$H1_EVIDENCE_SOURCE" ] && \
         grep -E "^#[[:space:]]+.*${TASK_ID}" "$COMPLETION_DOC" > /dev/null 2>&1; then
        H1_EVIDENCE_SOURCE="h1"
      fi
      if [ -z "$H1_EVIDENCE_SOURCE" ]; then
        echo "SECONDARY closure refused: task_id ${TASK_ID} not bound to ${COMPLETION_DOC}" >&2
        echo "  checked: filename match, Request-ID body line, H1 fallback — all missed" >&2
        exit 2
      fi

      # F2 check 2: task_id must appear in qa-report.json content (UNION rule).
      # P-TASKID (ba-spec-20260426-redev5.md M2 / AC-TASKID-1..3):
      # Match by literal-equality OR substring containment (TASK_ID in str(value)).
      # Real reports prefix request_id with 'qa-' / 'dev-' / 'commit-'; substring
      # match accepts these without enumerating prefixes. Task-ids are typically
      # 15+ char timestamps (YYYYMMDD-HHMMSS), making collision risk negligible.
      DEV_REPORT_PRECHECK="${DOCS_DIR}/dev-report-${TASK_ID}.json"
      if python3 -c "
import json, sys
try:
    with open(sys.argv[1]) as fh:
        data = json.load(fh)
except Exception:
    sys.exit(1)
if not isinstance(data, dict):
    sys.exit(1)
qa_node = data.get('qa') if isinstance(data.get('qa'), dict) else {}
keys_to_check = [
    data.get('task_id'),
    data.get('request_id'),
    qa_node.get('task_id'),
    qa_node.get('request_id'),
]
task_id = sys.argv[2]
def matches(value, tid):
    if value is None:
        return False
    if value == tid:
        return True
    if isinstance(value, str) and tid in value:
        return True
    return False
sys.exit(0 if any(matches(v, task_id) for v in keys_to_check) else 1)
" "$QA_REPORT" "$TASK_ID"; then
        :
      else
        echo "SECONDARY closure refused: task_id ${TASK_ID} not found in ${QA_REPORT} (checked task_id, request_id, qa.task_id, qa.request_id; literal+substring)" >&2
        exit 2
      fi

      # F2 check 3: task_id must appear in dev-report.json content (UNION rule).
      # P-TASKID (ba-spec-20260426-redev5.md M2 / AC-TASKID-2):
      # Same literal-or-substring matcher as the qa-report check above.
      if [ ! -f "$DEV_REPORT_PRECHECK" ]; then
        echo "SECONDARY closure refused: dev-report missing at ${DEV_REPORT_PRECHECK}" >&2
        exit 2
      fi
      if python3 -c "
import json, sys
try:
    with open(sys.argv[1]) as fh:
        data = json.load(fh)
except Exception:
    sys.exit(1)
if not isinstance(data, dict):
    sys.exit(1)
dev_node = data.get('dev') if isinstance(data.get('dev'), dict) else {}
keys_to_check = [
    data.get('task_id'),
    data.get('request_id'),
    dev_node.get('task_id'),
    dev_node.get('request_id'),
]
task_id = sys.argv[2]
def matches(value, tid):
    if value is None:
        return False
    if value == tid:
        return True
    if isinstance(value, str) and tid in value:
        return True
    return False
sys.exit(0 if any(matches(v, task_id) for v in keys_to_check) else 1)
" "$DEV_REPORT_PRECHECK" "$TASK_ID"; then
        :
      else
        echo "SECONDARY closure refused: task_id ${TASK_ID} not found in ${DEV_REPORT_PRECHECK} (checked task_id, request_id, dev.task_id, dev.request_id; literal+substring)" >&2
        exit 2
      fi

      CLOSURE_PATH="$COMPLETION_DOC"
      CLOSURE_KIND="secondary"
    fi
  fi
fi

if [ -z "$CLOSURE_KIND" ]; then
  echo "task not closed: no close-report or completion+qa-pass evidence for ${TASK_ID}" >&2
  echo "  looked for PRIMARY:   ${CLOSE_REPORT} (last line ^CLOSE:\\s*YES\\b)" >&2
  echo "  looked for SECONDARY: ${COMPLETION_DOC} + ${QA_REPORT} (.qa.status == 'pass')" >&2
  exit 2
fi

# -----------------------------------------------------------------------------
# Step 3 — resolve dev-report and extract allowed_files
# -----------------------------------------------------------------------------
DEV_REPORT="${DOCS_DIR}/dev-report-${TASK_ID}.json"
if [ ! -f "$DEV_REPORT" ]; then
  echo "dev-report missing: ${DEV_REPORT}" >&2
  exit 2
fi

# Union from an enumerated set of paths in the dev-report JSON.
#
# P-NESTED (ba-spec-20260426-redev5.md M3 / AC-NESTED-1..3):
# Real dev-reports nest files_modified/files_created under various paths.
# We enumerate the known schemas (deterministic + auditable; no recursive walk):
#   top.files_modified, top.files_created                             (existing)
#   dev.files_modified, dev.files_created                             (existing)
#   dev.tasks_completed[*].files_modified / files_created             (NEW)
#   tasks[*].files_modified / files_created                           (NEW alt schema)
#   deliverables[*].files_modified / files_created                    (NEW alt schema)
#
# Each entry is filtered to non-empty strings (defense against the list-of-dicts
# corner case BA-QA flagged in dev-report-20260420-080000.json).
# Empty union → fail-closed at the existing ALLOWED_RAW check below.
# Output: newline-separated, sorted+deduped.
ALLOWED_RAW="$(python3 - "$DEV_REPORT" <<'PY'
import json, sys
path = sys.argv[1]
try:
    with open(path) as fh:
        data = json.load(fh)
except Exception as e:
    sys.stderr.write(f"dev-report parse error: {e}\n")
    sys.exit(1)

def collect(node, key):
    if not isinstance(node, dict):
        return []
    val = node.get(key)
    if isinstance(val, list):
        return [v for v in val if isinstance(v, str) and v.strip()]
    return []

def collect_from_array(parent, array_key, file_key):
    if not isinstance(parent, dict):
        return []
    arr = parent.get(array_key)
    if not isinstance(arr, list):
        return []
    out = []
    for item in arr:
        out.extend(collect(item, file_key))
    return out

files = set()

# (1) top-level + .dev (existing schemas)
for node in (data, data.get('dev') if isinstance(data, dict) else None):
    files.update(collect(node, 'files_modified'))
    files.update(collect(node, 'files_created'))

# (2) dev.tasks_completed[*].files_*
dev_node = data.get('dev') if isinstance(data, dict) else None
files.update(collect_from_array(dev_node, 'tasks_completed', 'files_modified'))
files.update(collect_from_array(dev_node, 'tasks_completed', 'files_created'))

# (3) top-level tasks[*].files_*  (alt schema)
files.update(collect_from_array(data, 'tasks', 'files_modified'))
files.update(collect_from_array(data, 'tasks', 'files_created'))

# (4) top-level deliverables[*].files_*  (alt schema)
files.update(collect_from_array(data, 'deliverables', 'files_modified'))
files.update(collect_from_array(data, 'deliverables', 'files_created'))

# Print one path per line, sorted + deduped.
for f in sorted(files):
    print(f)
PY
)"

if [ -z "$ALLOWED_RAW" ]; then
  echo "dev-report.files_modified/files_created union is empty for ${TASK_ID}" >&2
  echo "  cannot derive allowed_files; refusing to commit." >&2
  exit 2
fi

# Preserve the FULL union for the audit log (M4 / AC-CROSSREPO-3).
ALLOWED_FULL_RAW="$ALLOWED_RAW"

# P-CROSSREPO (ba-spec-20260426-redev5.md M4 / AC-CROSSREPO-1..3):
# Filter allowed_files to current-repo membership BEFORE staging/comparison.
# A file belongs to the current repo if EITHER:
#   (a) `git ls-files --error-unmatch -- <path>` succeeds (tracked file), OR
#   (b) the path exists at <repo_root>/<path> on disk (newly-created file
#       not yet tracked, or path normalization edge cases).
# Empty filtered set → exit 2 with "wrong repo" message; the FULL set was
# non-empty (we'd have exited above otherwise), so this distinguishes
# "wrong repo" from "no files modified".
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$REPO_ROOT" ]; then
  echo "commit.sh: not inside a git repository (git rev-parse --show-toplevel failed)" >&2
  exit 2
fi

# Pass full-list via a temp file — heredoc-vs-herestring stdin conflicts with
# `python3 - <<PY ... PY <<< "$VAR"` (the herestring would clobber the heredoc).
ALLOWED_FULL_TMP="$(mktemp /tmp/claude-commit-allowed-XXXXXX)"
printf '%s\n' "$ALLOWED_FULL_RAW" > "$ALLOWED_FULL_TMP"

ALLOWED_RAW="$(python3 - "$REPO_ROOT" "$ALLOWED_FULL_TMP" <<'PY'
import os, subprocess, sys
repo_root = sys.argv[1]
list_path = sys.argv[2]
with open(list_path) as fh:
    paths = [l.strip() for l in fh.read().splitlines() if l.strip()]
def in_current_repo(path):
    # (a) tracked file in current repo (cheapest authoritative check).
    try:
        rc = subprocess.run(
            ['git', 'ls-files', '--error-unmatch', '--', path],
            cwd=repo_root,
            capture_output=True,
        ).returncode
    except Exception:
        rc = 1
    if rc == 0:
        return True
    # (b) exists on disk AND lives under repo_root (newly-created file).
    # NB: a bare os.path.exists() check is wrong — an absolute path like
    # /dev/shm/.../dot-claude/foo.sh would exist on disk but belongs to a
    # different repo. Require the resolved path to be under repo_root.
    abs_path = path if os.path.isabs(path) else os.path.join(repo_root, path)
    try:
        real_abs = os.path.realpath(abs_path)
        real_root = os.path.realpath(repo_root)
    except Exception:
        return False
    if not os.path.exists(abs_path):
        return False
    # Path must be under repo_root (or equal to it). Use commonpath for
    # boundary safety (avoids '/foo' matching '/foobar' as prefix).
    try:
        common = os.path.commonpath([real_abs, real_root])
    except ValueError:
        return False
    return common == real_root
kept = [p for p in paths if in_current_repo(p)]
for p in sorted(set(kept)):
    print(p)
PY
)"

# Best-effort cleanup of the temp list (keep output regardless of rm result).
[ -f "$ALLOWED_FULL_TMP" ] && : > "$ALLOWED_FULL_TMP" 2>/dev/null || true

if [ -z "$ALLOWED_RAW" ]; then
  echo "no dev-report files belong to this repo (${REPO_ROOT}); commit from the correct repo" >&2
  echo "--- allowed_files (full union) ---" >&2
  printf '%s\n' "$ALLOWED_FULL_RAW" >&2
  exit 2
fi

# Pack the FILTERED set into a bash array (used for staging + comparison).
ALLOWED_FILES=()
while IFS= read -r line; do
  [ -n "$line" ] && ALLOWED_FILES+=("$line")
done <<< "$ALLOWED_RAW"

# JSON-encode the FILTERED set for the grant manifest (W2: grant carries the
# FILTERED set; full set goes to the audit log only).
ALLOWED_JSON="$(python3 -c "
import json, sys
files = [l for l in sys.stdin.read().splitlines() if l.strip()]
print(json.dumps(sorted(set(files))))
" <<< "$ALLOWED_RAW")"

# JSON-encode the FULL set (audit-log only, M4 / AC-CROSSREPO-3).
ALLOWED_FULL_JSON="$(python3 -c "
import json, sys
files = [l for l in sys.stdin.read().splitlines() if l.strip()]
print(json.dumps(sorted(set(files))))
" <<< "$ALLOWED_FULL_RAW")"

# -----------------------------------------------------------------------------
# Step 4 — finalize commit message + compute sha256
# -----------------------------------------------------------------------------
# Closed-task mode message resolution (ba-spec-20260426-redev6.md M-MSG-1):
# -m is REQUIRED; the caller-supplied message is used verbatim. The auto-derive
# from CLOSURE_PATH H1 is REMOVED. Empty/missing -m has already been rejected
# above at the per-mode policy enforcement step (exit 2 with the verbatim
# AC-MSG-1 message). MESSAGE_SOURCE was already set to "caller" in that block.
COMMIT_MSG="$CALLER_MESSAGE"

MSG_SHA256="$(python3 -c "
import hashlib, sys
print(hashlib.sha256(sys.argv[1].encode('utf-8')).hexdigest())
" "$COMMIT_MSG")"

# -----------------------------------------------------------------------------
# Step 5 — write single-use grant manifest
# -----------------------------------------------------------------------------
SID="${CLAUDE_SESSION_ID:-$$}"
NONCE="$(python3 -c "import secrets; print(secrets.token_hex(16))")"
GRANT_FILE="/tmp/claude-commit-grant-${SID}-${NONCE}.json"
CREATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
PPID_VAL="$$"

python3 - "$GRANT_FILE" "$NONCE" "$SID" "$TASK_ID" "$ALLOWED_JSON" "$MSG_SHA256" "$CREATED_AT" "$PPID_VAL" <<'PY'
import json, sys
path, nonce, sid, task_id, allowed_json, msg_sha, created_at, ppid_val = sys.argv[1:9]
grant = {
    "nonce": nonce,
    "sid": sid,
    "task_id": task_id,
    "allowed_files": json.loads(allowed_json),
    "expected_message_sha256": msg_sha,
    "created_at": created_at,
    "ppid": int(ppid_val),
}
with open(path, "w") as fh:
    json.dump(grant, fh, indent=2, sort_keys=True)
PY

# -----------------------------------------------------------------------------
# Step 6 — stage exactly allowed_files; verify
# -----------------------------------------------------------------------------
git add -- "${ALLOWED_FILES[@]}"

STAGED_LIST="$(git diff --cached --name-only | sort -u)"
ALLOWED_LIST="$(printf '%s\n' "${ALLOWED_FILES[@]}" | sort -u)"

if [ "$STAGED_LIST" != "$ALLOWED_LIST" ]; then
  echo "commit.sh: staged-set does not equal allowed_files (refusing to commit)" >&2
  echo "--- staged ---" >&2
  printf '%s\n' "$STAGED_LIST" >&2
  echo "--- allowed ---" >&2
  printf '%s\n' "$ALLOWED_LIST" >&2
  exit 2
fi

# -----------------------------------------------------------------------------
# Step 7 — export env and run blessed commit
# -----------------------------------------------------------------------------
export CLAUDE_COMMIT_COMMAND_ACTIVE=1

# IMPORTANT: HEAD must advance on the current branch. Do NOT touch refs/checkpoints/*.
git commit -m "$COMMIT_MSG"

# AC-iter2-9: wrapper unlinks grant on success path (guard never fires on subprocess)
rm -f "$GRANT_FILE"
GRANT_FILE=""

# -----------------------------------------------------------------------------
# Step 8 — audit log
# -----------------------------------------------------------------------------
mkdir -p "$(dirname "$LOG_PATH")"
NEW_HEAD="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
MSG_SHA_SHORT="${MSG_SHA256:0:12}"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Append a single JSON line for downstream parsing convenience.
# M4 / AC-CROSSREPO-3: log both allowed_files_full and allowed_files_filtered.
# S2: log close_verdict_observed ("yes" | "no" | "absent") for forensics.
# S-MSG-AUDIT (redev6): log message_source ("caller" | "auto") so downstream
# forensics can distinguish orchestrator-written session summaries from auto-
# derived `commit(<task-id>): <H1>` boilerplate.
python3 - "$LOG_PATH" "$TS" "$SID" "$TASK_ID" "$NONCE" "$PPID_VAL" "$MSG_SHA_SHORT" "$NEW_HEAD" "$CLOSURE_KIND" "$ALLOWED_FULL_JSON" "$ALLOWED_JSON" "$CLOSE_VERDICT_OBSERVED" "$MESSAGE_SOURCE" <<'PY'
import json, sys
(path, ts, sid, task_id, nonce, ppid_val, msg_sha_short, head,
 closure_kind, allowed_full_json, allowed_filtered_json,
 close_verdict_observed, message_source) = sys.argv[1:14]
line = {
    "timestamp": ts,
    "sid": sid,
    "command_kind": "commit",
    "mode": "closed-task",
    "task_id": task_id,
    "sentinel_nonce": nonce,
    "ppid": int(ppid_val),
    "message_sha256_short": msg_sha_short,
    "head": head,
    "closure_kind": closure_kind,
    "allowed_files_full": json.loads(allowed_full_json),
    "allowed_files_filtered": json.loads(allowed_filtered_json),
    "close_verdict_observed": close_verdict_observed,
    "message_source": message_source,
}
with open(path, "a") as fh:
    fh.write(json.dumps(line) + "\n")
PY

echo "commit.sh: success — task=${TASK_ID} head=${NEW_HEAD} closure=${CLOSURE_KIND} files=${#ALLOWED_FILES[@]}"
exit 0
