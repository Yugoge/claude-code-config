#!/usr/bin/env python3
"""
PostToolUse Hook: Enforce one-step-at-a-time progression in workflow checklists.

Reads previous todo state from bookmark.last_todos. Compares against the new
TodoWrite input. Blocks if agent completed multiple steps at once, skipped
in_progress, set multiple steps to in_progress simultaneously, or modified
step content/activeForm (only status changes are allowed).

State: stored in .claude/workflow-{session_id}.json as 'last_todos' field.

Exit codes:
  0: Valid transition, allow
  2: Sequence violation, block
"""

import json
import os
import sys
from pathlib import Path

# Import shared canonical validation
sys.path.insert(0, str(Path(__file__).parent))
from lib.todo_canonical import validate_against_canonical


def check_content_immutability(last_todos, new_todos, violations):
    """Rule 5: content and activeForm are immutable after initialization."""
    for i, (old, new) in enumerate(zip(last_todos, new_todos)):
        old_content = old.get('content', '')
        new_content = new.get('content', '')
        if old_content != new_content:
            violations.append(
                f'Step {i} content modified: '
                f'"{old_content}" -> "{new_content}"'
            )
        old_form = old.get('activeForm', '')
        new_form = new.get('activeForm', '')
        if old_form != new_form:
            violations.append(
                f'Step {i} activeForm modified: '
                f'"{old_form}" -> "{new_form}"'
            )


def check_completion_rules(last_todos, new_todos, violations):
    """Rules 1-4: sequence, status transitions, ordering."""
    prev_completed = {
        i for i, t in enumerate(last_todos)
        if t.get('status') == 'completed'
    }
    new_completed = {
        i for i, t in enumerate(new_todos)
        if t.get('status') == 'completed'
    }
    newly_completed = new_completed - prev_completed

    # Rule 1: max 1 newly completed per call
    if len(newly_completed) > 1:
        names = [
            f'Step {i}: "{new_todos[i]["content"]}"'
            for i in sorted(newly_completed)
        ]
        violations.append(
            f"Completed {len(newly_completed)} steps in one call "
            f"(max 1 allowed):\n"
            + '\n'.join(f'  - {n}' for n in names)
        )

    # Rule 2: no pending -> completed (must pass through in_progress)
    for idx in newly_completed:
        if last_todos[idx].get('status') == 'pending':
            violations.append(
                f'Step {idx} ("{new_todos[idx]["content"]}"): '
                f'went from pending -> completed without in_progress'
            )

    # Rule 3: max 1 in_progress at a time
    in_progress = [
        t for t in new_todos if t.get('status') == 'in_progress'
    ]
    if len(in_progress) > 1:
        violations.append(
            f"Multiple steps in_progress simultaneously "
            f"({len(in_progress)}): "
            + ', '.join(f'"{t["content"]}"' for t in in_progress)
        )

    # Rule 4: can't start step N if any earlier step is pending
    newly_in_progress = [
        i for i, (prev, cur) in enumerate(zip(last_todos, new_todos))
        if prev.get('status') == 'pending'
        and cur.get('status') == 'in_progress'
    ]
    for idx in newly_in_progress:
        for prev_idx in range(idx):
            if new_todos[prev_idx].get('status') != 'completed':
                violations.append(
                    f'Step {idx} ("{new_todos[idx]["content"]}"): '
                    f'cannot start before Step {prev_idx} '
                    f'("{new_todos[prev_idx]["content"]}") is completed'
                )
                break


def build_hint(last_todos):
    """Build a hint for the required next action."""
    for i, t in enumerate(last_todos):
        if t.get('status') == 'in_progress':
            return (
                f'\nREQUIRED ACTION: Mark Step {i} '
                f'("{t["content"]}") as completed, then mark '
                f'Step {i+1} as in_progress -- one TodoWrite '
                f'at a time.'
            )
    return ''


def emit_error(bookmark_path, cmd_name, violations, last_todos):
    """Write violation error and lock the workflow."""
    next_hint = build_hint(last_todos) if last_todos else ''
    try:
        fresh = json.loads(bookmark_path.read_text())
        fresh['todo_acknowledged'] = False
        fresh['lock_reason'] = 'sequence_violation'
        bookmark_path.write_text(json.dumps(fresh))
    except Exception:
        pass

    numbered = '\n'.join(
        f'  [{j+1}] {v}' for j, v in enumerate(violations)
    )
    sys.stderr.write(
        f'\nBLOCKED STEP SEQUENCE VIOLATION in /{cmd_name}:\n'
        + numbered
        + '\n\nMANDATORY RULES:\n'
        '  1. Complete exactly ONE step per TodoWrite call\n'
        '  2. Each step must pass through in_progress before completed\n'
        '  3. Only ONE step can be in_progress at a time\n'
        '  4. Steps must be completed in order -- no skipping ahead\n'
        '  5. Step content and activeForm are immutable -- only '
        'status changes allowed\n'
        + next_hint + '\n'
    )
    sys.exit(2)


def save_state(bookmark_path, state, new_todos):
    """Persist new todo state to bookmark."""
    try:
        state['last_todos'] = new_todos
        bookmark_path.write_text(json.dumps(state))
    except Exception:
        pass


def main():
    try:
        data = json.load(sys.stdin)
        new_todos = data.get('tool_input', {}).get('todos', [])
        session_id = data.get('session_id', 'default')
    except Exception:
        sys.exit(0)

    if not new_todos:
        sys.exit(0)

    project_dir = Path(
        os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())
    )
    bookmark_path = (
        project_dir / '.claude' / f'workflow-{session_id}.json'
    )

    if not bookmark_path.exists():
        sys.exit(0)

    try:
        state = json.loads(bookmark_path.read_text())
    except Exception:
        sys.exit(0)

    cmd_name = state.get('command', '?')
    last_todos = state.get('last_todos')

    # First call (no previous state): validate against canonical, then save
    if last_todos is None:
        canonical_violations = validate_against_canonical(cmd_name, new_todos)
        if canonical_violations:
            numbered = '\n'.join(
                f'  [{j+1}] {v}'
                for j, v in enumerate(canonical_violations)
            )
            sys.stderr.write(
                f'\nBLOCKED TodoWrite (canonical validation):\n' + numbered
                + '\n\nContent/activeForm must match the canonical definition '
                'in ~/.claude/scripts/todo/\n\n'
            )
            sys.exit(2)
        save_state(bookmark_path, state, new_todos)
        sys.exit(0)

    # Length mismatch: validate against canonical, then run sequence rules
    # if possible before saving
    if len(last_todos) != len(new_todos):
        canonical_violations = validate_against_canonical(cmd_name, new_todos)
        if canonical_violations:
            numbered = '\n'.join(
                f'  [{j+1}] {v}'
                for j, v in enumerate(canonical_violations)
            )
            sys.stderr.write(
                f'\nBLOCKED TodoWrite (canonical validation):\n' + numbered
                + '\n\nContent/activeForm must match the canonical definition '
                'in ~/.claude/scripts/todo/\n\n'
            )
            sys.exit(2)
        save_state(bookmark_path, state, new_todos)
        sys.exit(0)

    # Normal case: same length, run full validation
    violations = []
    check_content_immutability(last_todos, new_todos, violations)
    check_completion_rules(last_todos, new_todos, violations)

    if violations:
        emit_error(bookmark_path, cmd_name, violations, last_todos)

    save_state(bookmark_path, state, new_todos)
    sys.exit(0)


if __name__ == '__main__':
    main()
