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


def is_hooks_path(file_path: str) -> bool:
    """Check if a file path targets the .claude/hooks/ directory."""
    normalized = file_path.replace('\\', '/')
    return '.claude/hooks/' in normalized or '.claude/hooks\\' in normalized


def is_state_file_path(file_path: str) -> bool:
    """Check if a file path targets an overnight state file."""
    normalized = file_path.replace('\\', '/')
    return 'overnight-state-' in normalized and normalized.endswith('.json')


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


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    # Only activate if any overnight session is active
    if not is_overnight_active():
        sys.exit(0)

    tool_name = data.get('tool_name', '')
    tool_input = data.get('tool_input', {})

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

    sys.exit(0)


if __name__ == '__main__':
    main()
