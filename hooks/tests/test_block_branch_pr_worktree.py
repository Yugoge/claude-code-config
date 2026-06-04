"""Unit tests for hooks/pretool-block-branch-pr-worktree.py.

The hook forbids branch / PR / worktree CREATION in EVERY context except a live
/dev-overnight session OWNED BY THE CALLING SESSION. dev-overnight is the sole
exception — /do and /allow do NOT bypass it (strict, per "永远禁止").

Tests invoke the hook as a subprocess (the way the harness does) and assert the
exit code: 0 = allow, 2 = block.

Run with: python3 -m pytest hooks/tests/test_block_branch_pr_worktree.py -v
"""

import json
import os
import subprocess
import sys

import pytest

HOOK = os.path.join(
    os.path.dirname(__file__), '..', 'pretool-block-branch-pr-worktree.py')


def _run(payload, project_dir):
    """Run the hook with payload on stdin.

    project_dir is pinned as both cwd and CLAUDE_PROJECT_DIR (a non-git tmp dir)
    so overnight detection is deterministic. Inherited overnight/session env is
    stripped so a real live session can never leak a bypass into block tests.
    """
    env = dict(os.environ)
    env.pop('CLAUDE_SESSION_ID', None)
    env['CLAUDE_PROJECT_DIR'] = str(project_dir)
    proc = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True, text=True, cwd=str(project_dir), env=env,
    )
    return proc.returncode, proc.stderr


def _bash(cmd, **extra):
    p = {'tool_name': 'Bash', 'tool_input': {'command': cmd}}
    p.update(extra)
    return p


# ── Blocked: branch creation (incl. attached / path-qualified / clustered) ───

@pytest.mark.parametrize('cmd', [
    'git checkout -b feature/x',
    'git checkout -B feature/x',
    'git checkout --orphan gh-pages',
    'git checkout -bfeature',           # attached short-opt value
    'git switch -c feature/x',
    'git switch -C feature/x',
    'git switch --create feature/x',
    'git switch --force-create feature/x',
    'git switch -cfeature',             # attached short-opt value
    'git branch new-feature',
    'git branch new-feature origin/master',
    'git branch -c old new',            # copy creates a branch
    'git branch -f forced start',       # force create/reset
    'git -C /some/repo branch newbr',   # git global-option prefix
    '/usr/bin/git checkout -b bypass',  # path-qualified git
    'git worktree add -b br ../wt HEAD',
    'true && git checkout -b chained',
    'sudo git checkout -b withsudo',
])
def test_branch_creation_blocked(cmd, tmp_path):
    rc, _ = _run(_bash(cmd), tmp_path)
    assert rc == 2, f'expected block for: {cmd}'


# ── Blocked: worktree / PR creation (incl. interspersed gh flags) ────────────

@pytest.mark.parametrize('cmd', [
    'git worktree add ../wt feature',
    '/usr/bin/git worktree add ../wt HEAD',
    'gh pr create --fill',
    'gh pr create --title x --body y',
    'gh -R cli/cli pr create --fill',   # global flag before pr
    'gh pr -R cli/cli create --fill',   # global flag between pr and create
    '/usr/bin/gh pr create --fill',     # path-qualified gh
])
def test_worktree_and_pr_creation_blocked(cmd, tmp_path):
    rc, _ = _run(_bash(cmd), tmp_path)
    assert rc == 2, f'expected block for: {cmd}'


def test_enterworktree_tool_blocked(tmp_path):
    rc, _ = _run({'tool_name': 'EnterWorktree', 'tool_input': {'name': 'wt'}},
                 tmp_path)
    assert rc == 2


# ── Allowed: non-creation git/gh forms ───────────────────────────────────────

@pytest.mark.parametrize('cmd', [
    'git branch',                      # list
    'git branch -a',
    'git branch -r',
    'git branch -v',
    'git branch -rl "*"',              # clustered short flags (list remotes)
    'git branch -avv',                 # clustered short flags
    'git branch --list "feat/*"',
    'git branch --show-current',
    'git branch --contains HEAD',      # value-flag, not creation
    'git branch -d old-feature',       # delete
    'git branch -D old-feature',
    'git branch -m old new',           # rename
    'git branch -u origin/x',          # set upstream
    'git branch --merged',
    'git worktree list',
    'git worktree remove ../wt',
    'git worktree prune',
    'git status',
    'git switch master',               # switch to existing, no -c
    'git checkout master',             # checkout existing, no -b
    'git checkout -- -b',              # pathspec literally named -b
    'gh pr list',
    'gh pr view 12',
    'gh pr checkout 12',
    'gh pr status',
])
def test_non_creation_forms_allowed(cmd, tmp_path):
    rc, _ = _run(_bash(cmd), tmp_path)
    assert rc == 0, f'expected allow for: {cmd}'


def test_quoted_branch_text_not_matched(tmp_path):
    # `git checkout -b foo` inside a quoted echo arg is non-executable -> allowed.
    rc, _ = _run(_bash('echo "to create run: git checkout -b foo"'), tmp_path)
    assert rc == 0


def test_non_bash_non_worktree_tool_ignored(tmp_path):
    rc, _ = _run({'tool_name': 'Read', 'tool_input': {'file_path': '/x'}},
                 tmp_path)
    assert rc == 0


def test_empty_command_allowed(tmp_path):
    rc, _ = _run(_bash(''), tmp_path)
    assert rc == 0


def test_malformed_stdin_fails_open(tmp_path):
    env = dict(os.environ)
    env['CLAUDE_PROJECT_DIR'] = str(tmp_path)
    proc = subprocess.run(
        [sys.executable, HOOK], input='not json',
        capture_output=True, text=True, cwd=str(tmp_path), env=env)
    assert proc.returncode == 0


# ── Strict: /do consent does NOT bypass this rule ────────────────────────────

def test_do_consent_does_not_bypass(tmp_path):
    sid = f'test-do-{os.getpid()}'
    flag = f'/tmp/claude-orchestrator-consent-{sid}.flag'
    with open(flag, 'w') as fh:
        fh.write('true')
    try:
        rc, _ = _run(_bash('git checkout -b feature/x', session_id=sid), tmp_path)
        assert rc == 2  # strict: consent is irrelevant
    finally:
        os.unlink(flag)


# ── The sole exception: a live /dev-overnight session owned by this session ──

def _write_overnight_state(project_dir, sid, live=True, owner=None):
    claude = project_dir / '.claude'
    claude.mkdir(parents=True, exist_ok=True)
    end = '2099-01-01T00:00:00Z' if live else '2000-01-01T00:00:00Z'
    state = {
        'current_phase': 'exploring' if live else 'complete',
        'end_time': end,
        'session_id': owner if owner is not None else sid,
    }
    (claude / f'overnight-state-{sid}.json').write_text(json.dumps(state))


@pytest.mark.parametrize('cmd', [
    'git checkout -b feature/x',
    'git worktree add ../wt feature',
    'gh pr create --fill',
    'git branch new-feature',
])
def test_creation_allowed_during_owned_live_overnight(cmd, tmp_path):
    sid = 'sess-own'
    _write_overnight_state(tmp_path, sid, live=True)
    rc, _ = _run(_bash(cmd, session_id=sid), tmp_path)
    assert rc == 0, f'expected allow during owned live overnight for: {cmd}'


def test_enterworktree_allowed_during_owned_live_overnight(tmp_path):
    sid = 'sess-own'
    _write_overnight_state(tmp_path, sid, live=True)
    rc, _ = _run({'tool_name': 'EnterWorktree', 'session_id': sid,
                  'tool_input': {'name': 'wt'}}, tmp_path)
    assert rc == 0


def test_creation_blocked_when_overnight_completed(tmp_path):
    sid = 'sess-own'
    _write_overnight_state(tmp_path, sid, live=False)
    rc, _ = _run(_bash('git checkout -b feature/x', session_id=sid), tmp_path)
    assert rc == 2


def test_forged_state_owned_by_other_session_does_not_bypass(tmp_path):
    # A live state file owned by a DIFFERENT session must not grant a bypass —
    # this is the anti-forgery binding (codex finding #1).
    _write_overnight_state(tmp_path, 'other-sess', live=True, owner='other-sess')
    rc, _ = _run(_bash('git checkout -b feature/x', session_id='attacker'),
                 tmp_path)
    assert rc == 2


def test_state_without_session_id_does_not_bypass(tmp_path):
    sid = 'sess-x'
    claude = tmp_path / '.claude'
    claude.mkdir(parents=True, exist_ok=True)
    (claude / f'overnight-state-{sid}.json').write_text(json.dumps(
        {'current_phase': 'exploring', 'end_time': '2099-01-01T00:00:00Z'}))
    rc, _ = _run(_bash('git checkout -b feature/x', session_id=sid), tmp_path)
    assert rc == 2


def test_missing_session_id_in_payload_blocks(tmp_path):
    # No caller session_id -> cannot own any state -> blocked.
    _write_overnight_state(tmp_path, 'sess-own', live=True)
    rc, _ = _run(_bash('git checkout -b feature/x'), tmp_path)
    assert rc == 2
