#!/usr/bin/env python3
"""PreToolUse hook: block non-dev subagents from writing code files.

Matcher: Write|Edit|NotebookEdit

Mechanism:
  1. If no agent_id in stdin -> main agent -> allow.
  2. If target file extension not in CODE_EXTENSIONS -> allow (docs, data, json).
  3. Scan $CLAUDE_PROJECT_DIR/.claude/specs/*/cp-state-*.json for matching
     agent_id (per-instance pin via payload.agent_id, same pattern as
     subagentstop-cp-enforce.py::_find_active_state).
  4. If not found -> fail-OPEN (non-/spec workflow) -> allow.
  5. If found and agent_type in ALLOWED_TYPES -> allow.
  6. Otherwise -> block (exit 2) with human-readable stderr.

Fails open on any unexpected exception to avoid breaking the tool pipeline.
"""

import glob
import json
import os
import sys
import time


ALLOWED_TYPES = {"dev"}

CODE_EXTENSIONS = {
    ".svg", ".css", ".html", ".js", ".ts", ".tsx", ".jsx",
    ".py", ".pyi", ".go", ".rs", ".c", ".cpp", ".h", ".hpp",
    ".java", ".mjs", ".cjs", ".rb", ".php", ".swift", ".kt",
}

# Approach Z (architect-20260424): a dev-family session dir older than this
# threshold is considered stale and does not trigger fail-closed enforcement.
# Rationale: /dev sessions complete in minutes to ~1h; 2h covers overnight
# edge cases. After that, any concurrent non-dev workflow (e.g. /clean) must
# not be falsely blocked by leftover session dirs.
MAX_SESSION_AGE_SECONDS = 7200

# Sentinel agent_type string used ONLY by the fail-closed branch when an
# unregistered subagent is detected during an active dev-family session.
# Chosen with leading/trailing underscores so it cannot collide with any
# real agent_type (which are bare identifiers like "ba", "qa", "dev").
_UNREGISTERED_DEV_SENTINEL = "__unregistered_dev_session__"


def _read_cp_state(path):
    """Load a cp-state file. Returns dict or None on I/O / JSON error."""
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _scan_cp_state_files(agent_id, project_dir):
    """/spec workflow lookup: scan cp-state files for matching agent_id."""
    pattern = f"{project_dir}/.claude/specs/*/cp-state-*.json"
    for path in glob.glob(pattern):
        data = _read_cp_state(path)
        if data and data.get("agent_id") == agent_id:
            return data.get("agent_type")
    return None


def _lookup_dev_registry_index(agent_id, project_dir):
    """/dev workflow lookup: consult dev-registry/agent-index.json.

    The index is written by pretool-cp-checkin.py when a subagent reads its
    sentinel file at .claude/dev-registry/<session_id>/<agent>.json. Root
    cause of the /dev gap: commit e086ccb scoped enforcement to /spec only;
    /dev sessions have no cp-state files, so _scan_cp_state_files returns
    None and the hook falls open. This secondary index closes that gap for
    any subagent that performs the sentinel Read as its first action.
    """
    index_path = f"{project_dir}/.claude/dev-registry/agent-index.json"
    data = _read_cp_state(index_path)
    if not data:
        return None
    value = data.get(agent_id)
    return value if isinstance(value, str) else None


def _is_dev_session_name(name):
    """Session dirs follow the orchestrator's naming convention."""
    return (
        name.startswith("dev-")
        or name.startswith("dev-command-")
        or name.startswith("dev-overnight-")
    )


def _is_fresh_nonempty_session(subdir, cutoff):
    """True if subdir mtime >= cutoff and contains >=1 .json sentinel."""
    try:
        if os.path.getmtime(subdir) < cutoff:
            return False
        return any(f.endswith(".json") for f in os.listdir(subdir))
    except OSError:
        return False


def _has_active_dev_session(project_dir):
    """Return True if any dev-registry session dir has sentinel files < 2h old.

    Approach Z helper: detects whether a /dev, /dev-command, or /dev-overnight
    orchestrator is currently active by scanning
    `.claude/dev-registry/<session>/` for fresh (age < MAX_SESSION_AGE_SECONDS)
    subdirs containing at least one .json sentinel.

    Fail-safe on OSError (registry dir missing) and on empty dirs (crashed
    orchestrator that ran mkdir but never wrote sentinels).

    See ba-spec-20260424-redev-A.md AC-A5 and AC-A5b.
    """
    base = os.path.join(project_dir, ".claude", "dev-registry")
    try:
        entries = os.listdir(base)
    except OSError:
        return False
    cutoff = time.time() - MAX_SESSION_AGE_SECONDS
    for name in entries:
        if not _is_dev_session_name(name):
            continue
        subdir = os.path.join(base, name)
        if not os.path.isdir(subdir):
            continue
        if _is_fresh_nonempty_session(subdir, cutoff):
            return True
    return False


def _find_agent_type(agent_id, project_dir):
    """Resolve agent_id to agent_type across both registration backends.

    1) /spec cp-state glob (existing) -- untouched; if a match is found there,
       return it immediately.
    2) /dev dev-registry agent-index (new) -- queried only when the cp-state
       scan misses, preserving the original fail-open semantics for /spec.
    """
    agent_type = _scan_cp_state_files(agent_id, project_dir)
    if agent_type is not None:
        return agent_type
    return _lookup_dev_registry_index(agent_id, project_dir)


def _get_target_path(tool_input):
    """Extract target file path from Write/Edit/NotebookEdit input."""
    return tool_input.get("file_path") or tool_input.get("notebook_path")


def _emit_block(agent_type, target):
    if agent_type == _UNREGISTERED_DEV_SENTINEL:
        sys.stderr.write(
            "BLOCKED: unregistered subagent in active dev-family session "
            "(skipped FIRST ACTION Read?). "
            "Only 'dev' subagent writes code (.svg/.css/.html/.js/.ts/.py/...). "
            "Your output: .md or .json.\n"
        )
        return
    sys.stderr.write(
        f"BLOCKED: '{agent_type}' cannot write code files. "
        f"Only 'dev' subagent writes code (.svg/.css/.html/.js/.ts/.py/...). "
        f"Your output: .md (docs) or .json (reports).\n"
    )


def _decide(agent_id, target):
    """Return (exit_code, agent_type_or_none) for given subagent + target."""
    ext = os.path.splitext(target)[1].lower()
    if ext not in CODE_EXTENSIONS:
        return 0, None
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    agent_type = _find_agent_type(agent_id, project_dir)
    if agent_type is None:
        # Approach Z (architect-20260424): fail-closed when a dev-family
        # session is active. An unregistered subagent here skipped its
        # FIRST ACTION sentinel Read. See ba-spec-20260424-redev-A.md AC-A1.
        if _has_active_dev_session(project_dir):
            return 2, _UNREGISTERED_DEV_SENTINEL
        return 0, None  # fail-open: no dev-family session active
    if agent_type in ALLOWED_TYPES:
        return 0, agent_type
    return 2, agent_type


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    agent_id = data.get("agent_id")
    if not agent_id:
        sys.exit(0)  # main agent -- allow
    target = _get_target_path(data.get("tool_input", {}))
    if not target:
        sys.exit(0)
    exit_code, agent_type = _decide(agent_id, target)
    if exit_code == 2:
        _emit_block(agent_type, target)
    sys.exit(exit_code)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
