#!/usr/bin/env python3
"""
PostToolUse Hook: Enforce canonical todo count immediately after TodoWrite.

Fires after every TodoWrite call.
If the number of todos written is less than blocking_count (from todo script),
block Claude and provide the full canonical todo list to re-submit.

Exit codes:
  0: Count correct, allow
  2: Count mismatch, block and show canonical todos
"""

import json
import os
import subprocess
import sys
from pathlib import Path


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
    try:
        data = json.load(sys.stdin)
        todos = data.get('tool_input', {}).get('todos', [])
        session_id = data.get('session_id', 'default')
    except Exception:
        sys.exit(0)

    if not todos:
        sys.exit(0)

    project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
    bookmark = project_dir / '.claude' / f'workflow-{session_id}.json'

    if not bookmark.exists():
        sys.exit(0)

    try:
        cmd_name = json.loads(bookmark.read_text()).get('command', '')
    except Exception:
        sys.exit(0)

    if not cmd_name:
        sys.exit(0)

    canonical = run_todo_script(cmd_name, project_dir)
    if not canonical:
        sys.exit(0)

    blocking_count = len(canonical)
    actual_count = len(todos)

    if actual_count < blocking_count:
        # Reset todo_acknowledged so PreToolUse blocks any further tools
        # until agent re-calls TodoWrite with the correct count
        try:
            state = json.loads(bookmark.read_text())
            state['todo_acknowledged'] = False
            state['lock_reason'] = 'count_mismatch'
            bookmark.write_text(json.dumps(state))
        except Exception:
            pass
        sys.stderr.write(
            f'\n⛔ TODO COUNT MISMATCH: /{cmd_name} requires {blocking_count} steps '
            f'but TodoWrite was called with only {actual_count}.\n'
            f'You MUST use the recommended canonical todos below — do NOT create custom or abbreviated steps.\n'
            f'All other tools are now blocked until you re-call TodoWrite with ALL {blocking_count} canonical steps:\n\n'
            + json.dumps(canonical, ensure_ascii=False, indent=2) + '\n'
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == '__main__':
    main()
