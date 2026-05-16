#!/usr/bin/env python3
"""SubagentStop Hook: Block ba/dev/qa subagents that did not call codex skill.

Activation logic:
  1. Read agent_id from stdin. If absent, exit 0 (non-subagent stop).
  2. Resolve agent entry via resolve_dev_registry_entry(agent_id, project_dir).
     If None (agent not in agent-index.json — skipped FIRST ACTION sentinel):
       exit 0 (fail-open). Rationale: other hooks enforce FIRST ACTION; a
       false-positive block here is more harmful than a miss.
  3. If dev_session_id is None (legacy flat-string entry): exit 0 (fail-open).
  4. If agent_type not in ["ba", "dev", "qa"]: exit 0 (specialist bypass).
  5. Check .claude/dev-registry/<dev_session_id>/codex-enforce.json.
     If absent or enabled != true: exit 0 (no enforcement for this session).
  6. Check .claude/dev-registry/<dev_session_id>/codex-ledger/<agent_id>.json.
     If absent: exit 2 with "CODEX_ENFORCE_BLOCKED" message.
     If present: exit 0.

Exit codes:
  0: Allow stop (pass-through).
  2: Block stop (CODEX_ENFORCE_BLOCKED — agent must call codex before stopping).
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.agent_resolver import resolve_dev_registry_entry

ENFORCED_AGENT_TYPES = {"ba", "dev", "qa"}


def _load_stdin() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> None:
    data = _load_stdin()
    if not data:
        sys.exit(0)

    agent_id = data.get("agent_id")
    if not agent_id:
        sys.exit(0)

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    # Resolve agent entry (both agent_type and dev_session_id)
    entry = resolve_dev_registry_entry(agent_id, project_dir)
    if entry is None:
        # Agent not in index: fail-open
        sys.exit(0)

    dev_session_id = entry.get("dev_session_id")
    if not dev_session_id:
        # Legacy flat-string entry: no session correlation, skip enforcement
        sys.exit(0)

    agent_type = entry.get("agent_type", "")
    if agent_type not in ENFORCED_AGENT_TYPES:
        # Specialist agent: bypass enforcement unconditionally
        sys.exit(0)

    # Check enforcement flag
    enforce_path = Path(project_dir) / ".claude" / "dev-registry" / dev_session_id / "codex-enforce.json"
    if not enforce_path.exists():
        # No enforcement flag for this session
        sys.exit(0)

    enforce_data = _read_json(enforce_path)
    if not enforce_data.get("enabled"):
        # Enforcement explicitly disabled
        sys.exit(0)

    # Check codex ledger
    ledger_path = Path(project_dir) / ".claude" / "dev-registry" / dev_session_id / "codex-ledger" / f"{agent_id}.json"
    if ledger_path.exists():
        # Agent called codex: allow stop
        sys.exit(0)

    # No ledger entry: block stop
    sys.stderr.write(
        f"CODEX_ENFORCE_BLOCKED: agent {agent_id} (type={agent_type}) has not called "
        f"codex skill in session {dev_session_id}.\n"
        f"Call Skill(skill='codex') before stopping, or ask the orchestrator to "
        f"disable enforcement if codex is genuinely unavailable.\n"
    )
    sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
