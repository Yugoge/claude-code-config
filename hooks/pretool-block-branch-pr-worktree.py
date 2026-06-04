#!/usr/bin/env python3
"""PreToolUse hook: forbid branch / PR / worktree CREATION outside /dev-overnight.

Policy (user directive 2026-06-04):
  "除了 dev-overnight，永远禁止创建任何分支或 PR 或 worktree"
  Branch creation, pull-request creation, and worktree creation are forbidden by
  default. A live /dev-overnight session is the always-on exception. In addition,
  two human-authorized escape hatches are preserved (the user's explicit choice,
  mirroring pretool-block-enterworktree.sh and pretool-git-privilege-guard.py):
  /do consent and /allow grants.

Scope: the Bash surface only. The EnterWorktree tool is governed by the companion
hook pretool-block-enterworktree.sh (same bypass semantics, including the
overnight exception); keeping the two surfaces in separate hooks avoids
double-blocking EnterWorktree.

Blocked Bash operations (detected on whitespace tokens of the context-stripped
command, so the literal word "git" inside a quoted string is never matched;
path-qualified forms like /usr/bin/git, leading env-var prefixes, and
attached/clustered short options are all caught):
  - git checkout -b/-B/--orphan <name>            (branch creation, incl. -bNAME)
  - git switch  -c/-C/--create/--force-create/--orphan  (branch creation, incl. -cNAME)
  - git branch <name>  /  -c/-C/--copy            (branch creation)
      list / delete / rename / upstream / info forms remain allowed.
  - git worktree add ...                          (worktree creation)
  - gh pr create ...                              (PR creation, flags interspersed)

Bypass order (any one → allow):
  1. live /dev-overnight session   (lib.overnight.is_overnight_active)
  2. /do consent flag              (main agent only — subagents never qualify)
  3. /allow grant                  (sentinel grant: main + subagent;
                                    legacy pattern grant: main agent only)

Coexistence
  Purely additive. PreToolUse blocks if ANY hook exits 2, so this hook only ever
  tightens — it never loosens an existing block.

Exit codes
  0 = allow, 2 = block (stderr shown to the agent). Fails OPEN (exit 0) on any
  unexpected error so a parser bug never bricks a session — same fail-open
  convention as pretool-git-privilege-guard.py.
"""

import json
import os
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
# Sole-exception detection: a live /dev-overnight session owned by this session.
# ---------------------------------------------------------------------------
def _get_session_id(data):
    try:
        return str(data.get('session_id', '') or '')
    except Exception:
        return ''


def _end_time_passed(end_str):
    try:
        end = datetime.fromisoformat(str(end_str).replace('Z', '+00:00'))
    except (ValueError, TypeError, AttributeError):
        return True
    if end.tzinfo is None:
        return datetime.now() > end
    return datetime.now(timezone.utc) > end


def _candidate_project_dirs(data):
    """Dirs whose .claude/ may hold the overnight-state file.

    The state file lives in the MAIN repo's .claude/. The overnight orchestrator
    runs with CLAUDE_PROJECT_DIR pointing at that repo, so it is the primary
    signal; payload cwd, getcwd, and git-toplevel are best-effort fallbacks.
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


def _state_grants_bypass(sf, sid):
    """True iff sf is a live overnight-state file owned by session `sid`.

    Ownership (state['session_id'] == caller sid) is what makes the bypass
    unforgeable in practice: an agent cannot self-grant by planting a state
    file, because writes to .claude/overnight-state-*.json are blocked by
    pretool-overnight-hook-guard.py, and a file owned by a *different* session
    does not match. An empty caller sid never matches.
    """
    if not sid:
        return False
    try:
        if sf.stat().st_size == 0:
            return False
        state = json.loads(sf.read_text())
    except (OSError, ValueError):
        return False
    if not isinstance(state, dict):
        return False
    if str(state.get('session_id', '')) != sid:
        return False
    if state.get('current_phase', '') in ('complete', 'completed'):
        return False
    if _end_time_passed(state.get('end_time', '')):
        return False
    return True


def _is_overnight_active(data):
    sid = _get_session_id(data)
    if not sid:
        return False
    for d in _candidate_project_dirs(data):
        try:
            for sf in Path(d).glob('.claude/overnight-state-*.json'):
                if _state_grants_bypass(sf, sid):
                    return True
        except Exception:
            continue
    return False


# ---------------------------------------------------------------------------
# Command classification. Operates on whitespace tokens of each shell segment
# of the context-stripped command (quotes/comments/heredocs already removed).
# ---------------------------------------------------------------------------
def _norm(command):
    if strip_non_executable_contexts:
        try:
            return strip_non_executable_contexts(command)
        except Exception:
            return command
    return command


def _segments(c):
    out, buf, i, n = [], [], 0, len(c)
    while i < n:
        two = c[i:i + 2]
        if two in ('&&', '||'):
            out.append(''.join(buf)); buf = []; i += 2; continue
        ch = c[i]
        if ch in ';\n|&`()':
            out.append(''.join(buf)); buf = []; i += 1; continue
        buf.append(ch); i += 1
    out.append(''.join(buf))
    return out


def _basename(tok):
    return tok.rsplit('/', 1)[-1]


# git global options that consume a separate following value token.
_GIT_GLOBAL_VALUE = {
    '-C', '-c', '--git-dir', '--work-tree', '--namespace',
    '--exec-path', '--super-prefix', '--config-env',
}


def _git_subcommand(args):
    """Return (subcommand, remaining_args) skipping git global options."""
    i = 0
    while i < len(args):
        a = args[i]
        if a in _GIT_GLOBAL_VALUE:
            i += 2
            continue
        if a.startswith('-'):
            i += 1
            continue
        return a, args[i + 1:]
    return None, []


def _is_co_sw_create(sub, sa):
    """True iff a `git checkout`/`git switch` invocation CREATES a branch."""
    create_letters = set('bB') if sub == 'checkout' else set('cC')
    for x in sa:
        if x == '--':
            break  # pathspec separator — options named like -b after it are files
        if x == '--orphan':
            return True
        if sub == 'switch' and (x == '--create' or x == '--force-create'
                                or x.startswith('--force-create=')):
            return True
        if x.startswith('--'):
            continue
        if x.startswith('-') and len(x) > 1:
            # short-option cluster / attached value: -b, -bNAME, -fb, -cNAME ...
            if any(ch in create_letters for ch in x[1:]):
                return True
    return False


# `git branch` is overloaded. Any of these op flags => NOT a creation.
_BRANCH_NON_CREATE_FLAGS = {
    '-d', '-D', '--delete', '-m', '-M', '--move', '--edit-description',
    '--show-current', '--list', '-l', '-a', '--all', '-r', '--remotes',
    '-v', '--verbose', '--merged', '--no-merged', '--contains',
    '--no-contains', '--points-at', '--unset-upstream', '--set-upstream-to',
    '-u', '--column', '--no-column', '--sort', '--format', '--color',
    '--no-color', '--abbrev', '--no-abbrev', '-h', '--help',
}
_BRANCH_COPY_CREATE_FLAGS = {'-c', '-C', '--copy'}


def _branch_creates(sa):
    flags = set()
    positionals = []
    j = 0
    while j < len(sa):
        x = sa[j]
        if x == '--':
            positionals.extend(t for t in sa[j + 1:] if t)
            break
        if x.startswith('--'):
            flags.add(x.split('=', 1)[0])
        elif x.startswith('-') and len(x) > 1:
            for ch in x[1:]:           # split short-option clusters: -rl -> -r,-l
                flags.add('-' + ch)
        else:
            positionals.append(x)
        j += 1
    if flags & _BRANCH_NON_CREATE_FLAGS:   # list/delete/rename/upstream/info
        return False
    if flags & _BRANCH_COPY_CREATE_FLAGS:  # -c/-C/--copy copies => creation
        return True
    return len(positionals) > 0            # a bare name => creation


# gh global flags that consume a separate following value token.
_GH_GLOBAL_VALUE = {'-R', '--repo'}


def _gh_skip_flags(args, i):
    while i < len(args):
        a = args[i]
        if a in _GH_GLOBAL_VALUE:
            i += 2
            continue
        if a.startswith('-'):
            i += 1
            continue
        break
    return i


def _is_gh_pr_create(args):
    i = _gh_skip_flags(args, 0)
    if i >= len(args) or args[i] != 'pr':
        return False
    i = _gh_skip_flags(args, i + 1)
    return i < len(args) and args[i] == 'create'


def _classify_segment(seg):
    """Return the creation kind ('worktree'|'PR'|'branch') in seg, or None."""
    toks = seg.split()
    for idx, t in enumerate(toks):
        base = _basename(t)
        if base == 'git':
            sub, sa = _git_subcommand(toks[idx + 1:])
            if sub == 'worktree':
                for x in sa:
                    if not x.startswith('-'):
                        return 'worktree' if x == 'add' else None
                return None
            if sub in ('checkout', 'switch'):
                return 'branch' if _is_co_sw_create(sub, sa) else None
            if sub == 'branch':
                return 'branch' if _branch_creates(sa) else None
            return None
        if base == 'gh':
            return 'PR' if _is_gh_pr_create(toks[idx + 1:]) else None
    return None


def _detect(command):
    c = _norm(command)
    for seg in _segments(c):
        kind = _classify_segment(seg)
        if kind:
            return kind
    return None


# ---------------------------------------------------------------------------
# Blocking.
# ---------------------------------------------------------------------------
_POLICY = (
    'Policy (2026-06-04): branch / PR / worktree creation is forbidden in every '
    'context EXCEPT a live /dev-overnight session. dev-overnight is the SOLE '
    'exception — no /do consent and no /allow grant relaxes this rule.\n'
    'To create one of these, run it from within /dev-overnight, or remove this '
    'rule from settings.json (hook: pretool-block-branch-pr-worktree.py).\n'
)


def _block(kind, detail):
    sys.stderr.write(
        '\nBLOCKED: %s creation is forbidden outside /dev-overnight.\n'
        '%s%s'
        % (kind,
           ('Command excerpt: %s\n' % detail[:200]) if detail else '',
           _POLICY)
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
        # The single exception: a live /dev-overnight session owned by this session.
        if _is_overnight_active(data):
            sys.exit(0)
        if tool == 'EnterWorktree':
            _block('worktree (EnterWorktree)', '')
        # tool == 'Bash'
        command = (data.get('tool_input', {}) or {}).get('command', '') or ''
        if not command.strip():
            sys.exit(0)
        kind = _detect(command)
        if kind:
            _block(kind, command)
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
    sys.exit(0)


if __name__ == '__main__':
    main()
