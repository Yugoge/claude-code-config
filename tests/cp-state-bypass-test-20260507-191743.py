#!/usr/bin/env python3
"""Cycle-2 cp-state bypass deterministic reproducer (spec-20260507-191743).

Lives at /dev/shm/dev-workspace/dot-claude/tests/ (durable; survives /tmp cleanup).
Verifies pretool-cp-state-write-guard.py blocks 22 known Bash-write forms,
does not regress 13 cycle-1 AC-1 baselines, does not false-positive on 13 AC-5
benign payloads. Total: 48 rows.

Subagent identity injection: every Bash payload MUST include both 'agent_id'
and 'subagent_type' for the hook's subagent path to fire (orchestrator events
silently exit 0).

Exit code: 0 iff all 48 rows pass; 1 if any row fails.
"""
import json
import subprocess
import sys

GUARD = "/root/.claude/hooks/pretool-cp-state-write-guard.py"
SPEC = "/dev/shm/dev-workspace/dot-claude/specs/spec-X"
TARGET = SPEC + "/cp-state-ba.json"

# AC-1 + AC-2: 22 cp-state Bash bypass forms; all expect rc=2 + BLOCKED diag.
BYPASS_BASH = {
    "cd_relative":            "cd " + SPEC + " && cat > cp-state-ba.json << EOF\n{}\nEOF",
    "cp_to_dir":              "cp /tmp/cp-state-ba.json " + SPEC + "/",
    "mv_to_dir":              "mv /tmp/cp-state-ba.json " + SPEC + "/",
    "install_to_dir":         "install -m 644 /tmp/cp-state-ba.json " + SPEC + "/",
    "ln_sf":                  "ln -sf /tmp/poison.json " + TARGET,
    "ln_s":                   "ln -s /tmp/poison.json " + TARGET,
    "python_c_open":          "python3 -c \"open('" + TARGET + "','w').write('{}')\"",
    "python_heredoc":         "python3 - <<'PY'\nfrom pathlib import Path\nPath('" + TARGET + "').write_text('{}')\nPY",
    "dd_of":                  "dd if=/tmp/x of=" + TARGET,
    "curl_o":                 "curl -s -o " + TARGET + " https://example/x",
    "wget_O":                 "wget -q -O " + TARGET + " https://example/x",
    "amp_redirect":           "echo {} &> " + TARGET,
    "git_checkout_dd":        "git checkout HEAD -- " + TARGET,
    "git_restore":            "git restore " + TARGET,
    "touch":                  "touch " + TARGET,
    "rsync_to_dir":           "rsync /tmp/cp-state-ba.json " + SPEC + "/",
    "truncate_dash_s_zero":   "truncate -s 0 " + TARGET,
    "truncate_dash_s_zero_fused": "truncate -s0 " + TARGET,
    "colon_redirect":         ": > " + TARGET,
    "python_c_shutil_copy":   "python3 -c \"import shutil; shutil.copy('/tmp/src.json','" + TARGET + "')\"",
    "python_c_shutil_copy2":  "python3 -c \"import shutil; shutil.copy2('/tmp/src.json','" + TARGET + "')\"",
    "python_c_shutil_move":   "python3 -c \"import shutil; shutil.move('/tmp/src.json','" + TARGET + "')\"",
}
assert len(BYPASS_BASH) == 22

# AC-5: 13 benign-Bash regression rows; all expect rc=0.
BENIGN_BASH = {
    "cd_to_tmp_redirect":    "cd /tmp && cat > out.json",
    "cp_to_tmp_dir":         "cp /tmp/a /tmp/dir/",
    "python_print":          "python3 -c \"print(1)\"",
    "touch_tmp":             "touch /tmp/foo",
    "curl_to_tmp":           "curl -o /tmp/x.json https://example/x",
    "git_status":            "git status",
    "rsync_to_tmp":          "rsync /tmp/a /tmp/b/",
    "truncate_tmp":          "truncate -s 100 /tmp/foo",
    "truncate_tmp_zero":     "truncate -s 0 /tmp/foo",
    "truncate_tmp_fused":    "truncate -s0 /tmp/foo",
    "colon_redirect_tmp":    ": > /tmp/foo.json",
    "shutil_copy_tmp":       "python3 -c \"import shutil; shutil.copy('/tmp/a','/tmp/b')\"",
    "shutil_move_tmp":       "python3 -c \"import shutil; shutil.move('/tmp/a','/tmp/b')\"",
}
assert len(BENIGN_BASH) == 13

# AC-1 baseline: 13 cycle-1 rows; mixed expectations (10 deny + 3 allow).
TARGET_CLAUDE = "/tmp/qa-20260507-142952/proj/.claude/specs/spec-test/cp-state-ba.json"
TARGET_DOCS = "/tmp/qa-20260507-142952/proj/docs/dev/specs/spec-test/cp-state-pm.json"
NON_CP = "/tmp/qa-20260507-142952/proj/random.py"

AC1_BASELINE = [
    ("AC-1.1 subagent Edit on cp-state (.claude/specs/)",
     {"agent_id": "qa-test", "tool_name": "Edit",
      "tool_input": {"file_path": TARGET_CLAUDE, "old_string": "x", "new_string": "y"}}, 2),
    ("AC-1.1b subagent Edit on cp-state (docs/dev/specs/)",
     {"agent_id": "qa-test", "tool_name": "Edit",
      "tool_input": {"file_path": TARGET_DOCS, "old_string": "x", "new_string": "y"}}, 2),
    ("AC-1.2 subagent Bash heredoc to cp-state",
     {"agent_id": "qa-test", "tool_name": "Bash",
      "tool_input": {"command": "cat > " + TARGET_CLAUDE + " << EOF\n{}\nEOF"}}, 2),
    ("AC-1.3 subagent Bash echo redirect to cp-state",
     {"agent_id": "qa-test", "tool_name": "Bash",
      "tool_input": {"command": "echo '{}' > " + TARGET_CLAUDE}}, 2),
    ("AC-1.4 subagent spec-check.py via Bash -> allowed",
     {"agent_id": "qa-test", "tool_name": "Bash",
      "tool_input": {"command": "python3 /root/.claude/scripts/spec-check.py status --spec-id spec-X"}}, 0),
    ("AC-1.5 orchestrator Edit on cp-state -> allowed (emergency repair)",
     {"tool_name": "Edit",
      "tool_input": {"file_path": TARGET_CLAUDE, "old_string": "x", "new_string": "y"}}, 0),
    ("AC-1.6 subagent_type-only (no agent_id) Edit -> blocked",
     {"subagent_type": "dev", "tool_name": "Edit",
      "tool_input": {"file_path": TARGET_CLAUDE, "old_string": "x", "new_string": "y"}}, 2),
    ("AC-1.7 subagent Edit on non-cp-state -> allowed",
     {"agent_id": "qa-test", "tool_name": "Edit",
      "tool_input": {"file_path": NON_CP, "old_string": "x", "new_string": "y"}}, 0),
    ("AC-1.8 subagent Bash tee to cp-state",
     {"agent_id": "qa-test", "tool_name": "Bash",
      "tool_input": {"command": "echo '{}' | tee " + TARGET_CLAUDE}}, 2),
    ("AC-1.9 subagent MultiEdit on cp-state",
     {"agent_id": "qa-test", "tool_name": "MultiEdit",
      "tool_input": {"file_path": TARGET_CLAUDE, "edits": [{"old_string": "x", "new_string": "y"}]}}, 2),
    ("AC-1.10 subagent NotebookEdit on cp-state",
     {"agent_id": "qa-test", "tool_name": "NotebookEdit",
      "tool_input": {"notebook_path": TARGET_CLAUDE, "new_source": "y"}}, 2),
    ("AC-1.11 subagent Edit on numbered cp-state slot",
     {"agent_id": "qa-test", "tool_name": "Edit",
      "tool_input": {"file_path": TARGET_CLAUDE.replace("cp-state-ba.json", "cp-state-dev-2.json"),
                      "old_string": "x", "new_string": "y"}}, 2),
    ("AC-1.12 subagent spec-check.py mark via Bash -> allowed",
     {"agent_id": "qa-test", "tool_name": "Bash",
      "tool_input": {"command": "python3 /root/.claude/scripts/spec-check.py mark --spec-id spec-X --agent dev --agent-id aid --cp-id cp-01"}}, 0),
]
assert len(AC1_BASELINE) == 13


def run_guard(payload):
    """Run guard hook with payload-as-stdin-JSON. Returns (rc, stdout, stderr)."""
    proc = subprocess.run(
        ["python3", GUARD],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=15,
    )
    return proc.returncode, proc.stdout, proc.stderr


def make_bash_payload(cmd):
    """Build a subagent Bash payload with required identity fields."""
    return {
        "agent_id": "test-dev",
        "subagent_type": "dev",
        "tool_name": "Bash",
        "tool_input": {"command": cmd},
    }


def check_bypass_row(name, cmd):
    """Check a bypass row: rc must be 2 and stderr must contain BLOCKED diag."""
    rc, _, stderr = run_guard(make_bash_payload(cmd))
    ok = (rc == 2 and "BLOCKED by cp-state write-guard:" in stderr)
    return ok, rc, stderr


def check_benign_row(name, cmd):
    """Check a benign row: rc must be 0."""
    rc, _, stderr = run_guard(make_bash_payload(cmd))
    return (rc == 0), rc, stderr


def check_ac1_row(name, payload, expected_rc):
    """Check an AC-1 baseline row: rc must match expected; deny rows must have BLOCKED diag."""
    rc, _, stderr = run_guard(payload)
    ok = (rc == expected_rc)
    if expected_rc == 2:
        ok = ok and "BLOCKED by cp-state write-guard:" in stderr
    return ok, rc, stderr


def run_section(title, rows, checker, expected_label, fails):
    """Run a checker over rows; print formatted PASS/FAIL lines; append failures."""
    print("=" * 78)
    print(title)
    print("=" * 78)
    count = 0
    for row in rows:
        count += 1
        if isinstance(rows, dict):
            name, cmd = row, rows[row]
            ok, rc, stderr = checker(name, cmd)
            print("  [%s] %-32s rc=%d expected=%s" % (
                "PASS" if ok else "FAIL", name, rc, expected_label))
        else:
            name, payload, exp = row[0], row[1], row[2]
            ok, rc, stderr = checker(name, payload, exp)
            print("  [%s] %-60s rc=%d expected=%d" % (
                "PASS" if ok else "FAIL", name[:60], rc, exp))
        if not ok:
            fails.append((title.split(":")[0].strip(), name, rc,
                          stderr.strip().splitlines()[:2]))
    return count


def main():
    fails = []
    total = 0
    total += run_section(
        "Section 1/3: 22 cp-state Bash bypass rows (AC-1 + AC-2) -- expect rc=2",
        BYPASS_BASH, check_bypass_row, "2", fails)
    print()
    total += run_section(
        "Section 2/3: 13 benign-Bash regression rows (AC-5) -- expect rc=0",
        BENIGN_BASH, check_benign_row, "0", fails)
    print()
    total += run_section(
        "Section 3/3: 13 cycle-1 AC-1 baseline rows -- mixed expectations",
        AC1_BASELINE, check_ac1_row, "mixed", fails)
    print()
    print("=" * 78)
    print("SUMMARY: %d/%d PASS, %d FAIL" % (total - len(fails), total, len(fails)))
    print("=" * 78)
    if fails:
        print()
        print("Failures:")
        for section, name, rc, stderr_head in fails:
            print("  [%s] %s: rc=%d, stderr=%s" % (section, name, rc, stderr_head))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
