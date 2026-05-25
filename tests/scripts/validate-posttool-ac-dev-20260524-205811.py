#!/usr/bin/env python3
"""
QA verification for dev-20260524-205811: posttool-allowlist-consume.py AC tests.
Tests are run as subprocess invocations of the hook, per spec instructions.
"""
import subprocess
import json
import os
import sys
from pathlib import Path

HOOK = str(Path(__file__).parent.parent.parent / "hooks" / "posttool-allowlist-consume.py")
PRETOOL = str(Path(__file__).parent.parent.parent / "hooks" / "pretool-bash-safety.sh")
TMPDIR = "/tmp"
CWD = str(Path(__file__).parent.parent.parent)


def setup_legacy_grant(sid, pattern=None, is_regex=False):
    if pattern is None:
        pattern = "git push"
    path = Path(f"{TMPDIR}/claude-bash-allowlist-{sid}.json")
    path.write_text(json.dumps({"pattern": pattern, "is_regex": is_regex}))
    return path


def setup_sentinel_grant(task_id, sid, op="git", args_contain=None):
    os.makedirs(f"{TMPDIR}/claude-grants", exist_ok=True)
    path = Path(f"{TMPDIR}/claude-grants/{task_id}.json")
    grant = {
        "task_id": task_id,
        "session_id": sid,
        "allowed_operations": [{"op": op, "args_contain": args_contain or ["push"]}],
        "created_at": "2026-05-24T20:00:00Z",
        "expires_at": "2099-01-01T00:00:00Z"
    }
    path.write_text(json.dumps(grant))
    return path


def run_hook(payload_dict, task_id_env=None, session_id_env=None):
    env = os.environ.copy()
    env.pop("CLAUDE_TASK_ID", None)
    env.pop("CLAUDE_SESSION_ID", None)
    if task_id_env:
        env["CLAUDE_TASK_ID"] = task_id_env
    if session_id_env:
        env["CLAUDE_SESSION_ID"] = session_id_env
    result = subprocess.run(
        ["python3", HOOK],
        input=json.dumps(payload_dict).encode(),
        capture_output=True,
        env=env,
        cwd=CWD,
    )
    return result


def run_pretool(payload_dict, session_id_env=None):
    env = os.environ.copy()
    env.pop("CLAUDE_TASK_ID", None)
    env.pop("CLAUDE_SESSION_ID", None)
    if session_id_env:
        env["CLAUDE_SESSION_ID"] = session_id_env
    result = subprocess.run(
        ["bash", PRETOOL],
        input=json.dumps(payload_dict).encode(),
        capture_output=True,
        env=env,
        cwd=CWD,
    )
    return result


violations = []
results = {}


# ---- AC1 canonical: subagent "git push" --------------------------------
print("=== AC1: Subagent canonical (git push) ===")
sid = "ac1-canonical-qa"
tid = "task-ac1-canonical-qa"
legacy = setup_legacy_grant(sid, pattern="git push")
sentinel = setup_sentinel_grant(tid, sid)
cmd_canonical = "git" + " " + "push"
payload = {
    "tool_name": "Bash",
    "tool_input": {"command": cmd_canonical},
    "agent_id": "test-subagent",
    "session_id": sid,
    "tool_response": {"exit_code": 0},
}
r = run_hook(payload, task_id_env=tid)
legacy_absent = not legacy.exists()
sentinel_absent = not sentinel.exists()
print(f"  exit={r.returncode} legacy_absent={legacy_absent} sentinel_absent={sentinel_absent}")
print(f"  stderr: {r.stderr.decode()[:300]}")
ac1_canonical = r.returncode == 0 and legacy_absent and sentinel_absent
results["AC1_canonical"] = ac1_canonical
if not ac1_canonical:
    violations.append({
        "ac": "AC1_canonical",
        "exit": r.returncode,
        "legacy_absent": legacy_absent,
        "sentinel_absent": sentinel_absent,
        "stderr": r.stderr.decode()[:300],
    })

# ---- AC1 whitespace: subagent "git   push" -----------------------------
print("=== AC1: Subagent whitespace variant (git   push) ===")
sid2 = "ac1-ws-qa"
tid2 = "task-ac1-ws-qa"
legacy2 = setup_legacy_grant(sid2, pattern="git push")
sentinel2 = setup_sentinel_grant(tid2, sid2)
cmd_ws = "git" + "   " + "push"
payload2 = {
    "tool_name": "Bash",
    "tool_input": {"command": cmd_ws},
    "agent_id": "test-subagent",
    "session_id": sid2,
    "tool_response": {"exit_code": 0},
}
r2 = run_hook(payload2, task_id_env=tid2)
legacy2_absent = not legacy2.exists()
sentinel2_absent = not sentinel2.exists()
print(f"  exit={r2.returncode} legacy_absent={legacy2_absent} sentinel_absent={sentinel2_absent}")
print(f"  stderr: {r2.stderr.decode()[:300]}")
ac1_ws = r2.returncode == 0 and legacy2_absent and sentinel2_absent
results["AC1_whitespace"] = ac1_ws
if not ac1_ws:
    violations.append({
        "ac": "AC1_whitespace",
        "detail": "whitespace-normalization divergence not fixed — sentinel matched but legacy not unlinked",
        "exit": r2.returncode,
        "legacy_absent": legacy2_absent,
        "sentinel_absent": sentinel2_absent,
    })

# ---- AC2: main-agent (no agent_id) ------------------------------------
print("=== AC2: Main-agent regression (no agent_id) ===")
sid3 = "ac2-main-qa"
legacy3 = setup_legacy_grant(sid3)
payload3 = {
    "tool_name": "Bash",
    "tool_input": {"command": "git" + " " + "push"},
    "session_id": sid3,
    "tool_response": {"exit_code": 0},
}
r3 = run_hook(payload3)
legacy3_absent = not legacy3.exists()
print(f"  exit={r3.returncode} legacy_absent={legacy3_absent}")
ac2 = r3.returncode == 0 and legacy3_absent
results["AC2"] = ac2
if not ac2:
    violations.append({
        "ac": "AC2",
        "exit": r3.returncode,
        "legacy_absent": legacy3_absent,
    })

# ---- AC4a: sentinel consumed on exit_code=0 ---------------------------
print("=== AC4a: Sentinel consumed (exit_code=0) ===")
sid4a = "ac4a-qa"
tid4a = "task-ac4a-qa"
s4a = setup_sentinel_grant(tid4a, sid4a)
payload4a = {
    "tool_name": "Bash",
    "tool_input": {"command": "git" + " " + "push"},
    "agent_id": "sub",
    "session_id": sid4a,
    "tool_response": {"exit_code": 0},
}
r4a = run_hook(payload4a, task_id_env=tid4a)
s4a_absent = not s4a.exists()
print(f"  exit={r4a.returncode} sentinel_absent={s4a_absent}")
ac4a = r4a.returncode == 0 and s4a_absent
results["AC4_exit0"] = ac4a
if not ac4a:
    violations.append({"ac": "AC4_exit0", "exit": r4a.returncode, "sentinel_absent": s4a_absent})

# ---- AC4b: sentinel consumed on exit_code=1 ---------------------------
print("=== AC4b: Sentinel consumed (exit_code=1) ===")
sid4b = "ac4b-qa"
tid4b = "task-ac4b-qa"
s4b = setup_sentinel_grant(tid4b, sid4b)
payload4b = {
    "tool_name": "Bash",
    "tool_input": {"command": "git" + " " + "push"},
    "agent_id": "sub",
    "session_id": sid4b,
    "tool_response": {"exit_code": 1},
}
r4b = run_hook(payload4b, task_id_env=tid4b)
s4b_absent = not s4b.exists()
print(f"  exit={r4b.returncode} sentinel_absent={s4b_absent}")
ac4b = r4b.returncode == 0 and s4b_absent
results["AC4_exit1"] = ac4b
if not ac4b:
    violations.append({"ac": "AC4_exit1", "exit": r4b.returncode, "sentinel_absent": s4b_absent})

# ---- AC5: absent legacy grant, no panic --------------------------------
print("=== AC5: Absent legacy grant, no panic ===")
sid5 = "ac5-qa"
tid5 = "task-ac5-qa"
Path(f"/tmp/claude-bash-allowlist-{sid5}.json").unlink(missing_ok=True)
s5 = setup_sentinel_grant(tid5, sid5)
payload5 = {
    "tool_name": "Bash",
    "tool_input": {"command": "git" + " " + "push"},
    "agent_id": "sub",
    "session_id": sid5,
    "tool_response": {"exit_code": 0},
}
r5 = run_hook(payload5, task_id_env=tid5)
s5_absent = not s5.exists()
has_traceback = "Traceback" in r5.stderr.decode()
print(f"  exit={r5.returncode} sentinel_absent={s5_absent} has_traceback={has_traceback}")
if r5.stderr.decode().strip():
    print(f"  stderr: {r5.stderr.decode()[:300]}")
ac5 = r5.returncode == 0 and not has_traceback and s5_absent
results["AC5"] = ac5
if not ac5:
    violations.append({
        "ac": "AC5",
        "exit": r5.returncode,
        "has_traceback": has_traceback,
        "sentinel_absent": s5_absent,
        "stderr": r5.stderr.decode()[:300],
    })

# ---- AC3: write firewall in userprompt-consent-allowlist.sh -----------
print("=== AC3: Write firewall (userprompt-consent-allowlist.sh) ===")
ALLOW_SCRIPT = str(Path(__file__).parent.parent.parent / "hooks" / "userprompt-consent-allowlist.sh")
sid_ac3 = "ac3-qa"
# Ensure no pre-existing files
Path(f"/tmp/claude-bash-allowlist-{sid_ac3}.json").unlink(missing_ok=True)
for f in Path("/tmp/claude-grants").glob("task-ac3-qa*.json"):
    f.unlink()
prompt_payload = json.dumps({"prompt": "/allow git" + " push", "session_id": sid_ac3, "agent_id": "subagent-123"})
r_ac3 = subprocess.run(
    ["bash", ALLOW_SCRIPT],
    input=prompt_payload.encode(),
    capture_output=True,
    cwd=CWD,
    env={**os.environ},
)
legacy_absent_ac3 = not Path(f"/tmp/claude-bash-allowlist-{sid_ac3}.json").exists()
sentinel_absent_ac3 = len(list(Path("/tmp/claude-grants").glob(f"task-ac3*"))) == 0
print(f"  exit={r_ac3.returncode} legacy_absent={legacy_absent_ac3} sentinel_absent={sentinel_absent_ac3}")
print(f"  stdout={r_ac3.stdout.decode()[:200]} stderr={r_ac3.stderr.decode()[:200]}")
ac3 = r_ac3.returncode == 0 and legacy_absent_ac3 and sentinel_absent_ac3
results["AC3"] = ac3
if not ac3:
    violations.append({
        "ac": "AC3",
        "exit": r_ac3.returncode,
        "legacy_absent": legacy_absent_ac3,
        "sentinel_absent": sentinel_absent_ac3,
    })

# ---- AC6: pretool-bash-safety.sh IS_SUBAGENT firewall -----------------
print("=== AC6: pretool IS_SUBAGENT firewall ===")
sid6 = "ac6-qa"
lg6 = setup_legacy_grant(sid6)
# Ensure no sentinel for this session
for f in Path("/tmp/claude-grants").glob(f"*{sid6}*.json"):
    f.unlink()
cmd6 = "git" + " " + "push"
payload6 = {
    "tool_name": "Bash",
    "tool_input": {"command": cmd6},
    "agent_id": "sub",
    "session_id": sid6,
}
r6 = run_pretool(payload6, session_id_env=sid6)
stdout6 = r6.stdout.decode()
stderr6 = r6.stderr.decode()
# Should NOT emit {"permissionDecision":"allow"} for legacy-only subagent
allows_via_legacy = '"allow"' in stdout6 and "permissionDecision" in stdout6
print(f"  exit={r6.returncode}")
print(f"  stdout={stdout6[:300]}")
print(f"  stderr={stderr6[:300]}")
print(f"  legacy_still_present={lg6.exists()} allows_via_legacy={allows_via_legacy}")
ac6 = not allows_via_legacy
results["AC6"] = ac6
if not ac6:
    violations.append({
        "ac": "AC6",
        "detail": "pretool issued allow for legacy-only subagent — IS_SUBAGENT firewall broken",
        "stdout": stdout6[:300],
    })
# Cleanup
lg6.unlink(missing_ok=True)

# ---- Final summary -----------------------------------------------------
print("\n=== SUMMARY ===")
all_pass = True
for k, v in results.items():
    status = "PASS" if v else "FAIL"
    if not v:
        all_pass = False
    print(f"  {k}: {status}")

print(f"\nOverall: {'PASS' if all_pass else 'FAIL'}")
print(f"Violations: {len(violations)}")

output = {
    "validator": "validate-posttool-ac-dev-20260524-205811",
    "status": "pass" if all_pass else "fail",
    "violations": violations,
    "summary": results,
}
print(json.dumps(output))
sys.exit(0 if all_pass else 1)
