#!/usr/bin/env python3
"""
PreToolUse Hook: Block foreground Agent during an active /spec Interview.

Activation conditions (ALL must be true to block):
  1. tool_name == "Agent"
  2. tool_input.get("run_in_background") is not True
     (background Explore agents are explicitly allowed by spec.md
      Interview Rule 5)
  3. data.get("agent_id") is falsy
     (nested subagent calls are exempt -- field name "agent_id" matches
      pretool-orchestrator-gate.py:71 and pretool-read-size-guard.py:23)
  4. The workflow bookmark at
       $CLAUDE_PROJECT_DIR/.claude/workflow-<sid>.json
     exists AND has command == "spec"
  5. The official todos file at
       ~/.claude/todos/<sid>-agent-<sid>.json
     exists AND has at least one step where status != "completed"

Exit 0 = allow. Exit 2 = block (stderr message shown to user).

Fail-open: any unexpected exception -> sys.exit(0). Never block on
malformed input, missing env vars, or corrupt state files.
"""

import json
import os
import sys
from pathlib import Path


def _official_todos_path(session_id: str) -> Path:
    return Path.home() / ".claude" / "todos" / f"{session_id}-agent-{session_id}.json"


def _workflow_bookmark_path(session_id: str) -> Path:
    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    return project_dir / ".claude" / f"workflow-{session_id}.json"


def _load_json(path: Path):
    """Read and json-parse a file. Return None on any failure."""
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _should_block(data: dict) -> tuple[bool, int, int]:
    """Evaluate all 5 activation conditions.

    Returns (block, done_count, total_count). When block is False the
    counts are zero.
    """
    # Condition 1: Agent tool only
    if data.get("tool_name") != "Agent":
        return False, 0, 0

    tool_input = data.get("tool_input") or {}

    # Condition 2: foreground Agent only
    if tool_input.get("run_in_background") is True:
        return False, 0, 0

    # Condition 3: subagent-initiated Agent calls are exempt
    if data.get("agent_id"):
        return False, 0, 0

    session_id = data.get("session_id") or "default"

    # Condition 4: bookmark exists AND command == "spec"
    bookmark = _load_json(_workflow_bookmark_path(session_id))
    if not isinstance(bookmark, dict):
        return False, 0, 0
    if bookmark.get("command") != "spec":
        return False, 0, 0

    # Condition 5: todos file exists AND has at least one non-completed step
    todos = _load_json(_official_todos_path(session_id))
    if not isinstance(todos, list) or not todos:
        return False, 0, 0

    total = len(todos)
    done = sum(1 for t in todos if isinstance(t, dict) and t.get("status") == "completed")
    if done >= total:
        return False, 0, 0

    return True, done, total


def _emit_block_message(done: int, total: int) -> None:
    """Write the multi-line block explanation to stderr."""
    sys.stderr.write(
        "SPEC INTERVIEW IN PROGRESS\n"
        f"A /spec interview is currently active ({done}/{total} steps complete).\n"
        "Foreground Agent calls are blocked until the interview finishes.\n"
        "To unblock:\n"
        f"  - Continue the interview and complete all {total} steps\n"
        "  - OR mark all todos completed via TodoWrite\n"
        "Background agents (run_in_background: true) are always allowed "
        "during the interview.\n"
    )


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        # Fail-open on malformed stdin
        sys.exit(0)

    try:
        block, done, total = _should_block(data)
    except Exception:
        # Fail-open on any unexpected error inside the evaluator
        sys.exit(0)

    if block:
        _emit_block_message(done, total)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
