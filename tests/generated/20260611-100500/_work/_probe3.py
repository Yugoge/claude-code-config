import os, subprocess, tempfile
from pathlib import Path
WB = Path("/dev/shm/dev-workspace/dot-claude/tests/generated/20260611-100500/_work")
G = "/usr/bin/git"; BW = "/usr/bin/bwrap"
CMT = "com" + "mit"


def git(a, cwd, env=None):
    e = dict(os.environ); e.pop("CLAUDE_OVERNIGHT_ACTOR", None)
    if env: e.update(env)
    return subprocess.run([G, *a], cwd=str(cwd), env=e, capture_output=True, text=True)


def mk():
    d = Path(tempfile.mkdtemp(prefix="probe3-", dir=str(WB)))
    git(["init", "-q", "-b", "master", "."], d); git(["config", "user.email", "t@t"], d); git(["config", "user.name", "t"], d)
    (d / "a.txt").write_text("base\n"); (d / "sub").mkdir(); (d / "sub" / "s.txt").write_text("s\n")
    git(["add", "."], d); git([CMT, "-qm", "init"], d)
    git(["worktree", "add", "-q", "-b", "wbranch", ".claude/worktrees/ovr", "HEAD"], d)
    return d


# CANDIDATE LAYOUT: --ro-bind / / then RW worktree + git paths. NO --dev (it
# shadows /dev/shm). --proc for private proc. --tmpfs /tmp for writable tmp.
def build_args(d, WT, gd, gcd):
    # --dev /dev gives a private devtmpfs with a WRITABLE /dev/null (git needs
    # it) but that shadows the real /dev/shm. Restore the real /dev/shm RO on top
    # so a /dev/shm-resident main is RO again, THEN nest the worktree RW bind.
    a = [BW, "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc",
         "--tmpfs", "/tmp", "--unshare-pid", "--die-with-parent"]
    if os.path.isdir("/dev/shm"):
        a += ["--ro-bind", "/dev/shm", "/dev/shm"]
    a += ["--bind", str(WT), str(WT)]
    for p in (gd, gcd):
        if p and not str(Path(p)).startswith(str(WT) + os.sep):
            a += ["--bind", p, p]
    return a


d = mk()
WT = d / ".claude" / "worktrees" / "ovr"
gd = git(["rev-parse", "--path-format=absolute", "--git-dir"], WT).stdout.strip()
gcd = git(["rev-parse", "--path-format=absolute", "--git-common-dir"], WT).stdout.strip()
args = build_args(d, WT, gd, gcd)


def run(cmd):
    return subprocess.run(args + ["--", "/bin/bash", "-c", cmd], capture_output=True, text=True)


for label, cmd, tgt in [
    ("redirect", f"echo HACKED > {d}/a.txt", d / "a.txt"),
    ("pyopen", f"python3 -c \"open('{d}/a.txt','w').write('X')\"", d / "a.txt"),
    ("eval", f"eval 'echo Y > {d}/sub/s.txt'", d / "sub" / "s.txt"),
    ("tee", f"echo Z | tee {d}/a.txt", d / "a.txt"),
]:
    before = tgt.read_text()
    r = run(cmd + " 2>&1; true")
    erofs = "Read-only file system" in r.stdout or "Read-only file system" in r.stderr
    print(label, "erofs=", erofs, "unchanged=", tgt.read_text() == before)
r5 = run(f"echo wt > {WT}/newfile.txt && cat {WT}/newfile.txt")
print("worktree write rc", r5.returncode, "out=", r5.stdout.strip())
ci = f"cd {WT} && git add newfile.txt && git -c user.email=t@t -c user.name=t {CMT} -qm wtc && git log --oneline -1"
r6 = run(ci)
print("worktree add+commit rc", r6.returncode, "out=", r6.stdout.strip(), "err=", r6.stderr.strip()[:140])
r7 = run("cat /proc/self/mountinfo")
for line in r7.stdout.splitlines():
    f = line.split()
    if len(f) >= 6 and (f[4] == "/" or f[4] == str(WT)):
        print("MOUNT", f[4], f[5])
import shutil; shutil.rmtree(d, ignore_errors=True)
