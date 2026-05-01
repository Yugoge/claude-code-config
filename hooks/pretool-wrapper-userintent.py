#!/usr/bin/env python3
"""PreToolUse hook: enforce user-intent sentinel for commit/push/merge wrappers.

Mirrors the /allow pattern — both writer (UserPromptSubmit prompt-workflow.py)
and reader (this PreToolUse hook) live in hook context, so both resolve the
real session_id from stdin JSON. Sid-keyed flags work because both ends agree.

Wrapper scripts (commit.sh / push.sh / merge.sh) carry NO sentinel logic
themselves — they're pure git workers, gated at the hook entrance.
"""
import json
import os
import shlex
import sys
import time
from pathlib import Path

WRAPPERS = ("commit", "push", "merge", "stop")
LAUNCHERS = ("bash", "sh", "exec", "source", ".")
SENTINEL_TTL_SECONDS = 1800  # 30min — covers debug-iterate cycles + session-resume edge cases; expires multi-hour-stale intent


def _is_invocation(tokens: list, i: int) -> bool:
    prev = tokens[i - 1] if i > 0 else ""
    return i == 0 or prev in LAUNCHERS


def _wrapper_at(token: str) -> str:
    base = token.split("/")[-1]
    if base.endswith(".sh") and base[:-3] in WRAPPERS:
        return base[:-3]
    return ""


def _detect_wrapper(cmd: str) -> str:
    try:
        tokens = shlex.split(cmd, posix=True)
    except ValueError:
        tokens = cmd.split()
    for i, t in enumerate(tokens):
        w = _wrapper_at(t)
        if w and _is_invocation(tokens, i):
            return w
    return ""


def _check(wrapper: str, sid: str) -> int:
    flag = Path(f"/tmp/claude-{wrapper}-userintent-{sid}.flag")
    if not flag.exists():
        sys.stderr.write(
            f"BLOCKED: {wrapper}.sh requires user-intent sentinel — "
            f"invoke via /{wrapper} slash command (model agents cannot self-invoke).\n"
        )
        return 2
    try:
        age = time.time() - flag.stat().st_mtime
    except OSError:
        age = 0
    if age > SENTINEL_TTL_SECONDS:
        # Do NOT unlink on expire — leave the file so a fresh /{wrapper} can
        # overwrite-with-new-mtime and recover without a manual rm. Stale
        # intent is gated by the age check, not by deletion.
        sys.stderr.write(
            f"BLOCKED: {wrapper}.sh user-intent sentinel expired (age {int(age)}s > {SENTINEL_TTL_SECONDS}s); "
            f"re-invoke /{wrapper}.\n"
        )
        return 2
    # Do NOT unlink on the gate path — wrappers consume on success only
    # (commit.sh removes the sentinel at the success path; failure leaves it
    # for retry within the TTL window without forcing the user to re-type).
    return 0


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if data.get("tool_name") != "Bash":
        return 0
    cmd = data.get("tool_input", {}).get("command", "") or ""
    wrapper = _detect_wrapper(cmd)
    if not wrapper:
        return 0
    # Bridge mode is internal to /dev-overnight (auto-bulk per-cycle commits) —
    # /dev-overnight has its own user-intent gate (the slash invocation), so
    # the per-Bash sentinel does not apply. Recognize the flag and let through.
    if "--auto-bulk-bridge" in cmd:
        return 0
    sid = data.get("session_id") or os.environ.get("CLAUDE_SESSION_ID", "default")
    return _check(wrapper, sid)


if __name__ == "__main__":
    sys.exit(main())
