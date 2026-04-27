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
  7. If any required step is not completed → exit 2
  8. Otherwise → exit 0

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


def _step_label(todo: dict, index: int) -> str:
    return todo.get('content') or todo.get('step') or f'Step {index}'


def _load_actual_todos(session_id: str) -> tuple[list, str]:
    todos_file = official_todos_path(session_id)
    if not todos_file.exists():
        return [], 'missing'
    try:
        payload = json.loads(todos_file.read_text())
    except Exception:
        return [], 'unreadable'
    if not isinstance(payload, list):
        return [], 'invalid'
    return payload, ''


def _canonical_shape_violations(actual: list, canonical: list) -> list:
    violations = []
    for idx, expected in enumerate(canonical):
        if idx >= len(actual):
            break
        actual_item = actual[idx] if isinstance(actual[idx], dict) else {}
        if actual_item.get('content') != expected.get('content'):
            violations.append(
                f'Step {idx} content mismatch: '
                f'"{actual_item.get("content", "")}" != "{expected.get("content", "")}"'
            )
        if actual_item.get('activeForm') != expected.get('activeForm'):
            violations.append(f'Step {idx} activeForm mismatch')
    return violations


def _incomplete_steps(actual: list, blocking_count: int) -> list:
    return [
        (idx, item)
        for idx, item in enumerate(actual[:blocking_count])
        if not isinstance(item, dict) or item.get('status') != 'completed'
    ]


def _emit_block(cmd_name: str, message: str) -> None:
    sys.stderr.write(f'\n⛔ WORKFLOW ENFORCEMENT: /{cmd_name} cannot stop.\n{message}\n')
    sys.exit(2)


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

    actual, load_error = _load_actual_todos(session_id)
    actual_count = len(actual)
    if load_error:
        _emit_block(
            cmd_name,
            f'Checklist file is {load_error}. Re-initialize and complete all '
            f'{blocking_count} required steps.',
        )

    if actual_count < blocking_count:
        _emit_block(
            cmd_name,
            f'/{cmd_name} requires {blocking_count} steps but only {actual_count} '
            f'were found in the checklist ({blocking_count - actual_count} missing).\n'
            f'The agent must not drop steps from the canonical workflow.\n'
            f'Re-initialize the checklist with all {blocking_count} steps.',
        )

    shape_violations = _canonical_shape_violations(actual, canonical)
    if shape_violations:
        _emit_block(
            cmd_name,
            'Checklist no longer matches the canonical workflow:\n'
            + '\n'.join(f'  - {value}' for value in shape_violations[:10]),
        )

    incomplete = _incomplete_steps(actual, blocking_count)
    if incomplete:
        sample = '\n'.join(
            f'  - Step {idx}: {_step_label(item if isinstance(item, dict) else {}, idx)} '
            f'[{item.get("status", "invalid") if isinstance(item, dict) else "invalid"}]'
            for idx, item in incomplete[:10]
        )
        remaining = '' if len(incomplete) <= 10 else f'\n  ... {len(incomplete) - 10} more'
        _emit_block(
            cmd_name,
            f'{len(incomplete)} required step(s) are not completed:\n'
            + sample
            + remaining
            + '\nComplete the workflow checklist before stopping.',
        )

    sys.exit(0)


if __name__ == '__main__':
    main()
