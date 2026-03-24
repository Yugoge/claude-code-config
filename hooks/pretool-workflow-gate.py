#!/usr/bin/env python3
"""
PreToolUse Hook: Require TodoWrite/TodoRead acknowledgment before other tools.

If an active workflow exists (bookmark present) and the agent has NOT yet
called TodoWrite or TodoRead (todo_acknowledged == false in bookmark), block
any other tool.

This prevents agents from ignoring the workflow checklist while still using
other tools freely.

Logic:
  1. If tool is TodoWrite or TodoRead → set todo_acknowledged=true → allow
  2. No bookmark → allow (no active workflow)
  3. todo_acknowledged == true → allow
  4. Otherwise → block

Exit codes:
  0: Allow tool use
  2: Block tool use (must call TodoWrite/TodoRead first)
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def official_todos_path(session_id: str) -> Path:
    return Path.home() / '.claude' / 'todos' / f'{session_id}-agent-{session_id}.json'


def run_canonical_todos(cmd_name: str, project_dir: Path) -> list:
    """Run the canonical todo script and return the full step list."""
    todo_script = project_dir / 'scripts' / 'todo' / f'{cmd_name}.py'
    if not todo_script.exists():
        global_todo = Path.home() / '.claude' / 'scripts' / 'todo' / f'{cmd_name}.py'
        if global_todo.exists():
            todo_script = global_todo
        else:
            return []
    result = subprocess.run(
        ['python3', str(todo_script)],
        capture_output=True, text=True, cwd=str(project_dir)
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        return json.loads(result.stdout)
    except Exception:
        return []


def build_next_todowrite_call(session_id: str, cmd_name: str = '', project_dir: Path = None) -> str:
    """Return ready-to-use JSON for the next TodoWrite call.

    Primary source: todos file (always clean — tracker guards against bad-count writes).
    Fallback: canonical script (when file doesn't exist, e.g. first-time count_mismatch).
    """
    try:
        todos_file = official_todos_path(session_id)
        if todos_file.exists():
            todos = json.loads(todos_file.read_text())
        elif cmd_name and project_dir:
            # File missing (e.g. first TodoWrite had wrong count, tracker skipped write)
            # Fall back to canonical so agent still gets a usable hint
            todos = run_canonical_todos(cmd_name, project_dir)
            if not todos:
                return ''
        else:
            return ''

        result = [t.copy() for t in todos]
        has_inprogress = any(t.get('status') == 'in_progress' for t in result)
        if not has_inprogress:
            for t in result:
                if t.get('status') == 'pending':
                    t['status'] = 'in_progress'
                    break
        return json.dumps(result, ensure_ascii=False, separators=(',', ': '))
    except Exception:
        return ''


def build_sequence_fix_call(last_todos: list) -> str:
    """For sequence violations: compute the correct next state from last_todos.

    Finds the in_progress step in last_todos (the pre-violation state), marks it
    completed, and marks the next pending step as in_progress. This gives the agent
    a valid, non-violating TodoWrite to submit.
    """
    if not last_todos:
        return ''
    try:
        result = [t.copy() for t in last_todos]
        in_progress_idx = next(
            (i for i, t in enumerate(result) if t.get('status') == 'in_progress'), None
        )
        if in_progress_idx is not None:
            result[in_progress_idx]['status'] = 'completed'
            for t in result[in_progress_idx + 1:]:
                if t.get('status') == 'pending':
                    t['status'] = 'in_progress'
                    break
        else:
            for t in result:
                if t.get('status') == 'pending':
                    t['status'] = 'in_progress'
                    break
        return json.dumps(result, ensure_ascii=False, separators=(',', ': '))
    except Exception:
        return ''


def main():
    try:
        data = json.load(sys.stdin)
        tool_name = data.get('tool_name', '')
        session_id = data.get('session_id', 'default')
    except Exception:
        sys.exit(0)

    project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
    bookmark_path = project_dir / '.claude' / f'workflow-{session_id}.json'

    # TodoWrite → acknowledge and allow
    # (Stop hook enforces todo count >= blocking_count, so reducing todos is caught at session end)
    # Note: type errors (todos as string instead of array) are caught by Claude Code's schema
    # validation BEFORE PreToolUse hooks run — no need to duplicate that check here.
    if tool_name == 'TodoWrite':
        if bookmark_path.exists():
            try:
                state = json.loads(bookmark_path.read_text())
                changed = False
                if not state.get('todo_acknowledged', False):
                    state['todo_acknowledged'] = True
                    changed = True
                # Always clear lock_reason on TodoWrite — PostToolUse hooks (count/sequence)
                # will re-set it if the new call is still violating.
                # This handles race condition where tracker overwrites todo_acknowledged=False.
                if state.get('lock_reason'):
                    state.pop('lock_reason', None)
                    changed = True
                if changed:
                    bookmark_path.write_text(json.dumps(state))
            except Exception:
                pass
        sys.exit(0)

    # No bookmark → no active workflow → allow
    if not bookmark_path.exists():
        sys.exit(0)

    try:
        state = json.loads(bookmark_path.read_text())
    except Exception:
        sys.exit(0)

    lock_reason = state.get('lock_reason', '')

    # Already acknowledged AND no active lock → allow
    # Note: lock_reason checked independently because todo_acknowledged may stay True
    # due to a race condition between PostToolUse tracker and sequence/count hooks.
    if state.get('todo_acknowledged', False) and not lock_reason:
        sys.exit(0)

    # Not acknowledged or locked → block with reason-specific message
    cmd_name = state.get('command', '?')
    if not lock_reason:
        lock_reason = 'not_started'

    if lock_reason == 'sequence_violation':
        # Hint uses last_todos (pre-violation state) to show the CORRECT next call,
        # not the violating todos-file state.
        last_todos = state.get('last_todos', [])
        next_json = build_sequence_fix_call(last_todos) if last_todos else ''
    else:
        next_json = build_next_todowrite_call(session_id, cmd_name, project_dir)

    json_hint = (
        f'\nCall TodoWrite with this exact todos array:\n{next_json}\n'
        if next_json else ''
    )

    if lock_reason == 'sequence_violation':
        sys.stderr.write(
            f'\n🚫 STEP SKIPPING DETECTED: /{cmd_name} workflow is locked.\n'
            f'You attempted to skip or reorder steps.\n'
            f'Call TodoWrite to fix the sequence — complete steps one at a time, in order.\n'
            + json_hint
        )
    elif lock_reason == 'count_mismatch':
        sys.stderr.write(
            f'\n🚫 STEP COUNT VIOLATION: /{cmd_name} workflow is locked.\n'
            f'TodoWrite was called with the wrong number of steps.\n'
            f'Call TodoWrite with the complete canonical step list.\n'
            + json_hint
        )
    else:
        sys.stderr.write(
            f'\n⚠️  CHECKLIST NOT STARTED: /{cmd_name} workflow is active.\n'
            f'Call TodoWrite to initialize the checklist before using other tools.\n'
            + json_hint
        )
    sys.exit(2)


if __name__ == '__main__':
    main()
