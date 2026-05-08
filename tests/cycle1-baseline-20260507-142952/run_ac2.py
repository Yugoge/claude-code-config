#!/usr/bin/env python3
"""AC-2 verification: subagentstop-cp-enforce.py orphan finalization."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = "/root/.claude/hooks/subagentstop-cp-enforce.py"


def run_stop(payload, project_dir):
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = project_dir
    proc = subprocess.run(
        ["python3", HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    return proc


def fresh_project():
    p = tempfile.mkdtemp(prefix="qa-stop-", dir="/tmp/qa-20260507-142952")
    os.makedirs(os.path.join(p, ".claude", "specs", "spec-x"), exist_ok=True)
    return p


def write_cp(project_dir, role, payload):
    path = os.path.join(project_dir, ".claude", "specs", "spec-x", f"cp-state-{role}.json")
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    return path


def read_cp(path):
    with open(path) as f:
        return json.load(f)


cases = []


# === AC-2.1 critical: synthetic orphan with agent_id=null, is_running=true,
#                      empty checkpoints. Expect Stop hook finalizes it.
def case_ac2_1():
    pdir = fresh_project()
    orphan = write_cp(pdir, "ba", {
        "agent_id": None,
        "agent_type": "ba",
        "is_running": True,
        "checked_in_at": "2026-05-07T13:00:00Z",
        "checkpoints": [],
    })
    # Stop event from a DIFFERENT agent (the orphan is invisible to its agent_id match)
    proc = run_stop({"agent_id": "different-agent-xyz"}, pdir)
    after = read_cp(orphan)
    ok = (
        proc.returncode == 0
        and after.get("is_running") is False
        and after.get("checked_out_at") is not None
        and "orphan-finalize" in proc.stderr
    )
    return ("AC-2.1 orphan agent_id=null finalized by stranger Stop", ok, {
        "rc": proc.returncode,
        "stderr_snippet": proc.stderr[:300],
        "after.is_running": after.get("is_running"),
        "after.checked_out_at": after.get("checked_out_at"),
    })


cases.append(case_ac2_1)


# === AC-2.2: orphan with dead pid, is_running=true, empty checkpoints. Expect finalize.
def case_ac2_2():
    pdir = fresh_project()
    # PID 999999 is essentially guaranteed dead
    orphan = write_cp(pdir, "qa", {
        "agent_id": "some-aid",
        "agent_type": "qa",
        "is_running": True,
        "pid": 999999,
        "checked_in_at": "2026-05-07T13:00:00Z",
        "checkpoints": [{"id": "cp-1", "state": "done"}],
    })
    proc = run_stop({"agent_id": "different-agent"}, pdir)
    after = read_cp(orphan)
    ok = (
        proc.returncode == 0
        and after.get("is_running") is False
        and after.get("checked_out_at") is not None
    )
    return ("AC-2.2 orphan with dead pid finalized", ok, {
        "rc": proc.returncode,
        "stderr_snippet": proc.stderr[:300],
        "after.is_running": after.get("is_running"),
    })


cases.append(case_ac2_2)


# === AC-2.3 (CRITICAL M11 INVARIANT): orphan with PENDING checkpoints + agent_id=null
#     -> orphan finalize MUST NOT touch this slot (M11 invariant preserved).
def case_ac2_3():
    pdir = fresh_project()
    orphan = write_cp(pdir, "pm", {
        "agent_id": None,  # orphaned shape
        "agent_type": "pm",
        "is_running": True,
        "checked_in_at": "2026-05-07T13:00:00Z",
        "checkpoints": [{"id": "cp-1", "state": "pending"}],  # but pending!
    })
    proc = run_stop({"agent_id": "different-agent"}, pdir)
    after = read_cp(orphan)
    # The slot's agent_id is null, so it CANNOT be the "live" pending block keyed off agent_id="different-agent".
    # The Stop hook _dispatch returns 0 (no active state for "different-agent" id).
    # Then orphan backstop runs but skips this slot because of pending. So is_running stays True.
    ok = after.get("is_running") is True
    return ("AC-2.3 orphan WITH pending checkpoints NOT finalized (M11)", ok, {
        "rc": proc.returncode,
        "after.is_running": after.get("is_running"),
        "stderr_snippet": proc.stderr[:300],
    })


cases.append(case_ac2_3)


# === AC-2.4: alive Stop case — owning agent_id matches its slot, all checkpoints done.
#     Expect normal clean finalize (rc=0, slot is_running=false).
def case_ac2_4():
    pdir = fresh_project()
    cp_file = write_cp(pdir, "ba", {
        "agent_id": "owning-aid-1",
        "agent_type": "ba",
        "is_running": True,
        "checked_in_at": "2026-05-07T13:00:00Z",
        "checkpoints": [{"id": "cp-1", "state": "done"}],
    })
    proc = run_stop({"agent_id": "owning-aid-1"}, pdir)
    after = read_cp(cp_file)
    ok = proc.returncode == 0 and after.get("is_running") is False
    return ("AC-2.4 normal clean dispatch (owning agent, no pending)", ok, {
        "rc": proc.returncode,
        "after.is_running": after.get("is_running"),
    })


cases.append(case_ac2_4)


# === AC-2.5: M11 normal — owning agent_id matches its slot, ONE pending checkpoint, NOT timed out.
#     Expect rc=2 (block), is_running stays True.
def case_ac2_5():
    pdir = fresh_project()
    from datetime import datetime, timezone
    fresh_now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    cp_file = write_cp(pdir, "ba", {
        "agent_id": "owning-aid-2",
        "agent_type": "ba",
        "is_running": True,
        "checked_in_at": fresh_now,
        "checkpoints": [{"id": "cp-1", "state": "pending"}, {"id": "cp-2", "state": "done"}],
    })
    proc = run_stop({"agent_id": "owning-aid-2"}, pdir)
    after = read_cp(cp_file)
    ok = proc.returncode == 2 and after.get("is_running") is True
    return ("AC-2.5 M11 normal block on pending (rc=2)", ok, {
        "rc": proc.returncode,
        "after.is_running": after.get("is_running"),
        "stderr_snippet": proc.stderr[:300],
    })


cases.append(case_ac2_5)


# === AC-2.6: orphan with completed checkpoints (no pending) but pid alive (current process pid).
#     pid is alive AND agent_id is null, so the agent_id-null path triggers finalize.
#     Verify still finalizes via agent_id=null branch.
def case_ac2_6():
    pdir = fresh_project()
    orphan = write_cp(pdir, "qa", {
        "agent_id": None,
        "agent_type": "qa",
        "is_running": True,
        "pid": os.getpid(),  # ALIVE pid
        "checked_in_at": "2026-05-07T13:00:00Z",
        "checkpoints": [],
    })
    proc = run_stop({"agent_id": "different"}, pdir)
    after = read_cp(orphan)
    # _is_orphan_slot returns True if agent_id is None (regardless of pid liveness).
    # So this should still finalize.
    ok = after.get("is_running") is False
    return ("AC-2.6 orphan with agent_id=null + alive pid still finalizes", ok, {
        "rc": proc.returncode,
        "after.is_running": after.get("is_running"),
    })


cases.append(case_ac2_6)


# === Run
passed = failed = 0
results = []
for c in cases:
    name, ok, detail = c()
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}")
    if not ok:
        print(f"    detail: {detail}")
    results.append({"case": name, "passed": ok, "detail": detail})
    if ok:
        passed += 1
    else:
        failed += 1

print(f"\nAC-2 summary: {passed} passed, {failed} failed of {len(cases)}")
with open("/tmp/qa-20260507-142952/ac2-results.json", "w") as f:
    json.dump({"passed": passed, "failed": failed, "total": len(cases), "results": results}, f, indent=2)
sys.exit(0 if failed == 0 else 1)
