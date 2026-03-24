#!/usr/bin/env python3
"""
PreToolUse Hook: Validate TodoWrite input BEFORE execution.

Prevents sequence violations by checking the proposed todos array against
the last known state. This is the enforcement counterpart to
posttool-todo-sequence.py (which can only warn after the fact).

State: reads last_todos from .claude/workflow-{session_id}.json

Rules enforced:
  1. Max 1 step completed per call
  2. Steps must pass through in_progress before completed
  3. Only 1 step can be in_progress at a time
  4. Content and activeForm are immutable (only status changes allowed)
  5. Steps must be completed in order (no skipping ahead)

Exit codes:
  0: Valid, allow TodoWrite
  2: Violation detected, block TodoWrite (calls sys.exit(2))
"""

import json
import os
import sys
from pathlib import Path

# Import shared canonical validation
sys.path.insert(0, str(Path(__file__).parent))
from lib.todo_canonical import validate_against_canonical, run_todo_script


def check_immutability(last, new, violations):
    """Content and activeForm are immutable after init."""
    for i, (o, n) in enumerate(zip(last, new)):
        if o.get('content', '') != n.get('content', ''):
            violations.append(
                f'Step {i} content modified: '
                f'"{o["content"]}" -> "{n["content"]}"'
            )
        if o.get('activeForm', '') != n.get('activeForm', ''):
            violations.append(
                f'Step {i} activeForm modified: '
                f'"{o["activeForm"]}" -> "{n["activeForm"]}"'
            )


def check_max_one_completion(last, new, violations):
    """Rule 1: max 1 newly completed per call."""
    prev = {i for i, t in enumerate(last) if t.get('status') == 'completed'}
    cur = {i for i, t in enumerate(new) if t.get('status') == 'completed'}
    fresh = cur - prev
    if len(fresh) > 1:
        names = [f'Step {i}: "{new[i]["content"]}"' for i in sorted(fresh)]
        violations.append(
            f"Completed {len(fresh)} steps in one call (max 1):\n"
            + '\n'.join(f'  - {n}' for n in names)
        )
    return fresh


def check_skip_in_progress(last, new, fresh, violations):
    """Rule 2: no pending -> completed without in_progress."""
    for idx in fresh:
        if idx < len(last) and last[idx].get('status') == 'pending':
            violations.append(
                f'Step {idx} ("{new[idx]["content"]}"): '
                f'pending -> completed without in_progress'
            )


def check_single_in_progress(new, violations):
    """Rule 3: max 1 in_progress at a time."""
    ip = [t for t in new if t.get('status') == 'in_progress']
    if len(ip) > 1:
        violations.append(
            f"Multiple in_progress ({len(ip)}): "
            + ', '.join(f'"{t["content"]}"' for t in ip)
        )


def check_ordering(last, new, violations):
    """Rule 4: can't start step N before earlier steps complete."""
    started = [
        i for i, (p, c) in enumerate(zip(last, new))
        if p.get('status') == 'pending' and c.get('status') == 'in_progress'
    ]
    for idx in started:
        for prev in range(idx):
            if new[prev].get('status') != 'completed':
                violations.append(
                    f'Step {idx} ("{new[idx]["content"]}"): '
                    f'cannot start before Step {prev} '
                    f'("{new[prev]["content"]}") is completed'
                )
                break


def build_correct_call(last):
    """Compute the valid next TodoWrite from last state."""
    if not last:
        return ''
    result = [t.copy() for t in last]
    ip = next(
        (i for i, t in enumerate(result) if t.get('status') == 'in_progress'),
        None
    )
    if ip is not None:
        result[ip]['status'] = 'completed'
        for t in result[ip + 1:]:
            if t.get('status') == 'pending':
                t['status'] = 'in_progress'
                break
    else:
        for t in result:
            if t.get('status') == 'pending':
                t['status'] = 'in_progress'
                break
    return json.dumps(result, ensure_ascii=False, separators=(',', ': '))


def load_state(session_id):
    """Load workflow bookmark, return state dict or None."""
    project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
    path = project_dir / '.claude' / f'workflow-{session_id}.json'
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def validate(last, new):
    """Run all validation rules, return list of violations."""
    violations = []
    check_immutability(last, new, violations)
    fresh = check_max_one_completion(last, new, violations)
    check_skip_in_progress(last, new, fresh, violations)
    check_single_in_progress(new, violations)
    check_ordering(last, new, violations)
    return violations


def emit_block(cmd, violations, last):
    """Print block message to stderr and exit 2."""
    hint = ''
    for i, t in enumerate(last):
        if t.get('status') == 'in_progress':
            hint = (
                f'\nREQUIRED: Complete Step {i} '
                f'("{t["content"]}"), then start Step {i+1}.'
            )
            break
    correct = build_correct_call(last)
    json_hint = f'\nCall TodoWrite with:\n{correct}\n' if correct else ''
    numbered = '\n'.join(f'  [{j+1}] {v}' for j, v in enumerate(violations))
    sys.stderr.write(
        f'\nBLOCKED TodoWrite for /{cmd}:\n' + numbered
        + '\n\nRULES: (1) One completion per call '
        '(2) Must pass through in_progress '
        '(3) One in_progress at a time '
        '(4) In order (5) Content immutable\n'
        + hint + json_hint + '\n'
    )
    sys.exit(2)


def emit_block_canonical(cmd, violations):
    """Print block message for canonical validation failures.

    Includes the canonical todos as a correct-call hint so the caller
    knows what values to use.
    """
    numbered = '\n'.join(f'  [{j+1}] {v}' for j, v in enumerate(violations))
    # Load canonical todos for the hint
    canonical = run_todo_script(cmd) if cmd else None
    hint = ''
    if canonical:
        hint = (
            '\nCorrect canonical todos:\n'
            + json.dumps(canonical, ensure_ascii=False, indent=2)
            + '\n'
        )
    sys.stderr.write(
        f'\nBLOCKED TodoWrite (canonical validation):\n' + numbered
        + '\n\nContent/activeForm must match the canonical definition '
        'in ~/.claude/scripts/todo/\n'
        + hint + '\n'
    )
    sys.exit(2)


def validate_against_canonical_if_needed(cmd, new_todos):
    """Validate new_todos against canonical script if available.

    Calls sys.exit(2) if violations are found.
    Returns True if validation passed (or no canonical existed).
    """
    violations = validate_against_canonical(cmd, new_todos)
    if violations:
        emit_block_canonical(cmd, violations)
        return False
    return True


def main():
    """Entry point: parse stdin, load state, validate, block or allow."""
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if data.get('tool_name') != 'TodoWrite':
        sys.exit(0)
    new_todos = data.get('tool_input', {}).get('todos', [])
    if not new_todos:
        sys.exit(0)
    state = load_state(data.get('session_id', 'default'))
    if not state:
        sys.exit(0)
    last = state.get('last_todos')
    cmd = state.get('command', '')

    # No previous state or count mismatch: validate against canonical if available
    if last is None or len(last) != len(new_todos):
        validate_against_canonical_if_needed(cmd, new_todos)
        sys.exit(0)

    violations = validate(last, new_todos)
    if violations:
        emit_block(cmd, violations, last)
    sys.exit(0)


if __name__ == '__main__':
    main()
