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
#   Candidate order:
#     1. $CLAUDE_DOCS_DIR  (new dedicated override)
#     2. $CLAUDE_PROJECT_DIR  (back-compat)
#     3. cwd's git toplevel
#     4. pwd
#     5. /root  (final fallback / legacy harness-root safety net)
DOCS_DIR_ROOT=""
for _cand in "${CLAUDE_DOCS_DIR:-}" "${CLAUDE_PROJECT_DIR:-}" "$(git rev-parse --show-toplevel 2>/dev/null || true)" "$(pwd)" "/root"; do
  [ -z "$_cand" ] && continue
  if [ -d "${_cand}/docs/dev" ]; then
    DOCS_DIR_ROOT="$_cand"
    break
  fi
done
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
    print("commit.sh: --force cannot infer task ownership safely; use a closed task-id semantic commit", file=sys.stderr)
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
    cleaned = value.strip().strip("`'\".,;)")
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

if non_doc_repos:
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

run_backup_only_push() {
  local repo_root="$1"
  local branch="$2"
  local commit_sha="$3"
  local short_sha="${commit_sha:0:12}"
  local backup_ref="refs/backups/claude/${branch}/${short_sha}"
  local backup_log="${CLAUDE_BACKUP_LOG:-${CLAUDE_LOG_DIR}/post-commit-auto-push.log}"
  local remote="${CLAUDE_BACKUP_REMOTE:-origin}"

  if ! git -C "$repo_root" check-ref-format "$backup_ref" >/dev/null 2>&1; then
    backup_ref="refs/backups/claude/detached/${short_sha}"
  fi
  mkdir -p "$(dirname "$backup_log")"
  git -C "$repo_root" update-ref "$backup_ref" "$commit_sha" 2>>"$backup_log" || true

  if git -C "$repo_root" remote get-url "$remote" >/dev/null 2>&1; then
    (
      git -C "$repo_root" push "$remote" "${commit_sha}:${backup_ref}" >>"$backup_log" 2>&1 || \
        printf '%s backup push failed remote=%s ref=%s sha=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$remote" "$backup_ref" "$commit_sha" >>"$backup_log"
    ) &
  else
    printf '%s backup push skipped remote=%s ref=%s sha=%s reason=remote-missing\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$remote" "$backup_ref" "$commit_sha" >>"$backup_log"
  fi

  printf '%s\n' "$backup_ref"
}

run_semantic_plan_commit() {
  local task_id="$1"
  local mode="$2"
  local closure_kind="$3"
  local close_verdict="$4"

  local tmp_dir patch_file meta_file
  tmp_dir="$(mktemp -d "${CLAUDE_TMPDIR%/}/claude-commit-plan-XXXXXX")"
  patch_file="${tmp_dir}/bundle.patch"
  meta_file="${tmp_dir}/plan-meta.json"
  build_semantic_plan_bundle "$task_id" "$mode" "$patch_file" "$meta_file" || {
    rm -rf "$tmp_dir"
    return 2
  }

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
  real_index_before="$(real_index_fingerprint "$repo_root")"
  staged_list_before="$(staged_file_list "$repo_root")"
  private_index="${tmp_dir}/index"

  GIT_INDEX_FILE="$private_index" git -C "$repo_root" read-tree "$expected_parent"
  if ! GIT_INDEX_FILE="$private_index" git -C "$repo_root" apply --cached --3way "$patch_file" 2>"${tmp_dir}/apply.err"; then
    echo "commit.sh: semantic plan conflict/overlap; branch, worktree, and real index were not mutated" >&2
    cat "${tmp_dir}/apply.err" >&2
    rm -rf "$tmp_dir"
    return 2
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
  if ! "$PYTHON_BIN" - "$meta_file" "$files_json" <<'PY'
import json
import sys

meta = json.load(open(sys.argv[1]))
patch_files = set(json.loads(sys.argv[2]))
semantic_files = {item["path"] for item in meta.get("semantic_files", [])}
missing = sorted(patch_files - semantic_files)
if missing:
    print("commit.sh: semantic plan missing ownership rationale for path(s): " + ", ".join(missing), file=sys.stderr)
    sys.exit(2)
PY
  then
    rm -rf "$tmp_dir"
    return 2
  fi
  if [ "${#plan_files[@]}" -gt 0 ]; then
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
  if [ "$staged_list_after" != "$staged_list_before" ]; then
    echo "commit.sh: staged-file list changed during semantic commit; refusing because shared staged ownership was not preserved" >&2
    printf 'before:\n%s\n' "$staged_list_before" >&2
    printf 'after:\n%s\n' "$staged_list_after" >&2
    rm -rf "$tmp_dir"
    return 2
  fi

  backup_ref="$(run_backup_only_push "$repo_root" "$branch" "$new_commit")"

  mkdir -p "$(dirname "$LOG_PATH")"
  local sid nonce ppid_val msg_sha_short ts audit_json
  sid="${CLAUDE_SESSION_ID:-$$}"
  nonce="$("$PYTHON_BIN" -c "import secrets; print(secrets.token_hex(16))")"
  ppid_val="$$"
  msg_sha_short="$("$PYTHON_BIN" -c "import hashlib, sys; print(hashlib.sha256(sys.argv[1].encode('utf-8')).hexdigest()[:12])" "$COMMIT_MSG")"
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  audit_json="${CLAUDE_LOG_DIR}/commit-semantic-${sid}-${nonce}.json"
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

  "$PYTHON_BIN" - "$audit_json" "$ts" "$sid" "$task_id" "$mode" "$branch" "$expected_parent" "$new_commit" "$plan_sha" "$plan_id" "$plan_base" "$files_json" "$plan_semantic" "$plan_excluded" "$backup_ref" "$closure_kind" "$close_verdict" "$MESSAGE_SOURCE" "$staged_before_json" "$staged_after_json" "$real_index_before" "$real_index_after" <<'PY'
import json
import sys

(path, ts, sid, task_id, mode, branch, parent, commit, plan_sha,
 plan_id, plan_base, files_json, semantic_json, excluded_json,
 backup_ref, closure_kind, close_verdict, message_source, staged_before_json,
 staged_after_json, index_before, index_after) = sys.argv[1:23]
data = {
    "timestamp": ts,
    "sid": sid,
    "command_kind": "commit",
    "engine": "semantic-commit",
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
with open(path, "w") as fh:
    json.dump(data, fh, indent=2, sort_keys=True)
PY

  "$PYTHON_BIN" - "$LOG_PATH" "$ts" "$sid" "$task_id" "$mode" "$nonce" "$ppid_val" "$msg_sha_short" "$new_commit" "$expected_parent" "$plan_sha" "$backup_ref" "$files_json" "$closure_kind" "$close_verdict" "$MESSAGE_SOURCE" "$audit_json" <<'PY'
import json
import sys

(path, ts, sid, task_id, mode, nonce, ppid_val, msg_sha_short, head,
 parent, plan_sha, backup_ref, files_json, closure_kind,
 close_verdict, message_source, audit_json) = sys.argv[1:18]
line = {
    "timestamp": ts,
    "sid": sid,
    "command_kind": "commit",
    "engine": "semantic-commit",
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
  COMMIT_MSG="$CALLER_MESSAGE"
  FORCE_TASK_SENTINEL="__force__"
  CLOSURE_KIND="force"
  CLOSE_VERDICT_OBSERVED="absent"
  run_semantic_plan_commit "$FORCE_TASK_SENTINEL" "force" "$CLOSURE_KIND" "$CLOSE_VERDICT_OBSERVED"
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
  # Last non-empty line — strip CR, drop blank lines, take final survivor.
  LAST_NONEMPTY="$(tr -d '\r' < "$CLOSE_REPORT" | awk 'NF{line=$0} END{print line}')"
  VERDICT_KIND="$("$PYTHON_BIN" "$CLOSE_VERDICT_HELPER" classify-line "$LAST_NONEMPTY" 2>/dev/null || echo unknown)"
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
run_semantic_plan_commit "$TASK_ID" "closed-task" "$CLOSURE_KIND" "$CLOSE_VERDICT_OBSERVED"
exit $?
