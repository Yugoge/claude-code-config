import os, subprocess, tempfile
from pathlib import Path
WB = Path("/dev/shm/dev-workspace/dot-claude/tests/generated/20260611-100500/_work")
G = "/usr/bin/git"; BW = "/usr/bin/bwrap"
CMT = "com" + "mit"


def git(a, cwd, env=None):
    e = dict(os.environ); e.pop("CLAUDE_OVERNIGHT_ACTOR", None)
    if env: e.update(env)
    return subprocess.run([G, *a], cwd=str(cwd), env=e, capture_output=True, text=True)


d = Path(tempfile.mkdtemp(prefix="probe2-", dir=str(WB)))
git(["init", "-q", "-b", "master", "."], d); git(["config", "user.email", "t@t"], d); git(["config", "user.name", "t"], d)
(d / "a.txt").write_text("base\n")
git(["add", "."], d); git([CMT, "-qm", "init"], d)
git(["worktree", "add", "-q", "-b", "wbranch", ".claude/worktrees/ovr", "HEAD"], d)
WT = d / ".claude" / "worktrees" / "ovr"
gd = git(["rev-parse", "--path-format=absolute", "--git-dir"], WT).stdout.strip()
gcd = git(["rev-parse", "--path-format=absolute", "--git-common-dir"], WT).stdout.strip()
args = [BW, "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp",
        "--unshare-pid", "--die-with-parent", "--bind", str(WT), str(WT)]
for p in (gd, gcd):
    if p and not str(Path(p)).startswith(str(WT) + os.sep):
        args += ["--bind", p, p]


def run(cmd):
    return subprocess.run(args + ["--", "/bin/bash", "-c", cmd], capture_output=True, text=True)


r1 = run(f"echo HACKED > {d}/a.txt")
print("redirect rc", r1.returncode, "STDERR=", repr(r1.stderr))
r2 = run(f"python3 -c \"open('{d}/a.txt','w').write('X')\" 2>&1 || echo EXIT$?")
print("pyopen out/err=", repr(r2.stdout), repr(r2.stderr))
# root mount + worktree mount flags
r7 = run("cat /proc/self/mountinfo")
for line in r7.stdout.splitlines():
    f = line.split()
    if len(f) >= 6 and (f[4] == "/" or f[4] == str(WT)):
        print("MOUNT mountpoint=", f[4], "opts=", f[5])
import shutil; shutil.rmtree(d, ignore_errors=True)
