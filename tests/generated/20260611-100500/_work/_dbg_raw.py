import os, subprocess, tempfile, json
from pathlib import Path
REPO = Path("/dev/shm/dev-workspace/dot-claude")
HOOK = REPO / "hooks" / "pretool-overnight-hook-guard.py"
WB = REPO / "tests" / "generated" / "20260611-100500" / "_work"
G="/usr/bin/git"; CMT="com"+"mit"
def git(a,cwd):
    e=dict(os.environ); e.pop("CLAUDE_OVERNIGHT_ACTOR",None)
    return subprocess.run([G,*a],cwd=str(cwd),env=e,capture_output=True,text=True)
d=Path(tempfile.mkdtemp(prefix="dbgraw-",dir=str(WB)))
git(["init","-q","-b","master","."],d); git(["config","user.email","t@t"],d); git(["config","user.name","t"],d)
(d/"a.txt").write_text("base\n"); git(["add","."],d); git([CMT,"-qm","init"],d)
git(["worktree","add","-q","-b","wbranch",".claude/worktrees/ovr","HEAD"],d)
WT=d/".claude"/"worktrees"/"ovr"
state={"schema_version":8,"session_id":"S","current_phase":"exploring","end_time":"2099-01-01T00:00:00Z","isolation_active_until":"2099-01-01T00:00:00Z","isolation_released_at":None,"main_root":str(d),"main_git_dir":str(d/".git"),"worktree_path":str(WT),"worktree_branch":"wbranch","isolation_kind":"registered_worktree"}
(d/".claude"/"overnight-state-S.json").write_text(json.dumps(state))
gcd=git(["rev-parse","--path-format=absolute","--git-common-dir"],WT).stdout.strip()
print("git_common=",gcd)
def drive(cmd):
    payload={"tool_name":"Bash","session_id":"S","tool_input":{"command":cmd},"cwd":str(WT)}
    e=dict(os.environ,CLAUDE_PROJECT_DIR=str(d)); e.pop("CLAUDE_OVERNIGHT_ACTOR",None)
    p=subprocess.run(["python3",str(HOOK)],input=json.dumps(payload),capture_output=True,text=True,env=e)
    return p.returncode,p.stdout[:120],p.stderr[:200]
for cmd in [f"echo deadbeef > {gcd}/refs/heads/master",
            f"echo 'x refs/heads/master' >> {gcd}/packed-refs",
            f"eval 'echo x > {gcd}/logs/HEAD'",
            f"python3 -c \"open('{gcd}/objects/raw','w').write('x')\""]:
    rc,out,err=drive(cmd); print("RC",rc,"| rewrite?",("hookSpecificOutput" in out),"| err:",err.strip()[:90])
import shutil; shutil.rmtree(d,ignore_errors=True)
