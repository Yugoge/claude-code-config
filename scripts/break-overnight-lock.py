#!/usr/bin/env python3
"""Break every active overnight time-lock + workflow-enforce.

Backdates end_time on every active overnight-state-*.json so
stop-overnight-timelock.py releases, and marks all todos completed so
stop-workflow-enforce.py releases.

Used by /stop slash command (commands/stop.md → hooks/stop.sh → here).
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

CLAUDE_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", "/root")) / ".claude"
TODOS_DIR = Path.home() / ".claude" / "todos"


def _backdate(sf: Path, past: str) -> str:
    d = json.loads(sf.read_text())
    sid = d.get("session_id", "?")
    old = d.get("end_time", "?")
    d["end_time"] = past
    d["current_phase"] = "completed"
    # M10/AC8: this user `/stop` release path is the ONLY sanctioned setter of
    # isolation_released_at and the closer of isolation_active_until.
    # update-overnight-state.sh rejects --set on these fields; the release
    # happens here so an overnight actor cannot self-release isolation.
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    d["isolation_released_at"] = now_iso
    if "isolation_active_until" in d:
        d["isolation_active_until"] = past
    sf.write_text(json.dumps(d, indent=2))
    print(f"  state {sid[:8]}: end_time {old} -> {past}; isolation_released_at={now_iso}")
    return sid


def _complete_todos(sid: str) -> None:
    todos = TODOS_DIR / f"{sid}-agent-{sid}.json"
    if not todos.exists():
        return
    items = json.loads(todos.read_text())
    for t in items:
        if isinstance(t, dict):
            t["status"] = "completed"
    todos.write_text(json.dumps(items))
    print(f"  todos {sid[:8]}: marked all {len(items)} completed")


def main() -> int:
    states = sorted(CLAUDE_DIR.glob("overnight-state-*.json"))
    if not states:
        print("no overnight state files found — nothing to unlock")
        return 0
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for sf in states:
        sid = _backdate(sf, past)
        _complete_todos(sid)
    print("done — both Stop hooks released; session can now terminate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
