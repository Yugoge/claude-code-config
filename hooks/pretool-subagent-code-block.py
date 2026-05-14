#!/usr/bin/env python3
"""PreToolUse:Write|Edit|NotebookEdit advisory shim (warn-only as of 2026-05-14).

Canonical enforcement: pretool-tool-policy.py + lib/policy_registry — this
hook is now registered in settings.json and authoritative. This shim was
originally a backstop for unregistered sessions; with tool-policy
authoritative, the shim is downgraded to advisory (exit 0 + stderr warning)
on every hit. Path-based denial of non-dev code writes is enforced by
pretool-tool-policy.py; this shim only emits a warning marker.
"""
from __future__ import annotations
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.agent_resolver import resolve_agent_type  # noqa: E402

CODE_PATTERN = re.compile(
    r"\.(svg|css|html|js|ts|tsx|jsx|py|pyi|go|rs|c|cpp|h|hpp|"
    r"java|mjs|cjs|rb|php|swift|kt)$",
    re.IGNORECASE,
)
WRITE_TOOLS = {"Write", "Edit", "NotebookEdit", "MultiEdit"}


def _target(tool_input: dict) -> str | None:
    if not isinstance(tool_input, dict):
        return None
    return tool_input.get("file_path") or tool_input.get("notebook_path")


def _warn_unregistered() -> None:
    """LOW-10 soft-policy: role unresolved -> warn + allow (was hard-block).

    Hard-block on unresolved role caused false positives when Claude Code
    dispatched subagents before any sentinel-creating tool fired (e.g. a
    second back-to-back `dev` worker in the same session). The strong
    invariant — wrong-role MUST NOT write code — is preserved by
    `_block_wrong_role`. Unresolved role degrades to advisory warning.
    """
    sys.stderr.write(
        "WARN (shim): unregistered subagent role; allowing write. "
        "(LOW-10 soft-policy; hard-block remains for resolved wrong-role)\n"
    )
    sys.exit(0)


def _block_wrong_role(role: str, target: str) -> None:
    sys.stderr.write(
        f"WARN (shim): role='{role}' attempting to write code file {target}. "
        "Only 'dev' should write source code. "
        "(Path-based denial is enforced by pretool-tool-policy.py; this shim is advisory.)\n"
    )
    sys.exit(0)


def _decide(data: dict, target: str) -> None:
    """Resolve role from stdin payload and apply the block matrix.

    - main agent (no agent_id) -> allow.
    - role 'dev' -> allow.
    - role None (subagent skipped sentinel) -> warn + allow (LOW-10 soft).
    - role any other -> block with role-specific message.
    """
    if not data.get("agent_id"):
        sys.exit(0)
    role = resolve_agent_type(data)
    if role == "dev":
        sys.exit(0)
    if role is None:
        _warn_unregistered()
    _block_wrong_role(role, target)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    if data.get("tool_name") not in WRITE_TOOLS:
        sys.exit(0)
    target = _target(data.get("tool_input") or {})
    if not target or not CODE_PATTERN.search(target):
        sys.exit(0)
    _decide(data, target)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
