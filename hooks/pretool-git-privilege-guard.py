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
  2026-04-25 (Scheme 6 manifest-validation): added two narrow
  authorized-exemption paths for `git push` and `git commit` driven by
  the new `/push` and `/commit` slash-command wrappers. Each path
  requires BOTH:
    1. an OS-level env var (`CLAUDE_PUSH_COMMAND_ACTIVE=1` for push,
       `CLAUDE_COMMIT_COMMAND_ACTIVE=1` for commit) set by the wrapper
       in the child's environment (NOT inline-prepended on the agent
       command line), AND
    2. a single-use grant manifest at
       `/tmp/claude-{push|commit}-grant-<sid>.json` whose contents
       bind the operation to a specific branch + expected_head + remote
       (push) or task_id + allowed_files + expected_message_sha256
       (commit).
  Inline-env injection (e.g. `CLAUDE_PUSH_COMMAND_ACTIVE=1 git push ...`
  on a single Bash call) is rejected by literal-substring scan of the
  raw command text BEFORE the env-var check, defeating the b5d447e
  attack class even if the agent learns the env name. The grant file
  is unlinked on first valid consumption (single-use); validation
  failures DO NOT consume the grant (forensics + brute-force
  resistance).  /do-consent is intentionally NOT honored — the git
  guard never consults `/tmp/claude-orchestrator-consent-<sid>.flag`.
  Cross-bypass is blocked: the push env name does NOT bypass commit,
  and vice versa.  Authority: spec ba-spec-20260425-redev2.md §4.1
  (AC-A1..AC-A17), close-report-20260425-push-commit-debate.md
  (Scheme 6 verdict CLOSE: YES).
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

import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


BLESSED_BRIDGE_RE = re.compile(r'auto-bulk:\s*end-of-cycle commit for\b')


def _block(message):
    sys.stderr.write(message)
    sys.exit(2)


# ---------------------------------------------------------------------------
# Scheme 6 manifest-validation helpers (added 2026-04-25)
# ---------------------------------------------------------------------------

def _get_session_id(data):
    """Extract session_id from the parsed PreToolUse stdin payload.

    Returns empty string when missing.  Used to compute the per-session
    grant-file path /tmp/claude-{kind}-grant-<sid>.json.
    """
    try:
        sid = data.get('session_id', '') or ''
        return str(sid)
    except Exception:
        return ''


def _inline_env_present(command, var_name):
    """True iff the raw command string contains literal `<var_name>=`.

    This is the literal-substring defense against the inline-env
    injection attack (e.g. `CLAUDE_PUSH_COMMAND_ACTIVE=1 git push ...`
    on a single Bash call).  We deliberately use plain substring
    matching on the raw command text - not a regex, not a normalized
    form - so that any encoding of the literal `VAR=` token in the
    command is caught.
    """
    if not command or not var_name:
        return False
    needle = var_name + '='
    return needle in command


def _grant_path_for(kind, sid):
    """Return /tmp/claude-{kind}-grant-<sid>.json for kind in {push, commit}.

    Retained for backward compat / readability; the live consumers use
    `_find_grant` so they discover per-nonce filenames written by the
    wrappers (close-report-20260425-push-commit-debate.md ratified the
    `<sid>-<nonce>.json` pattern in §1-2).
    """
    return '/tmp/claude-%s-grant-%s.json' % (kind, sid)


def _find_grant(kind, sid):
    """Return (resolved_path, grant_dict) or (None, None) on miss/invalid.

    Per close-report-20260425-push-commit-debate.md §1-2, wrappers write
    per-nonce filenames `/tmp/claude-{kind}-grant-<sid>-<nonce>.json` so
    that two concurrent wrapper invocations under the same SID cannot
    collide on a single shared file.  The guard discovers the grant by
    glob, sorts by mtime descending, and returns the most recent
    JSON-parseable candidate.  The caller is responsible for unlinking
    the resolved path (single-use) on validation success.
    """
    pattern = '/tmp/claude-%s-grant-%s-*.json' % (kind, sid)
    try:
        candidates = glob.glob(pattern)
    except Exception:
        return (None, None)
    try:
        candidates.sort(key=lambda p: os.stat(p).st_mtime, reverse=True)
    except Exception:
        # If stat() races a concurrent unlink, fall back to lexical order.
        candidates.sort(reverse=True)
    for path in candidates:
        grant = _load_grant(path)
        if grant is not None:
            return (path, grant)
    return (None, None)


def _load_grant(grant_path):
    """Read and JSON-parse a grant file.

    Returns the parsed dict on success, or None on missing / empty /
    malformed / unreadable.  Catches all exceptions and fails closed
    (caller treats None as "no valid grant -> block").
    """
    try:
        with open(grant_path, 'r') as fp:
            text = fp.read()
        if not text.strip():
            return None
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            return None
        return parsed
    except Exception:
        return None


def _unlink_grant(grant_path):
    """Remove the grant file, swallowing all errors.

    Single-use grant unlink: called ONLY on successful validation paths,
    NEVER on validation-failure paths (so failure does not consume the
    grant - this preserves forensic visibility and resists brute-force
    confirm/deny probing).
    """
    try:
        os.unlink(grant_path)
    except Exception:
        pass


def _git_output(args):
    """Run `git <args...>` and return stripped stdout, or '' on any error.

    Used to read the current branch / HEAD / staged-set inside the
    guard.  Always runs in the agent's CWD (no `-C` override) so that
    the resolved values match what the agent's `git push|commit` call
    would see.
    """
    try:
        result = subprocess.run(
            ['git'] + list(args),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return ''
        return (result.stdout or '').strip()
    except Exception:
        return ''


def _sha256_text(text):
    """Return lowercase hex sha256 of the UTF-8 bytes of `text`."""
    try:
        return hashlib.sha256((text or '').encode('utf-8')).hexdigest()
    except Exception:
        return ''


def _extract_push_remote(command):
    """Best-effort extraction of the explicit remote argument from a
    `git push` invocation.  Returns the first positional token after
    `push` that is not a flag (does not start with `-`), or '' when
    not found (typical for plain `git push` with upstream tracking).
    """
    m = re.search(r'(?:^|[\s;&|()`])git\s+push\b(.*)', command)
    if not m:
        return ''
    tail = m.group(1)
    # Stop at shell separators so trailing pipelines do not pollute.
    tail = re.split(r'[;&|`]', tail, maxsplit=1)[0]
    for tok in tail.strip().split():
        if tok.startswith('-'):
            continue
        return tok
    return ''


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


def _block_inline_env_commit(command):
    """AC-A2: literal-substring inline-env injection block for commit."""
    _block(
        '\nBLOCKED: agent git commit - inline-env injection blocked.\n'
        'Detected literal substring `CLAUDE_COMMIT_COMMAND_ACTIVE=` in '
        'the raw command text; agents are not permitted to set this '
        'env var inline.  Only the /commit wrapper may set it via '
        'subprocess + os.environ.\n'
        'Command excerpt: %s\n' % command[:200]
        + 'Spec: ba-spec-20260425-redev2.md AC-A2.\n'
    )


def _block_default_deny_commit(msg):
    """AC-A13: default-deny block when commit env is unset."""
    _block(
        '\nBLOCKED: agent git commit - only the blessed /merge '
        'auto-bulk bridge or the /commit wrapper may commit from an '
        'agent context.\n'
        'Commit message excerpt: %r\n' % msg[:200]
        + 'Allowed pattern: ^auto-bulk: end-of-cycle commit for <branch>\n'
        'For closed dev tasks, use /commit <task-id>.\n'
        'For human-driven commits, exit the agent context and run '
        'git commit directly.\n'
        'Spec: spec-20260424-233926 section 5.2.4 (R4.3); '
        'ba-spec-20260425-redev2.md AC-A13.\n'
    )


def _validate_commit_grant_message(grant, msg):
    """AC-A11: message sha256 must match grant.expected_message_sha256."""
    expected_hash = (grant.get('expected_message_sha256') or '').lower()
    actual_hash = _sha256_text(msg)
    if not expected_hash or expected_hash != actual_hash:
        _block(
            '\nBLOCKED: agent git commit - message hash mismatch.\n'
            'Expected sha256: %s\n' % (expected_hash or '<missing>')
            + 'Actual   sha256: %s\n' % actual_hash
            + 'Commit message excerpt: %r\n' % msg[:200]
            + 'Grant did NOT authorize this exact commit message.\n'
            'Spec: ba-spec-20260425-redev2.md AC-A11.\n'
        )


def _block_staged_superset(allowed_set, staged_set):
    """AC-A9: staged set has files outside the grant's allowed_files."""
    _block(
        '\nBLOCKED: agent git commit - staged-set superset of '
        'allowed_files.\n'
        'Allowed: %s\n' % sorted(allowed_set)
        + 'Staged : %s\n' % sorted(staged_set)
        + 'Extras : %s\n' % sorted(staged_set - allowed_set)
        + 'Spec: ba-spec-20260425-redev2.md AC-A9.\n'
    )


def _block_staged_subset(allowed_set, staged_set):
    """AC-A10: staged set is missing files declared in allowed_files."""
    _block(
        '\nBLOCKED: agent git commit - staged-set subset of '
        'allowed_files.\n'
        'Allowed: %s\n' % sorted(allowed_set)
        + 'Staged : %s\n' % sorted(staged_set)
        + 'Missing: %s\n' % sorted(allowed_set - staged_set)
        + 'Spec: ba-spec-20260425-redev2.md AC-A10.\n'
    )


def _validate_commit_grant_files(grant):
    """AC-A9 / AC-A10: staged set must equal grant.allowed_files exactly."""
    allowed_raw = grant.get('allowed_files') or []
    if not isinstance(allowed_raw, list):
        _block(
            '\nBLOCKED: agent git commit - grant.allowed_files is not a list.\n'
            'Spec: ba-spec-20260425-redev2.md AC-A9/A10.\n'
        )
    allowed_set = set(str(p) for p in allowed_raw if p)
    staged_raw = _git_output(['diff', '--cached', '--name-only'])
    staged_set = set(p for p in staged_raw.splitlines() if p)
    if staged_set - allowed_set:
        _block_staged_superset(allowed_set, staged_set)
    if allowed_set - staged_set:
        _block_staged_subset(allowed_set, staged_set)


def _block_missing_commit_grant(sid):
    """AC-A4 / AC-A16: env present but no on-disk grant for this SID."""
    pattern = '/tmp/claude-commit-grant-%s-*.json' % sid
    _block(
        '\nBLOCKED: agent git commit - CLAUDE_COMMIT_COMMAND_ACTIVE=1 '
        'is set but no valid grant manifest matching %s.\n' % pattern
        + 'Single-use grants are unlinked on first valid consumption; '
        'a missing grant means it was already used or never written.\n'
        'Spec: ba-spec-20260425-redev2.md AC-A16; '
        'close-report-20260425-push-commit-debate.md §1-2.\n'
    )


def _warn_bridge_message_drift(grant, msg):
    """Emit warning if bridge-mode message hash differs from grant.expected."""
    expected_hash = (grant.get('expected_message_sha256') or '').lower()
    actual_hash = _sha256_text(msg)
    if expected_hash and expected_hash != actual_hash:
        sys.stderr.write(
            'WARN: bridge-mode commit message hash mismatch '
            '(expected=%s actual=%s); allowed under AC-P3-4 transition.\n'
            % (expected_hash[:12], actual_hash[:12])
        )


def _warn_bridge_staged_drift(grant):
    """Emit warning if bridge-mode staged-set differs from grant.allowed_files."""
    allowed_raw = grant.get('allowed_files') or []
    if not isinstance(allowed_raw, list):
        return
    allowed_set = set(str(p) for p in allowed_raw if p)
    staged_raw = _git_output(['diff', '--cached', '--name-only'])
    staged_set = set(p for p in staged_raw.splitlines() if p)
    if staged_set != allowed_set:
        sys.stderr.write(
            'WARN: bridge-mode commit staged-set drift '
            '(extras=%s missing=%s); allowed under AC-P3-4 transition.\n'
            % (sorted(staged_set - allowed_set),
               sorted(allowed_set - staged_set))
        )


def _observe_bridge_commit(sid, msg):
    """AC-P3-2 defense-in-depth (added 2026-04-26 in dev-redev3-p3).

    When the blessed-bridge regex matches AND the wrapper has set
    CLAUDE_COMMIT_COMMAND_ACTIVE=1 AND a per-nonce grant manifest is
    on disk, validate message hash + staged set against the grant.
    Drift is logged (warning) but does NOT block — promotion to
    hard-block is deferred to a future cycle (AC-P3-5).  Manifest
    absence is allowed, preserving AC-P3-4 in-flight compatibility.
    """
    if os.environ.get('CLAUDE_COMMIT_COMMAND_ACTIVE') != '1':
        return
    grant_path, grant = _find_grant('commit', sid)
    if grant is None:
        return
    _warn_bridge_message_drift(grant, msg)
    _warn_bridge_staged_drift(grant)
    _unlink_grant(grant_path)


def _evaluate_commit(command, sid):
    # AC-A12: blessed-bridge regex commit STILL ALLOWED (regression).
    msg = _extract_commit_message(command)
    if msg and BLESSED_BRIDGE_RE.search(msg):
        # AC-P3-2 defense-in-depth: observe-only validation when a
        # bridge-mode grant accompanies the commit.  Plain blessed-bridge
        # commits with no env/grant continue to be allowed (AC-P3-4).
        _observe_bridge_commit(sid, msg)
        return
    # AC-A2: literal-substring inline-env injection (precedes env check).
    if _inline_env_present(command, 'CLAUDE_COMMIT_COMMAND_ACTIVE'):
        _block_inline_env_commit(command)
    # AC-A13: only the matching env name carries (cross-bypass blocked).
    if os.environ.get('CLAUDE_COMMIT_COMMAND_ACTIVE') != '1':
        _block_default_deny_commit(msg)
    # AC-A4 / AC-A16: env present -> require single-use grant manifest.
    # Per close-report §1-2, on-disk file is `<sid>-<nonce>.json`; glob+match.
    grant_path, grant = _find_grant('commit', sid)
    if grant is None:
        _block_missing_commit_grant(sid)
    # AC-A11 + AC-A9/A10: validate message hash and staged-set equality.
    _validate_commit_grant_message(grant, msg)
    _validate_commit_grant_files(grant)
    # All validations passed.  Consume grant (single-use), then allow.
    _unlink_grant(grant_path)


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


def _block_inline_env_push(command):
    """AC-A1: literal-substring inline-env injection block for push."""
    _block(
        '\nBLOCKED: agent git push - inline-env injection blocked.\n'
        'Detected literal substring `CLAUDE_PUSH_COMMAND_ACTIVE=` in '
        'the raw command text; agents are not permitted to set this '
        'env var inline.  Only the /push wrapper may set it via '
        'subprocess + os.environ.\n'
        'Command excerpt: %s\n' % command[:200]
        + 'Spec: ba-spec-20260425-redev2.md AC-A1.\n'
    )


def _block_default_deny_push(command):
    """AC-A5: default-deny block when push env is unset."""
    _block(
        '\nBLOCKED: agent git push - agents are not authorized to push '
        'to remote from an agent context.\n'
        'Command excerpt: %s\n' % command[:200]
        + 'For automated push, use the /push slash command (which sets '
        'CLAUDE_PUSH_COMMAND_ACTIVE=1 and writes a single-use grant).\n'
        'For human-driven push, exit the agent context and run '
        'git push directly.\n'
        'Spec: spec-20260424-233926 section 5.2.4 (R4.3); '
        'ba-spec-20260425-redev2.md AC-A5.\n'
    )


def _validate_push_grant_branch(grant):
    """AC-A7: grant.branch must match current branch."""
    grant_branch = grant.get('branch') or ''
    current_branch = _git_output(['branch', '--show-current'])
    if not grant_branch or grant_branch != current_branch:
        _block(
            '\nBLOCKED: agent git push - branch mismatch.\n'
            'Grant branch  : %r\n' % grant_branch
            + 'Current branch: %r\n' % current_branch
            + 'Spec: ba-spec-20260425-redev2.md AC-A7.\n'
        )


def _validate_push_grant_head(grant):
    """AC-A6: grant.expected_head must match current HEAD sha."""
    grant_head = grant.get('expected_head') or ''
    current_head = _git_output(['rev-parse', 'HEAD'])
    if not grant_head or grant_head != current_head:
        _block(
            '\nBLOCKED: agent git push - expected_head mismatch.\n'
            'Grant expected_head: %r\n' % grant_head
            + 'Current HEAD       : %r\n' % current_head
            + 'Spec: ba-spec-20260425-redev2.md AC-A6.\n'
        )


def _validate_push_grant_remote(grant, command):
    """AC-A6 (remote binding): explicit cmd remote must match grant.remote."""
    grant_remote = grant.get('remote') or ''
    cmd_remote = _extract_push_remote(command)
    if cmd_remote and grant_remote and cmd_remote != grant_remote:
        _block(
            '\nBLOCKED: agent git push - remote mismatch.\n'
            'Grant remote  : %r\n' % grant_remote
            + 'Command remote: %r\n' % cmd_remote
            + 'Spec: ba-spec-20260425-redev2.md AC-A6.\n'
        )


def _block_missing_push_grant(sid):
    """AC-A4: env present but no on-disk grant for this SID."""
    pattern = '/tmp/claude-push-grant-%s-*.json' % sid
    _block(
        '\nBLOCKED: agent git push - CLAUDE_PUSH_COMMAND_ACTIVE=1 '
        'is set but no valid grant manifest matching %s.\n' % pattern
        + 'Single-use grants are unlinked on first valid consumption; '
        'a missing grant means it was already used or never written.\n'
        'Spec: ba-spec-20260425-redev2.md AC-A4; '
        'close-report-20260425-push-commit-debate.md §1-2.\n'
    )


def _evaluate_push(command, sid):
    # AC-A1: literal-substring inline-env injection (precedes env check).
    if _inline_env_present(command, 'CLAUDE_PUSH_COMMAND_ACTIVE'):
        _block_inline_env_push(command)
    # AC-A5: default-deny when env unset.
    if os.environ.get('CLAUDE_PUSH_COMMAND_ACTIVE') != '1':
        _block_default_deny_push(command)
    # AC-A4: env present but no grant -> block.  Per close-report §1-2,
    # filename is `<sid>-<nonce>.json` (per-nonce); glob+match.
    grant_path, grant = _find_grant('push', sid)
    if grant is None:
        _block_missing_push_grant(sid)
    # AC-A7 + AC-A6: branch / head / remote binding.
    _validate_push_grant_branch(grant)
    _validate_push_grant_head(grant)
    _validate_push_grant_remote(grant, command)
    # All validations passed.  Consume grant (single-use), then allow.
    _unlink_grant(grant_path)


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


def _evaluate_command(command, sid):
    if _looks_like_git_reset_hard(command):
        _evaluate_reset_hard(command)
    if _looks_like_git_push(command):
        _evaluate_push(command, sid)
    if _looks_like_git_merge(command):
        _evaluate_merge(command)
    if _looks_like_git_commit(command):
        _evaluate_commit(command, sid)


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
        #
        # AC-A17: /do consent is intentionally NOT honored here.  This
        # guard MUST NOT consult /tmp/claude-orchestrator-consent-<sid>.flag
        # under any circumstances; the boundary is frozen by design.
        # Any future maintainer reading this: do not add a has_consent
        # check.  See ba-spec-20260425-redev2.md R-4 for the rationale.
        command = (data.get('tool_input', {}) or {}).get('command', '') or ''
        if not command:
            sys.exit(0)
        sid = _get_session_id(data)
        _evaluate_command(command, sid)
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
    sys.exit(0)


if __name__ == '__main__':
    main()
