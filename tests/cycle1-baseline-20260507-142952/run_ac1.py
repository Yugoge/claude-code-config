#!/usr/bin/env python3
"""AC-1 verification: pretool-cp-state-write-guard.py."""
import json
import subprocess
import sys

TARGET = "/tmp/qa-20260507-142952/test-cpstate/cp-state-ba.json"
GUARD = "/root/.claude/hooks/pretool-cp-state-write-guard.py"

CASES = [
    ("AC-1.1 subagent Edit on cp-state",
     {"agent_id": "qa-test", "tool_name": "Edit",
      "tool_input": {"file_path": TARGET, "old_string": "x", "new_string": "y"}},
     2),
    ("AC-1.2 subagent Bash heredoc to cp-state",
     {"agent_id": "qa-test", "tool_name": "Bash",
      "tool_input": {"command": f"cat > {TARGET} << EOF\n{{}}\nEOF"}},
     2),
    ("AC-1.3 subagent Bash redirect to cp-state",
     {"agent_id": "qa-test", "tool_name": "Bash",
      "tool_input": {"command": f'echo "{{}}" > {TARGET}'}},
     2),
    ("AC-1.4 subagent spec-check.py invocation",
     {"agent_id": "qa-test", "tool_name": "Bash",
      "tool_input": {"command": "python3 /root/.claude/scripts/spec-check.py status --spec-id spec-test"}},
     0),
    ("AC-1.5 orchestrator (no agent_id, no subagent_type) Edit on cp-state",
     {"tool_name": "Edit",
      "tool_input": {"file_path": TARGET, "old_string": "x", "new_string": "y"}},
     0),
    ("AC-1.6 subagent via subagent_type only (no agent_id)",
     {"subagent_type": "qa", "tool_name": "Edit",
      "tool_input": {"file_path": TARGET, "old_string": "x", "new_string": "y"}},
     2),
    ("AC-1.7 subagent Edit on non-cp-state file",
     {"agent_id": "qa-test", "tool_name": "Edit",
      "tool_input": {"file_path": "/tmp/qa-20260507-142952/random.py", "old_string": "x", "new_string": "y"}},
     0),
    ("AC-1.8 subagent Bash tee to cp-state",
     {"agent_id": "qa-test", "tool_name": "Bash",
      "tool_input": {"command": f'echo "{{}}" | tee {TARGET}'}},
     2),
    ("AC-1.9 subagent MultiEdit on cp-state",
     {"agent_id": "qa-test", "tool_name": "MultiEdit",
      "tool_input": {"file_path": TARGET, "edits": []}},
     2),
    ("AC-1.10 subagent Write on cp-state under docs/dev/specs/",
     {"agent_id": "qa-test", "tool_name": "Write",
      "tool_input": {"file_path": "/tmp/qa-20260507-142952/proj/docs/dev/specs/spec-x/cp-state-pm.json", "content": "{}"}},
     2),
]

passed = 0
failed = 0
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
    print(f"[{status}] {name}: expected={expected_rc} actual={actual}")
    if not ok:
        print(f"    stderr: {proc.stderr.strip()[:300]}")
    elif actual == 2:
        # spot-check that diagnostic message appears
        if "spec-check.py" not in proc.stderr:
            print(f"    WARN: deny missing spec-check.py reference in diagnostic")

print(f"\nAC-1 summary: {passed} passed, {failed} failed of {len(CASES)}")
sys.exit(0 if failed == 0 else 1)
