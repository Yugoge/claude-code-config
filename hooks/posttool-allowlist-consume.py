#!/usr/bin/env python3
"""
PostToolUse Hook: /allow grant consumption.

Atomically deletes the /allow grant file after a tool executes successfully.
PreToolUse hooks are now read-only grant checkers; this hook is the sole
consume point. Main-agent only (subagents are exempt).

PostToolUse fires only when all PreToolUse hooks exit 0 (tool was allowed).
If any PreToolUse hook exits 2, PostToolUse never fires — grant persists
for retry. This is correct UX: user can retry with the same grant.

Sentinel-grant consume-on-any-terminal-result semantic (task 20260519-211515
R2 / AC2): in addition to consuming the legacy pattern-string grant, this
hook also unlinks any sentinel grant at /tmp/claude-grants/<task_id>.json
when ANY terminal result is observed for the wrapped tool. The four mandated
terminal-consumption cases are: success (exit 0), failure / non_zero exit
(1..255), malformed grant JSON, and comment_only attack (the magic phrase
appears in the command but no sentinel JSON exists). All four unlink the
sentinel grant unconditionally — this is the consume-on-any-terminal-result
contract documented verbatim below.

Exit 0 always (fail-open). Silently exits if no grant or no match.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.subagent import is_subagent_context  # noqa: E402
from lib.allowlist import consume_grant_for_posttool  # noqa: E402


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
