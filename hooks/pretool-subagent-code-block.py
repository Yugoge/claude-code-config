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


ALLOWED_TYPES = {"dev"}

CODE_EXTENSIONS = {
    ".svg", ".css", ".html", ".js", ".ts", ".tsx", ".jsx",
    ".py", ".pyi", ".go", ".rs", ".c", ".cpp", ".h", ".hpp",
    ".java", ".mjs", ".cjs", ".rb", ".php", ".swift", ".kt",
}


def _read_cp_state(path):
    """Load a cp-state file. Returns dict or None on I/O / JSON error."""
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _find_agent_type(agent_id, project_dir):
    """Scan cp-state files for matching agent_id, return agent_type or None."""
    pattern = f"{project_dir}/.claude/specs/*/cp-state-*.json"
    for path in glob.glob(pattern):
        data = _read_cp_state(path)
        if data and data.get("agent_id") == agent_id:
            return data.get("agent_type")
    return None


def _get_target_path(tool_input):
    """Extract target file path from Write/Edit/NotebookEdit input."""
    return tool_input.get("file_path") or tool_input.get("notebook_path")


def _emit_block(agent_type, target):
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
        return 0, None  # fail-open: non-/spec workflow
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
