#!/usr/bin/env python3
"""PreToolUse Hook (Agent matcher): Enforce canonical aggregate dev-report
existence before allowing the orchestrator to dispatch the QA subagent in
parallel-dev cycles.

Predicate: BLOCK (exit 2) iff
  (a) docs/dev/ contains >=2 files matching dev-report-<role>-<task-id>.json
      sharing the same <task-id>, AND
  (b) the canonical singular dev-report-<task-id>.json is absent for that
      task-id.
Otherwise: silent exit 0.

Triggers ONLY for Agent tool calls dispatching subagent_type=qa. Other Agent
dispatches (ba, dev, specialists, etc.) are not gated -- the rule is that
the aggregate must exist BEFORE QA reads it.

Fail-open contract: parsing failures, missing stdin, missing project dir,
unexpected exceptions -> exit 0. Never crash the orchestrator on a self-bug.

Filename pattern (matches existing /commit task-id recognition):
  dev-report-<role>-<task-id>.json
    role     := alphanumeric (\\w+, no dashes inside the role token)
    task-id  := \\d{8}-\\d{6} (YYYYMMDD-HHMMSS)

Authoritative construction rule for the aggregate: commands/dev.md lines
613-670. See also docs/dev/dev-report-20260426-122733.json for a canonical
exemplar written in Phase 1.
"""

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path


# Per-worker filename: dev-report-<role>-<task-id>.json
# task-id format: YYYYMMDD-HHMMSS (8 digits, dash, 6 digits)
PER_WORKER_RE = re.compile(
    r"^dev-report-(?P<role>[A-Za-z0-9]+)-(?P<task_id>\d{8}-\d{6})\.json$"
)

# Canonical singular: dev-report-<task-id>.json
CANONICAL_RE = re.compile(r"^dev-report-(?P<task_id>\d{8}-\d{6})\.json$")

# Path to dev.md construction-rule citation
DEV_MD_REF = "commands/dev.md lines 613-670"


def _load_stdin():
    try:
        return json.load(sys.stdin)
    except Exception:
        return None


def _is_qa_dispatch(data):
    """Return True iff this Agent call dispatches subagent_type=qa."""
    if not isinstance(data, dict):
        return False
    if data.get("tool_name") != "Agent" and data.get("tool_name") != "Task":
        return False
    tool_input = data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return False
    return tool_input.get("subagent_type") == "qa"


def _scan_dev_dir(dev_dir):
    """Return ({task_id: [role,...]}, {task_id: True}).

    First dict maps task-id -> list of per-worker roles seen.
    Second dict marks task-ids that have a canonical singular file present.
    """
    per_worker = defaultdict(list)
    canonical_present = {}
    if not dev_dir.exists() or not dev_dir.is_dir():
        return per_worker, canonical_present
    try:
        children = list(dev_dir.iterdir())
    except OSError:
        return per_worker, canonical_present
    for child in children:
        if not child.is_file():
            continue
        name = child.name
        # Try canonical first (more specific tail match)
        m_can = CANONICAL_RE.match(name)
        if m_can is not None:
            canonical_present[m_can.group("task_id")] = True
            continue
        m_per = PER_WORKER_RE.match(name)
        if m_per is not None:
            per_worker[m_per.group("task_id")].append(m_per.group("role"))
    return per_worker, canonical_present


def _find_violations(per_worker, canonical_present):
    """Return list of (task_id, [roles], canonical_path) tuples that violate.

    Violation = >=2 per-worker reports for same task-id AND no canonical.
    """
    violations = []
    for task_id, roles in per_worker.items():
        if len(roles) >= 2 and not canonical_present.get(task_id):
            violations.append((task_id, sorted(roles)))
    return violations


def _emit_block(violations, dev_dir):
    """Print BLOCK message to stderr and exit 2."""
    lines = ["", "BLOCKED Agent dispatch (qa): canonical aggregate dev-report missing."]
    for task_id, roles in violations:
        canonical = dev_dir / f"dev-report-{task_id}.json"
        lines.append("")
        lines.append(f"  task-id: {task_id}")
        lines.append(f"  per-worker reports present: {', '.join(roles)}")
        lines.append(f"  missing canonical aggregate: {canonical}")
    lines.append("")
    lines.append(
        f"REQUIRED: orchestrator must write the canonical aggregate before "
        f"dispatching QA. See {DEV_MD_REF} for the construction rule."
    )
    lines.append("")
    sys.stderr.write("\n".join(lines) + "\n")
    sys.exit(2)


def _resolve_dev_dir():
    """Resolve docs/dev under CLAUDE_PROJECT_DIR, fail-open if absent."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return Path(project_dir) / "docs" / "dev"


def main():
    data = _load_stdin()
    if data is None:
        sys.exit(0)
    if not _is_qa_dispatch(data):
        sys.exit(0)
    dev_dir = _resolve_dev_dir()
    per_worker, canonical_present = _scan_dev_dir(dev_dir)
    violations = _find_violations(per_worker, canonical_present)
    if violations:
        _emit_block(violations, dev_dir)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Fail-open: never crash orchestrator on a self-bug
        sys.exit(0)
