#!/usr/bin/env python3
"""
PreToolUse Hook: Orchestrator Gate (Unified)

Three-tier policy for the main agent:
  1. ALWAYS_ALLOWED whitelist tools pass, but Bash is capped at 3
     consecutive same-name calls (4th blocked).
  2. Non-whitelist tools are allowed once per consecutive same-name
     streak (2nd same-name call blocked).
  3. PERMANENTLY_BLOCKED (EnterPlanMode, ExitPlanMode) are always
     blocked, even with /do consent.

Subagents (agent_id present) are fully exempt and do NOT update
the streak state.

/do consent (Design A) bypasses streak checks AND does not update
the streak state, preserving clean exit semantics.

State file: /tmp/claude-tool-streak-<sid>.json -- {"last_tool": str, "count": int}
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

BASH_MAX_CONSECUTIVE = 3
NON_WHITELIST_MAX_CONSECUTIVE = 1


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


def get_streak_state_file(session_id: str) -> Path:
    return Path(f"/tmp/claude-tool-streak-{session_id}.json")


def _parse_streak_state(data) -> dict:
    if not isinstance(data, dict):
        return {"last_tool": "", "count": 0}
    last_tool = data.get("last_tool", "")
    count = data.get("count", 0)
    if isinstance(last_tool, str) and isinstance(count, int):
        return {"last_tool": last_tool, "count": count}
    return {"last_tool": "", "count": 0}


def read_streak_state(state_file: Path) -> dict:
    try:
        if state_file.exists():
            return _parse_streak_state(json.loads(state_file.read_text()))
    except (ValueError, OSError, json.JSONDecodeError):
        pass
    return {"last_tool": "", "count": 0}


def write_streak_state(state_file: Path, state: dict) -> None:
    try:
        state_file.write_text(json.dumps(state))
    except OSError:
        pass


def update_streak(state_file: Path, tool_name: str) -> int:
    state = read_streak_state(state_file)
    if tool_name == state["last_tool"]:
        state["count"] += 1
    else:
        state = {"last_tool": tool_name, "count": 1}
    write_streak_state(state_file, state)
    return state["count"]


def block_permanent(tool_name: str) -> None:
    allowed = ", ".join(sorted(ALWAYS_ALLOWED))
    sys.stderr.write(
        f"[Orchestrator Gate] Permanently blocked: {tool_name}\n"
        f"Delegate to subagents (Agent tool) or run /do to unlock.\n"
        f"Allowed without /do: {allowed}\n"
    )
    sys.exit(2)


def block_streak(tool_name: str, count: int, limit: int) -> None:
    sys.stderr.write(
        f"[Orchestrator Gate] BLOCKED: {tool_name} used consecutively beyond limit ({count}/{limit}).\n"
        f"Delegate to a subagent (Agent tool) or ask the user to run /do to unlock.\n"
    )
    sys.exit(2)


def enforce_streak_limit(tool_name: str, count: int) -> None:
    if tool_name in ALWAYS_ALLOWED:
        if tool_name == "Bash" and count > BASH_MAX_CONSECUTIVE:
            block_streak(tool_name, count, BASH_MAX_CONSECUTIVE)
        return
    if count > NON_WHITELIST_MAX_CONSECUTIVE:
        block_streak(tool_name, count, NON_WHITELIST_MAX_CONSECUTIVE)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    if bool(data.get("agent_id")):
        sys.exit(0)

    if tool_name in PERMANENTLY_BLOCKED:
        block_permanent(tool_name)

    sid = get_session_id(data)
    if has_consent(sid):
        sys.exit(0)

    count = update_streak(get_streak_state_file(sid), tool_name)
    enforce_streak_limit(tool_name, count)
    sys.exit(0)


if __name__ == "__main__":
    main()
