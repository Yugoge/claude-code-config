"""Unit tests for hooks/pretool-block-branch-pr-worktree.py.

The hook forbids branch / PR / worktree CREATION on the Bash surface, with three
bypasses (in order): a live /dev-overnight session, /do consent (main agent),
and a /allow grant. The EnterWorktree tool is governed by a separate hook
(pretool-block-enterworktree.sh) and is intentionally ignored here.

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


def _run(payload, project_dir, env_extra=None):
    """Run the hook with payload on stdin.

    project_dir is pinned as both cwd and CLAUDE_PROJECT_DIR (a non-git tmp dir)
    so overnight detection is deterministic. CLAUDE_TASK_ID / CLAUDE_SESSION_ID
    are stripped so an inherited sentinel/consent from the live session can never
    leak a bypass into the block-path tests.
    """
    env = dict(os.environ)
    env.pop('CLAUDE_TASK_ID', None)
    env.pop('CLAUDE_SESSION_ID', None)
    env['CLAUDE_PROJECT_DIR'] = str(project_dir)
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True, text=True, cwd=str(project_dir), env=env,
    )
    return proc.returncode, proc.stderr


def _bash(cmd):
    return {'tool_name': 'Bash', 'tool_input': {'command': cmd}}


# ── Blocked: branch creation ─────────────────────────────────────────────────

@pytest.mark.parametrize('cmd', [
    'git checkout -b feature/x',
    'git checkout -B feature/x',
    'git checkout --orphan gh-pages',
    'git switch -c feature/x',
    'git switch -C feature/x',
    'git switch --create feature/x',
    'git branch new-feature',
    'git branch new-feature origin/master',
    'git branch -c old new',           # copy creates a branch
    'git -C /some/repo branch newbr',  # global-option prefix
    'true && git checkout -b chained',
])
def test_branch_creation_blocked(cmd, tmp_path):
    rc, _ = _run(_bash(cmd), tmp_path)
    assert rc == 2, f'expected block for: {cmd}'


# ── Blocked: worktree / PR creation ──────────────────────────────────────────

@pytest.mark.parametrize('cmd', [
    'git worktree add ../wt feature',
    'git worktree add -b br ../wt HEAD',
    'gh pr create --fill',
    'gh pr create --title x --body y',
])
def test_worktree_and_pr_creation_blocked(cmd, tmp_path):
    rc, _ = _run(_bash(cmd), tmp_path)
    assert rc == 2, f'expected block for: {cmd}'


# ── Allowed: non-creation git/gh forms ───────────────────────────────────────

@pytest.mark.parametrize('cmd', [
    'git branch',                      # list
    'git branch -a',
    'git branch -r',
    'git branch -v',
    'git branch --list "feat/*"',
    'git branch --show-current',
    'git branch -d old-feature',       # delete (not creation)
    'git branch -D old-feature',
    'git branch -m old new',           # rename
    'git branch --merged',
    'git worktree list',
    'git worktree remove ../wt',
    'git worktree prune',
    'git status',
    'git switch master',               # switch to existing, no -c
    'git checkout master',             # checkout existing, no -b
    'gh pr list',
    'gh pr view 12',
    'gh pr checkout 12',
])
def test_non_creation_forms_allowed(cmd, tmp_path):
    rc, _ = _run(_bash(cmd), tmp_path)
    assert rc == 0, f'expected allow for: {cmd}'


def test_quoted_branch_text_not_matched(tmp_path):
    # `git checkout -b foo` inside a quoted echo arg is non-executable -> allowed.
    rc, _ = _run(_bash('echo "to create run: git checkout -b foo"'), tmp_path)
    assert rc == 0


# ── Scope: this hook is Bash-only ────────────────────────────────────────────

def test_enterworktree_tool_ignored_by_this_hook(tmp_path):
    # EnterWorktree is governed by pretool-block-enterworktree.sh, not this hook.
    rc, _ = _run({'tool_name': 'EnterWorktree', 'tool_input': {'name': 'wt'}},
                 tmp_path)
    assert rc == 0


def test_non_bash_tool_ignored(tmp_path):
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


# ── Bypass 1: live /dev-overnight session ────────────────────────────────────

def _write_overnight_state(project_dir, live=True):
    claude = project_dir / '.claude'
    claude.mkdir(parents=True, exist_ok=True)
    end = '2099-01-01T00:00:00Z' if live else '2000-01-01T00:00:00Z'
    state = {
        'current_phase': 'exploring' if live else 'complete',
        'end_time': end,
        'session_id': 'test',
    }
    (claude / 'overnight-state-test.json').write_text(json.dumps(state))


@pytest.mark.parametrize('cmd', [
    'git checkout -b feature/x',
    'git worktree add ../wt feature',
    'gh pr create --fill',
    'git branch new-feature',
])
def test_creation_allowed_during_live_overnight(cmd, tmp_path):
    _write_overnight_state(tmp_path, live=True)
    rc, _ = _run(_bash(cmd), tmp_path)
    assert rc == 0, f'expected allow during live overnight for: {cmd}'


def test_creation_blocked_when_overnight_completed(tmp_path):
    # A completed/expired overnight state is NOT a live session.
    _write_overnight_state(tmp_path, live=False)
    rc, _ = _run(_bash('git checkout -b feature/x'), tmp_path)
    assert rc == 2


# ── Bypass 2: /do consent (main agent only) ──────────────────────────────────

def test_do_consent_allows_main_agent(tmp_path):
    sid = f'test-do-{os.getpid()}'
    flag = f'/tmp/claude-orchestrator-consent-{sid}.flag'
    with open(flag, 'w') as fh:
        fh.write('true')
    try:
        payload = {'tool_name': 'Bash', 'session_id': sid,
                   'tool_input': {'command': 'git checkout -b feature/x'}}
        rc, _ = _run(payload, tmp_path)
        assert rc == 0
    finally:
        os.unlink(flag)


def test_do_consent_does_not_help_subagent(tmp_path):
    # agent_id present => subagent => /do consent must NOT apply => blocked.
    sid = f'test-do-sub-{os.getpid()}'
    flag = f'/tmp/claude-orchestrator-consent-{sid}.flag'
    with open(flag, 'w') as fh:
        fh.write('true')
    try:
        payload = {'tool_name': 'Bash', 'session_id': sid, 'agent_id': 'sub-1',
                   'tool_input': {'command': 'git checkout -b feature/x'}}
        rc, _ = _run(payload, tmp_path)
        assert rc == 2
    finally:
        os.unlink(flag)


def test_subagent_blocked_without_bypass(tmp_path):
    payload = {'tool_name': 'Bash', 'session_id': 'whatever', 'agent_id': 'sub-9',
               'tool_input': {'command': 'git worktree add ../wt'}}
    rc, _ = _run(payload, tmp_path)
    assert rc == 2


# ── Bypass 3: /allow sentinel grant (reaches subagents) ──────────────────────

def test_allow_sentinel_grant_allows(tmp_path):
    grant_dir = '/tmp/claude-grants'
    os.makedirs(grant_dir, exist_ok=True)
    task_id = f'test-grant-{os.getpid()}'
    grant_path = os.path.join(grant_dir, f'{task_id}.json')
    grant = {
        'task_id': task_id,
        'session_id': 'sess-x',
        'allowed_operations': [{'op': 'git', 'target': 'checkout'}],
        'created_at': '2000-01-01T00:00:00Z',
        'expires_at': '2099-01-01T00:00:00Z',
    }
    with open(grant_path, 'w') as fh:
        json.dump(grant, fh)
    try:
        payload = {'tool_name': 'Bash', 'session_id': 'sess-x', 'agent_id': 'sub-2',
                   'tool_input': {'command': 'git checkout -b feature/x'}}
        rc, _ = _run(payload, tmp_path, env_extra={'CLAUDE_TASK_ID': task_id})
        assert rc == 0
    finally:
        if os.path.exists(grant_path):
            os.unlink(grant_path)
