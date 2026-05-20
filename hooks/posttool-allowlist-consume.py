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
from lib.allowlist import (  # noqa: E402
    consume_grant_for_posttool,
    consume_sentinel_grant_on_terminal_result,
)


def _classify_terminal_result(data: dict) -> str:
    """Classify the posttool terminal-result for sentinel consumption.

    Implements consume-on-any-terminal-result: every terminal outcome
    (success, failure, non_zero exit, malformed grant, comment_only attack)
    unlinks the sentinel. The returned label is logged but the unlink is
    unconditional.

    Returns one of: "success", "failure", "non_zero", "malformed",
                    "comment_only", "unknown_terminal".
    """
    response = data.get("tool_response") or {}
    if isinstance(response, dict):
        if response.get("is_error"):
            return "failure"
        exit_code = response.get("exit_code")
        if isinstance(exit_code, int):
            if exit_code == 0:
                return "success"
            if 1 <= exit_code <= 255:
                return "non_zero"
    return "unknown_terminal"


def main() -> None:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        # Malformed posttool input — still reap the sentinel for the
        # comment_only / malformed terminal case.
        task_id = os.environ.get("CLAUDE_TASK_ID", "")
        if task_id:
            consume_sentinel_grant_on_terminal_result(task_id, "malformed")
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

    # Sentinel-grant consume-on-any-terminal-result (task 20260519-211515 R2 / AC2).
    #
    # CF-2 scoping (codex iter-1 BLOCKER): the sentinel grants bash-command
    # authorization. PostToolUse fires for EVERY tool (matcher "*"), so an
    # unrelated Read/Grep/Glob call after `/allow` could otherwise unlink the
    # sentinel before the intended Bash call. We restrict sentinel consumption
    # to Bash terminal results AND only when the sentinel actually matched
    # this command structurally (`match_sentinel_grant_for_bash_command`).
    # The four mandated terminal cases (success/failure/non_zero/malformed)
    # are all hit only when Bash itself fires; non-Bash tool events skip the
    # sentinel-consume path entirely.
    task_id = (
        data.get("task_id")
        or os.environ.get("CLAUDE_TASK_ID")
        or session_id
    )
    if task_id and tool_name == "Bash":
        try:
            from lib.allowlist import (  # noqa: E402
                match_sentinel_grant_for_bash_command,
                load_sentinel_grant_for_task,
                _enumerate_sentinel_grant_files,
            )
        except Exception:
            match_sentinel_grant_for_bash_command = None
            load_sentinel_grant_for_task = None
            _enumerate_sentinel_grant_files = None
        terminal_result = _classify_terminal_result(data)
        should_consume = False
        if match_sentinel_grant_for_bash_command is not None:
            try:
                m = match_sentinel_grant_for_bash_command(task_id, command)
                if m is not None:
                    should_consume = True
            except Exception:
                should_consume = True
                terminal_result = "malformed"
        # Malformed-grant terminal case: a sentinel file exists for this task
        # but load_sentinel_grant_for_task returned None (parse failure or
        # expired). The AC2 contract requires unlink on malformed.
        if (not should_consume) and load_sentinel_grant_for_task is not None \
                and _enumerate_sentinel_grant_files is not None:
            try:
                if _enumerate_sentinel_grant_files(task_id) and load_sentinel_grant_for_task(task_id) is None:
                    should_consume = True
                    terminal_result = "malformed"
            except Exception:
                pass
        if should_consume:
            consume_sentinel_grant_on_terminal_result(task_id, terminal_result)
    sys.exit(0)


if __name__ == "__main__":
    main()
