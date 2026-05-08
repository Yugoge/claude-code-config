#!/usr/bin/env python3
"""AC-1 verification v2: pretool-cp-state-write-guard.py with correct fixture paths."""
import json
import subprocess
import sys

TARGET_CLAUDE = "/tmp/qa-20260507-142952/proj/.claude/specs/spec-test/cp-state-ba.json"
TARGET_DOCS = "/tmp/qa-20260507-142952/proj/docs/dev/specs/spec-test/cp-state-pm.json"
NON_CP = "/tmp/qa-20260507-142952/proj/random.py"
GUARD = "/root/.claude/hooks/pretool-cp-state-write-guard.py"

CASES = [
    # AC-1.1 critical: subagent Edit on cp-state under .claude/specs/
    ("AC-1.1 subagent Edit on cp-state (.claude/specs/)",
     {"agent_id": "qa-test", "tool_name": "Edit",
      "tool_input": {"file_path": TARGET_CLAUDE, "old_string": "x", "new_string": "y"}},
     2),
    # AC-1.1b: same on docs/dev/specs/ branch
    ("AC-1.1b subagent Edit on cp-state (docs/dev/specs/)",
     {"agent_id": "qa-test", "tool_name": "Edit",
      "tool_input": {"file_path": TARGET_DOCS, "old_string": "x", "new_string": "y"}},
     2),
    # AC-1.2: subagent Bash heredoc to cp-state (lib.bash_write_targets must extract this)
    ("AC-1.2 subagent Bash heredoc to cp-state",
     {"agent_id": "qa-test", "tool_name": "Bash",
      "tool_input": {"command": f"cat > {TARGET_CLAUDE} << EOF\n{{}}\nEOF"}},
     2),
    # AC-1.3: subagent Bash echo redirect
    ("AC-1.3 subagent Bash echo > redirect to cp-state",
     {"agent_id": "qa-test", "tool_name": "Bash",
      "tool_input": {"command": f'echo "{{}}" > {TARGET_CLAUDE}'}},
     2),
    # AC-1.4: subagent invoking spec-check.py via Bash -> ALLOWED
    ("AC-1.4 subagent spec-check.py via Bash -> allowed",
     {"agent_id": "qa-test", "tool_name": "Bash",
      "tool_input": {"command": "python3 /root/.claude/scripts/spec-check.py status --spec-id spec-test"}},
     0),
    # AC-1.5: orchestrator (no agent_id, no subagent_type) -> ALLOWED
    ("AC-1.5 orchestrator Edit on cp-state -> allowed (emergency repair)",
     {"tool_name": "Edit",
      "tool_input": {"file_path": TARGET_CLAUDE, "old_string": "x", "new_string": "y"}},
     0),
    # AC-1.6: subagent_type only (no agent_id) -> blocked (codex Q4 hardening)
    ("AC-1.6 subagent_type-only (no agent_id) Edit -> blocked",
     {"subagent_type": "qa", "tool_name": "Edit",
      "tool_input": {"file_path": TARGET_CLAUDE, "old_string": "x", "new_string": "y"}},
     2),
    # AC-1.7: subagent Edit on UNRELATED file -> ALLOWED
    ("AC-1.7 subagent Edit on non-cp-state -> allowed",
     {"agent_id": "qa-test", "tool_name": "Edit",
      "tool_input": {"file_path": NON_CP, "old_string": "x", "new_string": "y"}},
     0),
    # AC-1.8: subagent Bash tee to cp-state
    ("AC-1.8 subagent Bash tee to cp-state",
     {"agent_id": "qa-test", "tool_name": "Bash",
      "tool_input": {"command": f'echo "{{}}" | tee {TARGET_CLAUDE}'}},
     2),
    # AC-1.9: subagent MultiEdit on cp-state
    ("AC-1.9 subagent MultiEdit on cp-state",
     {"agent_id": "qa-test", "tool_name": "MultiEdit",
      "tool_input": {"file_path": TARGET_CLAUDE, "edits": []}},
     2),
    # AC-1.10: NotebookEdit on cp-state
    ("AC-1.10 subagent NotebookEdit on cp-state",
     {"agent_id": "qa-test", "tool_name": "NotebookEdit",
      "tool_input": {"notebook_path": TARGET_CLAUDE, "new_source": "{}"}},
     2),
    # AC-1.11: numbered slot cp-state-ba-2.json
    ("AC-1.11 subagent Edit on numbered cp-state slot",
     {"agent_id": "qa-test", "tool_name": "Edit",
      "tool_input": {"file_path": "/tmp/qa-20260507-142952/proj/.claude/specs/spec-test/cp-state-ba-2.json",
                     "old_string": "x", "new_string": "y"}},
     2),
    # AC-1.12: spec-check.py write subprocess (the Bash command is "python3 /root/.../spec-check.py mark ...") - hook sees only command string, no shell write target
    ("AC-1.12 subagent spec-check.py mark via Bash -> allowed",
     {"agent_id": "qa-test", "tool_name": "Bash",
      "tool_input": {"command": "python3 /root/.claude/scripts/spec-check.py mark --spec-id spec-test --agent ba --agent-id x --cp-id cp-1"}},
     0),
]

passed = 0
failed = 0
results = []
for name, payload, expected_rc in CASES:
    proc = subprocess.run(
        ["python3", GUARD],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    actual = proc.returncode
    ok = actual == expected_rc
    status = "PASS" if ok else "FAIL"
    if ok:
        passed += 1
    else:
        failed += 1
    diag = ""
    if actual == 2 and "spec-check.py" not in proc.stderr:
        diag = " (warn: deny missing spec-check.py reference)"
    print(f"[{status}] {name}: expected={expected_rc} actual={actual}{diag}")
    if not ok:
        print(f"    stderr: {proc.stderr.strip()[:300]}")
    results.append({"case": name, "expected": expected_rc, "actual": actual, "passed": ok})

print(f"\nAC-1 summary: {passed} passed, {failed} failed of {len(CASES)}")
import json as J
with open("/tmp/qa-20260507-142952/ac1-results.json", "w") as f:
    J.dump({"passed": passed, "failed": failed, "total": len(CASES), "results": results}, f, indent=2)
sys.exit(0 if failed == 0 else 1)
