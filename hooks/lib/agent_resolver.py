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

LOW-10 (2026-05-07): callers MUST NOT hard-block on `None`. Claude Code
may dispatch subagents before any sentinel-creating tool runs, so the
agent-index entry can legitimately be missing during the first write.
The canonical contract is: hard-block on resolved-but-wrong role; for
None, degrade to warn + allow. See pretool-subagent-code-block.py.
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


def _lookup_dev_registry_index(agent_id: str, project_dir: str) -> Optional[str]:
    index_path = f"{project_dir}/.claude/dev-registry/agent-index.json"
    data = _read_json(index_path)
    if not data:
        return None
    value = data.get(agent_id)
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        t = value.get("agent_type")
        return t if isinstance(t, str) else None
    return None


def resolve_dev_registry_entry(agent_id: str, project_dir: str) -> Optional[dict]:
    """Return a normalized entry dict for agent_id, or None.

    Always returns {"agent_type": str, "dev_session_id": str|None}.
    Handles both legacy flat-string values (wraps as {"agent_type": value,
    "dev_session_id": None}) and M0 object values (normalizes via .get()
    so missing keys never cause KeyError on malformed entries).
    Returns None when agent_id is absent, agent_type is not a str, or
    any I/O error occurs.
    Used by posttool-codex-skill-ledger.py and subagentstop-codex-enforce.py
    to access both agent_type AND dev_session_id from a single index read.
    """
    index_path = f"{project_dir}/.claude/dev-registry/agent-index.json"
    data = _read_json(index_path)
    if not data:
        return None
    value = data.get(agent_id)
    if isinstance(value, str):
        return {"agent_type": value, "dev_session_id": None}
    if isinstance(value, dict):
        t = value.get("agent_type")
        if not isinstance(t, str):
            return None
        return {"agent_type": t, "dev_session_id": value.get("dev_session_id")}
    return None


_FAIL_CLOSED = object()  # sentinel: cross-role active collision -> deny


def _glob_cp_state(project_dir: str) -> list:
    pattern = f"{project_dir}/.claude/specs/*/cp-state-*.json"
    try:
        return glob.glob(pattern)
    except OSError:
        return []


def _scan_cp_state_files(agent_id: str, project_dir: str):
    """Tri-state cp-state scan.

    Returns: agent_type str | _FAIL_CLOSED sentinel | None.
      - str: a single resolved active match (F14 M9)
      - _FAIL_CLOSED: active cross-role collision (F14 M8 fail-closed);
        caller MUST NOT fall through to agent-index.
      - None: no match or inactive-only (AC-3 non-authoritative); caller
        MAY fall through to agent-index.
    """
    paths = _glob_cp_state(project_dir)
    matches = [d for d in (_read_match(p, agent_id) for p in paths) if d]
    if not matches:
        return None
    active = [m for m in matches if m.get("is_running")]
    if not active:
        return None
    picked = _pick_active(active)
    return _FAIL_CLOSED if picked is None else picked


def _resolve_by_id(agent_id: str) -> Optional[str]:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    spec_hit = _scan_cp_state_files(agent_id, project_dir)
    if spec_hit is _FAIL_CLOSED:
        return None  # active collision: deny, do NOT consult agent-index
    if isinstance(spec_hit, str):
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
