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


def _read_match(path: str, agent_id: str) -> Optional[dict]:
    """Return cp-state dict if agent_id matches, else None.

    Unlike _match_cp_state (which returns just agent_type), this returns
    the full payload so disambiguation in _scan_cp_state_files can inspect
    is_running and checked_in_at without re-reading the file.
    """
    data = _read_json(path)
    if not data or data.get("agent_id") != agent_id:
        return None
    t = data.get("agent_type")
    if not isinstance(t, str):
        return None
    return data


def _pick_active(matches: list) -> Optional[str]:
    """Disambiguate among is_running=true matches.

    Cross-role active collision -> None (fail closed).
    Same-role active collision -> that agent_type.
    Single active -> its agent_type.
    """
    types = {m.get("agent_type") for m in matches}
    if len(types) > 1:
        return None  # F14 M8: cross-role active collision -> fail closed
    return next(iter(types))  # F14 M9: deterministic same-role active


def _scan_cp_state_files(agent_id: str, project_dir: str) -> Optional[str]:
    """F14: prefer is_running=true match; fail-closed on cross-role collision.

    Active-match preference: cp-state-spec-20260428-183820 incident showed
    stale qa cp-state could shadow a live dev subagent under first-glob bias.
    """
    pattern = f"{project_dir}/.claude/specs/*/cp-state-*.json"
    try:
        paths = glob.glob(pattern)
    except OSError:
        return None
    matches = [d for d in (_read_match(p, agent_id) for p in paths) if d]
    if not matches:
        return None
    active = [m for m in matches if m.get("is_running")]
    if active:
        return _pick_active(active)
    return matches[0].get("agent_type")  # legacy fallback (single match case)


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
