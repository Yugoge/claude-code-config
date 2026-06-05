#!/usr/bin/env python3
"""PreToolUse hook: forbid branch / PR / worktree CREATION outside /dev-overnight.

Policy (user directive 2026-06-04; the verbatim user directive is preserved in
docs/dev/do-report-44e208af-b8b8-4266-a2ba-fcfc77f92d24.json, the sanctioned
artifact location for non-English user-binding quotes):
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
# Command classification. Operates on whitespace tokens of each shell segment of
# the context-stripped command.
# ---------------------------------------------------------------------------
def _norm(command):
    if strip_non_executable_contexts:
        try:
            return strip_non_executable_contexts(command)
        except Exception:
            return command
    return command


def _segments(c):
    """Split on shell separators ; \n | & && || ` ( ) into command segments."""
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
    """True iff a `git checkout`/`git switch` invocation CREATES a branch.

    Creation triggers, for BOTH checkout and switch:
      --orphan                              (orphan branch)
      -t / --track                          (local tracking branch; creates one)
    Checkout-only short letters: -b / -B    (create / create-or-reset)
    Switch-only long opts: --create / --force-create / --orphan and --guess
      (--guess is switch's explicit "create from a remote-tracking name" flag).

    Handles bare and attached short options (-b, -bNAME, -fb, -tb), long options
    with or without an attached =value (base = token.split('=')[0], tolerant of a
    nonexistent --track=value form), short-option clusters containing a create
    letter or `t`, and stops at the `--` pathspec separator.

    KNOWN LIMITATION (intentionally NOT fixed — fixing would over-block): a BARE
    `git switch <name>` / `git checkout <name>` with no create flag uses git's
    default --guess, which CAN create a local branch when <name> matches exactly
    one remote-tracking branch. That is indistinguishable, without repo state,
    from switching to an existing local branch, and blocking it would break the
    legitimate `git switch master` / `git checkout master`. So a bare
    switch/checkout to a name stays ALLOWED.
    """
    create_letters = set('bB') if sub == 'checkout' else set('cC')
    create_letters.add('t')  # -t == --track creates a local tracking branch
    for x in sa:
        if x == '--':
            break  # pathspec separator — options named like -b after it are files
        base = x.split('=', 1)[0]  # strip attached =value for long options
        if base in ('--orphan', '--track'):
            return True
        if sub == 'switch' and base in ('--create', '--force-create', '--guess'):
            return True
        if x.startswith('--'):
            continue
        if x.startswith('-') and len(x) > 1:
            # short-option cluster / attached value: -b, -bNAME, -fb, -tNAME ...
            if any(ch in create_letters for ch in x[1:]):
                return True
    return False


# `git branch` is overloaded — display/formatting flags are ORTHOGONAL to
# creation (they can accompany either a list OR a create), so they MUST NOT veto
# creation. The classifier below is a left-to-right token parser, not a set
# membership test, because value-consuming flags (--sort X, --format X,
# --points-at X, -u X, ...) take a separate following token that must NOT be
# mistaken for a positional branch name.

# Long-opt VETO flags → exclusive op or list/query mode → NOT creation.
_BRANCH_VETO_LONG = {
    '--delete', '--move', '--edit-description', '--list', '--all', '--remotes',
    '--show-current', '--merged', '--no-merged', '--contains', '--no-contains',
    '--points-at', '--set-upstream-to', '--unset-upstream', '--help',
}
# Short VETO letters (in a cluster, any of these → veto).
_BRANCH_VETO_SHORT = set('dDmMlaruh')
# Long-opt COPY flags → creation.
_BRANCH_COPY_LONG = {'--copy'}
# Short COPY letters → creation.
_BRANCH_COPY_SHORT = set('cC')
# Long flags that consume the NEXT token as their value (when not attached '=').
_BRANCH_VALUE_LONG = {
    '--contains', '--no-contains', '--merged', '--no-merged', '--points-at',
    '--sort', '--format', '--color', '--column', '--abbrev', '--set-upstream-to',
}


def _branch_creates(sa):
    """Left-to-right parse of `git branch` args. Returns True iff it creates.

    VETO flag seen      -> False (exclusive op / list / query mode).
    else COPY flag seen -> True  (-c/-C/--copy copies => creation).
    else >=1 positional -> True  (a bare branch name => creation).
    else                -> False (list / display-only, no name).

    Value-consuming flags swallow their following token so a space-separated
    value (e.g. `--sort refname`, `--format %(refname)`) is never read as a
    positional branch name. Display/boolean flags (-v, --verbose, -q, --quiet,
    --no-color, --no-column, --no-abbrev, and any unrecognized -x) are ignored —
    they neither veto nor positional. Veto short-circuits immediately, so a veto
    flag's space-separated value is never mis-read as a positional.
    """
    saw_copy = False
    positionals = 0
    j = 0
    n = len(sa)
    while j < n:
        x = sa[j]
        if x == '--':
            # everything after is positional
            for t in sa[j + 1:]:
                if t:
                    positionals += 1
            break
        if x.startswith('--'):
            base = x.split('=', 1)[0]
            attached = '=' in x
            if base in _BRANCH_VETO_LONG:
                return False  # short-circuit; do not consume a value as positional
            if base in _BRANCH_COPY_LONG:
                saw_copy = True
            elif base in _BRANCH_VALUE_LONG and not attached:
                j += 1  # swallow the separate value token
            # else: display/boolean long flag (--verbose, --no-color, ...) ignored
        elif x.startswith('-') and len(x) > 1:
            cluster = set(x[1:])
            # -u (==--set-upstream-to) carries 'u' in the veto set, so it (and
            # any other veto cluster) short-circuits here; its space-separated
            # value is never reached/mis-read as a positional. Good.
            if cluster & _BRANCH_VETO_SHORT:
                return False
            if cluster & _BRANCH_COPY_SHORT:
                saw_copy = True
            # else: display/boolean short cluster (-v, -q, -vv, ...) ignored
        else:
            positionals += 1
        j += 1
    if saw_copy:
        return True
    return positionals > 0


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
# Bypass checks (overnight handled inline in main; these are the two
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
    main-agent-only.
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
    'Policy (2026-06-04): branch / PR / worktree creation is forbidden outside a '
    'live /dev-overnight session.\n'
    'Escape hatches: run it inside /dev-overnight, or (main agent) use /do, or '
    '/allow the specific command first.\n'
)


def _block(kind, command, data):
    lines = [
        '',
        f'BLOCKED: {kind} creation is forbidden outside /dev-overnight.',
    ]
    if command:
        lines.append(f'Command excerpt: {command[:200]}')
    lines.append('')
    lines.append(_POLICY.rstrip('\n'))
    if data.get('agent_id'):
        lines.append(
            'You are a subagent: PAUSE and report this block to the user per '
            'Subagent Hook Discipline — do NOT attempt to work around it.')
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
        kind = _detect(command)
        if not kind:
            sys.exit(0)
        # Bypasses — any one allows the operation.
        if is_overnight_active(data.get('cwd')):
            sys.exit(0)
        if _has_do_consent(data):
            sys.exit(0)
        if _allow_grant_matches(command, data):
            sys.exit(0)
        _block(kind, command, data)
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
    sys.exit(0)


if __name__ == '__main__':
    main()
