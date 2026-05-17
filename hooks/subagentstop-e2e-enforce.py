#!/usr/bin/env python3
"""SubagentStop Hook: Block QA subagents that did not perform E2E verification.

Activation logic:
  1. Read agent_id from stdin. If absent, exit 0 (non-subagent stop).
  2. Resolve agent entry via resolve_dev_registry_entry(agent_id, project_dir).
     If None (agent not in agent-index.json -- skipped FIRST ACTION sentinel):
       exit 0 (fail-open). Rationale: other hooks enforce FIRST ACTION; a
       false-positive block here is more harmful than a miss.
  3. If dev_session_id is None (legacy flat-string entry): exit 0 (fail-open).
  4. If agent_type != "qa": exit 0 (scoped to QA only).
  5. Check .claude/dev-registry/<dev_session_id>/e2e-enforce.json.
     If absent or enabled != true: exit 0 (no enforcement for this session).
  6. Find the most recent qa-report-*.json in docs/dev/ within project_dir.
     If none found: exit 2 (no QA report means no E2E evidence).
  7. Read e2e_enforcement.status from the QA report.
     If status is "performed", "legitimately_skipped" (with blocking_reason),
     "ran", or "blocked_app_unavailable": exit 0.
     If status is "skipped_without_justification" or field is absent:
       exit 2 with "E2E_ENFORCE_BLOCKED" message.

Exit codes:
  0: Allow stop (pass-through).
  2: Block stop (E2E_ENFORCE_BLOCKED -- QA must perform E2E verification).
"""

import glob
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.agent_resolver import resolve_dev_registry_entry

# Only enforce for QA agents
ENFORCED_AGENT_TYPE = "qa"

# Statuses that allow QA to stop
PASSING_STATUSES = {"performed", "ran", "blocked_app_unavailable", "legitimately_skipped"}


def _load_stdin() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _find_latest_qa_report(project_dir: str, dev_session_id: str | None = None) -> Path | None:
    """Find the most relevant QA report for the current session.

    If dev_session_id is provided (e.g. "dev-20260516-161724"), return only a
    session-correlated report. Returns None if no correlated report is found or
    if session_ts cannot be extracted. No global fallback when session ID is present.
    """
    pattern = os.path.join(project_dir, "docs", "dev", "qa-report-*.json")
    matches = glob.glob(pattern)
    if not matches:
        return None
    # Sort by filename (timestamp-based names sort chronologically)
    matches.sort()

    if dev_session_id:
        # dev_session_id format: "dev-YYYYMMDD-HHMMSS"
        # Extract YYYYMMDD-HHMMSS portion from any session ID format
        _m = re.search(r'\d{8}-\d{6}', dev_session_id)
        if not _m:
            # Cannot correlate without a timestamp; fail closed — do not guess
            return None
        session_ts = _m.group()
        # Check by filename match first (fastest)
        for p in reversed(matches):
            fname = os.path.basename(p)
            if session_ts in fname:
                return Path(p)
        # Check by task_id/request_id inside recent reports (last 5)
        for p in reversed(matches[-5:]):
            try:
                data = json.loads(Path(p).read_text(encoding="utf-8"))
                report_id = data.get("task_id") or data.get("request_id") or ""
                if report_id and session_ts in report_id:
                    return Path(p)
            except Exception:
                continue
        # No correlated report found; do not fall back to unrelated sessions
        return None
    # dev_session_id is None — legacy/direct-call mode (dead code in enforcement path)
    return Path(matches[-1]) if matches else None


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
    if agent_type != ENFORCED_AGENT_TYPE:
        # Not a QA agent: bypass enforcement unconditionally
        sys.exit(0)

    # Check enforcement flag
    enforce_path = (
        Path(project_dir)
        / ".claude"
        / "dev-registry"
        / dev_session_id
        / "e2e-enforce.json"
    )
    if not enforce_path.exists():
        # No enforcement flag for this session: fail-open
        sys.exit(0)

    enforce_data = _read_json(enforce_path)
    if not enforce_data.get("enabled"):
        # Enforcement explicitly disabled
        sys.exit(0)

    # Check for force-mode sentinel: /close --force writes this before any QA dispatch.
    # If present, skip E2E enforcement — forced closes dispatch zero QA subagents by design.
    # This is defense-in-depth; the primary fix is the 2-step force-path todo in close.md.
    force_sentinel_pattern = f"/tmp/claude-close-force-{dev_session_id}.flag"
    if glob.glob(force_sentinel_pattern):
        sys.stderr.write(
            f"subagentstop-e2e-enforce: force-mode sentinel found at "
            f"{force_sentinel_pattern}; skipping E2E enforcement.\n"
        )
        sys.exit(0)

    # Read qa_mode from authoritative sentinel (set by orchestrator before dispatch)
    qa_sentinel_path = (
        Path(project_dir) / ".claude" / "dev-registry" / dev_session_id / "qa.json"
    )
    qa_sentinel = _read_json(qa_sentinel_path)
    if qa_sentinel.get("qa_mode") == "ba_validation":
        sys.exit(0)  # BA-validation QA: no E2E obligation; role confirmed by sentinel

    # Find QA report to check e2e_enforcement field (prefer session-correlated)
    qa_report_path = _find_latest_qa_report(project_dir, dev_session_id)
    if qa_report_path is None:
        sys.stderr.write(
            f"E2E_ENFORCE_BLOCKED: agent {agent_id} (type={agent_type}) has no "
            f"qa-report-*.json in {project_dir}/docs/dev/ under session {dev_session_id}.\n"
            f"QA must produce a report with e2e_enforcement.status before stopping.\n"
        )
        sys.exit(2)

    qa_report = _read_json(qa_report_path)

    # Navigate to e2e_enforcement field (may be nested under qa.*)
    e2e = None
    qa_section = qa_report.get("qa", {})
    if isinstance(qa_section, dict):
        e2e = qa_section.get("e2e_enforcement")
    if e2e is None:
        e2e = qa_report.get("e2e_enforcement")

    # Guard: e2e must be a dict; malformed value fails closed
    if e2e is not None and not isinstance(e2e, dict):
        sys.stderr.write(
            f"E2E_ENFORCE_BLOCKED: agent {agent_id} (type={agent_type}) QA report "
            f"at {qa_report_path} has malformed e2e_enforcement field (expected dict, "
            f"got {type(e2e).__name__}).\n"
        )
        sys.exit(2)

    if e2e is None:
        sys.stderr.write(
            f"E2E_ENFORCE_BLOCKED: agent {agent_id} (type={agent_type}) QA report "
            f"at {qa_report_path} has no e2e_enforcement field.\n"
            f"Add e2e_enforcement.status to the QA report before stopping.\n"
        )
        sys.exit(2)

    status = e2e.get("status", "")

    if status in PASSING_STATUSES:
        # For legitimately_skipped, blocking_reason should be populated
        # but we do not hard-block on missing blocking_reason (advisory check only)
        sys.exit(0)

    # status is skipped_without_justification, empty, or unrecognized
    blocking_reason = e2e.get("blocking_reason") or "(none provided)"
    sys.stderr.write(
        f"E2E_ENFORCE_BLOCKED: agent {agent_id} (type={agent_type}) in session "
        f"{dev_session_id} has e2e_enforcement.status={status!r}.\n"
        f"blocking_reason: {blocking_reason}\n"
        f"E2E verification is required. Perform E2E testing and update "
        f"e2e_enforcement.status to 'performed', 'legitimately_skipped', "
        f"'blocked_app_unavailable', or 'ran' before stopping.\n"
    )
    sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
