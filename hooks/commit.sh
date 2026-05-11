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
#   3. Build an internal semantic plan from task artifacts and repo state
#   4. Seed a private index from current branch tip and apply only planned patches
#   5. Create the commit object with git commit-tree
#   6. Advance refs/heads/<branch> by expected-parent CAS
#   7. Write backup-only recovery refs and append audit JSON/log entries
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

# ─── User-intent sentinel ────────────────────────────────────────────────────
# Enforcement lives in pretool-wrapper-userintent.py (PreToolUse hook). The
# hook checks /tmp/claude-commit-userintent-<sid>.flag (written by
# prompt-workflow.py on /commit) before this script runs. Mirrors /allow:
# both writer and reader are hooks, so sid-keying round-trips correctly.


# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
# Permanent DOCS_DIR resolution (P-DOCS-MULTI):
#   Walk an ordered candidate list, pick the FIRST one where docs/dev/ exists.
#   This makes commit.sh robust against subprocess-env-var-stripping (the
#   parent shell's CLAUDE_PROJECT_DIR may not propagate into bash subprocs)
#   and against orchestrator cwd choice.
#   Project-local-first ordering (Plan A′ from QA × Codex debate
#   2026-05-09): the cwd's git toplevel and pwd take priority so a /commit
#   issued from /root/orchestra resolves to /root/orchestra, not the
#   parent /root project that happens to also carry docs/dev/. /root is
#   demoted to the last-position safety net so legacy harness-root flows
#   still resolve when no nearer candidate matches.
#   A1 — explicit CLI flag overrides have priority over env vars and cwd.
#   Candidate order (after A1):
#     1. --docs-dir <path>      (A1 explicit; routes only DOCS_DIR_ROOT)
#     2. --repo <path>          (A1 explicit; routes BOTH repo + docs-dir if
#                                --docs-dir not given)
#     3. $CLAUDE_DOCS_DIR       (env override)
#     4. $CLAUDE_PROJECT_DIR    (back-compat env)
#     5. cwd's git toplevel
#     6. pwd
#     7. /root                  (legacy harness-root safety net)
#
# Pre-scan ONLY for --repo / --docs-dir / --plan up front so DOCS_DIR_ROOT can be
# resolved before any artifact lookup. Other flags (-m, --manifest, --force,
# --auto-bulk-bridge) are handled by the existing pre-scan loop later. We do NOT
# remove these flags from $@ here — that responsibility belongs to the second
# pre-scan + dispatch.
EXPLICIT_REPO=""
EXPLICIT_DOCS_DIR=""
PLAN_MODE=0
_repo_scan_i=0
_repo_scan_args=("$@")
while [ $_repo_scan_i -lt ${#_repo_scan_args[@]} ]; do
  _scan_a="${_repo_scan_args[$_repo_scan_i]}"
  case "$_scan_a" in
    --repo)
      _repo_scan_i=$((_repo_scan_i + 1))
      if [ $_repo_scan_i -ge ${#_repo_scan_args[@]} ]; then
        echo "commit.sh: --repo requires a path argument" >&2
        exit 2
      fi
      EXPLICIT_REPO="${_repo_scan_args[$_repo_scan_i]}"
      ;;
    --docs-dir)
      _repo_scan_i=$((_repo_scan_i + 1))
      if [ $_repo_scan_i -ge ${#_repo_scan_args[@]} ]; then
        echo "commit.sh: --docs-dir requires a path argument" >&2
        exit 2
      fi
      EXPLICIT_DOCS_DIR="${_repo_scan_args[$_repo_scan_i]}"
      ;;
    --plan)
      PLAN_MODE=1
      ;;
  esac
  _repo_scan_i=$((_repo_scan_i + 1))
done

DOCS_DIR_ROOT=""
if [ -n "$EXPLICIT_DOCS_DIR" ]; then
  if [ ! -d "$EXPLICIT_DOCS_DIR/docs/dev" ] && [ ! -d "$EXPLICIT_DOCS_DIR" ]; then
    echo "commit.sh: --docs-dir path does not exist: $EXPLICIT_DOCS_DIR" >&2
    exit 2
  fi
  DOCS_DIR_ROOT="$EXPLICIT_DOCS_DIR"
elif [ -n "$EXPLICIT_REPO" ]; then
  if [ ! -d "$EXPLICIT_REPO" ]; then
    echo "commit.sh: --repo path does not exist: $EXPLICIT_REPO" >&2
    exit 2
  fi
  # --repo sets both: docs-dir defaults to <repo>/docs/dev parent for lookup.
  DOCS_DIR_ROOT="$EXPLICIT_REPO"
else
  for _cand in "${CLAUDE_DOCS_DIR:-}" "${CLAUDE_PROJECT_DIR:-}" "$(git rev-parse --show-toplevel 2>/dev/null || true)" "$(pwd)" "/root"; do
    [ -z "$_cand" ] && continue
    if [ -d "${_cand}/docs/dev" ]; then
      DOCS_DIR_ROOT="$_cand"
      break
    fi
  done
fi
# Last-resort fallback: keep redev7 P-CWD-FALLBACK behavior so dev-report
# lookup at least produces a useful error path.
if [ -z "$DOCS_DIR_ROOT" ]; then
  DOCS_DIR_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
fi
DOCS_DIR="${DOCS_DIR_ROOT}/docs/dev"
# Log and runtime helper paths are intentionally user-home-anchored: audit
# artifacts live with Claude infrastructure, not the target project. Do NOT
# derive them from CLAUDE_PROJECT_DIR — that would mix project repos and global
# toolchain state (AC-DOCS-4). Operators may override these paths for tests.
CLAUDE_HOME="${CLAUDE_HOME:-${HOME}/.claude}"
CLAUDE_LOG_DIR="${CLAUDE_LOG_DIR:-${CLAUDE_HOME}/logs}"
CLAUDE_TMPDIR="${CLAUDE_TMPDIR:-${TMPDIR:-/tmp}}"
PYTHON_BIN="${CLAUDE_PYTHON_BIN:-${CLAUDE_HOME}/venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="${CLAUDE_PYTHON_FALLBACK:-python}"
fi
CLOSE_VERDICT_HELPER="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)/lib/close-verdict.py"
LOG_PATH="${CLAUDE_GIT_PRIVILEGE_LOG:-${CLAUDE_LOG_DIR}/git-privilege-grants.log}"
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
#   commit.sh <task-id> [-m "<msg>"]      — closed-task semantic commit (PRIMARY/SECONDARY)
#                                             -m optional; omitted messages are derived from artifacts.
#   commit.sh --auto-bulk-bridge <branch>   — overnight per-cycle commit (P3 bridge mode)
#                                             -m FORBIDDEN (BLESSED_BRIDGE_RE locks message)
#   commit.sh --force -m "<msg>"          — irregular-path escape hatch (redev6 P-FORCE)
#                                             -m REQUIRED non-empty; bypasses closure /
#                                             task-id / dev-report / cross-repo / P-CLOSEHONOR
#                                             / H1 checks. The four always-on security layers
#                                             (disable-model-invocation on commit.md,
#                                             inline-env literal-substring rejection,
#                                             bulk-commit-detector, grant emission)
#                                             remain engaged.
#
# --force and --auto-bulk-bridge are mutually exclusive; passing both -> exit 2.
#
# Bridge mode (AC-P3-2):
#   Used by /dev-overnight per-cycle finalization. Stages from the already-cached
#   set (caller pre-stages with `git add`), emits commit message
#   `auto-bulk: end-of-cycle commit for <branch>` (matches BLESSED_BRIDGE_RE in
#   pretool-git-privilege-guard.py:92), AND writes a grant file so the guard
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
  echo "  commit.sh <task-id> [-m \"<msg>\"]            # closed-task semantic commit" >&2
  echo "  commit.sh --auto-bulk-bridge <branch>      # overnight per-cycle commit (-m forbidden)" >&2
  echo "  commit.sh --force -m \"<msg>\"                # irregular-path escape hatch" >&2
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
MANIFEST_PATH=""
HAS_MANIFEST=0
# A2: --force-rescue is a deliberate alias for --force that signals the operator
# pre-staged content via `git add` and grants stage-then-force semantics. When 1,
# the force-mode short-circuit reads the staged delta as the patch source.
FORCE_RESCUE_MODE=0

# Pre-scan: extract `-m "<msg>"` (or `--message "<msg>"`) and `--manifest <path>`
# from anywhere in argv (M-MSG-5 / AC-MSG-6 — orchestrator may pass these flags
# before or after the mode flag). The remaining (non-flag-pair) tokens are
# repacked into the positional argv for the first-pass dispatch + second-pass
# leftover loop.
#
# --manifest semantics (BA ticket 20260510-191533 M1/M11/M12):
#   * OPTIONAL precision input on top of closed-task and --force modes.
#   * Mutually exclusive with --auto-bulk-bridge (enforced after pre-scan).
#   * Gated by CLAUDE_COMMIT_MANIFEST_DISABLED=1 operator env (fail-closed here).
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
  elif [ "$PRESCAN_ARG" = "--manifest" ]; then
    PRESCAN_I=$((PRESCAN_I + 1))
    if [ $PRESCAN_I -gt $# ]; then
      echo "commit.sh: --manifest requires a JSON path argument" >&2
      exit 2
    fi
    if [ "$HAS_MANIFEST" -eq 1 ]; then
      echo "commit.sh: --manifest specified more than once" >&2
      exit 2
    fi
    MANIFEST_PATH="${!PRESCAN_I}"
    HAS_MANIFEST=1
  elif [ "$PRESCAN_ARG" = "--repo" ]; then
    # A1: consumed in early pre-scan above; skip value here.
    PRESCAN_I=$((PRESCAN_I + 1))
  elif [ "$PRESCAN_ARG" = "--docs-dir" ]; then
    # A1: consumed in early pre-scan above; skip value here.
    PRESCAN_I=$((PRESCAN_I + 1))
  elif [ "$PRESCAN_ARG" = "--plan" ]; then
    # A3: consumed in early pre-scan above; PLAN_MODE flag already set.
    :
  elif [ "$PRESCAN_ARG" = "--force-rescue" ]; then
    # A2: alias for --force that authorizes the stage-then-force plan source.
    # Set a sentinel; the dispatch below detects it and routes to the stage-then-force
    # path inside the force-mode short-circuit.
    FORCE_RESCUE_MODE=1
    PRESCAN_REMAINING+=("--force")
  else
    PRESCAN_REMAINING+=("$PRESCAN_ARG")
  fi
done
# Repack argv with -m / --message / --manifest stripped out.
set -- "${PRESCAN_REMAINING[@]+"${PRESCAN_REMAINING[@]}"}"

# Feature gate (M11): CLAUDE_COMMIT_MANIFEST_DISABLED=1 AND --manifest set →
# fail-closed at argv-parse with the exact documented error string.
if [ "${CLAUDE_COMMIT_MANIFEST_DISABLED:-0}" = "1" ] && [ "$HAS_MANIFEST" -eq 1 ]; then
  echo "commit.sh: manifest path disabled by operator (CLAUDE_COMMIT_MANIFEST_DISABLED=1)" >&2
  exit 2
fi

# After pre-scan, at least one positional must remain (the mode flag or task-id).
if [ $# -lt 1 ] || [ -z "${1:-}" ]; then
  echo "commit.sh: no mode argument (task-id, --auto-bulk-bridge <branch>, or --force)" >&2
  exit 2
fi

# First-pass dispatch: identify the mode based on the first positional arg.
if [ "$1" = "--auto-bulk-bridge" ]; then
  # M12: bridge mode's content authority is the pre-staged shared index; manifest
  # patch source would conflict. Reject combination at argv-parse with the
  # specific documented error.
  if [ "$HAS_MANIFEST" -eq 1 ]; then
    echo "commit.sh: --auto-bulk-bridge and --manifest are mutually exclusive" >&2
    exit 2
  fi
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
  # Explicit task-id echo (spec-20260503-091826.md M11 / AC-11.1) — surfaces
  # the resolved task-id at the top of the toolchain log so close.md / dev.md
  # / downstream agents can re-confirm chain integrity in one glance.
  #
  # Forward-reference artifact filename convention for THIS toolchain:
  #   ticket-<task-id>.md (legacy: ba-spec-<task-id>.md)
  # The closure / completion / qa-report / dev-report lookup helpers below
  # resolve by `${TASK_ID}` and do NOT depend on the BA-side artifact prefix;
  # historical citations of past specs by name (e.g., references to
  # ba-spec-20260426-redev5.md as the authority for a code block) remain
  # preserved literal — they are documentation of which past spec defined
  # the code, not active lookup templates.
  echo "TASK-ID: ${TASK_ID}"
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
      echo "  commit.sh <task-id> [-m \"<msg>\"]            # closed-task semantic commit" >&2
      echo "  commit.sh --auto-bulk-bridge <branch>      # overnight per-cycle commit (-m forbidden)" >&2
      echo "  commit.sh --force -m \"<msg>\"                # irregular-path escape hatch" >&2
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
      CALLER_MESSAGE="$(CLAUDE_PROJECT_DIR="$DOCS_DIR_ROOT" "$HELPER" "$TASK_ID")"
      if [ -n "$CALLER_MESSAGE" ]; then
        HAS_CALLER_MESSAGE=1
        MESSAGE_SOURCE="auto"
      fi
    fi
  else
    MESSAGE_SOURCE="caller"
  fi
  if [ "$HAS_CALLER_MESSAGE" -eq 0 ] || [ -z "$CALLER_MESSAGE" ]; then
    echo "commit message could not be auto-generated from task artifacts for $TASK_ID" >&2
    exit 2
  fi
fi

# S-FORCE-WARNING: emit a one-line stderr warning for --force mode so the
# operator is reminded that closure/task-id/dev-report layers are bypassed
# but the four always-on security layers remain engaged.
if [ "$MODE" = "force" ]; then
  echo "commit.sh: --force bypasses closure/task-id/dev-report checks; semantic planning still uses private-index/CAS audit" >&2
fi

# -----------------------------------------------------------------------------
# Semantic plan helpers
# -----------------------------------------------------------------------------
real_index_fingerprint() {
  local repo_root="$1"
  local index_path
  index_path="$(git -C "$repo_root" rev-parse --git-path index 2>/dev/null || true)"
  if [ -n "$index_path" ] && [ -f "$index_path" ]; then
    sha256sum "$index_path" | awk '{print $1}'
  else
    echo "__missing__"
  fi
}

staged_file_list() {
  git -C "$1" diff --cached --name-only | LC_ALL=C sort -u
}

sync_real_index_to_commit_paths() {
  local repo_root="$1"
  local commit_sha="$2"
  local tmp_dir="$3"
  shift 3
  local index_info="${tmp_dir}/real-index-info"
  local entry_file="${tmp_dir}/tree-entry"
  local removals=()
  : > "$index_info"
  local planned_path
  for planned_path in "$@"; do
    git -C "$repo_root" ls-tree -z "$commit_sha" -- "$planned_path" > "$entry_file"
    if [ -s "$entry_file" ]; then
      cat "$entry_file" >> "$index_info"
    else
      removals+=("$planned_path")
    fi
  done
  if [ -s "$index_info" ]; then
    git -C "$repo_root" update-index -z --index-info < "$index_info"
  fi
  if [ "${#removals[@]}" -gt 0 ]; then
    git -C "$repo_root" update-index --force-remove -- "${removals[@]}"
  fi
}

build_semantic_plan_bundle() {
  local task_id="$1"
  local mode="$2"
  local patch_path="$3"
  local meta_path="$4"

  # A1: pass EXPLICIT_REPO (when set) so the dev-report path's repo resolver
  # honors caller intent before falling through to artifact-derived discovery.
  CLAUDE_COMMIT_EXPLICIT_REPO="${EXPLICIT_REPO:-}" \
  "$PYTHON_BIN" - "$task_id" "$mode" "$DOCS_DIR_ROOT" "$DOCS_DIR" "$patch_path" "$meta_path" <<'PY'
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

task_id, mode, docs_root, docs_dir, patch_path, meta_path = sys.argv[1:7]
docs_root = os.path.abspath(docs_root)
docs_dir = os.path.abspath(docs_dir)

if mode == "force":
    # A2: plain --force is still refused via the dev-report path because no
    # task ownership can be inferred without artifacts. The error names the two
    # legitimate routes: --manifest <path> (precision input) OR --force-rescue
    # with pre-staged content via `git add` (stage-then-force semantics).
    print(
        "commit.sh: --force without --manifest or pre-staged content cannot infer task ownership; "
        "use --force --manifest <path> OR --force-rescue (after `git add <files>`)",
        file=sys.stderr,
    )
    sys.exit(2)

def run_git(cwd, args, check=True):
    proc = subprocess.run(
        ["git", "-C", cwd, *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git command failed")
    return proc

def git_root_for_existing(path):
    cur = Path(path)
    if not cur.is_absolute():
        cur = Path(docs_root) / cur
    cur = Path(os.path.realpath(str(cur)))
    if cur.exists() and cur.is_file():
        cur = cur.parent
    if not cur.exists():
        for parent in [cur.parent, *cur.parents]:
            if parent.exists():
                cur = parent
                break
    proc = subprocess.run(
        ["git", "-C", str(cur), "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        return ""
    return os.path.realpath(proc.stdout.strip())

def under(path, root):
    try:
        Path(os.path.realpath(path)).relative_to(Path(os.path.realpath(root)))
        return True
    except ValueError:
        return False

def rel_to_repo(path, repo_root):
    p = Path(path)
    if not p.is_absolute():
        candidates = [Path(repo_root) / p, Path(docs_root) / p]
    else:
        candidates = [p]
    repo_real = Path(os.path.realpath(repo_root))
    for candidate in candidates:
        real = Path(os.path.realpath(str(candidate)))
        try:
            return str(real.relative_to(repo_real))
        except ValueError:
            continue
    return ""

artifact_names = [
    f"close-report-{task_id}.md",
    f"dev-report-{task_id}.json",
    f"qa-report-{task_id}.json",
    f"completion-{task_id}.md",
    f"context-{task_id}.json",
    f"ticket-{task_id}.md",
    f"ba-spec-{task_id}.md",
    f"ba-qa-report-{task_id}.json",
]
artifacts = [os.path.join(docs_dir, name) for name in artifact_names if os.path.exists(os.path.join(docs_dir, name))]

path_values = set()

def maybe_add_path(value):
    if not isinstance(value, str):
        return
    if value.startswith(("http://", "https://")):
        return
    # NOTE: do NOT include '.' in the strip set. str.strip(chars) treats chars
    # as a character class and reads from BOTH ends; including '.' eats the
    # leading dot of dotfile paths (.claude/, .github/, .gitignore, ...),
    # causing path_in_planned mismatch and silent fall-through to "unrelated"
    # at the ownership classifier. Bug surfaced cycle 20260511-100000 when 6
    # Worker-1 .claude/commands/* files were silently dropped from commit
    # a46dc0ec despite being declared in dev-report.dev.files_modified.
    cleaned = value.strip().strip("`'\",;)")
    if not cleaned:
        return
    if cleaned.startswith("/") or "/" in cleaned or re.match(r"^[A-Za-z0-9._-]+$", cleaned):
        path_values.add(cleaned)

unresolved_authoritative = []

def add_authoritative_paths(values):
    if not isinstance(values, list):
        return
    for item in values:
        if isinstance(item, str):
            maybe_add_path(item)

dev_report_path = os.path.join(docs_dir, f"dev-report-{task_id}.json")
if os.path.exists(dev_report_path):
    try:
        dev_report = json.load(open(dev_report_path, encoding="utf-8"))
    except Exception:
        dev_report = {}
    dev_block = dev_report.get("dev", {}) if isinstance(dev_report, dict) else {}
    if isinstance(dev_block, dict):
        add_authoritative_paths(dev_block.get("files_modified"))
        add_authoritative_paths(dev_block.get("files_created"))
        for task in dev_block.get("tasks_completed", []) or []:
            if isinstance(task, dict):
                add_authoritative_paths(task.get("files_modified"))
                add_authoritative_paths(task.get("files_created"))
        for script in dev_block.get("scripts_created", []) or []:
            if isinstance(script, dict):
                maybe_add_path(script.get("path"))

non_doc_repos = set()
for value in path_values:
    abs_value = value if os.path.isabs(value) else os.path.join(docs_root, value)
    if under(abs_value, docs_dir):
        continue
    root = git_root_for_existing(abs_value)
    if root:
        non_doc_repos.add(root)

if len(non_doc_repos) > 1:
    print("commit.sh: task artifacts reference more than one target repository; refusing ambiguous ownership", file=sys.stderr)
    for root in sorted(non_doc_repos):
        print(f"  repo: {root}", file=sys.stderr)
    sys.exit(2)

explicit_repo = os.environ.get("CLAUDE_COMMIT_EXPLICIT_REPO", "").strip()
if explicit_repo:
    # A1: caller named the target repo with --repo; resolve to its git toplevel
    # and short-circuit the discovery ladder so ambiguous artifacts don't drag
    # the resolution elsewhere.
    explicit_root = git_root_for_existing(explicit_repo) or os.path.realpath(explicit_repo)
    repo_root = explicit_root
elif non_doc_repos:
    repo_root = sorted(non_doc_repos)[0]
else:
    current_root = git_root_for_existing(os.getcwd())
    docs_repo = git_root_for_existing(docs_root)
    repo_root = current_root or docs_repo
if not repo_root:
    print("commit.sh: cannot resolve target repository for semantic plan", file=sys.stderr)
    sys.exit(2)

try:
    base_commit = run_git(repo_root, ["rev-parse", "HEAD"]).stdout.strip()
except Exception:
    print("commit.sh: semantic plan requires a repository with HEAD", file=sys.stderr)
    sys.exit(2)

planned = {}
for value in sorted(path_values):
    rel = rel_to_repo(value, repo_root)
    if rel and rel != ".":
        planned.setdefault(rel, "dev report declares this implementation path")
    else:
        unresolved_authoritative.append(value)
for artifact in artifacts:
    rel = rel_to_repo(artifact, repo_root)
    if rel and rel != ".":
        planned.setdefault(rel, "same-task cycle artifact")

def lines_from_git(args):
    proc = run_git(repo_root, args)
    return {line for line in proc.stdout.splitlines() if line}

dirty = set()
dirty |= lines_from_git(["diff", "--name-only", "HEAD", "--"])
dirty |= lines_from_git(["ls-files", "--others", "--exclude-standard"])
staged = lines_from_git(["diff", "--cached", "--name-only"])
unstaged = lines_from_git(["diff", "--name-only"])

def is_generated(path):
    base = os.path.basename(path)
    return (
        "__pycache__/" in path
        or base.endswith((".pyc", ".pyo", ".tmp", ".temp", ".bak", ".swp", "~"))
        or path.endswith(".log")
    )

task_doc_re = re.compile(r"^docs/dev/(?:[^/]*-)?([0-9]{8}-[0-9]{6}[^/]*)")

def is_other_session(path):
    if not path.startswith("docs/dev/"):
        return False
    base = os.path.basename(path)
    return bool(re.search(r"[0-9]{8}-[0-9]{6}", base)) and task_id not in base

included = []
excluded = []
blocking = []
for value in sorted(unresolved_authoritative):
    record = {
        "path": value,
        "category": "ambiguous_overlap",
        "reason": "dev report path could not be mapped inside the target repository",
    }
    excluded.append(record)
    blocking.append(record)
for path in sorted(dirty):
    if path in planned and path in staged:
        record = {
            "path": path,
            "category": "ambiguous_overlap",
            "reason": "planned path already has shared-index content; refusing to mix ownership",
        }
        excluded.append(record)
        blocking.append(record)
    elif path in planned or (path.startswith("docs/dev/") and task_id in os.path.basename(path)):
        included.append({
            "path": path,
            "category": "task_owned",
            "reason": planned.get(path, "same-task artifact name"),
        })
    elif is_generated(path):
        excluded.append({"path": path, "category": "garbage/generated", "reason": "generated or scratch file"})
    elif is_other_session(path):
        excluded.append({"path": path, "category": "other_session", "reason": "belongs to another task-id"})
    else:
        excluded.append({"path": path, "category": "unrelated", "reason": "not declared by same-task dev report"})

if blocking:
    print("commit.sh: ambiguous task ownership; refusing semantic commit", file=sys.stderr)
    for item in blocking:
        print(f"  {item['path']}: {item['reason']}", file=sys.stderr)
    sys.exit(2)

if not included:
    print(f"commit.sh: no task-owned dirty changes found for {task_id}; unrelated work was preserved", file=sys.stderr)
    if excluded:
        for item in excluded[:20]:
            print(f"  excluded {item['category']}: {item['path']} — {item['reason']}", file=sys.stderr)
    sys.exit(2)

patch_chunks = []
tracked = lines_from_git(["ls-files"])
for item in included:
    path = item["path"]
    if path in tracked:
        proc = run_git(repo_root, ["diff", "--binary", "HEAD", "--", path])
    else:
        proc = subprocess.run(
            ["git", "-C", repo_root, "diff", "--binary", "--no-index", "--", "/dev/null", path],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.returncode not in (0, 1):
            print(proc.stderr.strip() or f"commit.sh: failed to diff new file {path}", file=sys.stderr)
            sys.exit(2)
    if proc.stdout.strip():
        patch_chunks.append(proc.stdout if proc.stdout.endswith("\n") else proc.stdout + "\n")

patch_text = "".join(patch_chunks)
if not patch_text.strip():
    print("commit.sh: semantic plan produced no patch content", file=sys.stderr)
    sys.exit(2)
if re.search(r"(?m)^GIT binary patch$", patch_text):
    print("commit.sh: binary patches are not supported by the semantic plan path", file=sys.stderr)
    sys.exit(2)

with open(patch_path, "w", encoding="utf-8") as fh:
    fh.write(patch_text)

plan_seed = json.dumps(
    {"task_id": task_id, "repo_root": repo_root, "base_commit": base_commit, "included": included, "excluded": excluded},
    sort_keys=True,
).encode("utf-8") + patch_text.encode("utf-8")
meta = {
    "engine": "semantic-commit",
    "plan_id": hashlib.sha256(plan_seed).hexdigest()[:16],
    "plan_sha256": hashlib.sha256(plan_seed).hexdigest(),
    "task_id": task_id,
    "repo_root": repo_root,
    "base_commit": base_commit,
    "patch_count": len(patch_chunks),
    "semantic_files": included,
    "excluded_dirty": excluded,
    "artifact_paths": artifacts,
    "dirty_candidates": sorted(dirty),
    "staged_candidates": sorted(staged),
    "unstaged_candidates": sorted(unstaged),
}
with open(meta_path, "w", encoding="utf-8") as fh:
    json.dump(meta, fh, indent=2, sort_keys=True)
PY
}

# -----------------------------------------------------------------------------
# A2 — force-rescue source-acquisition helper
# -----------------------------------------------------------------------------
# Produces (patch_file, meta_file) for the stage-then-force mode. The operator
# pre-stages content via `git add`; the wrapper reads the staged delta and uses
# it as the patch source. No manifest is required, no closure / task-id /
# dev-report binding is enforced. All post-apply safety remains engaged
# (real_index_fingerprint, staged_files_before/after, backup ref, expected-parent
# CAS, plus the four always-on layers).
#
# Refuse when nothing is staged: force-rescue's source authority is the staged
# set, so an empty stage is a usage error (the operator forgot `git add`).
build_force_rescue_plan_bundle() {
  local patch_path="$1"
  local meta_path="$2"

  local force_repo_root=""
  for _cand_dir in "${EXPLICIT_REPO:-}" "${CLAUDE_DOCS_DIR:-}" "${CLAUDE_PROJECT_DIR:-}" "$(git rev-parse --show-toplevel 2>/dev/null || true)" "$(pwd)" "/root"; do
    [ -z "$_cand_dir" ] && continue
    force_repo_root="$(git -C "$_cand_dir" rev-parse --show-toplevel 2>/dev/null || true)"
    [ -n "$force_repo_root" ] && break
  done
  if [ -z "$force_repo_root" ]; then
    echo "commit.sh: cannot resolve target repo for force-rescue plan" >&2
    return 2
  fi

  local staged_list
  staged_list="$(git -C "$force_repo_root" diff --cached --name-only | sort -u)"
  if [ -z "$staged_list" ]; then
    echo "commit.sh: force-rescue requires pre-staged content via 'git add'" >&2
    echo "  staged set is empty in repo: ${force_repo_root}" >&2
    return 2
  fi

  # Patch source: stage diff against HEAD. --binary so binary changes survive
  # round-trip through `git apply --cached --3way`. If HEAD is missing (root
  # commit), bail with a clear message — root-commit support is out of scope.
  local force_head
  force_head="$(git -C "$force_repo_root" rev-parse HEAD 2>/dev/null || true)"
  if [ -z "$force_head" ]; then
    echo "commit.sh: force-rescue requires a repository with HEAD" >&2
    return 2
  fi
  git -C "$force_repo_root" diff --cached --binary HEAD -- > "$patch_path" || {
    echo "commit.sh: force-rescue could not capture staged diff" >&2
    return 2
  }
  if [ ! -s "$patch_path" ]; then
    echo "commit.sh: force-rescue produced empty patch (staged set may equal HEAD content)" >&2
    return 2
  fi

  # Build meta file with the same shape as build_semantic_plan_bundle.
  CLAUDE_FORCE_RESCUE_REPO="$force_repo_root" \
  CLAUDE_FORCE_RESCUE_PATCH="$patch_path" \
  "$PYTHON_BIN" - "$meta_path" <<'PY'
import hashlib, json, os, subprocess, sys
meta_path = sys.argv[1]
repo_root = os.environ["CLAUDE_FORCE_RESCUE_REPO"]
patch_path = os.environ["CLAUDE_FORCE_RESCUE_PATCH"]
with open(patch_path, "rb") as fh:
    patch_bytes = fh.read()
staged = subprocess.run(
    ["git", "-C", repo_root, "diff", "--cached", "--name-only"],
    text=True, stdout=subprocess.PIPE,
).stdout.splitlines()
staged = sorted({l for l in staged if l})
base_commit = subprocess.run(
    ["git", "-C", repo_root, "rev-parse", "HEAD"],
    text=True, stdout=subprocess.PIPE,
).stdout.strip()
plan_seed = json.dumps(
    {"engine": "force-rescue-commit", "repo_root": repo_root, "base_commit": base_commit, "staged": staged},
    sort_keys=True,
).encode("utf-8") + patch_bytes
included = [{"path": p, "category": "force_rescue_staged",
             "reason": "operator-staged path via 'git add' under --force-rescue"} for p in staged]
meta = {
    "engine": "force-rescue-commit",
    "plan_id": hashlib.sha256(plan_seed).hexdigest()[:16],
    "plan_sha256": hashlib.sha256(plan_seed).hexdigest(),
    "task_id": "",
    "repo_root": repo_root,
    "base_commit": base_commit,
    "patch_count": 1,
    "semantic_files": included,
    "excluded_dirty": [],
    "artifact_paths": [],
    "dirty_candidates": [],
    "staged_candidates": staged,
    "unstaged_candidates": [],
}
with open(meta_path, "w") as fh:
    json.dump(meta, fh, indent=2, sort_keys=True)
PY
}

run_backup_only_push() {
  # D2 (backup-push observability): emits the backup ref to a sentinel file
  # (path passed as $4) instead of stdout-via-command-substitution. This lets
  # the function MUTATE caller-scope state (BACKUP_PUSH_FAILED) without losing
  # those mutations to a subshell. The caller reads $4 to get the backup ref.
  local repo_root="$1"
  local branch="$2"
  local commit_sha="$3"
  local backup_ref_out="$4"
  local short_sha="${commit_sha:0:12}"
  local backup_ref="refs/backups/claude/${branch}/${short_sha}"
  local backup_log="${CLAUDE_BACKUP_LOG:-${CLAUDE_LOG_DIR}/post-commit-auto-push.log}"
  local remote="${CLAUDE_BACKUP_REMOTE:-origin}"

  if ! git -C "$repo_root" check-ref-format "$backup_ref" >/dev/null 2>&1; then
    backup_ref="refs/backups/claude/detached/${short_sha}"
  fi
  mkdir -p "$(dirname "$backup_log")"
  git -C "$repo_root" update-ref "$backup_ref" "$commit_sha" 2>>"$backup_log" || true

  # New behaviour:
  #   * Always emit one stderr line on failure (regardless of env)
  #   * When CLAUDE_BACKUP_REMOTE_REQUIRED=1, run the push SYNCHRONOUSLY and
  #     set BACKUP_PUSH_FAILED=1 so the caller can elevate exit to 2.
  #   * When CLAUDE_BACKUP_REMOTE_REQUIRED=1 AND the remote is missing,
  #     emit stderr + set BACKUP_PUSH_FAILED=1 (required-remote semantics).
  #   * Default (env unset) keeps async background push so commit latency is
  #     unaffected; the async failure path emits one stderr line.
  BACKUP_PUSH_FAILED=0
  if git -C "$repo_root" remote get-url "$remote" >/dev/null 2>&1; then
    if [ "${CLAUDE_BACKUP_REMOTE_REQUIRED:-0}" = "1" ]; then
      if ! git -C "$repo_root" push "$remote" "${commit_sha}:${backup_ref}" >>"$backup_log" 2>&1; then
        printf '%s backup push failed remote=%s ref=%s sha=%s\n' \
          "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$remote" "$backup_ref" "$commit_sha" >>"$backup_log"
        echo "commit.sh: backup push failed: remote=${remote} ref=${backup_ref} sha=${commit_sha} (logged to ${backup_log})" >&2
        BACKUP_PUSH_FAILED=1
      fi
    else
      (
        if ! git -C "$repo_root" push "$remote" "${commit_sha}:${backup_ref}" >>"$backup_log" 2>&1; then
          printf '%s backup push failed remote=%s ref=%s sha=%s\n' \
            "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$remote" "$backup_ref" "$commit_sha" >>"$backup_log"
          echo "commit.sh: backup push failed: remote=${remote} ref=${backup_ref} sha=${commit_sha} (logged to ${backup_log})" >&2
        fi
      ) &
    fi
  else
    printf '%s backup push skipped remote=%s ref=%s sha=%s reason=remote-missing\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$remote" "$backup_ref" "$commit_sha" >>"$backup_log"
    if [ "${CLAUDE_BACKUP_REMOTE_REQUIRED:-0}" = "1" ]; then
      echo "commit.sh: backup push skipped: remote=${remote} unreachable (no remote URL configured)" >&2
      BACKUP_PUSH_FAILED=1
    fi
  fi

  printf '%s\n' "$backup_ref" > "$backup_ref_out"
}

# -----------------------------------------------------------------------------
# Manifest source-acquisition helper (BA ticket 20260510-191533, M8)
# -----------------------------------------------------------------------------
# Reads a manifest JSON, hardens its contents, and produces (patch_file, meta_file)
# in the same shape consumed by run_private_index_commit. The shared core then
# applies all 10 M5 invariants against the produced patch independently of source.
#
# Schema contract (M2): the literal string version-acceptance contract from the
# pre-fe9c0f2 backup (`if str(version).lower() not in {'3','v3','commit-intent-v3'}`)
# is REPLACED with a named-integer protocol:
#   * REQUIRE schema_name == "commit-manifest"
#   * REQUIRE integer schema_version == 3 (NOT string "3" / "v3")
#   * ACCEPT optional integer schema_minor
# String aliases are rejected with an error naming the offending field.
#
# Hardening (M8):
#   * path-hygiene on every entry in manifest.files and every header path in
#     the inline unified-diff text (no absolute paths, no `..`, no `.git/`,
#     no NUL, no empty-after-strip).
#   * semantic_files normalization: must be list of {path,reason} dicts; bare
#     strings rejected (the legacy backup tolerated bare strings).
#   * anchored binary rejection — `^GIT binary patch$` multiline match.
#   * base_commit binding: when present, must equal expected_parent passed in
#     by the wrapper.
#   * repo_root rejection: recorded for audit but never consulted for repo
#     redirection (path B: per-session worktree is the spatial boundary).
#   * task_id binding rules are enforced by run_private_index_commit after
#     this helper returns (it sees the wrapper's task-id binding state).
#
# Audit emission (M3): meta carries schema_name, schema_version, schema_minor,
# engine="manifest-commit"; the legacy magic-string version surface is replaced.
build_manifest_plan_bundle() {
  local manifest_path="$1"
  local mode="$2"
  local expected_parent="$3"
  local patch_path="$4"
  local meta_path="$5"

  "$PYTHON_BIN" - "$manifest_path" "$mode" "$expected_parent" "$patch_path" "$meta_path" <<'PY'
import hashlib
import json
import os
import re
import sys

manifest_path, mode, expected_parent, patch_path, meta_path = sys.argv[1:6]

try:
    raw = open(manifest_path, "rb").read()
except FileNotFoundError:
    print(f"commit.sh: manifest not found: {manifest_path}", file=sys.stderr)
    sys.exit(2)
except Exception as exc:
    print(f"commit.sh: cannot read manifest: {exc}", file=sys.stderr)
    sys.exit(2)

try:
    data = json.loads(raw.decode("utf-8"))
except Exception as exc:
    print(f"commit.sh: manifest JSON parse error: {exc}", file=sys.stderr)
    sys.exit(2)

if not isinstance(data, dict):
    print("commit.sh: manifest must be a JSON object", file=sys.stderr)
    sys.exit(2)

# Schema-version validator (M2): named-integer only; reject string aliases.
schema_name = data.get("schema_name")
schema_version = data.get("schema_version")
schema_minor = data.get("schema_minor")
# Legacy-field migration detection (AC1): if the manifest uses the pre-fe9c0f2
# `version` field (which accepted string aliases like "v3" / "commit-intent-v3"),
# emit a migration error that explicitly names BOTH `schema_name` and
# `schema_version` and the rejected legacy field, so the AC1 stderr contract
# is satisfied with one diagnostic instead of the generic missing-schema_name
# error.
legacy_version = data.get("version")
if legacy_version is not None and "schema_name" not in data and "schema_version" not in data:
    print(
        "commit.sh: manifest.version is a legacy field; use schema_name=\"commit-manifest\" "
        f"+ integer schema_version=3 instead (got version={legacy_version!r})",
        file=sys.stderr,
    )
    sys.exit(2)
if schema_name != "commit-manifest":
    print(
        "commit.sh: manifest.schema_name must equal \"commit-manifest\" "
        f"(got {schema_name!r})",
        file=sys.stderr,
    )
    sys.exit(2)
# Integer-only acceptance: bool is subclass of int in Python; explicitly reject bools.
if not isinstance(schema_version, int) or isinstance(schema_version, bool):
    print(
        "commit.sh: manifest.schema_version must be an integer (string aliases like "
        f"\"v3\" / \"commit-intent-v3\" are rejected; got {type(schema_version).__name__})",
        file=sys.stderr,
    )
    sys.exit(2)

# B2 (incompatible_after) — OPTIONAL future-major schema negotiation. When
# present, MUST be a non-negative integer; if schema_version > incompatible_after
# the wrapper refuses, signalling that a NEWER manifest format exists which this
# wrapper version cannot apply. Absent → no check (default behaviour unchanged).
# This check is ordered BEFORE the `schema_version != 3` check so that a
# manifest with schema_version=4 + incompatible_after=3 emits the named
# future-major error (rather than the generic "must equal 3" error).
incompatible_after = data.get("incompatible_after")
if incompatible_after is not None:
    if not isinstance(incompatible_after, int) or isinstance(incompatible_after, bool) or incompatible_after < 0:
        print(
            "commit.sh: manifest.incompatible_after must be a non-negative integer when "
            f"present (got {incompatible_after!r})",
            file=sys.stderr,
        )
        sys.exit(2)
    if schema_version > incompatible_after:
        print(
            f"commit.sh: manifest.schema_version={schema_version} exceeds "
            f"incompatible_after={incompatible_after}; this wrapper cannot apply",
            file=sys.stderr,
        )
        sys.exit(2)

if schema_version != 3:
    print(
        "commit.sh: manifest.schema_version must equal integer 3 in this slice "
        f"(got {schema_version!r})",
        file=sys.stderr,
    )
    sys.exit(2)
if schema_minor is not None and (
    not isinstance(schema_minor, int) or isinstance(schema_minor, bool)
):
    print(
        "commit.sh: manifest.schema_minor must be an integer when present "
        f"(got {type(schema_minor).__name__})",
        file=sys.stderr,
    )
    sys.exit(2)

# Path-hygiene helper (M8).
def reject_path(value, field):
    if not isinstance(value, str):
        print(
            f"commit.sh: manifest.{field} path entries must be strings (got "
            f"{type(value).__name__})",
            file=sys.stderr,
        )
        sys.exit(2)
    if "\x00" in value:
        print(f"commit.sh: manifest.{field} contains NUL byte; rejected", file=sys.stderr)
        sys.exit(2)
    stripped = value.strip()
    if not stripped:
        print(f"commit.sh: manifest.{field} contains empty-after-strip entry; rejected", file=sys.stderr)
        sys.exit(2)
    if stripped.startswith("/"):
        print(
            f"commit.sh: manifest.{field} contains absolute path {stripped!r}; rejected",
            file=sys.stderr,
        )
        sys.exit(2)
    # Reject any `..` path segment anywhere.
    parts = stripped.replace("\\", "/").split("/")
    if any(part == ".." for part in parts):
        print(
            f"commit.sh: manifest.{field} contains `..` segment in {stripped!r}; rejected",
            file=sys.stderr,
        )
        sys.exit(2)
    if stripped.startswith(".git/") or stripped == ".git" or "/.git/" in stripped:
        print(
            f"commit.sh: manifest.{field} touches .git/ path {stripped!r}; rejected",
            file=sys.stderr,
        )
        sys.exit(2)
    return stripped

# files: rationale-only declaration list (M6).
declared_files_raw = data.get("files", [])
if not isinstance(declared_files_raw, list):
    print("commit.sh: manifest.files must be a list", file=sys.stderr)
    sys.exit(2)
declared_files = [reject_path(entry, "files") for entry in declared_files_raw]

# semantic_files: dict-only shape (M8 normalization; legacy backup allowed
# bare strings — explicitly rejected here per BA ticket M8).
semantic_files_raw = data.get("semantic_files", [])
if not isinstance(semantic_files_raw, list):
    print("commit.sh: manifest.semantic_files must be a list", file=sys.stderr)
    sys.exit(2)
semantic_files = []
for idx, entry in enumerate(semantic_files_raw):
    if not isinstance(entry, dict):
        print(
            f"commit.sh: manifest.semantic_files[{idx}] must be an object with "
            "{path, reason}; bare string entries rejected",
            file=sys.stderr,
        )
        sys.exit(2)
    sf_path = entry.get("path")
    sf_reason = entry.get("reason")
    sf_path = reject_path(sf_path, f"semantic_files[{idx}].path")
    if not isinstance(sf_reason, str) or not sf_reason.strip():
        print(
            f"commit.sh: manifest.semantic_files[{idx}].reason must be a non-empty string",
            file=sys.stderr,
        )
        sys.exit(2)
    semantic_files.append({"path": sf_path, "reason": sf_reason})

# Patch text acquisition: inline only (no external patch path).
patch_text = data.get("patch")
if not isinstance(patch_text, str) or not patch_text.strip():
    print(
        "commit.sh: manifest.patch must be a non-empty inline unified-diff string",
        file=sys.stderr,
    )
    sys.exit(2)

# Anchored binary rejection (M8) — codex-finding simplification of substring
# scan to anchored line match, reducing false positives on text files that
# contain the phrase in prose.
if re.search(r"(?m)^GIT binary patch$", patch_text):
    print(
        "commit.sh: binary patches are not supported by the manifest path",
        file=sys.stderr,
    )
    sys.exit(2)

# Path-hygiene the header paths inside the unified-diff (M8 + B3 hygiene
# tightening). This scans the patch text for any line that LOOKS like a diff
# header (diff --git, ---, +++) and enforces the canonical `a/<path>`/`b/<path>`
# prefix form. Other shapes are handled as follows:
#   * Quoted-with-spaces form (`"a/path with spaces"`): ACCEPT after un-quoting
#     (git emits these for paths with spaces); the un-quoted path then runs
#     through reject_path for the usual hygiene rules.
#   * Bare-path form (no `a/`/`b/` prefix): REJECT with specific error.
#   * Absolute-path form (e.g. `/etc/passwd`): REJECT with specific error
#     (also caught by reject_path for the canonical form).
#   * `..`-segment form (e.g. `a/../etc/foo`): REJECT (also caught by
#     reject_path).
# The canonical regex below matches only the well-formed `a/<path>`/`b/<path>`
# shape. A second pass enumerates ALL header-shaped lines and rejects anything
# the canonical regex did NOT match (catching bare/absolute/`..`/garbage).
# /dev/null is a legitimate header for new/deleted files; the canonical regex
# requires a/ or b/ prefix so /dev/null never appears as a captured group.

def _git_quoted_unquote(s):
    # Git wraps paths containing special chars in C-style quotes (see
    # quote.c::quote_c_style_counted). Recognise the leading and trailing `"`
    # then decode backslash escapes: \a \b \t \n \v \f \r \\ \" and octal \NNN.
    if not (s.startswith('"') and s.endswith('"') and len(s) >= 2):
        return None
    body = s[1:-1]
    out = []
    i = 0
    while i < len(body):
        c = body[i]
        if c == "\\":
            i += 1
            if i >= len(body):
                return None
            nxt = body[i]
            esc = {"a": "\a", "b": "\b", "t": "\t", "n": "\n", "v": "\v",
                   "f": "\f", "r": "\r", "\\": "\\", '"': '"'}
            if nxt in esc:
                out.append(esc[nxt])
                i += 1
            elif nxt.isdigit() and i + 2 < len(body) and body[i + 1].isdigit() and body[i + 2].isdigit():
                out.append(chr(int(body[i:i + 3], 8)))
                i += 3
            else:
                return None
        else:
            out.append(c)
            i += 1
    return "".join(out)

canonical_header_re = re.compile(
    r"^(?:diff --git a/(\S+) b/(\S+)|--- a/(\S+)|\+\+\+ b/(\S+))$",
    re.MULTILINE,
)
# Also accept the git-quoted shape for paths with spaces: `diff --git "a/<p>" "b/<p>"`
# and `--- "a/<p>"`/`+++ "b/<p>"`. The captured groups are the FULL quoted token
# including the `a/`/`b/` prefix and the surrounding quotes; we strip both layers.
quoted_header_re = re.compile(
    r'^(?:diff --git ("a/[^"]*") ("b/[^"]*")|--- ("a/[^"]*")|\+\+\+ ("b/[^"]*"))$',
    re.MULTILINE,
)
# Path-hygiene check the canonical and quoted header captures up front. The
# line-by-line header-region walk below then rejects any header-shaped line
# that the canonical/quoted regex did not accept.
for match in canonical_header_re.finditer(patch_text):
    for grp in match.groups():
        if grp:
            reject_path(grp, "patch header")
for match in quoted_header_re.finditer(patch_text):
    for grp in match.groups():
        if not grp:
            continue
        # grp is like '"a/<path>"' or '"b/<path>"'; un-quote, then strip prefix
        unquoted = _git_quoted_unquote(grp)
        if unquoted is None:
            print(
                f"commit.sh: manifest patch header {grp!r} is malformed git-quoted form; rejected",
                file=sys.stderr,
            )
            sys.exit(2)
        if unquoted.startswith("a/") or unquoted.startswith("b/"):
            inner = unquoted[2:]
        else:
            print(
                f"commit.sh: manifest patch header {grp!r} is missing required a/ or b/ prefix; rejected",
                file=sys.stderr,
            )
            sys.exit(2)
        reject_path(inner, "patch header")
# Now reject any header-shaped line not covered by the canonical or quoted
# matchers (bare paths, absolute paths, `..` segments, missing a/b prefix).
# B3 hunk-body false-positive fix: header validation MUST be scoped to the
# diff-header REGION of each file's diff (between `diff --git` and the first
# `@@` hunk-marker line). Lines inside the hunk body that happen to start with
# `+++ ` or `--- ` (legitimate added/removed content rows whose payload begins
# with `+ `/`- `) are NOT header candidates. We walk the patch line-by-line and
# only inspect candidate header lines while in HEADER region.
in_header_region = False
for line in patch_text.split("\n"):
    if line.startswith("diff --git "):
        in_header_region = True
        # The diff --git line itself is a header — check it.
        if not (canonical_header_re.match(line) or quoted_header_re.match(line)):
            print(
                f"commit.sh: manifest patch header form rejected (expected "
                f"`diff --git a/<path> b/<path>` or git-quoted equivalent): {line!r}",
                file=sys.stderr,
            )
            sys.exit(2)
        continue
    if line.startswith("@@ "):
        in_header_region = False
        continue
    if not in_header_region:
        continue
    if line.startswith("--- ") or line.startswith("+++ "):
        # /dev/null exception preserved.
        if line in ("--- /dev/null", "+++ /dev/null"):
            continue
        if canonical_header_re.match(line) or quoted_header_re.match(line):
            continue
        print(
            f"commit.sh: manifest patch header form rejected (expected `a/<path>` / "
            f"`b/<path>` prefix or git-quoted equivalent; bare/absolute/`..`/malformed "
            f"headers refused): {line!r}",
            file=sys.stderr,
        )
        sys.exit(2)

# binary_files (B1) — OPTIONAL top-level list declaring binary blobs to stage
# via `git update-index --add --cacheinfo <mode>,<blob_sha>,<path>` after the
# text patch applies. The manifest does NOT carry binary content; operator must
# pre-run `git hash-object -w <file>` so the blob exists in the repo's object
# database. The wrapper verifies the blob's presence at apply time.
#
# Schema:
#   binary_files: [
#     {
#       "path": "<repo-relative path>",            # path-hygiene per files
#       "blob_sha": "<40-hex-lower>",             # git blob SHA-1
#       "size": <int >= 0>,                        # blob size in bytes
#       "reason": "<non-empty string>"             # rationale, mirrors semantic_files
#     },
#     ...
#   ]
# Absent or empty → no binary entries, behaviour identical to pre-B1.
binary_files_raw = data.get("binary_files", [])
if not isinstance(binary_files_raw, list):
    print("commit.sh: manifest.binary_files must be a list when present", file=sys.stderr)
    sys.exit(2)
binary_files = []
_blob_re = re.compile(r"^[0-9a-f]{40}$")
for idx, entry in enumerate(binary_files_raw):
    if not isinstance(entry, dict):
        print(
            f"commit.sh: manifest.binary_files[{idx}] must be an object with "
            "{path, blob_sha, size, reason}",
            file=sys.stderr,
        )
        sys.exit(2)
    bf_path = reject_path(entry.get("path"), f"binary_files[{idx}].path")
    bf_blob = entry.get("blob_sha")
    if not isinstance(bf_blob, str) or not _blob_re.match(bf_blob):
        print(
            f"commit.sh: manifest.binary_files[{idx}].blob_sha must be a 40-hex "
            f"lower-case string (got {bf_blob!r})",
            file=sys.stderr,
        )
        sys.exit(2)
    bf_size = entry.get("size")
    if not isinstance(bf_size, int) or isinstance(bf_size, bool) or bf_size < 0:
        print(
            f"commit.sh: manifest.binary_files[{idx}].size must be a non-negative "
            f"integer (got {bf_size!r})",
            file=sys.stderr,
        )
        sys.exit(2)
    bf_reason = entry.get("reason")
    if not isinstance(bf_reason, str) or not bf_reason.strip():
        print(
            f"commit.sh: manifest.binary_files[{idx}].reason must be a non-empty string",
            file=sys.stderr,
        )
        sys.exit(2)
    binary_files.append({
        "path": bf_path,
        "blob_sha": bf_blob,
        "size": bf_size,
        "reason": bf_reason,
    })

# base_commit binding (M8): when present, must equal wrapper's resolved
# expected_parent. Mismatch refuses with both SHAs printed.
declared_base = data.get("base_commit")
if declared_base is not None:
    if not isinstance(declared_base, str) or not declared_base.strip():
        print(
            "commit.sh: manifest.base_commit must be a non-empty string when present",
            file=sys.stderr,
        )
        sys.exit(2)
    if declared_base.strip() != expected_parent:
        print(
            "commit.sh: manifest.base_commit does not match resolved expected_parent",
            file=sys.stderr,
        )
        print(f"  manifest.base_commit: {declared_base.strip()}", file=sys.stderr)
        print(f"  expected_parent:      {expected_parent}", file=sys.stderr)
        sys.exit(2)
else:
    declared_base = ""

# repo_root: recorded but never consulted (M8). Path B per-session worktree IS
# the spatial boundary; manifest does not redirect repo resolution.
declared_repo_root = data.get("repo_root", "")
if declared_repo_root and not isinstance(declared_repo_root, str):
    print("commit.sh: manifest.repo_root must be a string when present", file=sys.stderr)
    sys.exit(2)

# task_id read-through: M8 + M7 — task_id binding rules are enforced by the
# wrapper / shared core (which knows whether closed-task or force-manifest mode
# applies). This helper only carries the manifest's declared task_id through.
manifest_task_id = data.get("task_id")
if manifest_task_id is not None and not isinstance(manifest_task_id, str):
    print("commit.sh: manifest.task_id must be a string when present", file=sys.stderr)
    sys.exit(2)

# Write the patch.
with open(patch_path, "w", encoding="utf-8") as fh:
    fh.write(patch_text if patch_text.endswith("\n") else patch_text + "\n")

# Build the plan meta with the same key set the dev-report path produces, plus
# manifest-specific extras. engine="manifest-commit" — the literal
# the pre-fe9c0f2 literal version surface NEVER appears.
plan_seed = json.dumps(
    {
        "manifest_path": os.path.abspath(manifest_path),
        "task_id": manifest_task_id or "",
        "base_commit": expected_parent,
        "semantic_files": semantic_files,
        "files_declared": declared_files,
        # B1: include binary_files in plan_seed so two manifests with the same
        # text patch but different binary blobs hash to different plan IDs.
        "binary_files": binary_files,
        # B2: incompatible_after also folded so plan IDs differ when the
        # manifest declares a future-major negotiation hint.
        "incompatible_after": incompatible_after,
    },
    sort_keys=True,
).encode("utf-8") + patch_text.encode("utf-8")

meta = {
    "engine": "manifest-commit",
    "schema_name": "commit-manifest",
    "schema_version": 3,
    "schema_minor": schema_minor if schema_minor is not None else 0,
    "plan_id": hashlib.sha256(plan_seed).hexdigest()[:16],
    "plan_sha256": hashlib.sha256(plan_seed).hexdigest(),
    "task_id": manifest_task_id or "",
    "manifest_task_id": manifest_task_id or "",
    "repo_root": "",  # never consulted; wrapper resolves via its own ladder
    "manifest_repo_root_observed_but_ignored": declared_repo_root,
    "base_commit": expected_parent,
    "manifest_base_commit_declared": declared_base,
    "manifest_base_commit_observed": expected_parent,
    "manifest_path": os.path.abspath(manifest_path),
    "manifest_sha256": hashlib.sha256(raw).hexdigest(),
    "patch_count": 1,
    "semantic_files": semantic_files,
    "files_declared": declared_files,
    "binary_files": binary_files,
    "incompatible_after": incompatible_after,
    "excluded_dirty": [],
    "artifact_paths": [],
    "dirty_candidates": [],
    "staged_candidates": [],
    "unstaged_candidates": [],
}
with open(meta_path, "w", encoding="utf-8") as fh:
    json.dump(meta, fh, indent=2, sort_keys=True)

# S3 stderr operator-confidence message (BA ticket S3).
if declared_base and declared_base.strip() == expected_parent:
    print("commit.sh: manifest base_commit matches HEAD", file=sys.stderr)
PY
}

run_private_index_commit() {
  local task_id="$1"
  local mode="$2"
  local closure_kind="$3"
  local close_verdict="$4"
  # Optional 5th arg: plan source. "dev-report" (default) → build_semantic_plan_bundle;
  # "manifest" → build_manifest_plan_bundle. Manifest path is read from MANIFEST_PATH
  # global (set by argv pre-scan).
  local plan_source="${5:-dev-report}"

  local tmp_dir patch_file meta_file
  tmp_dir="$(mktemp -d "${CLAUDE_TMPDIR%/}/claude-commit-plan-XXXXXX")"
  patch_file="${tmp_dir}/bundle.patch"
  meta_file="${tmp_dir}/plan-meta.json"

  if [ "$plan_source" = "force-rescue" ]; then
    # A2: stage-then-force source authority is the operator's staged set. No
    # manifest, no task-id binding, no closure. All post-apply safety still
    # engaged via the shared core.
    if ! build_force_rescue_plan_bundle "$patch_file" "$meta_file"; then
      rm -rf "$tmp_dir"
      return 2
    fi
  elif [ "$plan_source" = "manifest" ]; then
    # Manifest path needs expected_parent BEFORE building the plan (M8 base_commit
    # binding requires the resolved branch HEAD at apply time). Resolve repo_root +
    # expected_parent here, then call the manifest helper. This mirrors the
    # build_semantic_plan_bundle contract (plan meta carries repo_root + base_commit
    # so the shared post-build code can use the same resolution path).
    # Repo-resolution ladder (M8 + A1): mirror the wrapper's existing
    # DOCS_DIR_ROOT discovery ladder so manifest mode resolves to the same
    # target repo a closed-task commit would. A1 inserts --repo at the front
    # of the ladder for explicit caller intent. Order:
    #   1. --repo <path>  (A1 explicit; EXPLICIT_REPO if non-empty)
    #   2. CLAUDE_DOCS_DIR (operator override; usually a docs-aware project root)
    #   3. CLAUDE_PROJECT_DIR (back-compat env)
    #   4. cwd-toplevel
    #   5. pwd
    #   6. /root (legacy harness-root safety net)
    # First candidate that resolves to a git toplevel wins.
    local manifest_repo_root="" manifest_branch manifest_expected_parent _cand_dir
    for _cand_dir in "${EXPLICIT_REPO:-}" "${CLAUDE_DOCS_DIR:-}" "${CLAUDE_PROJECT_DIR:-}" "$(git rev-parse --show-toplevel 2>/dev/null || true)" "$(pwd)" "/root"; do
      [ -z "$_cand_dir" ] && continue
      manifest_repo_root="$(git -C "$_cand_dir" rev-parse --show-toplevel 2>/dev/null || true)"
      [ -n "$manifest_repo_root" ] && break
    done
    if [ -z "$manifest_repo_root" ]; then
      echo "commit.sh: cannot resolve target repo for manifest plan (tried CLAUDE_DOCS_DIR / CLAUDE_PROJECT_DIR / cwd-toplevel / pwd / /root)" >&2
      rm -rf "$tmp_dir"
      return 2
    fi
    manifest_branch="$(git -C "$manifest_repo_root" symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
    if [ -z "$manifest_branch" ]; then
      echo "commit.sh: manifest commit requires a branch (detached HEAD refused)" >&2
      rm -rf "$tmp_dir"
      return 2
    fi
    manifest_expected_parent="$(git -C "$manifest_repo_root" rev-parse "refs/heads/${manifest_branch}^{commit}")"
    build_manifest_plan_bundle "$MANIFEST_PATH" "$mode" "$manifest_expected_parent" "$patch_file" "$meta_file" || {
      rm -rf "$tmp_dir"
      return 2
    }
    # Inject resolved repo_root into the manifest meta (overwrites the empty
    # string the helper wrote; the helper does not call git so it cannot resolve
    # the repo on its own).
    "$PYTHON_BIN" - "$meta_file" "$manifest_repo_root" <<'PY'
import json, sys
meta = json.load(open(sys.argv[1]))
meta["repo_root"] = sys.argv[2]
with open(sys.argv[1], "w") as fh:
    json.dump(meta, fh, indent=2, sort_keys=True)
PY
    # task_id binding rules (M8): in closed-task mode with manifest:
    #   * IF manifest.task_id is present, it MUST equal the wrapper-arg task-id.
    #   * IF dev-report is also present AND parses cleanly, its task_id MUST
    #     equal the wrapper-arg task-id (cross-check).
    #   * IF NEITHER manifest.task_id NOR a parseable dev-report task_id
    #     is present, REFUSE — closed-task manifest mode demands at least one
    #     bound identity proof.
    # In force-manifest mode, no binding (force does not bind task_id).
    local manifest_declared_task
    manifest_declared_task="$("$PYTHON_BIN" - "$meta_file" <<'PY'
import json, sys
value = json.load(open(sys.argv[1])).get("manifest_task_id")
print("" if value is None else value)
PY
)"
    if [ "$mode" = "closed-task" ]; then
      if [ -n "$manifest_declared_task" ] && [ "$manifest_declared_task" != "$task_id" ]; then
        echo "commit.sh: manifest.task_id ${manifest_declared_task} does not match wrapper task-id ${task_id}" >&2
        rm -rf "$tmp_dir"
        return 2
      fi
      # Dev-report cross-check + neither-bound refusal (M8 task_id binding rules).
      local dev_report_for_manifest_check
      dev_report_for_manifest_check="${DOCS_DIR}/dev-report-${task_id}.json"
      local dev_report_task_evidence
      dev_report_task_evidence="$("$PYTHON_BIN" - "$dev_report_for_manifest_check" "$task_id" <<'PY'
import json, os, sys
path, wrapper_task = sys.argv[1:3]
if not os.path.exists(path):
    # Dev-report absent: emit empty (not a failure on its own; the
    # neither-bound rule below decides).
    print("absent")
    sys.exit(0)
try:
    data = json.load(open(path, encoding="utf-8"))
except Exception:
    print("unparseable")
    sys.exit(0)
if not isinstance(data, dict):
    print("unparseable")
    sys.exit(0)
def matches(value, tid):
    if value is None:
        return False
    if value == tid:
        return True
    if isinstance(value, str) and tid in value:
        return True
    return False
dev_node = data.get("dev") if isinstance(data.get("dev"), dict) else {}
candidates = [
    data.get("task_id"), data.get("request_id"),
    dev_node.get("task_id"), dev_node.get("request_id"),
]
present = any(c is not None for c in candidates)
if not present:
    print("absent")
    sys.exit(0)
if any(matches(c, wrapper_task) for c in candidates):
    print("bound")
else:
    print("mismatch")
PY
)"
      if [ "$dev_report_task_evidence" = "mismatch" ]; then
        echo "commit.sh: dev-report at ${dev_report_for_manifest_check} task_id does not match wrapper task-id ${task_id}" >&2
        rm -rf "$tmp_dir"
        return 2
      fi
      if [ -z "$manifest_declared_task" ] && [ "$dev_report_task_evidence" != "bound" ]; then
        echo "commit.sh: closed-task manifest mode requires manifest.task_id OR a parseable dev-report at ${dev_report_for_manifest_check} with matching task_id; neither found" >&2
        rm -rf "$tmp_dir"
        return 2
      fi
    fi
  else
    build_semantic_plan_bundle "$task_id" "$mode" "$patch_file" "$meta_file" || {
      rm -rf "$tmp_dir"
      return 2
    }
  fi

  local plan_repo repo_root
  plan_repo="$("$PYTHON_BIN" - "$meta_file" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
print(data.get("repo_root", ""))
PY
)"
  local plan_task_for_check
  plan_task_for_check="$("$PYTHON_BIN" - "$meta_file" <<'PY'
import json, sys
value = json.load(open(sys.argv[1])).get("task_id")
print("" if value is None else value)
PY
)"
  if [ "$mode" = "closed-task" ] && [ -n "$plan_task_for_check" ] && [ "$plan_task_for_check" != "$task_id" ]; then
    echo "commit.sh: semantic plan task_id ${plan_task_for_check} does not match requested task ${task_id}" >&2
    rm -rf "$tmp_dir"
    return 2
  fi
  if [ -n "$plan_repo" ]; then
    repo_root="$(git -C "$plan_repo" rev-parse --show-toplevel 2>/dev/null || true)"
  else
    repo_root=""
  fi
  if [ -z "$repo_root" ] && [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
    repo_root="$(git -C "$CLAUDE_PROJECT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
  fi
  if [ -z "$repo_root" ]; then
    repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  fi
  if [ -z "$repo_root" ]; then
    echo "commit.sh: cannot resolve target repo for semantic plan" >&2
    rm -rf "$tmp_dir"
    return 2
  fi

  local branch expected_parent real_index_before real_index_after private_index staged_list_before staged_list_after index_path probe_index
  branch="$(git -C "$repo_root" symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
  if [ -z "$branch" ]; then
    echo "commit.sh: semantic commit requires a branch (detached HEAD refused)" >&2
    rm -rf "$tmp_dir"
    return 2
  fi
  expected_parent="$(git -C "$repo_root" rev-parse "refs/heads/${branch}^{commit}")"
  # Manifest-mode base_commit re-assertion (M8 + codex-iter race-window fix):
  # build_manifest_plan_bundle validated declared_base against the pre-resolution
  # expected_parent. Re-assert here so a HEAD advance between manifest plan
  # construction and the shared-core resolution can't silently accept a stale
  # manifest base against a different parent.
  if [ "$plan_source" = "manifest" ]; then
    local manifest_declared_base
    manifest_declared_base="$("$PYTHON_BIN" - "$meta_file" <<'PY'
import json, sys
value = json.load(open(sys.argv[1])).get("manifest_base_commit_declared", "")
print(value or "")
PY
)"
    if [ -n "$manifest_declared_base" ] && [ "$manifest_declared_base" != "$expected_parent" ]; then
      echo "commit.sh: manifest.base_commit drifted from current branch HEAD between plan and apply" >&2
      echo "  manifest.base_commit: ${manifest_declared_base}" >&2
      echo "  expected_parent:      ${expected_parent}" >&2
      rm -rf "$tmp_dir"
      return 2
    fi
  fi
  real_index_before="$(real_index_fingerprint "$repo_root")"
  staged_list_before="$(staged_file_list "$repo_root")"
  private_index="${tmp_dir}/index"

  # A3 (--plan dry-run): emit the resolved plan and exit 0 BEFORE any
  # apply / commit / branch advance / audit emission. The staged_list_before
  # vs staged_list_after invariant verifies post-run (no side effect).
  if [ "${PLAN_MODE:-0}" -eq 1 ]; then
    local _plan_files_preview _plan_msg_preview _plan_binary_files
    _plan_files_preview="$("$PYTHON_BIN" - "$meta_file" <<'PY'
import json, sys
meta = json.load(open(sys.argv[1]))
files = [item["path"] for item in meta.get("semantic_files", [])]
print(json.dumps(files))
PY
)"
    _plan_binary_files="$("$PYTHON_BIN" - "$meta_file" <<'PY'
import json, sys
meta = json.load(open(sys.argv[1]))
print(json.dumps([entry["path"] for entry in meta.get("binary_files", [])]))
PY
)"
    _plan_msg_preview="${COMMIT_MSG:0:200}"
    local _plan_mode_label
    case "$plan_source" in
      manifest)     _plan_mode_label="${mode}|manifest" ;;
      force-rescue) _plan_mode_label="force-rescue" ;;
      *)            _plan_mode_label="${mode}|dev-report" ;;
    esac
    local _plan_patch_source
    case "$plan_source" in
      manifest)     _plan_patch_source="manifest" ;;
      force-rescue) _plan_patch_source="staged" ;;
      *)            _plan_patch_source="dev-report" ;;
    esac
    cat <<PLAN_OUT
PLAN:
  task_id: ${task_id}
  mode: ${_plan_mode_label}
  message_source: ${MESSAGE_SOURCE}
  message_preview: ${_plan_msg_preview}
  patch_source: ${_plan_patch_source}
  files_planned: ${_plan_files_preview}
  binary_files_planned: ${_plan_binary_files}
  manifest_active: $([ "$plan_source" = "manifest" ] && echo true || echo false)
  repo_root: ${repo_root}
  expected_parent: ${expected_parent}
EXIT: dry-run (no commit created)
PLAN_OUT
    # Verify zero side-effect by comparing staged list (should be unchanged
    # since we only ran read-tree on the private index, which has not yet
    # touched the real index).
    local _staged_after_plan
    _staged_after_plan="$(staged_file_list "$repo_root")"
    if [ "$_staged_after_plan" != "$staged_list_before" ]; then
      echo "commit.sh: --plan invariant violated: staged list changed during dry-run" >&2
      rm -rf "$tmp_dir"
      return 2
    fi
    rm -rf "$tmp_dir"
    return 0
  fi

  GIT_INDEX_FILE="$private_index" git -C "$repo_root" read-tree "$expected_parent"
  if ! GIT_INDEX_FILE="$private_index" git -C "$repo_root" apply --cached --3way "$patch_file" 2>"${tmp_dir}/apply.err"; then
    echo "commit.sh: semantic plan conflict/overlap; branch, worktree, and real index were not mutated" >&2
    cat "${tmp_dir}/apply.err" >&2
    rm -rf "$tmp_dir"
    return 2
  fi
  # B1 (binary_files apply): stage declared binary blobs via update-index
  # --add --cacheinfo. Each blob_sha must already exist in the repo's object
  # database (operator pre-runs `git hash-object -w <file>`). Verified via
  # `git cat-file -e <sha>` before staging. Default file mode is 100644
  # (regular file); B1's M5-invariant subset check below unions
  # binary_files.path with files_declared so the post-apply diff name list
  # may legitimately include these paths.
  local binary_apply_count=0
  local binary_applied_json="[]"
  if [ "$plan_source" = "manifest" ]; then
    local binary_entries_json
    binary_entries_json="$("$PYTHON_BIN" - "$meta_file" <<'PY'
import json, sys
meta = json.load(open(sys.argv[1]))
print(json.dumps(meta.get("binary_files", [])))
PY
)"
    # Iterate using python to keep robustness against odd shell escaping.
    binary_applied_json="$(
      GIT_INDEX_FILE="$private_index" "$PYTHON_BIN" - "$repo_root" "$binary_entries_json" <<'PY'
import json, os, subprocess, sys
repo_root, entries_json = sys.argv[1:3]
entries = json.loads(entries_json)
applied = []
env = os.environ.copy()
if "GIT_INDEX_FILE" not in env:
    print("commit.sh: GIT_INDEX_FILE not set during binary apply", file=sys.stderr)
    sys.exit(2)
for entry in entries:
    path = entry["path"]
    sha = entry["blob_sha"]
    size = entry["size"]
    reason = entry["reason"]
    # Verify blob exists in the repo's object database.
    rc = subprocess.run(
        ["git", "-C", repo_root, "cat-file", "-e", sha],
        env=env,
    ).returncode
    if rc != 0:
        print(
            f"commit.sh: manifest.binary_files entry references blob_sha {sha} for "
            f"path {path!r} but the blob is not present in the repo's object database; "
            "operator must pre-run `git hash-object -w <file>` to populate the blob",
            file=sys.stderr,
        )
        sys.exit(2)
    # Optional cross-check: size echoed in stderr only when mismatch.
    proc = subprocess.run(
        ["git", "-C", repo_root, "cat-file", "-s", sha],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if proc.returncode == 0:
        try:
            actual_size = int(proc.stdout.strip())
        except Exception:
            actual_size = None
        if actual_size is not None and actual_size != size:
            print(
                f"commit.sh: manifest.binary_files entry size={size} for {path!r} "
                f"does not match actual blob size={actual_size} (sha={sha})",
                file=sys.stderr,
            )
            sys.exit(2)
    # Stage via update-index --add --cacheinfo. Default mode 100644.
    rc = subprocess.run(
        ["git", "-C", repo_root, "update-index", "--add", "--cacheinfo",
         f"100644,{sha},{path}"],
        env=env,
    ).returncode
    if rc != 0:
        print(
            f"commit.sh: failed to stage binary entry path={path!r} sha={sha} "
            "via update-index --add --cacheinfo",
            file=sys.stderr,
        )
        sys.exit(2)
    applied.append({"path": path, "blob_sha": sha, "size": size, "reason": reason})
print(json.dumps(applied))
PY
)" || {
      rm -rf "$tmp_dir"
      return 2
    }
    # Count how many entries were applied (length of applied array).
    binary_apply_count="$("$PYTHON_BIN" -c "import json,sys; print(len(json.loads(sys.argv[1])))" "$binary_applied_json")"
    # Write binary_files_applied into the meta file so downstream audit emission
    # can pick it up (same shape pattern as repo_root injection above).
    "$PYTHON_BIN" - "$meta_file" "$binary_applied_json" <<'PY'
import json, sys
meta_path, applied_json = sys.argv[1:3]
meta = json.load(open(meta_path))
meta["binary_files_applied"] = json.loads(applied_json)
with open(meta_path, "w") as fh:
    json.dump(meta, fh, indent=2, sort_keys=True)
PY
  fi
  if [ -n "$(GIT_INDEX_FILE="$private_index" git -C "$repo_root" ls-files -u)" ]; then
    echo "commit.sh: semantic plan left unmerged private-index entries; refusing commit" >&2
    rm -rf "$tmp_dir"
    return 2
  fi
  if [ "$(real_index_fingerprint "$repo_root")" != "$real_index_before" ]; then
    echo "commit.sh: real shared index changed during semantic private-index preparation; refusing branch advance" >&2
    rm -rf "$tmp_dir"
    return 2
  fi
  if ! GIT_INDEX_FILE="$private_index" git -C "$repo_root" diff --cached --check "$expected_parent" --; then
    echo "commit.sh: private-index diff check failed; refusing commit" >&2
    rm -rf "$tmp_dir"
    return 2
  fi
  if GIT_INDEX_FILE="$private_index" git -C "$repo_root" diff --cached --quiet --exit-code "$expected_parent" --; then
    echo "commit.sh: semantic plan produced no commit diff" >&2
    rm -rf "$tmp_dir"
    return 2
  fi

  local files_json tree new_commit backup_ref plan_sha plan_id plan_base plan_excluded plan_semantic staged_before_json staged_after_json staged_overlap
  local plan_files=()
  mapfile -t plan_files < <(GIT_INDEX_FILE="$private_index" git -C "$repo_root" diff --cached --name-only "$expected_parent" --)
  files_json="$(GIT_INDEX_FILE="$private_index" git -C "$repo_root" diff --cached --name-only "$expected_parent" -- | "$PYTHON_BIN" -c 'import json,sys; print(json.dumps([l for l in sys.stdin.read().splitlines() if l]))')"
  # Manifest mode: M6 subset assertion against manifest.files MUST run BEFORE the
  # semantic_files rationale check so AC4's stderr-text contract — "not declared
  # in manifest.files" naming the offending path — wins. If we ran the rationale
  # check first, the diagnostic would name the missing semantic_files rationale
  # instead of the manifest.files declaration violation.
  if [ "$plan_source" = "manifest" ]; then
    if ! "$PYTHON_BIN" - "$meta_file" "$files_json" <<'PY'
import json
import sys

meta = json.load(open(sys.argv[1]))
patch_files = set(json.loads(sys.argv[2]))
# B1: M6 subset assertion unions manifest.files with manifest.binary_files[].path
# because binary files are staged outside the unified-diff text but legitimately
# appear in the post-apply name list.
declared = set(meta.get("files_declared", []))
declared |= {entry["path"] for entry in meta.get("binary_files", [])}
extras = sorted(patch_files - declared)
if extras:
    print(
        "commit.sh: applied patch touches path(s) not declared in manifest.files "
        "or manifest.binary_files: " + ", ".join(extras),
        file=sys.stderr,
    )
    sys.exit(2)
PY
    then
      rm -rf "$tmp_dir"
      return 2
    fi
  fi
  if ! "$PYTHON_BIN" - "$meta_file" "$files_json" <<'PY'
import json
import sys

meta = json.load(open(sys.argv[1]))
patch_files = set(json.loads(sys.argv[2]))
# B1: a binary_files entry carries its own reason field; include its paths in
# the rationale set so binary-only paths satisfy the ownership-rationale rule.
semantic_files = {item["path"] for item in meta.get("semantic_files", [])}
semantic_files |= {entry["path"] for entry in meta.get("binary_files", [])}
missing = sorted(patch_files - semantic_files)
if missing:
    print("commit.sh: semantic plan missing ownership rationale for path(s): " + ", ".join(missing), file=sys.stderr)
    sys.exit(2)
PY
  then
    rm -rf "$tmp_dir"
    return 2
  fi
  if [ "$plan_source" = "manifest" ]; then
    # M7 is_other_session over POST-APPLY diff for the manifest path: refuse
    # cross-task docs/dev artifacts when a task identity is bound. Closed-task
    # mode is always bound (task_id is the wrapper-arg). force-manifest mode is
    # bound ONLY when manifest declares its own task_id. force-manifest without
    # manifest.task_id skips the filter (codex finding #6: naïve filter without
    # task identity would mis-classify all docs/dev artifacts).
    local manifest_task_for_filter=""
    if [ "$mode" = "closed-task" ]; then
      manifest_task_for_filter="$task_id"
    elif [ "$mode" = "force-manifest" ]; then
      manifest_task_for_filter="$("$PYTHON_BIN" - "$meta_file" <<'PY'
import json, sys
value = json.load(open(sys.argv[1])).get("manifest_task_id")
print("" if value is None else value)
PY
)"
    fi
    if [ -n "$manifest_task_for_filter" ]; then
      if ! "$PYTHON_BIN" - "$files_json" "$manifest_task_for_filter" <<'PY'
import json
import os
import re
import sys

patch_files = json.loads(sys.argv[1])
bound_task = sys.argv[2]
ts_re = re.compile(r"[0-9]{8}-[0-9]{6}")
offending = []
for path in patch_files:
    if not path.startswith("docs/dev/"):
        continue
    base = os.path.basename(path)
    if ts_re.search(base) and bound_task not in base:
        offending.append(path)
if offending:
    print(
        "commit.sh: manifest patch touches cross-task docs/dev artifact(s) for "
        f"task_id={bound_task}: " + ", ".join(sorted(offending)),
        file=sys.stderr,
    )
    sys.exit(2)
PY
      then
        rm -rf "$tmp_dir"
        return 2
      fi
    fi
  fi
  # A2: force-rescue's patch source IS the staged set, so by definition the
  # plan_files overlap with the shared staged-set. Skipping the overlap guard
  # is intentional for plan_source=="force-rescue"; for all other plan sources
  # the guard remains in force.
  if [ "${#plan_files[@]}" -gt 0 ] && [ "$plan_source" != "force-rescue" ]; then
    staged_overlap="$(git -C "$repo_root" diff --cached --name-only -- "${plan_files[@]}" | LC_ALL=C sort -u)"
    if [ -n "$staged_overlap" ]; then
      echo "commit.sh: semantic plan touches path(s) already staged by another session; refusing to preserve shared index ownership" >&2
      printf '%s\n' "$staged_overlap" >&2
      rm -rf "$tmp_dir"
      return 2
    fi
  fi
  tree="$(GIT_INDEX_FILE="$private_index" git -C "$repo_root" write-tree)"
  new_commit="$(printf '%s\n' "$COMMIT_MSG" | GIT_INDEX_FILE="$private_index" git -C "$repo_root" commit-tree "$tree" -p "$expected_parent")"

  if [ "$(real_index_fingerprint "$repo_root")" != "$real_index_before" ]; then
    echo "commit.sh: real shared index changed before CAS branch advance; refusing branch advance" >&2
    rm -rf "$tmp_dir"
    return 2
  fi
  index_path="$(git -C "$repo_root" rev-parse --git-path index 2>/dev/null || true)"
  probe_index="${tmp_dir}/real-index-probe"
  if [ -n "$index_path" ] && [ -f "$index_path" ]; then
    cp "$index_path" "$probe_index"
    if ! GIT_INDEX_FILE="$probe_index" sync_real_index_to_commit_paths "$repo_root" "$new_commit" "$tmp_dir" "${plan_files[@]}"; then
      echo "commit.sh: shared-index planned-path reconciliation preflight failed; refusing branch advance" >&2
      rm -rf "$tmp_dir"
      return 2
    fi
  fi
  if ! git -C "$repo_root" update-ref "refs/heads/${branch}" "$new_commit" "$expected_parent"; then
    echo "commit.sh: expected-parent CAS failed for refs/heads/${branch}; branch advanced concurrently, retry on the new HEAD" >&2
    rm -rf "$tmp_dir"
    return 2
  fi
  if ! sync_real_index_to_commit_paths "$repo_root" "$new_commit" "$tmp_dir" "${plan_files[@]}"; then
    echo "commit.sh: branch advanced, but shared-index planned-path reconciliation failed" >&2
    rm -rf "$tmp_dir"
    return 2
  fi
  staged_list_after="$(staged_file_list "$repo_root")"
  real_index_after="$(real_index_fingerprint "$repo_root")"
  # A2: for force-rescue mode the staged set IS the patch source; after the
  # commit lands and sync_real_index_to_commit_paths reconciles the real index,
  # the previously-staged paths legitimately leave the staged-set (they now
  # match HEAD). The before/after equality invariant must be relaxed for
  # plan_source=="force-rescue" — instead verify the post-commit staged set is
  # a SUBSET of staged_list_before (no new entries appeared from outside the
  # plan; the only legitimate diff is REMOVALS of paths now matching HEAD).
  if [ "$plan_source" = "force-rescue" ]; then
    printf '%s\n' "$staged_list_before" > "${tmp_dir}/staged-before.lst"
    printf '%s\n' "$staged_list_after"  > "${tmp_dir}/staged-after.lst"
    if ! "$PYTHON_BIN" - "${tmp_dir}/staged-before.lst" "${tmp_dir}/staged-after.lst" <<'PY'
import sys
before = set(l for l in open(sys.argv[1]).read().splitlines() if l)
after  = set(l for l in open(sys.argv[2]).read().splitlines() if l)
extras = sorted(after - before)
if extras:
    print(
        "commit.sh: force-rescue post-commit staged set gained unexpected entries: "
        + ", ".join(extras),
        file=sys.stderr,
    )
    sys.exit(2)
PY
    then
      rm -rf "$tmp_dir"
      return 2
    fi
  elif [ "$staged_list_after" != "$staged_list_before" ]; then
    echo "commit.sh: staged-file list changed during semantic commit; refusing because shared staged ownership was not preserved" >&2
    printf 'before:\n%s\n' "$staged_list_before" >&2
    printf 'after:\n%s\n' "$staged_list_after" >&2
    rm -rf "$tmp_dir"
    return 2
  fi

  # D2: run_backup_only_push writes the backup ref to a sentinel file (not via
  # command-substitution stdout) so it can mutate caller-scope BACKUP_PUSH_FAILED
  # without losing the mutation to a subshell. We then read the file to recover
  # the backup ref string.
  local backup_ref_sentinel="${tmp_dir}/backup-ref"
  run_backup_only_push "$repo_root" "$branch" "$new_commit" "$backup_ref_sentinel"
  backup_ref="$(cat "$backup_ref_sentinel" 2>/dev/null || echo "")"

  mkdir -p "$(dirname "$LOG_PATH")"
  local sid nonce ppid_val msg_sha_short ts audit_json
  sid="${CLAUDE_SESSION_ID:-$$}"
  # A4 (audit-filename collision-safety rationale): the audit JSON filename
  # composes `${sid}-${nonce}` where nonce is `secrets.token_hex(16)` — a
  # cryptographic-quality 128-bit random nonce per invocation. Concurrent runs
  # by the same sid produce different nonces (collision probability < 2^-64
  # per pair, astronomically rare even at fleet scale). The wrapper writes the
  # file via Python `open(path, "w")` which is an atomic create-or-replace at
  # the filesystem layer for the single-writer model; no rename-dance needed
  # because nonce uniqueness already disjoins concurrent paths. No race window.
  nonce="$("$PYTHON_BIN" -c "import secrets; print(secrets.token_hex(16))")"
  ppid_val="$$"
  msg_sha_short="$("$PYTHON_BIN" -c "import hashlib, sys; print(hashlib.sha256(sys.argv[1].encode('utf-8')).hexdigest()[:12])" "$COMMIT_MSG")"
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  # M9: manifest-mode audit filename uses `commit-manifest-` prefix so log
  # filtering can distinguish manifest commits from dev-report-driven semantic
  # commits without parsing the JSON body. Dev-report path keeps the original
  # `commit-semantic-` prefix (AC3 byte-identity invariant — the filename is
  # not part of the JSON content but path-level tests may inspect it).
  if [ "$plan_source" = "manifest" ]; then
    audit_json="${CLAUDE_LOG_DIR}/commit-manifest-${sid}-${nonce}.json"
  else
    audit_json="${CLAUDE_LOG_DIR}/commit-semantic-${sid}-${nonce}.json"
  fi
  plan_sha="$("$PYTHON_BIN" - "$meta_file" <<'PY'
import json, sys
print(json.load(open(sys.argv[1])).get("plan_sha256", ""))
PY
)"
  plan_id="$("$PYTHON_BIN" - "$meta_file" <<'PY'
import json, sys
print(json.load(open(sys.argv[1])).get("plan_id", ""))
PY
)"
  plan_base="$("$PYTHON_BIN" - "$meta_file" <<'PY'
import json, sys
print(json.load(open(sys.argv[1])).get("base_commit", ""))
PY
)"
  plan_excluded="$("$PYTHON_BIN" - "$meta_file" <<'PY'
import json, sys
print(json.dumps(json.load(open(sys.argv[1])).get("excluded_dirty", [])))
PY
)"
  plan_semantic="$("$PYTHON_BIN" - "$meta_file" <<'PY'
import json, sys
print(json.dumps(json.load(open(sys.argv[1])).get("semantic_files", [])))
PY
)"
  staged_before_json="$(printf '%s\n' "$staged_list_before" | "$PYTHON_BIN" -c 'import json,sys; print(json.dumps([l for l in sys.stdin.read().splitlines() if l]))')"
  staged_after_json="$(printf '%s\n' "$staged_list_after" | "$PYTHON_BIN" -c 'import json,sys; print(json.dumps([l for l in sys.stdin.read().splitlines() if l]))')"

  "$PYTHON_BIN" - "$audit_json" "$ts" "$sid" "$task_id" "$mode" "$branch" "$expected_parent" "$new_commit" "$plan_sha" "$plan_id" "$plan_base" "$files_json" "$plan_semantic" "$plan_excluded" "$backup_ref" "$closure_kind" "$close_verdict" "$MESSAGE_SOURCE" "$staged_before_json" "$staged_after_json" "$real_index_before" "$real_index_after" "$meta_file" <<'PY'
import json
import sys

(path, ts, sid, task_id, mode, branch, parent, commit, plan_sha,
 plan_id, plan_base, files_json, semantic_json, excluded_json,
 backup_ref, closure_kind, close_verdict, message_source, staged_before_json,
 staged_after_json, index_before, index_after, meta_path) = sys.argv[1:24]
# Engine + schema metadata come from the plan-meta file. Dev-report path emits
# engine="semantic-commit" (existing baseline byte-identity invariant per AC3).
# Manifest path emits engine="manifest-commit" + schema_name/schema_version/
# schema_minor + manifest_* descriptors (M3 — the pre-fe9c0f2 legacy
# string-aliased version field is no longer present in audit emission).
meta = json.load(open(meta_path))
engine = meta.get("engine", "semantic-commit")
data = {
    "timestamp": ts,
    "sid": sid,
    "command_kind": "commit",
    "engine": engine,
    "mode": mode,
    "task_id": task_id,
    "branch": branch,
    "parent": parent,
    "commit": commit,
    "plan_sha256": plan_sha,
    "plan_id": plan_id,
    "plan_base_commit": plan_base,
    "files": json.loads(files_json),
    "semantic_files": json.loads(semantic_json),
    "excluded_dirty": json.loads(excluded_json),
    "staged_files_before": json.loads(staged_before_json),
    "staged_files_after": json.loads(staged_after_json),
    "real_index_fingerprint_before": index_before,
    "real_index_fingerprint_after": index_after,
    "backup_ref": backup_ref,
    "closure_kind": closure_kind,
    "close_verdict_observed": close_verdict,
    "message_source": message_source,
}
# Conditional manifest-mode audit fields: emit ONLY when the plan came from the
# manifest helper (engine=="manifest-commit"). This preserves AC3 byte-identity
# for the dev-report path — its meta file does not set these keys, so they do
# not appear in the audit JSON for that path.
if engine == "manifest-commit":
    data["schema_name"] = meta.get("schema_name", "commit-manifest")
    data["schema_version"] = meta.get("schema_version", 3)
    data["schema_minor"] = meta.get("schema_minor", 0)
    data["manifest_path"] = meta.get("manifest_path", "")
    data["manifest_sha256"] = meta.get("manifest_sha256", "")
    data["manifest_task_id"] = meta.get("manifest_task_id", "")
    data["manifest_base_commit_declared"] = meta.get("manifest_base_commit_declared", "")
    data["manifest_base_commit_observed"] = meta.get("manifest_base_commit_observed", "")
    data["manifest_repo_root_observed_but_ignored"] = meta.get(
        "manifest_repo_root_observed_but_ignored", ""
    )
    data["files_declared"] = meta.get("files_declared", [])
    # B1 additive: binary_files (declared) + binary_files_applied (post-apply set)
    # appear ONLY on manifest-path audits; dev-report-path audits never see these
    # keys (AC-CYCLE-2 byte-identity invariant).
    data["binary_files"] = meta.get("binary_files", [])
    data["binary_files_applied"] = meta.get("binary_files_applied", [])
    # B2 additive: incompatible_after (when declared by the manifest) is echoed
    # for audit traceability; absent value (None) is preserved so log readers
    # can distinguish "no field" from "value 0".
    data["incompatible_after"] = meta.get("incompatible_after")
with open(path, "w") as fh:
    json.dump(data, fh, indent=2, sort_keys=True)
PY

  local log_engine
  log_engine="$("$PYTHON_BIN" - "$meta_file" <<'PY'
import json, sys
print(json.load(open(sys.argv[1])).get("engine", "semantic-commit"))
PY
)"
  "$PYTHON_BIN" - "$LOG_PATH" "$ts" "$sid" "$task_id" "$mode" "$nonce" "$ppid_val" "$msg_sha_short" "$new_commit" "$expected_parent" "$plan_sha" "$backup_ref" "$files_json" "$closure_kind" "$close_verdict" "$MESSAGE_SOURCE" "$audit_json" "$log_engine" <<'PY'
import json
import sys

(path, ts, sid, task_id, mode, nonce, ppid_val, msg_sha_short, head,
 parent, plan_sha, backup_ref, files_json, closure_kind,
 close_verdict, message_source, audit_json, engine) = sys.argv[1:19]
line = {
    "timestamp": ts,
    "sid": sid,
    "command_kind": "commit",
    "engine": engine,
    "mode": mode,
    "task_id": task_id,
    "sentinel_nonce": nonce,
    "ppid": int(ppid_val),
    "message_sha256_short": msg_sha_short,
    "head": head,
    "parent": parent,
    "plan_sha256": plan_sha,
    "backup_ref": backup_ref,
    "files": json.loads(files_json),
    "closure_kind": closure_kind,
    "close_verdict_observed": close_verdict,
    "message_source": message_source,
    "audit_json": audit_json,
}
with open(path, "a") as fh:
    fh.write(json.dumps(line) + "\n")
PY

  _USERINTENT_SID="${CLAUDE_SESSION_ID:-default}"
  rm -f "/tmp/claude-commit-userintent-${_USERINTENT_SID}.flag"
  rm -rf "$tmp_dir"
  echo "commit.sh: success — semantic task=${task_id} branch=${branch} parent=${expected_parent} head=${new_commit} backup_ref=${backup_ref}"
  # D2: when CLAUDE_BACKUP_REMOTE_REQUIRED=1 and the synchronous backup push
  # failed, return 2 so the wrapper exit code reflects the missing remote
  # safety net. Default behaviour (env unset) remains return 0 — the async
  # push runs in background and the operator gets a stderr surface on failure.
  if [ "${BACKUP_PUSH_FAILED:-0}" = "1" ]; then
    echo "commit.sh: backup push failed (CLAUDE_BACKUP_REMOTE_REQUIRED=1)" >&2
    return 2
  fi
  return 0
}

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
#   - Write a per-nonce grant file with allowed_files + expected_message_sha256
#     + branch (defense-in-depth: the guard's defense-in-depth path validates
#     this grant when it sees a bridge-mode commit with the env+grant pair).
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

  # JSON-encode for the grant file.
  ALLOWED_JSON="$("$PYTHON_BIN" -c "
import json, sys
files = [l for l in sys.stdin.read().splitlines() if l.strip()]
print(json.dumps(sorted(set(files))))
" <<< "$STAGED_RAW")"

  # Bridge-mode commit message (matches BLESSED_BRIDGE_RE — preserves
  # backwards-compat with the existing privilege-guard early-return at line
  # 440-442 of pretool-git-privilege-guard.py).
  COMMIT_MSG="auto-bulk: end-of-cycle commit for ${BRIDGE_BRANCH}"

  MSG_SHA256="$("$PYTHON_BIN" -c "
import hashlib, sys
print(hashlib.sha256(sys.argv[1].encode('utf-8')).hexdigest())
" "$COMMIT_MSG")"

  # Grant file (per-nonce; mirrors the closed-task path).
  SID="${CLAUDE_SESSION_ID:-$$}"
  NONCE="$("$PYTHON_BIN" -c "import secrets; print(secrets.token_hex(16))")"
  GRANT_FILE="/tmp/claude-commit-grant-${SID}-${NONCE}.json"
  CREATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  PPID_VAL="$$"

  "$PYTHON_BIN" - "$GRANT_FILE" "$NONCE" "$SID" "$BRIDGE_BRANCH" "$ALLOWED_JSON" "$MSG_SHA256" "$CREATED_AT" "$PPID_VAL" <<'PY'
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

  "$PYTHON_BIN" - "$LOG_PATH" "$TS" "$SID" "$BRIDGE_BRANCH" "$NONCE" "$PPID_VAL" "$MSG_SHA_SHORT" "$NEW_HEAD" <<'PY'
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
#   - Skip dev-report parsing (dev-report is not content authority here).
#   - Skip P-CLOSEHONOR (no close-report consultation).
#   - Skip P-H1 / P-TASKID / P-NESTED / P-CROSSREPO checks.
#   - Use the semantic private-index/CAS path.
#   - Use caller-supplied message verbatim (CALLER_MESSAGE, validated above).
#   - Create the commit object from a private index; no real-index staging.
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
#   4. audit JSON binding message hash, plan hash, parent, commit, files,
#      and backup recovery ref.
if [ "$MODE" = "force" ]; then
  # A2 mutual exclusion: --force-rescue chooses staged-set as patch source;
  # --manifest provides a different patch source. They cannot both be active
  # for the same commit — refuse at argv-parse with a specific error so the
  # operator does not silently route through the unintended path.
  if [ "$FORCE_RESCUE_MODE" -eq 1 ] && [ "$HAS_MANIFEST" -eq 1 ]; then
    echo "commit.sh: --force-rescue and --manifest are mutually exclusive (the patch source must come from exactly one authority — either the staged set or the manifest)" >&2
    exit 2
  fi
  COMMIT_MSG="$CALLER_MESSAGE"
  FORCE_TASK_SENTINEL="__force__"
  CLOSURE_KIND="force"
  CLOSE_VERDICT_OBSERVED="absent"
  if [ "$HAS_MANIFEST" -eq 1 ]; then
    # M12 routing constraint: --force --manifest MUST route around
    # build_semantic_plan_bundle (which exits 2 on mode=="force") by feeding the
    # manifest source-acquisition helper directly into the shared core. Audit
    # records mode="force-manifest" so log filtering can distinguish from plain
    # force (which today is dead-coded per W2).
    run_private_index_commit "$FORCE_TASK_SENTINEL" "force-manifest" "$CLOSURE_KIND" "$CLOSE_VERDICT_OBSERVED" "manifest"
    exit $?
  fi
  if [ "$FORCE_RESCUE_MODE" -eq 1 ]; then
    # A2: --force-rescue with pre-staged content. Patch source = staged delta.
    # Audit records mode="force-rescue" so log filtering can distinguish.
    run_private_index_commit "$FORCE_TASK_SENTINEL" "force-rescue" "$CLOSURE_KIND" "$CLOSE_VERDICT_OBSERVED" "force-rescue"
    exit $?
  fi
  run_private_index_commit "$FORCE_TASK_SENTINEL" "force" "$CLOSURE_KIND" "$CLOSE_VERDICT_OBSERVED"
  exit $?
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

# PRIMARY: close-report exists AND the shared verdict contract classifies the
# last non-empty CLOSE line as yes.
#
# P-CLOSEHONOR (ba-spec-20260426-redev5.md M5 / AC-CLOSEHONOR-1..4):
# When a close-report exists for the task-id, its verdict is AUTHORITATIVE.
#   yes → PRIMARY (current behavior preserved, AC-CLOSEHONOR-2)
#   no  → REFUSE the commit (AC-CLOSEHONOR-1) — do NOT fall through to SECONDARY
#   neither   → REFUSE (defensive; AC-CLOSEHONOR-4) — do NOT fall through
# This closes the SECONDARY back-door that previously admitted commits even
# when /close had returned a deliberate negative verdict.
if [ -f "$CLOSE_REPORT" ]; then
  # Last non-empty line — kept for diagnostic messages below (audit log /
  # exit-2 error output).  Verdict classification, however, MUST go through
  # the tolerant `classify-file` mode (W5 C1, ticket-20260511-070000 γ.AC1):
  # strict last-line check first, then fallback regex scan that accepts
  # decorated forms like `**Final verdict: CLOSE: YES**`. Using the strict
  # `classify-line` here would bypass the tolerant fallback and reject
  # legitimately-decorated close-reports at the production gate.
  LAST_NONEMPTY="$(tr -d '\r' < "$CLOSE_REPORT" | awk 'NF{line=$0} END{print line}')"
  VERDICT_KIND="$("$PYTHON_BIN" "$CLOSE_VERDICT_HELPER" classify-file "$CLOSE_REPORT" 2>/dev/null || echo unknown)"
  if [ "$VERDICT_KIND" = "yes" ]; then
    CLOSURE_PATH="$CLOSE_REPORT"
    CLOSURE_KIND="primary"
    CLOSE_VERDICT_OBSERVED="yes"
  elif [ "$VERDICT_KIND" = "no" ]; then
    CLOSE_VERDICT_OBSERVED="no"
    echo "task closed with verdict NO; cannot commit until /close passes" >&2
    echo "  close-report: ${CLOSE_REPORT}" >&2
    echo "  last non-empty line: ${LAST_NONEMPTY}" >&2
    exit 2
  else
    # close-report exists but the last line is not a recognized verdict — fail closed.
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
    QA_STATUS_OK="$("$PYTHON_BIN" -c "
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
      #   (c) H1 contains task-id — kept as legacy fallback.
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
      if "$PYTHON_BIN" -c "
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
      if "$PYTHON_BIN" -c "
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
# Step 3 — semantic private-index commit
# -----------------------------------------------------------------------------
COMMIT_MSG="$CALLER_MESSAGE"
# Closed-task mode supports an OPTIONAL --manifest precision input. When present,
# the plan is sourced from the manifest helper (which enforces named-integer
# schema + path hygiene + binary rejection + base_commit binding); when absent,
# the dev-report-driven build_semantic_plan_bundle is used as before. Audit
# emits mode="closed-task" in BOTH branches; the engine field distinguishes
# them ("semantic-commit" vs "manifest-commit").
if [ "$HAS_MANIFEST" -eq 1 ]; then
  run_private_index_commit "$TASK_ID" "closed-task" "$CLOSURE_KIND" "$CLOSE_VERDICT_OBSERVED" "manifest"
  exit $?
fi
run_private_index_commit "$TASK_ID" "closed-task" "$CLOSURE_KIND" "$CLOSE_VERDICT_OBSERVED"
exit $?
