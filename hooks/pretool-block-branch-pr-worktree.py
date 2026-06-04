#!/usr/bin/env python3
"""PreToolUse hook: forbid branch / PR / worktree CREATION outside /dev-overnight.

Policy (user directive 2026-06-04):
  "除了 dev-overnight，永远禁止创建任何分支或 PR 或 worktree"
  Branch creation, pull-request creation, and worktree creation are forbidden in
  EVERY context (interactive, /do, subagent, automation) EXCEPT while a live
  /dev-overnight session is active.

Blocked operations
  Bash tool:
    - git checkout -b / -B / --orphan <name>      (branch creation)
    - git switch  -c / -C / --create / --orphan    (branch creation)
    - git branch <name>                            (branch creation; copy -c/-C too)
        list / delete / rename / upstream / info forms remain allowed.
    - git worktree add ...                         (worktree creation)
    - gh pr create ...                             (PR creation)
  EnterWorktree tool:
    - always treated as worktree creation.

Sole exception
  A live overnight-state-*.json under <project>/.claude/ — the marker that
  /dev-overnight writes (current_phase != complete and end_time not yet passed).
  This is the ONLY bypass: /do consent and /allow grants do NOT relax this rule,
  per the literal "永远禁止 … 除了 dev-overnight".

Coexistence
  Purely additive. Runs alongside pretool-block-enterworktree.sh and
  pretool-git-privilege-guard.py. PreToolUse blocks if ANY hook exits 2, so this
  hook only ever tightens — it never loosens an existing block.

Exit codes
  0 = allow, 2 = block (stderr shown to the agent).
  Fails OPEN (exit 0) on any unexpected error so a parser bug never bricks a
  session — the same fail-open convention as pretool-git-privilege-guard.py.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    from lib.bash_context_strip import strip_non_executable_contexts
except Exception:  # pragma: no cover - lib always present in repo
    strip_non_executable_contexts = None


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
# Overnight-active detection (the sole exception).
# ---------------------------------------------------------------------------
def _end_time_passed(end_str):
    try:
        end = datetime.fromisoformat(str(end_str).replace('Z', '+00:00'))
    except (ValueError, TypeError, AttributeError):
        return True
    if end.tzinfo is None:
        return datetime.now() > end
    return datetime.now(timezone.utc) > end


def _state_file_is_live(sf):
    try:
        if sf.stat().st_size == 0:
            return False
        state = json.loads(sf.read_text())
    except (OSError, ValueError):
        return False
    if not isinstance(state, dict):
        return False
    if state.get('current_phase', '') in ('complete', 'completed'):
        return False
    if _end_time_passed(state.get('end_time', '')):
        return False
    return True


def _candidate_project_dirs(data):
    """Directories whose .claude/ may hold the overnight-state file.

    The state file lives in the MAIN repo's .claude/. A subagent inside a
    worktree has CLAUDE_PROJECT_DIR still pointing at the main repo (harness
    env), so that env var is the reliable signal; cwd and git-toplevel are
    added as best-effort fallbacks.
    """
    dirs = []
    candidates = [
        os.environ.get('CLAUDE_PROJECT_DIR'),
        data.get('cwd') if isinstance(data, dict) else None,
        os.getcwd(),
    ]
    for d in candidates:
        if d and d not in dirs:
            dirs.append(d)
    try:
        top = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True, text=True, timeout=3,
        )
        if top.returncode == 0:
            t = (top.stdout or '').strip()
            if t and t not in dirs:
                dirs.append(t)
    except Exception:
        pass
    return dirs


def _is_overnight_active(data):
    for d in _candidate_project_dirs(data):
        try:
            for sf in Path(d).glob('.claude/overnight-state-*.json'):
                if _state_file_is_live(sf):
                    return True
        except Exception:
            continue
    return False


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


# ---------------------------------------------------------------------------
# Blocking.
# ---------------------------------------------------------------------------
_POLICY = (
    'Policy (2026-06-04): branch / PR / worktree creation is forbidden in every '
    'context EXCEPT a live /dev-overnight session.\n'
    'No /do consent and no /allow grant relaxes this rule.\n'
    'To create one of these, run it from within /dev-overnight, or remove this '
    'rule from settings.json (hook: pretool-block-branch-pr-worktree.py).\n'
)


def _block(kind, what, detail):
    sys.stderr.write(
        '\nBLOCKED: %s creation is forbidden outside /dev-overnight.\n'
        'Matched: %s\n'
        '%s\n'
        '%s'
        % (kind, what, ('Command excerpt: %s' % detail[:200]) if detail else '',
           _POLICY)
    )
    sys.exit(2)


def _block_enterworktree():
    sys.stderr.write(
        '\nBLOCKED: worktree creation (EnterWorktree) is forbidden outside '
        '/dev-overnight.\n'
        + _POLICY
    )
    sys.exit(2)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    try:
        tool = data.get('tool_name', '')
        if tool not in ('Bash', 'EnterWorktree'):
            sys.exit(0)
        # The single exception: an active /dev-overnight session.
        if _is_overnight_active(data):
            sys.exit(0)
        if tool == 'EnterWorktree':
            _block_enterworktree()
        # tool == 'Bash'
        command = (data.get('tool_input', {}) or {}).get('command', '') or ''
        if not command.strip():
            sys.exit(0)
        c = _norm(command)
        if _is_worktree_add(c):
            _block('worktree', 'git worktree add', command)
        if _is_gh_pr_create(c):
            _block('PR', 'gh pr create', command)
        if _is_checkout_create(c) or _is_switch_create(c) or _is_branch_create(c):
            _block('branch',
                   'branch creation (git branch <name> / checkout -b / switch -c)',
                   command)
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
    sys.exit(0)


if __name__ == '__main__':
    main()
