#!/usr/bin/env python3
"""
PreToolUse Hook: Orchestrator Gate

Allowlist-based: only ALWAYS_ALLOWED tools pass without consent.
Subagents (agent_id present) are never blocked.
EnterPlanMode/ExitPlanMode are permanently blocked even with /do.
"""

import json
import os
import sys
from pathlib import Path

ALWAYS_ALLOWED = {
    "Agent",
    "TodoWrite",
    "AskUserQuestion",
    "Skill",
    "CronCreate",
    "CronDelete",
    "CronList",
    "ScheduleWakeup",
    "mcp__happy__change_title",
    "Bash",
    "Read",
    "Glob",
    "Grep",
}

PERMANENTLY_BLOCKED = {
    "EnterPlanMode",
    "ExitPlanMode",
}


def get_session_id(data: dict) -> str:
    sid = data.get("session_id") or os.environ.get("CLAUDE_SESSION_ID", "")
    if sid:
        return sid
    sys.stderr.write("[Orchestrator Gate] WARNING: session_id unavailable, using shared default\n")
    return "default"


def has_consent(session_id: str) -> bool:
    flag = Path(f"/tmp/claude-orchestrator-consent-{session_id}.flag")
    try:
        return flag.exists() and flag.read_text().strip() == "true"
    except Exception:
        return False


def block(tool_name: str, reason: str) -> None:
    allowed = ", ".join(sorted(ALWAYS_ALLOWED))
    sys.stderr.write(
        f"[Orchestrator Gate] {reason}: {tool_name}\n"
        f"Delegate to subagents (Agent tool) or run /do to unlock.\n"
        f"Allowed without /do: {allowed}\n"
    )
    sys.exit(2)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    if bool(data.get("agent_id")):
        sys.exit(0)

    if tool_name in PERMANENTLY_BLOCKED:
        block(tool_name, "Permanently blocked")

    if tool_name in ALWAYS_ALLOWED:
        sys.exit(0)

    if has_consent(get_session_id(data)):
        sys.exit(0)

    block(tool_name, "Blocked")


if __name__ == "__main__":
    main()
