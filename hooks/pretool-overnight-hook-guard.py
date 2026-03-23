#!/usr/bin/env python3
"""
PreToolUse Hook: Block Write/Edit/Bash targeting .claude/hooks/ during overnight sessions.

Activation: Only when .claude/overnight-state.json exists (overnight session active).
Purpose: Prevent the agent from modifying hook infrastructure during unattended operation.

Exit codes:
  0: Allow tool use
  2: Block tool use (overnight hook protection active)
"""

import json
import os
import re
import sys
from pathlib import Path


def get_state_path() -> Path:
    """Path to overnight state file, derived from project dir."""
    project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
    return project_dir / '.claude' / 'overnight-state.json'


def is_hooks_path(file_path: str) -> bool:
    """Check if a file path targets the .claude/hooks/ directory."""
    normalized = file_path.replace('\\', '/')
    return '.claude/hooks/' in normalized or '.claude/hooks\\' in normalized


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

    # Only activate if overnight state file exists
    if not get_state_path().exists():
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

    if tool_name == 'Bash':
        command = tool_input.get('command', '')
        if check_bash_targets_hooks(command):
            sys.stderr.write(
                '\nOVERNIGHT HOOK PROTECTION: Writing to .claude/hooks/ '
                'via Bash is blocked during overnight sessions.\n'
            )
            sys.exit(2)

    sys.exit(0)


if __name__ == '__main__':
    main()
