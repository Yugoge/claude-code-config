#!/usr/bin/env python3
"""
PreToolUse Hook: Overnight session file modification guard.

Activation: Session-specific — only the session owning an overnight state file
is subject to worktree enforcement. Global security checks (hooks/state
protection) apply when any overnight session is active.

Enforcement layers:
  1. Global: Block modifications to .claude/hooks/ and overnight-state files.
  2. Session: Block file writes where path lacks "worktree" string.
  3. Session: Block file writes outside the worktree realpath boundary.

Exit codes:
  0: Allow tool use
  2: Block tool use
"""

import json
import os
import re
import sys
from pathlib import Path


def _is_session_live(state: dict) -> bool:
    """Check if session is still live (not complete and end_time passed)."""
    from datetime import datetime, timezone
    phase = state.get("current_phase", "")
    if phase in ("complete", "completed"):
        return False
    end_time_str = state.get("end_time", "")
    if end_time_str:
        try:
            end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > end_time:
                return False
        except (ValueError, OSError):
            pass
    return True


def is_overnight_active() -> bool:
    """Check if any overnight session is still live."""
    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    state_files = list((project_dir / ".claude").glob("overnight-state-*.json"))
    if not state_files:
        return False
    return any(
        _is_session_live(json.loads(sf.read_text()))
        for sf in state_files
        if sf.stat().st_size > 0
    )

def get_overnight_state_for_session(project_dir: Path, session_id: str) -> dict | None:
    """Load overnight state file for the specific session."""
    if not session_id:
        return None
    state_path = project_dir / '.claude' / f'overnight-state-{session_id}.json'
    if not state_path.exists():
        return None
    try:
        return json.loads(state_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def is_hooks_path(file_path: str) -> bool:
    """Check if a file path targets the .claude/hooks/ directory."""
    normalized = file_path.replace('\\', '/')
    return '.claude/hooks/' in normalized or '.claude/hooks\\' in normalized


def is_state_file_path(file_path: str) -> bool:
    """Check if a file path targets an overnight state file."""
    normalized = file_path.replace('\\', '/')
    return 'overnight-state-' in normalized and normalized.endswith('.json')


def is_outside_worktree(file_path: str, worktree_path: str) -> bool:
    """Check if a file path is outside the worktree directory."""
    abs_file = os.path.realpath(os.path.abspath(file_path))
    abs_wt = os.path.realpath(os.path.abspath(worktree_path))
    return not abs_file.startswith(abs_wt + os.sep) and abs_file != abs_wt


def path_lacks_worktree_string(file_path: str) -> bool:
    """Check if 'worktree' is absent from the file path (case-insensitive).

    Used to block overnight sessions from modifying files outside worktree
    directories. Any path containing 'worktree' is considered safe.
    """
    return 'worktree' not in file_path.lower()


def _matches_any(command: str, patterns: list[str]) -> bool:
    """Return True if command matches any regex pattern."""
    return any(re.search(p, command) for p in patterns)


def check_bash_targets_state(command: str) -> bool:
    """Check if bash command modifies/deletes overnight state files."""
    return _matches_any(command, [
        r'rm\s+.*overnight-state-',
        r'rm\s+-f\s+.*overnight-state-',
        r'rm\s+-rf\s+.*overnight-state-',
        r'>\s*.*overnight-state-',
        r'>>\s*.*overnight-state-',
        r'mv\s+.*overnight-state-',
        r'cp\s+.*overnight-state-.*\.json\s',
        r'echo\s+.*>\s*.*overnight-state-',
        r'cat\s+.*>\s*.*overnight-state-',
        r'tee\s+.*overnight-state-',
    ])


def check_bash_targets_hooks(command: str) -> bool:
    """Check if a bash command writes to .claude/hooks/ directory."""
    return _matches_any(command, [
        r'(?:echo|printf)\s+.*>\s*.*\.claude/hooks/',
        r'cat\s+.*>\s*.*\.claude/hooks/',
        r'cp\s+.*\.claude/hooks/',
        r'mv\s+.*\.claude/hooks/',
        r'tee\s+.*\.claude/hooks/',
        r'>\s*.*\.claude/hooks/',
        r'>>\s*.*\.claude/hooks/',
    ])


def _block(message: str) -> None:
    """Write message to stderr and exit 2."""
    sys.stderr.write(message)
    sys.exit(2)


def _check_write_edit_security(tool_name: str, file_path: str) -> None:
    """Block Write/Edit to hooks or state files during overnight."""
    if is_hooks_path(file_path):
        _block(
            '\nOVERNIGHT HOOK PROTECTION: Modifying .claude/hooks/ '
            'is blocked during overnight sessions.\n'
            f'Blocked: {tool_name} to {file_path}\n'
        )
    if is_state_file_path(file_path):
        _block(
            '\nOVERNIGHT STATE PROTECTION: Direct modification of '
            'overnight-state files is blocked.\n'
            f'Blocked: {tool_name} to {file_path}\n'
        )


def _check_bash_security(command: str) -> None:
    """Block Bash commands targeting hooks or state files."""
    if check_bash_targets_hooks(command):
        _block(
            '\nOVERNIGHT HOOK PROTECTION: Writing to .claude/hooks/ '
            'via Bash is blocked during overnight sessions.\n'
        )
    if check_bash_targets_state(command):
        _block(
            '\nOVERNIGHT STATE PROTECTION: Modifying or deleting '
            'overnight-state-*.json via Bash is blocked.\n'
            'The state file can only be removed after end-time expires.\n'
        )


def apply_global_security_checks(tool_name: str, tool_input: dict) -> None:
    """Block hooks/state modifications for ALL sessions during any overnight."""
    if tool_name in ('Write', 'Edit'):
        _check_write_edit_security(tool_name, tool_input.get('file_path', ''))
    if tool_name == 'Bash':
        _check_bash_security(tool_input.get('command', ''))


def _extract_bash_write_paths(command: str) -> list[str]:
    """Extract file paths from common Bash write patterns."""
    paths = []
    # Redirect: > /path, >> /path
    for m in re.finditer(r'>{1,2}\s*(/[^\s;|&]+)', command):
        paths.append(m.group(1))
    # tee /path
    for m in re.finditer(r'tee\s+(?:-a\s+)?(/[^\s;|&]+)', command):
        paths.append(m.group(1))
    # cp source /dest, mv source /dest
    for m in re.finditer(r'(?:cp|mv)\s+\S+\s+(/[^\s;|&]+)', command):
        paths.append(m.group(1))
    # sed -i ... /path
    for m in re.finditer(r'sed\s+-i[^\s]*\s+\S+\s+(/[^\s;|&]+)', command):
        paths.append(m.group(1))
    return paths


def _block_worktree_string_violation(tool_name: str, path: str) -> None:
    """Block operation on path lacking 'worktree' string."""
    _block(
        f'\nWORKTREE STRING ENFORCEMENT: Path does not contain "worktree".\n'
        f'Overnight sessions can only modify files in worktree directories.\n'
        f'Attempted: {tool_name} to {path}\n'
    )


def _block_worktree_violation(tool_name: str, path: str, wt: str) -> None:
    """Block operation outside worktree with exit 2."""
    _block(
        f'\nWORKTREE ENFORCEMENT: File is outside the overnight worktree.\n'
        f'Overnight changes MUST stay inside: {wt}\n'
        f'Attempted: {tool_name} to {path}\n'
        f'Use absolute paths inside the worktree.\n'
    )


def _enforce_write_edit_worktree(tool_name: str, tool_input: dict, wt: str) -> None:
    """Check Write/Edit file_path against worktree boundary."""
    file_path = tool_input.get('file_path', '')
    if file_path and is_outside_worktree(file_path, wt):
        _block_worktree_violation(tool_name, file_path, wt)


def _enforce_bash_worktree(command: str, wt: str) -> None:
    """Check Bash write targets against worktree boundary."""
    for path in _extract_bash_write_paths(command):
        if is_outside_worktree(path, wt):
            _block_worktree_violation('Bash', path, wt)


def apply_worktree_string_check(tool_name: str, tool_input: dict) -> None:
    """Block when overnight session writes to path without 'worktree' in it."""
    if tool_name in ('Write', 'Edit'):
        file_path = tool_input.get('file_path', '')
        if file_path and path_lacks_worktree_string(file_path):
            _block_worktree_string_violation(tool_name, file_path)
    if tool_name == 'Bash':
        command = tool_input.get('command', '')
        for path in _extract_bash_write_paths(command):
            if path_lacks_worktree_string(path):
                _block_worktree_string_violation('Bash', path)


def apply_worktree_enforcement(tool_name: str, tool_input: dict, wt: str) -> None:
    """Hard-block when overnight session writes outside its worktree."""
    if tool_name in ('Write', 'Edit'):
        _enforce_write_edit_worktree(tool_name, tool_input, wt)
    if tool_name == 'Bash':
        _enforce_bash_worktree(tool_input.get('command', ''), wt)


def main():
    """Entry point for the overnight hook guard.

    Session isolation: only the session that owns an overnight state file
    is subject to worktree enforcement. Other sessions are unaffected.
    Global security checks (hooks/state protection) still apply when any
    overnight session is active.
    """
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = data.get('tool_name', '')
    tool_input = data.get('tool_input', {})
    session_id = data.get('session_id', '')

    # Global security: block hooks/state modifications when ANY overnight
    # session is active (security invariant, applies to all sessions).
    if is_overnight_active():
        apply_global_security_checks(tool_name, tool_input)

    # Session-specific enforcement: only apply to the session that owns
    # an overnight state file. Other sessions are free to operate.
    if not session_id:
        sys.exit(0)

    project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
    state = get_overnight_state_for_session(project_dir, session_id)
    if not state or not _is_session_live(state):
        sys.exit(0)

    # This session has an active overnight state. Enforce restrictions.
    # 1. Block any file modification where path lacks "worktree" string.
    apply_worktree_string_check(tool_name, tool_input)

    # 2. If worktree_path is set, enforce realpath boundary too.
    wt = state.get('worktree_path', '')
    if wt:
        apply_worktree_enforcement(tool_name, tool_input, wt)

    sys.exit(0)


if __name__ == '__main__':
    main()
