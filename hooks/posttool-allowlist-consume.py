#!/usr/bin/env python3
"""
PostToolUse Hook: /allow grant consumption.

Atomically deletes the /allow grant file after a tool executes successfully.
PreToolUse hooks are now read-only grant checkers; this hook is the sole
consume point. Main-agent only (subagents are exempt).

PostToolUse fires only when all PreToolUse hooks exit 0 (tool was allowed).
If any PreToolUse hook exits 2, PostToolUse never fires — grant persists
for retry. This is correct UX: user can retry with the same grant.

Exit 0 always (fail-open). Silently exits if no grant or no match.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.subagent import is_subagent_context  # noqa: E402
from lib.allowlist import consume_grant_for_posttool  # noqa: E402


def _split_bash_command(cmd: str) -> list:
    """Split a compound Bash command on &&, ||, ;, | separators.

    Mirrors pretool-bash-safety.sh split_subcommands (lines 227-230):
    process || before | so '||' becomes a double-newline, not two pipes.
    """
    # Order matters: || must be replaced before |
    s = cmd.replace("||", "\n\n").replace("&&", "\n").replace(";", "\n").replace("|", "\n")
    return [t.strip() for t in s.split("\n") if t.strip()]


def main() -> None:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        sys.exit(0)

    # Main-agent only — subagents are exempt
    if is_subagent_context(data):
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    session_id = data.get("session_id") or os.environ.get("CLAUDE_SESSION_ID", "default")

    if tool_name == "Bash":
        command = (data.get("tool_input") or {}).get("command", "")
    else:
        command = ""

    consume_grant_for_posttool(session_id, tool_name, command)
    sys.exit(0)


if __name__ == "__main__":
    main()
