#!/usr/bin/env python3
"""
PostToolUse:Agent Hook: Track subagent invocations in workflow bookmark.

After Agent tool completes, checks if the current in_progress step has
subagent_call metadata. If so, sets subagent_calls[step_index] = true
in the bookmark, unblocking other tools via pretool-subagent-enforce.py.

B8 fix: Also validates that the Agent's tool_input contains the expected
subagent_type keyword before marking. Emits warning on mismatch but
still marks for backward compatibility.

Exit codes:
  0: Always (tracking only, never blocks)
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.todo_canonical import run_todo_script


def load_bookmark(session_id: str) -> tuple:
    """Load workflow bookmark. Returns (state_dict, path) or (None, path)."""
    project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
    path = project_dir / '.claude' / f'workflow-{session_id}.json'
    if not path.exists():
        return None, path
    try:
        return json.loads(path.read_text()), path
    except Exception:
        return None, path


def find_in_progress_index(last_todos: list) -> int | None:
    """Return the index of the current in_progress step, or None."""
    for i, t in enumerate(last_todos):
        if t.get('status') == 'in_progress':
            return i
    return None


def step_has_subagent_call(canonical: list, step_index: int) -> bool:
    """Check if a canonical step has subagent_call metadata."""
    if step_index < 0 or step_index >= len(canonical):
        return False
    return canonical[step_index].get('subagent_call') is not None


def record_subagent_call(state: dict, step_index: int, bm_path: Path):
    """Mark the subagent as called for this step in the bookmark."""
    try:
        fresh = json.loads(bm_path.read_text())
        calls = fresh.get('subagent_calls', {})
        calls[str(step_index)] = True
        fresh['subagent_calls'] = calls
        bm_path.write_text(json.dumps(fresh))
    except Exception:
        pass


def get_expected_type(canonical: list, step_index: int) -> str:
    """Extract expected subagent_type from canonical step metadata."""
    if step_index < 0 or step_index >= len(canonical):
        return ''
    call = canonical[step_index].get('subagent_call', {})
    if not isinstance(call, dict):
        return ''
    return call.get('subagent_type', '')


def warn_type_mismatch(ip_index: int, expected: str) -> None:
    """Emit warning when Agent prompt does not match expected type (B8)."""
    sys.stderr.write(
        f'WARNING: Agent call on step {ip_index} expected '
        f'subagent_type="{expected}" but prompt does not match. '
        f'Marking call anyway for backward compatibility.\n'
    )


def parse_stdin() -> tuple:
    """Parse stdin JSON. Returns (session_id, agent_prompt) or exits."""
    try:
        data = json.load(sys.stdin)
        ti = data.get('tool_input', {})
        prompt = ti.get('prompt', '') if isinstance(ti, dict) else ''
        return data.get('session_id', 'default'), prompt
    except Exception:
        sys.exit(0)


def resolve_context(session_id: str) -> tuple | None:
    """Load state, canonical, and find in-progress index."""
    state, bm_path = load_bookmark(session_id)
    if state is None:
        return None
    cmd_name = state.get('command', '')
    last_todos = state.get('last_todos')
    if not cmd_name or not last_todos:
        return None
    canonical = run_todo_script(cmd_name)
    if not canonical:
        return None
    ip_index = find_in_progress_index(last_todos)
    if ip_index is None:
        return None
    if not step_has_subagent_call(canonical, ip_index):
        return None
    return state, canonical, last_todos, ip_index, bm_path


def main():
    session_id, agent_prompt = parse_stdin()
    ctx = resolve_context(session_id)
    if ctx is None:
        sys.exit(0)
    state, canonical, last_todos, ip_index, bm_path = ctx
    expected = get_expected_type(canonical, ip_index)
    if expected and expected.lower() not in agent_prompt.lower():
        warn_type_mismatch(ip_index, expected)
    record_subagent_call(state, ip_index, bm_path)
    content = last_todos[ip_index].get('content', '?')
    print(f'SUBAGENT TRACKED: Step {ip_index} ("{content}") '
          f'subagent call recorded.')
    sys.exit(0)


if __name__ == '__main__':
    main()
