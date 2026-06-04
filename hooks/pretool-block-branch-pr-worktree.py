#!/usr/bin/env python3
"""PreToolUse hook: forbid branch / PR / worktree CREATION outside /dev-overnight.

Policy (user directive 2026-06-04):
  "除了 dev-overnight，永远禁止创建任何分支或 PR 或 worktree"
  Branch creation, pull-request creation, and worktree creation are forbidden by
  default. A live /dev-overnight session is the always-on exception; in addition
  two human-authorized escape hatches are preserved (mirrors
  pretool-block-enterworktree.sh and pretool-git-privilege-guard.py): /do consent
  and /allow grants.

Scope: the Bash surface only. The EnterWorktree tool is governed by the
companion hook pretool-block-enterworktree.sh (same bypass semantics, including
the overnight exception); keeping the two surfaces in separate hooks avoids
double-blocking EnterWorktree.

Blocked Bash operations (detected on the context-stripped command so the literal
word "git" inside a quoted python -c string is never matched):
  - git checkout -b / -B / --orphan <name>       (branch creation)
  - git switch  -c / -C / --create / --orphan     (branch creation)
  - git branch <name>                             (branch creation; copy -c/-C too)
      list / delete / rename / upstream / info forms remain allowed.
  - git worktree add ...                          (worktree creation)
  - gh pr create ...                              (PR creation)

Bypass order (any one → allow):
  1. live /dev-overnight session   (lib.overnight.is_overnight_active)
  2. /do consent flag              (main agent only — subagents never qualify)
  3. /allow grant                  (sentinel grant: main + subagent;
                                    legacy pattern grant: main agent only)

Coexistence: purely additive. PreToolUse blocks if ANY hook exits 2, so this
hook only ever tightens — it never loosens an existing block.

Exit codes: 0 = allow, 2 = block (stderr shown to the agent). Fails OPEN (exit 0)
on any unexpected error so a parser bug never bricks a session — the same
fail-open convention as pretool-git-privilege-guard.py.
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    from lib.bash_context_strip import strip_non_executable_contexts
except Exception:  # pragma: no cover - lib always present in repo
    strip_non_executable_contexts = None
from lib.allowlist import (  # noqa: E402
    match_grant_for_bash_command,
    match_sentinel_grant_for_bash_command,
)
from lib.overnight import is_overnight_active  # noqa: E402


# ---------------------------------------------------------------------------
# Command anchors (replicated from pretool-git-privilege-guard.py for parity so
# that `git -C <dir> branch foo` and other global-option prefixes are matched,
# while the literal word "git" inside a quoted python -c string is not — the
# context strip removes quoted regions before these run).
# ---------------------------------------------------------------------------
GIT_GLOBAL_OPTION_RE = (
    r'(?:\s+(?:-[Cc]\s+\S+|-[Cc]\S+|'
    r'--(?:git-dir|work-tree|namespace|exec-path|super-prefix|config-env)'
    r'(?:=\S+|\s+\S+)|'
    r'--(?:bare|no-pager|paginate|no-replace-objects|literal-pathspecs|'
    r'glob-pathspecs|noglob-pathspecs|icase-pathspecs|no-optional-locks)|'
    r'-[pP]))*'
)
GIT_COMMAND_RE = r'(?:^|[\s;&|()`])git' + GIT_GLOBAL_OPTION_RE + r'\s+'
GH_COMMAND_RE = r'(?:^|[\s;&|()`])gh\s+'


# ---------------------------------------------------------------------------
# Command detectors. Each consumes the context-stripped command string.
# ---------------------------------------------------------------------------
def _norm(command):
    if strip_non_executable_contexts:
        try:
            return strip_non_executable_contexts(command)
        except Exception:
            return command
    return command


def _is_worktree_add(c):
    return bool(re.search(GIT_COMMAND_RE + r'worktree\s+add\b', c))


def _is_gh_pr_create(c):
    return bool(re.search(GH_COMMAND_RE + r'pr\s+create\b', c))


def _is_checkout_create(c):
    # `git checkout -b/-B <name>` or `git checkout --orphan <name>`.
    return bool(re.search(
        GIT_COMMAND_RE + r'checkout\b[^;&|`\n]*\s(?:-b|-B|--orphan)\b', c))


def _is_switch_create(c):
    # `git switch -c/-C/--create/--orphan <name>`.
    return bool(re.search(
        GIT_COMMAND_RE + r'switch\b[^;&|`\n]*\s(?:-c|-C|--create|--orphan)\b', c))


# `git branch` is overloaded: list / delete / rename / upstream / info forms
# must stay allowed; only the create forms are blocked.
_BRANCH_NON_CREATE_FLAGS = {
    '-d', '-D', '--delete', '-m', '-M', '--move', '--edit-description',
    '--show-current', '--list', '-l', '-a', '--all', '-r', '--remotes',
    '-v', '-vv', '--verbose', '--merged', '--no-merged', '--contains',
    '--no-contains', '--points-at', '--unset-upstream', '--set-upstream-to',
    '-u', '--column', '--no-column', '--sort', '--format', '--color',
    '--no-color', '--abbrev', '--no-abbrev',
}
_BRANCH_COPY_CREATE_FLAGS = {'-c', '-C', '--copy'}


def _is_branch_create(c):
    m = re.search(GIT_COMMAND_RE + r'branch\b(.*)', c)
    if not m:
        return False
    # Only the first shell segment after `branch`.
    tail = re.split(r'[;&|`\n]', m.group(1), maxsplit=1)[0]
    tokens = tail.strip().split()
    bases = [t.split('=', 1)[0] for t in tokens]
    # Any list/delete/rename/upstream/info flag => not a creation.
    if any(b in _BRANCH_NON_CREATE_FLAGS for b in bases):
        return False
    # `git branch -c/-C/--copy <new>` copies an existing branch => creation.
    if any(b in _BRANCH_COPY_CREATE_FLAGS for b in bases):
        return True
    # A bare positional token is the new branch name => creation.
    return any(not t.startswith('-') for t in tokens)


def _detect(c):
    """Ordered list of creation kinds present in the context-stripped command."""
    kinds = []
    if _is_worktree_add(c):
        kinds.append('worktree')
    if _is_gh_pr_create(c):
        kinds.append('PR')
    if _is_checkout_create(c) or _is_switch_create(c) or _is_branch_create(c):
        kinds.append('branch')
    return kinds


# ---------------------------------------------------------------------------
# Bypass checks (overnight is handled inline in main; these are the two
# human-authorized escape hatches the user chose to preserve).
# ---------------------------------------------------------------------------
def _get_session_id(data):
    try:
        return str(data.get('session_id', '') or '')
    except Exception:
        return ''


def _has_do_consent(data):
    """True iff the main agent holds /do consent for this session."""
    if data.get('agent_id'):  # subagents never qualify for /do
        return False
    sid = _get_session_id(data)
    if not sid:
        return False
    try:
        flag = Path(f'/tmp/claude-orchestrator-consent-{sid}.flag')
        return flag.exists() and flag.read_text().strip() == 'true'
    except Exception:
        return False


def _allow_grant_matches(command, data):
    """True iff a /allow grant authorizes this command.

    Sentinel grants reach subagents and the main agent (mirrors the M2 decision
    in pretool-git-privilege-guard.py); the legacy pattern grant is
    main-agent-only. The sentinel matcher is fed the RAW command (not the
    context-stripped form) so its structural head-token match sees real tokens.
    """
    sid = _get_session_id(data)
    task_id = os.environ.get('CLAUDE_TASK_ID') or sid
    try:
        if task_id and match_sentinel_grant_for_bash_command(task_id, command) is not None:
            return True
    except Exception:
        pass
    if data.get('agent_id'):
        return False
    if not sid:
        return False
    try:
        return match_grant_for_bash_command(command, sid) is not None
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Blocking.
# ---------------------------------------------------------------------------
_POLICY = (
    'Policy (2026-06-04): branch / PR / worktree creation is forbidden outside '
    'a live /dev-overnight session.\n'
    'Escape hatches: run it inside /dev-overnight, or (main agent) use /do, or '
    '/allow the specific command first.\n'
)


def _block(kinds, command, data):
    ops = ' + '.join(kinds)
    lines = [
        '',
        f'BLOCKED: {ops} creation is forbidden outside /dev-overnight.',
        f'Command excerpt: {command[:200]}',
        '',
        _POLICY.rstrip('\n'),
    ]
    if data.get('agent_id'):
        lines += [
            'You are a subagent: PAUSE and report this block to the user per '
            'Subagent Hook Discipline — do NOT attempt to work around it.',
        ]
    sys.stderr.write('\n'.join(lines) + '\n')
    sys.exit(2)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    try:
        if data.get('tool_name', '') != 'Bash':
            sys.exit(0)
        command = (data.get('tool_input', {}) or {}).get('command', '') or ''
        if not command.strip():
            sys.exit(0)
        kinds = _detect(_norm(command))
        if not kinds:
            sys.exit(0)
        # Bypasses — any one allows the operation.
        if is_overnight_active(data.get('cwd')):
            sys.exit(0)
        if _has_do_consent(data):
            sys.exit(0)
        if _allow_grant_matches(command, data):
            sys.exit(0)
        _block(kinds, command, data)
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
    sys.exit(0)


if __name__ == '__main__':
    main()
