"""Shared /dev-overnight session detection for PreToolUse hooks.

Single source of truth for the question "is a /dev-overnight session currently
live?". A session is live iff a `<project>/.claude/overnight-state-*.json` file
exists with a non-empty body, `current_phase` not in {complete, completed}, and
an `end_time` that has not yet passed.

Mirrors the canonical probe previously inlined in pretool-git-privilege-guard.py
(`_is_overnight_active` / `_state_file_is_live`), extracted here so new hooks
(pretool-block-branch-pr-worktree.py and the EnterWorktree guard) share one
implementation instead of copying it. The privilege-guard keeps its own inlined
copy to avoid disturbing tested behavior; this module governs new callers only.

Stdlib-only; never raises (every probe fails closed → "not active").
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _end_time_passed(end_str):
    """True iff end_str (ISO-8601) is in the past, or is missing/unparseable.

    A missing or malformed end_time is treated as "passed" so a half-written
    state file never counts as a live session (fail closed).
    """
    try:
        end = datetime.fromisoformat(str(end_str).replace('Z', '+00:00'))
    except (ValueError, TypeError, AttributeError):
        return True
    if end.tzinfo is None:
        return datetime.now() > end
    return datetime.now(timezone.utc) > end


def _state_file_is_live(sf):
    """True iff state file `sf` describes an in-progress overnight session."""
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


def _candidate_project_dirs(project_dir=None):
    """Ordered, de-duplicated list of directories that may hold .claude/state.

    Precedence: explicit project_dir arg → $CLAUDE_PROJECT_DIR → cwd. The
    overnight-state file lives in the MAIN repo's .claude/, so a subagent
    running inside a worktree still resolves it via $CLAUDE_PROJECT_DIR.
    """
    dirs = []
    if project_dir:
        dirs.append(Path(project_dir))
    env = os.environ.get('CLAUDE_PROJECT_DIR')
    if env:
        dirs.append(Path(env))
    try:
        dirs.append(Path(os.getcwd()))
    except Exception:
        pass
    seen, out = set(), []
    for d in dirs:
        s = str(d)
        if s not in seen:
            seen.add(s)
            out.append(d)
    return out


def is_overnight_active(project_dir=None):
    """True iff a live overnight-state-*.json exists under any candidate
    project dir's .claude/. Fails closed (returns False) on any error."""
    try:
        for d in _candidate_project_dirs(project_dir):
            try:
                state_files = list((d / '.claude').glob('overnight-state-*.json'))
            except Exception:
                continue
            if any(_state_file_is_live(sf) for sf in state_files):
                return True
        return False
    except Exception:
        return False
