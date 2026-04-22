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

CP_AGENTS = {
    "ba", "dev", "qa", "pm", "architect",
    "product-owner", "ui-specialist", "user",
}


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


def _cp_file(project_dir, spec_id, agent):
    return Path(project_dir) / ".claude" / "specs" / spec_id / f"cp-state-{agent}.json"


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


def main():
    data = _load_stdin()
    if data is None:
        sys.exit(0)
    spec_id, agent = _extract_target(data)
    if spec_id is None or agent not in CP_AGENTS:
        sys.exit(0)
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    path = _cp_file(project_dir, spec_id, agent)
    if not path.exists():
        sys.exit(0)
    payload = _read_payload(path)
    if payload is None:
        sys.exit(0)
    agent_id = data.get("agent_id")
    payload = _update_payload(payload, agent_id)
    _write_payload(path, payload)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
