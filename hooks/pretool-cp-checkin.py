#!/usr/bin/env python3
"""PreToolUse Hook (Read): Auto-register subagent into cp-state on view-file read.

Triggers when a subagent's `Read` tool call targets a file whose path matches:

    <project>/docs/dev/specs/<spec-id>/views/<agent>.md

If a cp-state file already exists for this spec+agent AND agent_id is present
in the hook stdin data, set is_running=true with flock serialization. This
avoids the arch-1 race window where a subagent reads the view file but exits
before the cp-enforce hook could find any state.

If no cp-state file exists yet (e.g., spec subagent did not run or this is a
legacy spec without a manifest), exit 0 quietly -- the cp system is simply
not in effect for this invocation.

Fail-open: any error -> exit 0. Never block on unexpected input.
"""

import fcntl
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


VIEW_PATH_PATTERN = re.compile(
    r".*/docs/dev/specs/(?P<spec_id>[^/]+)/views/(?P<agent>[^/]+)\.md$"
)

# Dev-registry sentinel: sibling mechanism for /dev, /dev-command, /dev-overnight
# workflows. These workflows produce no spec views, so VIEW_PATH_PATTERN never
# fires for them. Root cause: commit e086ccb scoped enforcement to /spec only;
# /dev sessions have no cp-state files, so the enforcement hook fails open.
# Fix: orchestrators write .claude/dev-registry/<session_id>/<agent>.json
# sentinels; subagents read them as FIRST ACTION; this hook extracts the agent
# type from the path and writes the Claude-stdin agent_id -> agent_type mapping
# to .claude/dev-registry/agent-index.json. See ba-spec-20260424-110000.md.
DEV_SENTINEL_PATTERN = re.compile(
    r".*/\.claude/dev-registry/(?P<session_id>[^/]+)/(?P<agent>[^/]+)\.json$"
)

CP_AGENTS = {
    "ba", "dev", "qa", "pm", "architect",
    "product-owner", "ui-specialist", "user",
}

# Expanded set for dev-registry: /dev-overnight also launches inspector/cleaner
# specialists. Kept separate from CP_AGENTS to avoid expanding /spec semantics.
DEV_REGISTRY_AGENTS = CP_AGENTS | {
    "cleaner", "rule-inspector", "style-inspector", "prompt-inspector",
    "cleanliness-inspector", "git-edge-case-analyst",
    "test-executor", "test-validator",
}


# Slot filename pattern: cp-state-<agent>.json (primary)
#                    or  cp-state-<agent>-<N>.json (numbered, N>=2, auto-allocated
#                        by spec-check.py when the primary is held by a running
#                        instance). See /root/bin/spec-check.py for the writer.


def _now_iso_z():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_stdin():
    try:
        return json.load(sys.stdin)
    except Exception:
        return None


def _extract_target(data):
    if not isinstance(data, dict):
        return None, None
    if data.get("tool_name") != "Read":
        return None, None
    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    m = VIEW_PATH_PATTERN.match(file_path)
    if not m:
        return None, None
    return m.group("spec_id"), m.group("agent")


def _extract_dev_sentinel(data):
    """Extract (session_id, agent) for a Read targeting the dev-registry.

    Returns (None, None) when the Read does not match the sentinel path or the
    agent name is not in DEV_REGISTRY_AGENTS. Validating the agent name here
    prevents arbitrary JSON reads from being written into the index.
    """
    if not isinstance(data, dict):
        return None, None
    if data.get("tool_name") != "Read":
        return None, None
    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    m = DEV_SENTINEL_PATTERN.match(file_path)
    if not m:
        return None, None
    agent = m.group("agent")
    if agent not in DEV_REGISTRY_AGENTS:
        return None, None
    return m.group("session_id"), agent


def _dev_registry_index_path(project_dir):
    return Path(project_dir) / ".claude" / "dev-registry" / "agent-index.json"


def _read_index(index_path):
    """Load agent-index.json as dict, returning {} on any error."""
    try:
        existing = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return existing if isinstance(existing, dict) else {}


def _write_index_locked(index_path, agent_id, agent_type):
    """Write the merged mapping while holding fcntl.LOCK_EX on a sibling lock."""
    lock_path = index_path.with_suffix(index_path.suffix + ".lock")
    with open(lock_path, "w") as lh:
        fcntl.flock(lh.fileno(), fcntl.LOCK_EX)
        existing = _read_index(index_path)
        existing[agent_id] = agent_type
        index_path.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        fcntl.flock(lh.fileno(), fcntl.LOCK_UN)


def _update_dev_registry_index(project_dir, agent_id, agent_type):
    """Append {agent_id: agent_type} to agent-index.json under fcntl.LOCK_EX.

    Fails silent (returns False) on I/O errors so the hook remains fail-open.
    """
    index_path = _dev_registry_index_path(project_dir)
    try:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        _write_index_locked(index_path, agent_id, agent_type)
    except OSError:
        return False
    return True


def _cp_dir(project_dir, spec_id):
    return Path(project_dir) / ".claude" / "specs" / spec_id


def _all_cp_files(project_dir, spec_id, agent):
    """Return every cp-state slot file for (spec, agent): primary + numbered.

    Primary (cp-state-<agent>.json) first, then numbered slots in ascending
    integer order (cp-state-<agent>-2.json, -3.json, ...). Mirrors the
    allocation policy in /root/bin/spec-check.py.
    """
    cp_dir = _cp_dir(project_dir, spec_id)
    if not cp_dir.exists():
        return []
    files = []
    primary = cp_dir / f"cp-state-{agent}.json"
    if primary.exists():
        files.append(primary)
    pattern = re.compile(rf"^cp-state-{re.escape(agent)}-(\d+)\.json$")
    numbered = []
    for child in cp_dir.iterdir():
        m = pattern.match(child.name)
        if m:
            numbered.append((int(m.group(1)), child))
    numbered.sort(key=lambda pair: pair[0])
    files.extend(p for _, p in numbered)
    return files


def _read_payload(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_payload(path, payload):
    lock_path = path.with_suffix(path.suffix + ".lock")
    with open(lock_path, "w") as lh:
        fcntl.flock(lh.fileno(), fcntl.LOCK_EX)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        fcntl.flock(lh.fileno(), fcntl.LOCK_UN)


def _update_payload(payload, agent_id):
    payload["is_running"] = True
    if agent_id:
        payload["agent_id"] = agent_id
    payload["checked_in_at"] = _now_iso_z()
    payload["checked_out_at"] = None
    return payload


def _load_slots(files):
    loaded = []
    for p in files:
        payload = _read_payload(p)
        if payload is not None:
            loaded.append((p, payload))
    return loaded


def _match_by_agent_id(loaded, agent_id):
    if not agent_id:
        return None
    for p, payload in loaded:
        if payload.get("agent_id") == agent_id:
            return p, payload
    return None


def _first_idle_slot(loaded):
    for p, payload in loaded:
        if not payload.get("is_running"):
            return p, payload
    return None


def _pick_slot(files, agent_id):
    """Choose which cp-state slot this Read belongs to.

    1. If agent_id is present, prefer a slot whose stored agent_id matches
       (unambiguous pin for parallel instances of the same agent type).
    2. Otherwise, prefer the first slot that is NOT is_running (the slot
       that will transition to running via this Read).
    3. Otherwise, fall back to the primary slot (first file).

    Returns (path, payload) or (None, None).
    """
    loaded = _load_slots(files)
    if not loaded:
        return None, None
    pinned = _match_by_agent_id(loaded, agent_id)
    if pinned is not None:
        return pinned
    idle = _first_idle_slot(loaded)
    if idle is not None:
        return idle
    return loaded[0]


def _handle_spec_view(data, project_dir):
    """Process a VIEW_PATH_PATTERN Read; update the matching cp-state slot.

    Returns True when handled (matched), False when the Read does not target a
    /spec view file or no cp-state exists for the (spec_id, agent) pair.
    """
    spec_id, agent = _extract_target(data)
    if spec_id is None or agent not in CP_AGENTS:
        return False
    files = _all_cp_files(project_dir, spec_id, agent)
    if not files:
        return False
    agent_id = data.get("agent_id")
    path, payload = _pick_slot(files, agent_id)
    if path is None or payload is None:
        return False
    payload = _update_payload(payload, agent_id)
    _write_payload(path, payload)
    return True


def _handle_dev_sentinel(data, project_dir):
    """Process a DEV_SENTINEL_PATTERN Read; register UUID -> agent_type.

    Returns True when handled, False when the Read does not target a sentinel
    or the Claude-stdin agent_id is missing (main-agent Read is ignored).
    """
    session_id, agent = _extract_dev_sentinel(data)
    if session_id is None:
        return False
    agent_id = data.get("agent_id")
    if not agent_id:
        return False
    _update_dev_registry_index(project_dir, agent_id, agent)
    return True


def main():
    data = _load_stdin()
    if data is None:
        sys.exit(0)
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    # Try /spec view first (existing behavior untouched), then /dev sentinel.
    # Both handlers are fail-open: any miss or error -> exit 0.
    if _handle_spec_view(data, project_dir):
        sys.exit(0)
    _handle_dev_sentinel(data, project_dir)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
