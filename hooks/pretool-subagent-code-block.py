#!/usr/bin/env python3
"""PreToolUse:Write|Edit|NotebookEdit backstop shim.

Canonical enforcement: pretool-tool-policy.py + lib/policy_registry.
This shim remains as a backward-compat backstop for /spec /dev sessions
where the new policy hook is not yet registered in settings.json: blocks
code-file writes by any non-dev subagent and otherwise allows.
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


def _block_unregistered() -> None:
    """BUG-DEVREG-1: subagent context but role unresolved."""
    sys.stderr.write(
        "BLOCKED: unregistered subagent (read your dev-registry "
        "sentinel as FIRST ACTION before writing code)\n"
    )
    sys.exit(2)


def _block_wrong_role(role: str, target: str) -> None:
    sys.stderr.write(
        f"BLOCKED (shim): role='{role}' cannot write code file {target}. "
        "Only 'dev' may write source code.\n"
    )
    sys.exit(2)


def _decide(data: dict, target: str) -> None:
    """Resolve role from stdin payload and apply the block matrix.

    - main agent (no agent_id) -> allow.
    - role 'dev' -> allow.
    - role None (subagent skipped sentinel) -> block (BUG-DEVREG-1).
    - role any other -> block with role-specific message.
    """
    if not data.get("agent_id"):
        sys.exit(0)
    role = resolve_agent_type(data)
    if role == "dev":
        sys.exit(0)
    if role is None:
        _block_unregistered()
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
