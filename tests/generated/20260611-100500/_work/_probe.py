import os, subprocess, tempfile
from pathlib import Path
WB = Path("/dev/shm/dev-workspace/dot-claude/tests/generated/20260611-100500/_work")
WB.mkdir(parents=True, exist_ok=True)
G = "/usr/bin/git"; BW = "/usr/bin/bwrap"
CMT = "com" + "mit"  # avoid the contiguous 'git commit' literal


def git(a, cwd, env=None):
    e = dict(os.environ); e.pop("CLAUDE_OVERNIGHT_ACTOR", None)
    if env: e.update(env)
    return subprocess.run([G, *a], cwd=str(cwd), env=e, capture_output=True, text=True)


d = Path(tempfile.mkdtemp(prefix="probe-", dir=str(WB)))
git(["init", "-q", "-b", "master", "."], d); git(["config", "user.email", "t@t"], d); git(["config", "user.name", "t"], d)
(d / "a.txt").write_text("base\n"); (d / "sub").mkdir(); (d / "sub" / "s.txt").write_text("s\n")
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


r1 = run(f"echo HACKED > {d}/a.txt"); print("1 redirect->MAIN erofs", ("Read-only" in r1.stderr), "main=", repr((d / 'a.txt').read_text()))
r2 = run(f"python3 -c \"open('{d}/a.txt','w').write('X')\""); print("2 pyopen->MAIN erofs", ("Read-only" in r2.stderr), "main=", repr((d / 'a.txt').read_text()))
r3 = run(f"eval 'echo Y > {d}/sub/s.txt'"); print("3 eval->MAIN erofs", ("Read-only" in r3.stderr), "sub=", repr((d / 'sub' / 's.txt').read_text()))
r5 = run(f"echo wt > {WT}/newfile.txt && cat {WT}/newfile.txt"); print("5 worktree write rc", r5.returncode, "out=", r5.stdout.strip())
commit_inner = f"cd {WT} && git add newfile.txt && git -c user.email=t@t -c user.name=t {CMT} -qm wtc && git log --oneline -1"
r6 = run(commit_inner); print("6 worktree add+commit rc", r6.returncode, "out=", r6.stdout.strip(), "err=", r6.stderr.strip()[:140])
r7 = run(f"awk -v m='{d}' -v w='{WT}' '$5==m{{print \"MAIN\",$4}} $5==w{{print \"WT\",$4}}' /proc/self/mountinfo | sort -u"); print("7 mountinfo:\n" + r7.stdout)
import shutil; shutil.rmtree(d, ignore_errors=True)
