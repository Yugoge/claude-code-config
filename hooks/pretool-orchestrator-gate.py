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


SUBAGENT_ID_KEYS = (
    "agent_id",
    # Codex compatibility runtimes may not preserve Claude's exact
    # `agent_id` field name in PreToolUse stdin.  Treat these as identity
    # aliases so the orchestrator-only gate remains main-agent-only.
    "subagent_id",
    "agent_path",
    "parent_agent_id",
)

SUBAGENT_ENV_KEYS = (
    "CLAUDE_AGENT_ID",
    # Codex/native agent runners use their own naming in some builds.
    "CODEX_AGENT_ID",
    "CODEX_AGENT_PATH",
    "OPENAI_AGENT_ID",
    # T1.5 (redev-tier123): codex compat runtime sets CLAUDE_COMPAT_RUNTIME=codex
    # in child Bash environments via .codex/hooks/claude_legacy_hook_wrapper.py.
    # Treat its presence as subagent context so codex-driven Bash bursts do not
    # increment the main-agent orchestrator-gate streak counter.
    "CLAUDE_COMPAT_RUNTIME",
)

def get_session_id(data: dict) -> str:
    sid = data.get("session_id") or os.environ.get("CLAUDE_SESSION_ID", "")
    if sid:
        return sid
    sys.stderr.write("[Orchestrator Gate] WARNING: session_id unavailable, using shared default\n")
    return "default"


def _truthy(value) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip() not in {"", "0", "false", "False", "null", "None"}
    return bool(value)


def _transcript_meta_says_subagent(transcript_path: str) -> bool:
    """Detect Codex spawned-agent transcripts from their session metadata."""
    if not transcript_path:
        return False
    path = Path(transcript_path)
    try:
        with path.open(errors="ignore") as fh:
            for _ in range(20):
                line = fh.readline()
                if not line:
                    break
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") != "session_meta":
                    continue
                payload = event.get("payload", {})
                source = payload.get("source")
                return isinstance(source, dict) and isinstance(source.get("subagent"), dict)
    except OSError:
        return False
    return False


def is_subagent_context(data: dict) -> bool:
    """Return True when this hook is running inside a subagent.

    The canonical Claude hook payload contains top-level `agent_id`.  Codex
    compatibility can run the same hook without that exact field even though
    the call is inside a spawned agent.  This helper accepts equivalent
    top-level identity aliases and environment aliases, but deliberately does
    not inspect `tool_input.subagent_type`: that field belongs to main-agent
    Agent dispatch calls and would incorrectly exempt the orchestrator.
    """
    if any(_truthy(data.get(key)) for key in SUBAGENT_ID_KEYS):
        return True
    if any(_truthy(os.environ.get(key)) for key in SUBAGENT_ENV_KEYS):
        return True

    # Codex compatibility note:
    # Spawned agents may arrive without `agent_id` or agent-specific env vars.
    # Their transcript's session_meta source is structured as
    # {"subagent": {"thread_spawn": ...}}. Use that as the authoritative
    # fallback instead of text-searching parent transcripts, because subagent
    # transcripts often mention the parent/root id in prompts.
    if _transcript_meta_says_subagent(str(data.get("transcript_path") or "").strip()):
        return True

    return False


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

    if is_subagent_context(data):
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
