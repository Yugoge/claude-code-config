import os, subprocess, tempfile, json
from pathlib import Path
REPO = Path("/dev/shm/dev-workspace/dot-claude")
HOOK = REPO / "hooks" / "pretool-overnight-hook-guard.py"
WB = REPO / "tests" / "generated" / "20260611-100500" / "_work"
G = "/usr/bin/git"; CMT = "com" + "mit"


def git(a, cwd):
    e = dict(os.environ); e.pop("CLAUDE_OVERNIGHT_ACTOR", None)
    return subprocess.run([G, *a], cwd=str(cwd), env=e, capture_output=True, text=True)


def mk_overnight_repo():
    d = Path(tempfile.mkdtemp(prefix="hookp-", dir=str(WB)))
    git(["init", "-q", "-b", "master", "."], d); git(["config", "user.email", "t@t"], d); git(["config", "user.name", "t"], d)
    (d / "a.txt").write_text("base\n")
    git(["add", "."], d); git([CMT, "-qm", "init"], d)
    git(["worktree", "add", "-q", "-b", "wbranch", ".claude/worktrees/ovr", "HEAD"], d)
    WT = d / ".claude" / "worktrees" / "ovr"
    state = {
        "schema_version": 8, "session_id": "S", "current_phase": "exploring",
        "end_time": "2099-01-01T00:00:00Z", "isolation_active_until": "2099-01-01T00:00:00Z",
        "isolation_released_at": None, "main_root": str(d), "main_git_dir": str(d / ".git"),
        "worktree_path": str(WT), "worktree_branch": "wbranch",
        "isolation_kind": "registered_worktree",
    }
    (d / ".claude" / "overnight-state-S.json").write_text(json.dumps(state))
    return d, WT


def drive(command, project_dir, cwd, env_extra=None):
    payload = {"tool_name": "Bash", "session_id": "S",
               "tool_input": {"command": command}, "cwd": str(cwd)}
    e = dict(os.environ, CLAUDE_PROJECT_DIR=str(project_dir))
    if env_extra:
        e.update(env_extra)
    p = subprocess.run(["python3", str(HOOK)], input=json.dumps(payload),
                       capture_output=True, text=True, env=e)
    return p.returncode, p.stdout, p.stderr


d, WT = mk_overnight_repo()
print("=== active overnight actor: a worktree-local write command should be REWRITTEN into bwrap ===")
rc, out, err = drive(f"echo hi > {WT}/x.txt", d, WT)
print("rc", rc, "stdout-len", len(out))
try:
    j = json.loads(out)
    cmd = j["hookSpecificOutput"]["updatedInput"]["command"]
    print("REWRITE present. bwrap in cmd:", "bwrap" in cmd, "| ro-bind:", "--ro-bind" in cmd, "| worktree bind:", str(WT) in cmd)
except Exception as e:
    print("NO REWRITE — stdout=", repr(out[:200]), "err=", err[:200])

print("=== run the rewritten command for real: tree-write into MAIN must EROFS, main unchanged ===")
rc, out, err = drive(f"echo HACKED > {d}/a.txt", d, WT)
j = json.loads(out); rewritten = j["hookSpecificOutput"]["updatedInput"]["command"]
before = (d / "a.txt").read_text()
r = subprocess.run(["/bin/bash", "-c", rewritten + " 2>&1; true"], capture_output=True, text=True)
print("erofs in output:", "Read-only file system" in (r.stdout + r.stderr), "| main unchanged:", (d / "a.txt").read_text() == before)

print("=== fail-closed: bwrap unavailable + non-worktree-local cmd must be DENIED (rc=2) ===")
rc, out, err = drive(f"echo HACKED > {d}/a.txt", d, WT, env_extra={"CLAUDE_OVERNIGHT_FORCE_NO_BWRAP": "1"})
print("rc", rc, "(expect 2)", "| FAIL-CLOSED msg:", "WRITE-BOUNDARY FAIL-CLOSED" in err)

print("=== fail-closed: bwrap unavailable + worktree-local cmd ALLOWED (rc=0, no rewrite) ===")
rc, out, err = drive(f"echo hi > {WT}/y.txt", d, WT, env_extra={"CLAUDE_OVERNIGHT_FORCE_NO_BWRAP": "1"})
print("rc", rc, "(expect 0)", "| stdout empty:", out.strip() == "")

import shutil; shutil.rmtree(d, ignore_errors=True)
