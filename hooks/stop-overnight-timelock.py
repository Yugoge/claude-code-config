#!/usr/bin/env python3
"""
Stop Hook: Block conversation termination until overnight end-time.

Logic:
  1. Read JSON from stdin (session_id)
  2. Scan for any .claude/overnight-state-*.json files
  3. If no state file: exit 0 (allow stop)
  4. If current time < end_time: exit 2 (block stop)
  5. If current time >= end_time: exit 0 (allow stop)

Exit codes:
  0: Allow stop
  2: Block stop (time-lock active)
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def read_stdin_context() -> dict:
    """Read and parse JSON from stdin."""
    try:
        if not sys.stdin.isatty():
            return json.load(sys.stdin)
    except Exception:
        pass
    return {}


def load_state(project_dir: Path) -> dict | None:
    """Load any active overnight state file. Scans overnight-state-*.json."""
    claude_dir = project_dir / '.claude'
    for p in sorted(claude_dir.glob('overnight-state-*.json')):
        try:
            state = json.loads(p.read_text())
            return state
        except (json.JSONDecodeError, OSError):
            continue
    return None


def parse_end_time(state: dict) -> datetime | None:
    """Extract and parse end_time from state dict."""
    end_time_str = state.get('end_time')
    if not end_time_str:
        return None
    try:
        return datetime.fromisoformat(end_time_str)
    except (ValueError, TypeError):
        return None


def block_with_message(end_time: datetime, state: dict) -> None:
    """Write time-lock message to stderr and exit 2."""
    remaining = end_time - datetime.now()
    total_seconds = int(remaining.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    phase = state.get('current_phase', 'unknown')
    cycle_count = state.get('cycle_count', 0)
    issues_fixed = state.get('issues_fixed', 0)

    sys.stderr.write(
        f'\n TIME-LOCK ACTIVE: Overnight session runs until '
        f'{end_time.strftime("%Y-%m-%d %H:%M")}.\n'
        f'Time remaining: {hours}h {minutes}m\n'
        f'Current phase: {phase} | Cycles: {cycle_count} | '
        f'Fixed: {issues_fixed}\n'
        f'The session cannot end until the end-time is reached.\n'
        f'Continue working on the current cycle.\n'
    )
    sys.exit(2)


def main():
    """Entry point for the stop-overnight-timelock hook."""
    context = read_stdin_context()
    if context.get('stop_hook_active', False):
        sys.exit(0)

    project_dir = Path(
        os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())
    )
    state = load_state(project_dir)
    if state is None:
        sys.exit(0)

    # Only block the overnight session itself — not other agents in the same project.
    # If CLAUDE_SESSION_ID is set and doesn't match the state file's session_id, allow stop.
    current_session_id = os.environ.get('CLAUDE_SESSION_ID', '')
    state_session_id = state.get('session_id', '')
    if current_session_id and state_session_id and current_session_id != state_session_id:
        sys.exit(0)

    end_time = parse_end_time(state)
    if end_time is None:
        sys.exit(0)

    if datetime.now() < end_time:
        block_with_message(end_time, state)

    sys.exit(0)


if __name__ == '__main__':
    main()
