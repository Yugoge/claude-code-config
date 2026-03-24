#!/usr/bin/env python3
"""
Stop Hook: Enforce workflow structural integrity before allowing Claude to stop.

Logic:
  1. If stop_hook_active → exit 0
  2. Read .claude/workflow-{session_id}.json for session_id + command (bookmark only)
  3. If missing or session mismatch → exit 0
  4. Run todo script fresh to get canonical blocking_count
  5. Read ~/.claude/todos/{sid}-agent-{sid}.json for actual len(todos)
  6. If len(todos) < blocking_count → exit 2 (Claude dropped steps)
  7. Otherwise → exit 0

blocking_count always computed from todo script — never from cache.

Exit codes:
  0: Allow stop
  2: Block stop
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def official_todos_path(session_id: str) -> Path:
    return Path.home() / '.claude' / 'todos' / f'{session_id}-agent-{session_id}.json'


def run_todo_script(cmd_name: str, project_dir: Path) -> list:
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


def main():
    stop_hook_active = False
    session_id = 'default'
    try:
        if not sys.stdin.isatty():
            data = json.load(sys.stdin)
            stop_hook_active = data.get('stop_hook_active', False)
            session_id = data.get('session_id', 'default')
    except Exception:
        pass

    if stop_hook_active:
        sys.exit(0)

    project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
    bookmark = project_dir / '.claude' / f'workflow-{session_id}.json'

    if not bookmark.exists():
        sys.exit(0)

    try:
        state = json.loads(bookmark.read_text())
    except Exception:
        sys.exit(0)

    cmd_name = state.get('command')
    if not cmd_name:
        sys.exit(0)

    # Get blocking_count fresh from todo script — never from cache
    canonical = run_todo_script(cmd_name, project_dir)
    if not canonical:
        sys.exit(0)

    blocking_count = len(canonical)

    # Read actual todos
    todos_file = official_todos_path(session_id)
    if not todos_file.exists():
        actual_count = 0
    else:
        try:
            actual_count = len(json.loads(todos_file.read_text()))
        except Exception:
            sys.exit(0)

    if actual_count < blocking_count:
        sys.stderr.write(
            f'\n⛔ WORKFLOW ENFORCEMENT: /{cmd_name} requires {blocking_count} steps '
            f'but only {actual_count} found in checklist ({blocking_count - actual_count} missing).\n'
            f'Claude must not drop steps from the canonical workflow.\n'
            f'Re-initialize the checklist with all {blocking_count} steps.\n'
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == '__main__':
    main()
