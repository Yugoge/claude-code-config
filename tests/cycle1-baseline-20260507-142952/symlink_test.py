#!/usr/bin/env python3
"""Test codex's symlink/realpath finding for AC-1 guard hook."""
import json
import subprocess

GUARD = "/root/.claude/hooks/pretool-cp-state-write-guard.py"

# The cp-state file under /root/.claude (symlink) resolves to /dev/shm/.../dot-claude/specs/...
# /root/.claude/specs/* matches the glob */.claude/specs/*/cp-state-*.json
# But the realpath /dev/shm/dev-workspace/dot-claude/specs/* does NOT — no .claude/ segment.

CASES = [
    ("via /root/.claude/ symlink path",
     "/root/.claude/specs/spec-X/cp-state-ba.json"),
    ("via /dev/shm/.../dot-claude/ realpath",
     "/dev/shm/dev-workspace/dot-claude/specs/spec-X/cp-state-ba.json"),
    # Also worth: docs/dev/specs version
    ("docs/dev/specs version (no nested .claude alias)",
     "/dev/shm/dev-workspace/happy-dev/docs/dev/specs/spec-X/cp-state-ba.json"),
]

for name, path in CASES:
    payload = {"agent_id": "qa-test", "tool_name": "Edit",
               "tool_input": {"file_path": path, "old_string": "x", "new_string": "y"}}
    proc = subprocess.run(
        ["python3", GUARD],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    print(f"path={path}")
    print(f"  rc={proc.returncode}  stderr_head={proc.stderr.strip()[:80]!r}")
    print()
