#!/usr/bin/env python3
"""
PostToolUse:TodoWrite Hook: Overnight Loop Detection

Fires after every TodoWrite call. Checks if:
1. This is a dev-overnight workflow (overnight-state.json exists)
2. ALL todos have status "completed"
3. end_time is still in the future

If all conditions met: increments cycle_count in state, prints
continuation instructions telling the agent to reset its own todos
and resume from Step 2.

Does NOT directly modify the todos file -- prints instructions
for the agent to act on, avoiding race conditions with other hooks.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def _all_completed(data: dict) -> bool:
    """Check if all todos in the tool_input are completed."""
    todos = data.get('tool_input', {}).get('todos', [])
    if not todos:
        return False
    return all(t.get('status') == 'completed' for t in todos)


def _load_overnight_state() -> tuple[dict | None, Path]:
    """Load overnight state. Scans overnight-state-*.json files."""
    project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
    claude_dir = project_dir / '.claude'
    for p in sorted(claude_dir.glob('overnight-state-*.json')):
        try:
            state = json.loads(p.read_text())
            return state, p
        except Exception:
            continue
    return None, claude_dir / 'overnight-state-unknown.json' 


def _check_end_time(state: dict) -> datetime | None:
    """Parse end_time from state. Returns None if expired or invalid."""
    et = state.get('end_time')
    if not et:
        return None
    try:
        end_time = datetime.fromisoformat(et)
    except (ValueError, TypeError):
        return None
    if datetime.now() >= end_time:
        return None
    return end_time


def _update_state_cycle(state: dict, state_path: Path) -> None:
    """Increment cycle_count and reset phase in state file."""
    state['cycle_count'] = state.get('cycle_count', 0) + 1
    state['current_phase'] = 'exploring'
    tmp = state_path.with_suffix('.tmp')
    try:
        tmp.write_text(json.dumps(state, indent=2))
        os.rename(str(tmp), str(state_path))
    except Exception:
        pass


def _print_loop_instructions(state: dict, end_time: datetime, state_path: Path) -> None:
    """Print continuation instructions for the agent."""
    remaining = end_time - datetime.now()
    hours = int(remaining.total_seconds() // 3600)
    minutes = int((remaining.total_seconds() % 3600) // 60)
    cc = state.get('cycle_count', 0)
    fixed = state.get('issues_fixed', 0)
    wt = state.get('worktree_path', 'unknown')

    print(f'OVERNIGHT LOOP: Cycle {cc} complete. Starting cycle {cc + 1}.')
    print(f'Time remaining: {hours}h {minutes}m')
    print(f'Issues fixed this session: {fixed}')
    print()
    print('INSTRUCTIONS: Reset your todo list to all-pending and begin Step 1 again.')
    print(f'State file: {state_path} (read it for current state)')
    print(f'Worktree: {wt} (already exists, DO NOT create another)')
    print()
    print('Resume from Step 2 (exploration) -- Step 1 setup is already done.')


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if not _all_completed(data):
        sys.exit(0)

    state, state_path = _load_overnight_state()
    if state is None:
        sys.exit(0)

    end_time = _check_end_time(state)
    if end_time is None:
        sys.exit(0)

    _update_state_cycle(state, state_path)
    _print_loop_instructions(state, end_time, state_path)
    sys.exit(0)


if __name__ == '__main__':
    main()
