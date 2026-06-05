"""Throwaway live exit-code verifier for pretool-block-branch-pr-worktree.py.

Lives as a file so the dangerous command strings are NOT on the Bash command
surface (the hook itself would otherwise block this verification run). Delete
after use.
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(__file__), '..',
                    'pretool-block-branch-pr-worktree.py')
WORK = tempfile.mkdtemp()


def run(cmd):
    env = dict(os.environ)
    env.pop('CLAUDE_TASK_ID', None)
    env.pop('CLAUDE_SESSION_ID', None)
    env['CLAUDE_PROJECT_DIR'] = WORK
    payload = {"tool_name": "Bash", "session_id": "x",
               "tool_input": {"command": cmd}}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, cwd=WORK, env=env)
    return p.returncode


BLOCK = [
    'gh pr new --fill',
    'gh -R o/r pr new',
    'git switch --cr foo',
    'git checkout --or foo',
    'git checkout --tr origin/x',
    'git switch --g foo',
    'git switch --force-c foo',
    'git stash branch foo',
    'git fetch . HEAD:refs/heads/foo',
    'git pull origin x:refs/heads/foo',
    'git update-ref refs/heads/foo HEAD',
    'echo $(git checkout -b foo)',
    'x=$(git switch -c foo)',
    'result=`git checkout -b foo`',
]

ALLOW = [
    'gh pr list',
    'gh pr view 3',
    'git switch --detach',
    'git switch --force',
    'git switch --no-track',
    'git checkout --force',
    'git checkout --ours x',
    'git checkout --theirs x',
    'git stash',
    'git stash list',
    'git stash pop',
    'git fetch',
    'git fetch origin',
    'git fetch --all',
    'git pull origin main',
    'git update-ref -d refs/heads/foo',
    'echo $(git status)',
    'git log --format %(refname)',
    'git branch --format %(refname)',
    'git switch master',
    'git checkout master',
]

fail = 0
print("=== MUST BLOCK (expect 2) ===")
for c in BLOCK:
    rc = run(c)
    ok = rc == 2
    fail |= (not ok)
    print(f"{'OK' if ok else 'WRONG':6s} rc={rc}  {c}")

print("\n=== MUST ALLOW (expect 0) ===")
for c in ALLOW:
    rc = run(c)
    ok = rc == 0
    fail |= (not ok)
    print(f"{'OK' if ok else 'WRONG':6s} rc={rc}  {c}")

print("\nOVERALL:", "ALL_CORRECT" if not fail else "HAS_DEVIATIONS")
