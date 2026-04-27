#!/usr/bin/env python3
"""Resolve subagent identity to agent_type string.

Refactored from pretool-subagent-code-block.py::_find_agent_type so that
multiple hooks (pretool-subagent-code-block.py, pretool-tool-policy.py)
can share one canonical lookup.

Resolution order (first hit wins):
  1. payload.subagent_type — if the runtime already injects the role label.
  2. payload.agent_id matched against /spec cp-state files.
  3. payload.agent_id matched against /dev dev-registry agent-index.json.
  4. None — caller decides (main agent or unknown).

Fail-safe: every I/O path is wrapped; on any unexpected exception we
return None rather than raise.
"""

from __future__ import annotations

import glob
import json
import os
from typing import Optional


def _read_json(path: str) -> Optional[dict]:
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _match_cp_state(path: str, agent_id: str) -> Optional[str]:
    data = _read_json(path)
    if not data or data.get("agent_id") != agent_id:
        return None
    t = data.get("agent_type")
    return t if isinstance(t, str) else None


def _scan_cp_state_files(agent_id: str, project_dir: str) -> Optional[str]:
    pattern = f"{project_dir}/.claude/specs/*/cp-state-*.json"
    try:
        paths = glob.glob(pattern)
    except OSError:
        return None
    for path in paths:
        hit = _match_cp_state(path, agent_id)
        if hit is not None:
            return hit
    return None


def _lookup_dev_registry_index(agent_id: str, project_dir: str) -> Optional[str]:
    index_path = f"{project_dir}/.claude/dev-registry/agent-index.json"
    data = _read_json(index_path)
    if not data:
        return None
    value = data.get(agent_id)
    return value if isinstance(value, str) else None


def _resolve_by_id(agent_id: str) -> Optional[str]:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    spec_hit = _scan_cp_state_files(agent_id, project_dir)
    if spec_hit is not None:
        return spec_hit
    return _lookup_dev_registry_index(agent_id, project_dir)


def resolve_agent_type(payload: dict) -> Optional[str]:
    """Public API: PreToolUse stdin payload -> agent_type or None."""
    if not isinstance(payload, dict):
        return None
    direct = payload.get("subagent_type")
    if isinstance(direct, str) and direct:
        return direct
    agent_id = payload.get("agent_id")
    if not agent_id or not isinstance(agent_id, str):
        return None
    return _resolve_by_id(agent_id)
