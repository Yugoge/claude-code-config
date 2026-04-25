#!/usr/bin/env python3
"""
PreToolUse Hook: Agent git-privilege guard.

Scope: Runs on every Bash tool call in every session. Refuses dangerous
git verbs unless explicitly blessed by the orchestrator. Closes the
gap that allowed b5d447e (2026-04-21 17:45 UTC) to commit a 93-file
sweep WITHOUT human authorship — the orchestrator-gate fired (rate-based
4/3 streak) but the agent reset the streak with a Grep call and the
SAME git commit succeeded 9 seconds later.

Forbidden agent operations:
  - `git commit -m '<msg>'` whose message does NOT match
    `^auto-bulk: end-of-cycle commit for ` (the blessed bridge from
    /merge per spec §5.2.1.2 R2). Stderr literal:
    `BLOCKED: agent git commit`.
  - `git merge` unless the env var `CLAUDE_MERGE_COMMAND_ACTIVE=1` is
    set by /merge at start. Stderr literal: `BLOCKED: agent git merge`.
  - `git push` (any form). Stderr literal:
    `BLOCKED: agent git push`.
  - `git reset --hard <ref>` where `<ref>` is non-HEAD. Stderr literal:
    `BLOCKED: agent git reset --hard <non-HEAD>`.

Allowed: `git add`, `git status`, `git log`, `git diff`, `git show`,
`git blame`, `git ls-files`, `git ls-tree`, `git restore` (working-tree
only), `git branch` (list), `git rev-list`, `git rev-parse`,
`git symbolic-ref`, `git for-each-ref`, `git stash list/show/pop`
(non-destructive forms), and reset to HEAD itself.

Spec: spec-20260424-233926 §5.2.4 (R4.3) line 233.

Exit codes:
  0: Allow tool use
  2: Block tool use

Fail-open: Any uncaught exception during hook evaluation results in
exit 0.
"""

import json
import os
import re
import sys


BLESSED_BRIDGE_RE = re.compile(r'auto-bulk:\s*end-of-cycle commit for\b')


def _block(message: str) -> None:
    """Write to stderr and exit 2."""
    sys.stderr.write(message)
    sys.exit(2)


def _looks_like_git_commit(command: str) -> bool:
    """True iff the command starts a `git commit` invocation."""
    return bool(re.search(r'(?:^|[\s;&|()`])git\s+commit\b', command))


def _looks_like_git_merge(command: str) -> bool:
    """True iff the command starts a `git merge` invocation (exclude `merge-base`/`mergetool`)."""
    return bool(re.search(r'(?:^|[\s;&|()`])git\s+merge(?!-base|tool)\b', command))


def _looks_like_git_push(command: str) -> bool:
    """True iff the command starts a `git push` invocation."""
    return bool(re.search(r'(?:^|[\s;&|()`])git\s+push\b', command))


def _looks_like_git_reset_hard(command: str) -> bool:
    """True iff command is a `git reset --hard <ref>` form."""
    return bool(re.search(
        r"(?:^|[\s;&|()`])git\s+reset\s+(?:[^;|&]*\s+)?--hard\b",
        command,
    ))


def _extract_commit_message(command: str) -> str:
    """Best-effort extraction of `-m <msg>` content from a `git commit`."""
    # -m 'msg' or -m "msg" or -m=msg
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
    # Bare token after -m (no quotes)
    m = re.search(r'-m\s+(\S+)', command)
    if m:
        return m.group(1)
    return ''


def _extract_reset_target(command: str) -> str:
    """Extract the ref token after `--hard` (best effort)."""
    m = re.search(
        r"git\s+reset\s+(?:[^;|&]*?\s+)?--hard\s+([^\s;|&]+)",
        command,
    )
    return m.group(1) if m else ''


def _is_head_ref(ref: str) -> bool:
    """True iff ref is exactly HEAD (or HEAD trivially equivalent)."""
    if not ref:
        # `git reset --hard` with no ref defaults to HEAD; allow it.
        return True
    return ref == 'HEAD'


def _is_agent_context(data: dict) -> bool:
    """True iff this PreToolUse fired from an agent (sub or main).

    Heuristic per BA spec: presence of `agent_id` in stdin data signals
    a subagent. Main-agent invocations do NOT have `agent_id` but are
    ALSO subject to the rule. Therefore: this hook applies regardless of
    `agent_id` — the field is informational only. The user's bypass is
    NOT to remove `agent_id`; it is the blessed-bridge / env-var /
    HEAD-only allowances built into each rule.
    """
    return True  # Apply to all PreToolUse(Bash) calls; gates are semantic.


def _evaluate_commit(command: str) -> None:
    """Block agent git commit unless blessed-bridge."""
    msg = _extract_commit_message(command)
    if msg and BLESSED_BRIDGE_RE.search(msg):
        return  # blessed bridge from /merge per R2
    _block(
        '\nBLOCKED: agent git commit — only the blessed `/merge` '
        'auto-bulk bridge may commit from an agent context.\n'
        f'Commit message excerpt: {msg[:200]!r}\n'
        'Allowed pattern: ^auto-bulk: end-of-cycle commit for <branch>\n'
        'If the human user wants to commit, exit the agent context '
        'and run `git commit` directly.\n'
        'Spec: spec-20260424-233926 §5.2.4 (R4.3).\n'
    )


def _evaluate_merge(command: str) -> None:
    """Block agent git merge unless CLAUDE_MERGE_COMMAND_ACTIVE=1."""
    if os.environ.get('CLAUDE_MERGE_COMMAND_ACTIVE') == '1':
        return
    _block(
        '\nBLOCKED: agent git merge — only the `/merge` slash command '
        'may run `git merge` from an agent context.\n'
        f'Command excerpt: {command[:200]}\n'
        'To bypass: set env var CLAUDE_MERGE_COMMAND_ACTIVE=1 (the '
        '/merge command does this automatically).\n'
        'Spec: spec-20260424-233926 §5.2.4 (R4.3).\n'
    )


def _evaluate_push(command: str) -> None:
    """Block agent git push (any form)."""
    _block(
        '\nBLOCKED: agent git push — agents are not authorized to push '
        'to remote.\n'
        f'Command excerpt: {command[:200]}\n'
        'If the human user wants to push, exit the agent context and '
        'run `git push` directly.\n'
        'Spec: spec-20260424-233926 §5.2.4 (R4.3).\n'
    )


def _evaluate_reset_hard(command: str) -> None:
    """Block agent git reset --hard for non-HEAD refs."""
    target = _extract_reset_target(command)
    if _is_head_ref(target):
        return
    _block(
        f'\nBLOCKED: agent git reset --hard <non-HEAD> — destructive '
        f'history-mutating reset to {target!r} is forbidden from an '
        f'agent context.\n'
        f'Command excerpt: {command[:200]}\n'
        f'Allowed: `git reset --hard HEAD` (or `--hard` with no ref). '
        f'For other targets, the human user must run the command '
        f'directly.\n'
        f'Spec: spec-20260424-233926 §5.2.4 (R4.3).\n'
    )


def _evaluate_command(command: str) -> None:
    """Dispatch by detected git verb."""
    if _looks_like_git_reset_hard(command):
        _evaluate_reset_hard(command)
    if _looks_like_git_push(command):
        _evaluate_push(command)
    if _looks_like_git_merge(command):
        _evaluate_merge(command)
    if _looks_like_git_commit(command):
        _evaluate_commit(command)


def main() -> None:
    """Entry point: read JSON-from-stdin, evaluate, exit 0/2."""
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    try:
        if data.get('tool_name', '') != 'Bash':
            sys.exit(0)
        if not _is_agent_context(data):
            sys.exit(0)
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
