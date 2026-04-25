#!/usr/bin/env python3
"""
PreToolUse Hook: Agent git-privilege guard.

Scope: Runs on EVERY Bash tool call in agent (subagent + main-agent
orchestrator) contexts, regardless of whether the session is overnight
or interactive. The b5d447e regression (2026-04-21 17:45 UTC) which
this guard exists to prevent - a 93-file `git commit` + `git push`
sweep authored by the orchestrator with no human signoff - happened in
an INTERACTIVE session (JSONL message 293 of session
962de59f-fe0b-416e-b88b-7345fdf569e2, prompt `全部commit push`,
no overnight-state-*.json present). Gating this hook on overnight-
context only would let that exact regression class pass through; the
guard must be always-on per spec 5.2.4 line 240-241.

The whitelists below preserve the legitimate paths:
  - `^auto-bulk: end-of-cycle commit for ` blessed bridge from /merge
  - CLAUDE_MERGE_COMMAND_ACTIVE=1 env exemption for git merge
  - reset to HEAD (non-destructive)
  - human-driven commits: the human exits the agent context and runs
    git commit at their own shell; this hook does not see those calls.

Forbidden agent operations:
  - git commit -m '<msg>' whose message does NOT match
    `^auto-bulk: end-of-cycle commit for ` (the blessed bridge from
    /merge per spec section 5.2.1.2 R2). Stderr literal:
    `BLOCKED: agent git commit`.
  - git merge unless the env var `CLAUDE_MERGE_COMMAND_ACTIVE=1` is
    set by /merge at start. Stderr literal: `BLOCKED: agent git merge`.
  - git push (any form). Stderr literal:
    `BLOCKED: agent git push`.
  - destructive history-rewriting reset to a non-HEAD ref. Stderr
    literal: `BLOCKED: agent git reset to non-HEAD`.

Allowed: git add, git status, git log, git diff, git show, git blame,
git ls-files, git ls-tree, git restore (working-tree only), git branch
(list), git rev-list, git rev-parse, git symbolic-ref, git for-each-ref,
git stash list/show/pop (non-destructive forms), and reset to HEAD only.

Spec: spec-20260424-233926 section 5.2.4 (R4.3) line 233-249.

Revision history:
  2026-04-25 (Option alpha): made always-on. Removed the overnight-
  context gate after confirming b5d447e occurred in an interactive
  session - the gate would have let the regression through. The
  `_is_overnight_active()` helper is retained as dead code for
  reference but is no longer consulted by main().
  2026-04-25 (earlier): replaced the dead-code `CLAUDE_OVERNIGHT_ACTIVE`
  env-var path with the canonical state-file probe.

Exit codes:
  0: Allow tool use
  2: Block tool use
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


BLESSED_BRIDGE_RE = re.compile(r'auto-bulk:\s*end-of-cycle commit for\b')


def _block(message):
    sys.stderr.write(message)
    sys.exit(2)


def _looks_like_git_commit(command):
    return bool(re.search(r'(?:^|[\s;&|()`])git\s+commit\b', command))


def _looks_like_git_merge(command):
    return bool(re.search(r'(?:^|[\s;&|()`])git\s+merge(?!-base|tool)\b', command))


def _looks_like_git_push(command):
    return bool(re.search(r'(?:^|[\s;&|()`])git\s+push\b', command))


def _looks_like_git_reset_hard(command):
    return bool(re.search(
        r"(?:^|[\s;&|()`])git\s+reset\s+(?:[^;|&]*\s+)?--hard\b",
        command,
    ))


def _extract_commit_message(command):
    patterns = [
        r"-m\s*=?\s*'([^']*)'",
        r'-m\s*=?\s*"([^"]*)"',
        r'--message\s*=?\s*"([^"]*)"',
        r"--message\s*=?\s*'([^']*)'",
    ]
    for p in patterns:
        m = re.search(p, command)
        if m:
            return m.group(1)
    m = re.search(r'-m\s+(\S+)', command)
    if m:
        return m.group(1)
    return ''


def _extract_reset_target(command):
    m = re.search(
        r"git\s+reset\s+(?:[^;|&]*?\s+)?--hard\s+([^\s;|&]+)",
        command,
    )
    return m.group(1) if m else ''


def _is_head_ref(ref):
    if not ref:
        return True
    return ref == 'HEAD'


def _end_time_passed(end_str):
    try:
        end = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
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
    if state.get('current_phase', '') in ('complete', 'completed'):
        return False
    if _end_time_passed(state.get('end_time', '')):
        return False
    return True


def _is_overnight_active():
    """True iff a live overnight-state-*.json exists in <project>/.claude/."""
    try:
        project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR') or os.getcwd())
        state_files = list((project_dir / '.claude').glob('overnight-state-*.json'))
        return any(_state_file_is_live(sf) for sf in state_files)
    except Exception:
        return False


def _evaluate_commit(command):
    msg = _extract_commit_message(command)
    if msg and BLESSED_BRIDGE_RE.search(msg):
        return
    _block(
        '\nBLOCKED: agent git commit - only the blessed /merge '
        'auto-bulk bridge may commit from an overnight context.\n'
        'Commit message excerpt: %r\n' % msg[:200]
        + 'Allowed pattern: ^auto-bulk: end-of-cycle commit for <branch>\n'
        'If the human user wants to commit, exit the agent context '
        'and run git commit directly.\n'
        'Spec: spec-20260424-233926 section 5.2.4 (R4.3).\n'
    )


def _evaluate_merge(command):
    if os.environ.get('CLAUDE_MERGE_COMMAND_ACTIVE') == '1':
        return
    _block(
        '\nBLOCKED: agent git merge - only the /merge slash command '
        'may run git merge from an overnight context.\n'
        'Command excerpt: %s\n' % command[:200]
        + 'To bypass: set env var CLAUDE_MERGE_COMMAND_ACTIVE=1.\n'
        'Spec: spec-20260424-233926 section 5.2.4 (R4.3).\n'
    )


def _evaluate_push(command):
    _block(
        '\nBLOCKED: agent git push - agents are not authorized to push '
        'to remote from an overnight context.\n'
        'Command excerpt: %s\n' % command[:200]
        + 'If the human user wants to push, exit the agent context and '
        'run git push directly.\n'
        'Spec: spec-20260424-233926 section 5.2.4 (R4.3).\n'
    )


def _evaluate_reset_hard(command):
    target = _extract_reset_target(command)
    if _is_head_ref(target):
        return
    _block(
        '\nBLOCKED: agent git reset to non-HEAD - destructive '
        'history-mutating reset to %r is forbidden from an overnight '
        'context.\n' % target
        + 'Command excerpt: %s\n' % command[:200]
        + 'Spec: spec-20260424-233926 section 5.2.4 (R4.3).\n'
    )


def _evaluate_command(command):
    if _looks_like_git_reset_hard(command):
        _evaluate_reset_hard(command)
    if _looks_like_git_push(command):
        _evaluate_push(command)
    if _looks_like_git_merge(command):
        _evaluate_merge(command)
    if _looks_like_git_commit(command):
        _evaluate_commit(command)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    try:
        if data.get('tool_name', '') != 'Bash':
            sys.exit(0)
        # Always-on per spec 5.2.4 line 240-241; overnight gate removed
        # 2026-04-25 (Option alpha) after b5d447e proved interactive
        # sessions need this guard too.
        command = (data.get('tool_input', {}) or {}).get('command', '') or ''
        if not command:
            sys.exit(0)
        _evaluate_command(command)
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
    sys.exit(0)


if __name__ == '__main__':
    main()
