#!/usr/bin/env python3
"""
PreToolUse Hook: Block modifications to hooks AND overnight state files during overnight.

Activation: Only when any .claude/overnight-state-*.json exists.
Purpose: Prevent agent from modifying hooks or deleting state files (timelock bypass).

Exit codes:
  0: Allow tool use
  2: Block tool use (overnight hook protection active)
"""

import json
import os
import re
import sys
from pathlib import Path


def is_overnight_active() -> bool:
    """Check if any overnight session is active (any state file exists)."""
    project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
    return any((project_dir / '.claude').glob('overnight-state-*.json'))


def get_overnight_state_for_session(project_dir: Path, session_id: str) -> dict | None:
    """Load overnight state file for the specific session."""
    state_path = project_dir / '.claude' / f'overnight-state-{session_id}.json'
    if state_path.exists():
        try:
            return json.loads(state_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
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
    abs_worktree = os.path.realpath(os.path.abspath(worktree_path))
    return not abs_file.startswith(abs_worktree + os.sep) and abs_file != abs_worktree


def check_bash_targets_state(command: str) -> bool:
    """Check if bash command modifies/deletes overnight state files."""
    patterns = [
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
    ]
    for pattern in patterns:
        if re.search(pattern, command):
            return True
    return False


def check_bash_targets_hooks(command: str) -> bool:
    """Check if a bash command writes to .claude/hooks/ directory."""
    patterns = [
        r'(?:echo|printf)\s+.*>\s*.*\.claude/hooks/',
        r'cat\s+.*>\s*.*\.claude/hooks/',
        r'cp\s+.*\.claude/hooks/',
        r'mv\s+.*\.claude/hooks/',
        r'tee\s+.*\.claude/hooks/',
        r'>\s*.*\.claude/hooks/',
        r'>>\s*.*\.claude/hooks/',
    ]
    for pattern in patterns:
        if re.search(pattern, command):
            return True
    return False


def apply_global_security_checks(tool_name: str, tool_input: dict) -> None:
    """Block hooks/state modifications for ALL sessions during any overnight run."""
    if tool_name in ('Write', 'Edit'):
        file_path = tool_input.get('file_path', '')
        if is_hooks_path(file_path):
            sys.stderr.write(
                '\nOVERNIGHT HOOK PROTECTION: Modifying .claude/hooks/ '
                'is blocked during overnight sessions.\n'
                f'Blocked: {tool_name} to {file_path}\n'
            )
            sys.exit(2)
        if is_state_file_path(file_path):
            sys.stderr.write(
                '\nOVERNIGHT STATE PROTECTION: Direct modification of '
                'overnight-state files is blocked.\n'
                f'Blocked: {tool_name} to {file_path}\n'
            )
            sys.exit(2)

    if tool_name == 'Bash':
        command = tool_input.get('command', '')
        if check_bash_targets_hooks(command):
            sys.stderr.write(
                '\nOVERNIGHT HOOK PROTECTION: Writing to .claude/hooks/ '
                'via Bash is blocked during overnight sessions.\n'
            )
            sys.exit(2)
        if check_bash_targets_state(command):
            sys.stderr.write(
                '\nOVERNIGHT STATE PROTECTION: Modifying or deleting '
                'overnight-state-*.json via Bash is blocked.\n'
                'The state file can only be removed after end-time expires.\n'
            )
            sys.exit(2)


def apply_worktree_enforcement(tool_name: str, tool_input: dict, worktree_path: str) -> None:
    """Warn when overnight session writes outside its worktree."""
    if tool_name not in ('Write', 'Edit'):
        return
    file_path = tool_input.get('file_path', '')
    if not file_path:
        return
    if is_outside_worktree(file_path, worktree_path):
        sys.stderr.write(
            f'\n⚠️  WORKTREE WARNING: File is outside the overnight worktree.\n'
            f'Overnight changes should stay inside: {worktree_path}\n'
            f'Attempted path: {file_path}\n'
            f'Use absolute paths inside the worktree to maintain branch isolation.\n'
        )
        # Advisory only — exit 0 to allow the operation but inform the agent


def main():
    """Entry point for the overnight hook guard."""
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    # Global security: only activates when any overnight session is running.
    if not is_overnight_active():
        sys.exit(0)

    tool_name = data.get('tool_name', '')
    tool_input = data.get('tool_input', {})

    # Block hooks/state modifications for all sessions (security invariant).
    apply_global_security_checks(tool_name, tool_input)

    # Worktree enforcement: only for the specific overnight session.
    current_session_id = os.environ.get('CLAUDE_SESSION_ID', '')
    if current_session_id:
        project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
        state = get_overnight_state_for_session(project_dir, current_session_id)
        if state:
            worktree_path = state.get('worktree_path', '')
            if worktree_path:
                apply_worktree_enforcement(tool_name, tool_input, worktree_path)

    sys.exit(0)


if __name__ == '__main__':
    main()
