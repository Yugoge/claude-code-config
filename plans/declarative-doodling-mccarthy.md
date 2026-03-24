# Plan: Delete ask-debug Command

## Context

The ask-debug command is no longer needed and should be removed.

## Files to Delete

- `/root/knowledge-system/.claude/commands/ask-debug.md`
- `/root/knowledge-system/scripts/todo/ask-debug.py`

## No Other Changes Needed

No references to ask-debug in settings.json or other hooks.

---

# (Archive) Plan: Step Sequence Enforcement Hook

## Context

The workflow hook system enforces todo COUNT but not SEQUENCE. Agents bypass it by calling
TodoWrite once with multiple steps simultaneously marked "completed" — effectively skipping
steps wholesale. The current hooks (`hook-enforce-todo-count.py`, `hook-enforce-workflow.py`)
only verify that the LIST has enough entries (quantity), not that entries were completed ONE
AT A TIME in proper order (quality of progression).

**Root problem**: No hook captures state transitions between successive TodoWrite calls, so
there's no way to detect "you completed 3 steps at once without executing them."

---

## Root Cause

The workflow bookmark only stores `{command, todo_acknowledged}`. There is no "previous todos
state" persisted between TodoWrite calls. Thus every hook compares the NEW todos list against
a static canonical template — never against what the state was BEFORE this call.

The agent exploits this: in a single TodoWrite it flips steps 1, 2, 3 to "completed", and no
hook detects that they went from "pending" to "completed" without passing through "in_progress"
one at a time.

---

## Solution: `hook-enforce-step-sequence.py`

A new PostToolUse/TodoWrite hook that:

1. Reads the **previous todos state** from `bookmark.last_todos` (stored by this hook)
2. Reads the **new todos state** from TodoWrite input
3. Detects and blocks three violation types
4. Updates `bookmark.last_todos` only when the transition is valid

### Violation Rules

| # | Rule | Detection |
|---|------|-----------|
| 1 | Only 1 step can be newly completed per call | `len(newly_completed) > 1` |
| 2 | Steps must pass through `in_progress` before `completed` | `prev[i].status == 'pending' and new[i].status == 'completed'` |
| 3 | Only 1 step can be `in_progress` at a time | `count(in_progress) > 1` |

### Initialization Exception

When `bookmark.last_todos` is absent (first TodoWrite of the session):
- Allow any combination of pending/in_progress
- Block only if any step is already "completed"
- Write the initial state to `bookmark.last_todos`

---

## Files to Create

### 1. `/root/.claude/hooks/hook-enforce-step-sequence.py`

```python
#!/usr/bin/env python3
"""
PostToolUse Hook: Enforce one-step-at-a-time progression in workflow checklists.

Reads previous todo state from bookmark.last_todos. Compares against the new
TodoWrite input. Blocks if agent completed multiple steps at once, skipped
in_progress, or set multiple steps to in_progress simultaneously.

State: stored in .claude/workflow-{session_id}.json as 'last_todos' field.

Exit codes:
  0: Valid transition, allow
  2: Sequence violation, block
"""

import json, os, sys
from pathlib import Path


def main():
    try:
        data = json.load(sys.stdin)
        new_todos = data.get('tool_input', {}).get('todos', [])
        session_id = data.get('session_id', 'default')
    except Exception:
        sys.exit(0)

    if not new_todos:
        sys.exit(0)

    project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
    bookmark_path = project_dir / '.claude' / f'workflow-{session_id}.json'

    if not bookmark_path.exists():
        sys.exit(0)

    try:
        state = json.loads(bookmark_path.read_text())
    except Exception:
        sys.exit(0)

    cmd_name = state.get('command', '?')
    last_todos = state.get('last_todos')  # None on first call

    violations = []

    if last_todos is None:
        # Initialization: no completed steps allowed yet
        completed = [t for t in new_todos if t.get('status') == 'completed']
        if completed:
            violations.append(
                f"Initial TodoWrite cannot have completed steps — "
                f"{len(completed)} step(s) already marked completed: "
                + ', '.join(f'"{t[\"content\"]}"' for t in completed)
            )
    else:
        # Subsequent call: enforce sequence rules
        if len(last_todos) != len(new_todos):
            # Count mismatch handled by hook-enforce-todo-count; skip
            sys.exit(0)

        prev_completed = {i for i, t in enumerate(last_todos) if t.get('status') == 'completed'}
        new_completed = {i for i, t in enumerate(new_todos) if t.get('status') == 'completed'}
        newly_completed = new_completed - prev_completed

        # Rule 1: max 1 newly completed per call
        if len(newly_completed) > 1:
            names = [f'Step {i}: "{new_todos[i]["content"]}"' for i in sorted(newly_completed)]
            violations.append(
                f"Completed {len(newly_completed)} steps in one call (max 1 allowed):\n"
                + '\n'.join(f'  - {n}' for n in names)
            )

        # Rule 2: no pending → completed (must pass through in_progress)
        for idx in newly_completed:
            if last_todos[idx].get('status') == 'pending':
                violations.append(
                    f'Step {idx} ("{new_todos[idx]["content"]}"): '
                    f'went from pending → completed without in_progress'
                )

        # Rule 3: max 1 in_progress at a time
        in_progress = [t for t in new_todos if t.get('status') == 'in_progress']
        if len(in_progress) > 1:
            violations.append(
                f"Multiple steps in_progress simultaneously ({len(in_progress)}): "
                + ', '.join(f'"{t["content"]}"' for t in in_progress)
            )

    if violations:
        # Find what step should actually be next
        next_hint = ''
        if last_todos:
            for i, t in enumerate(last_todos):
                if t.get('status') == 'in_progress':
                    next_hint = (
                        f'\nREQUIRED ACTION: Mark Step {i} ("{t["content"]}") as completed, '
                        f'then mark Step {i+1} as in_progress — one TodoWrite at a time.'
                    )
                    break

        sys.stderr.write(
            f'\n⛔ STEP SEQUENCE VIOLATION in /{cmd_name}:\n'
            + '\n'.join(f'  [{j+1}] {v}' for j, v in enumerate(violations))
            + '\n\nMANDATORY RULES:\n'
            '  1. Complete exactly ONE step per TodoWrite call\n'
            '  2. Each step must pass through in_progress before completed\n'
            '  3. Only ONE step can be in_progress at a time\n'
            + next_hint + '\n'
        )
        sys.exit(2)

    # Valid transition — persist new state
    try:
        state['last_todos'] = new_todos
        bookmark_path.write_text(json.dumps(state))
    except Exception:
        pass

    sys.exit(0)


if __name__ == '__main__':
    main()
```

### 2. `/root/knowledge-system/scripts/hooks/hook-enforce-step-sequence.py`

Identical content to the global hook (project-level copy following existing pattern).

---

## Files to Modify

### 3. `/root/.claude/settings.json`

Add after `hook-enforce-todo-count.py` in the PostToolUse/TodoWrite hooks array:

```json
{
  "type": "command",
  "stdin_json": true,
  "command": "python3 ~/.claude/hooks/hook-enforce-step-sequence.py"
}
```

### 4. `/root/knowledge-system/.claude/settings.json`

Add after `hook-enforce-todo-count.py` in the PostToolUse/TodoWrite hooks array:

```json
{
  "type": "command",
  "stdin_json": true,
  "command": "python3 \"$CLAUDE_PROJECT_DIR\"/scripts/hooks/hook-enforce-step-sequence.py"
}
```

---

## Execution Order (PostToolUse/TodoWrite chain)

1. `hook-todo-state-tracker.py` — display progress (non-blocking)
2. `hook-enforce-todo-count.py` — enforce minimum count (blocking)
3. **`hook-enforce-step-sequence.py`** ← NEW — enforce one-at-a-time sequence (blocking)

Count enforcement runs first so that if count is wrong, the sequence hook doesn't need to handle
mismatched list lengths.

---

## Verification

1. Run `/dev` or `/ask` and try calling TodoWrite with multiple steps completed at once
2. The new hook should immediately block with `⛔ STEP SEQUENCE VIOLATION`
3. Correct a single step at a time and verify it passes
4. Confirm `bookmark.last_todos` updates correctly after each valid TodoWrite
5. Verify initialization (all-pending first call) is NOT blocked

---

## Edge Cases Handled

- **Initial TodoWrite**: `last_todos` absent → allow if no completed steps
- **Count mismatch**: delegate to `hook-enforce-todo-count.py` (exits early if lengths differ)
- **Re-completing already-completed steps**: `newly_completed` is a set diff, so already-done steps are excluded
- **No active workflow**: bookmark absent → exit 0 immediately
- **Concurrent in_progress + newly completed**: allowed (completing one while starting next)
