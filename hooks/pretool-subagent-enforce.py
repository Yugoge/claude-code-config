#!/usr/bin/env python3
"""
PreToolUse Hook: Enforce subagent invocation at designated workflow steps.

Gate 4 in the enforcement chain. Two behaviors:

1. BLOCKING (exit 2): When the current in_progress step has subagent_call
   metadata AND the Agent tool has not yet been called (per bookmark),
   block all tools EXCEPT Agent and TodoWrite.

2. ADVISORY (exit 0, stderr hint): When the current in_progress step is
   the step BEFORE a step with subagent_call, print a non-blocking hint.

Reads subagent_call metadata from canonical todo script (NOT from
TodoWrite payloads). Reads/writes subagent tracking state in the
workflow bookmark's 'subagent_calls' dict.

Exit codes:
  0: Allow tool use (with optional advisory hint on stderr)
  2: Block tool use (subagent must be called first)
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.todo_canonical import run_todo_script


# Tools always allowed even during subagent enforcement
ALWAYS_ALLOWED = {'Agent', 'TodoWrite', 'TodoRead', 'mcp__happy__change_title'}


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


def get_subagent_call(canonical: list, step_index: int):
    """Get subagent_call metadata for a step from canonical todos."""
    if step_index < 0 or step_index >= len(canonical):
        return None
    return canonical[step_index].get('subagent_call')


def is_subagent_called(state: dict, step_index: int) -> bool:
    """Check if the subagent has been called for this step."""
    calls = state.get('subagent_calls', {})
    return calls.get(str(step_index), False)


def init_subagent_tracking(state: dict, step_index: int, bookmark_path: Path):
    """Initialize subagent tracking for a step if not already present."""
    calls = state.get('subagent_calls', {})
    key = str(step_index)
    if key not in calls:
        calls[key] = False
        state['subagent_calls'] = calls
        try:
            bookmark_path.write_text(json.dumps(state))
        except Exception:
            pass


def format_subagent_hint(subagent_call) -> str:
    """Format a human-readable hint about which subagent to call."""
    if isinstance(subagent_call, list):
        agents = [s.get('subagent_type', '?') for s in subagent_call]
        return ', '.join(agents)
    if isinstance(subagent_call, dict):
        return subagent_call.get('subagent_type', '?')
    return '?'


def emit_block(step_index: int, step_content: str, subagent_call):
    """Block with clear message about which subagent to call."""
    hint = format_subagent_hint(subagent_call)
    sys.stderr.write(
        f'\nBLOCKED: Step {step_index} ("{step_content}") requires '
        f'a subagent call before other tools can be used.\n'
        f'Required subagent: {hint}\n'
        f'Call the Agent tool with the appropriate subagent, '
        f'then other tools will be unblocked.\n'
        f'Allowed tools: Agent, TodoWrite\n\n'
    )
    sys.exit(2)


def emit_advisory(next_step_index: int, next_content: str, subagent_call):
    """Print non-blocking hint about upcoming subagent step."""
    hint = format_subagent_hint(subagent_call)
    sys.stderr.write(
        f'\nHINT: Next step (Step {next_step_index}: "{next_content}") '
        f'requires subagent call: {hint}\n'
        f'Prepare to invoke the Agent tool after completing '
        f'the current step.\n\n'
    )


def check_current_step(state, bookmark_path, last_todos, canonical, ip_index):
    """Check if current in_progress step requires subagent enforcement."""
    subagent_call = get_subagent_call(canonical, ip_index)
    if not subagent_call:
        return
    init_subagent_tracking(state, ip_index, bookmark_path)
    if not is_subagent_called(state, ip_index):
        step_content = last_todos[ip_index].get('content', '?')
        emit_block(ip_index, step_content, subagent_call)


def check_next_step_advisory(canonical, ip_index):
    """Emit advisory hint if the next step requires a subagent."""
    next_index = ip_index + 1
    next_call = get_subagent_call(canonical, next_index)
    if next_call and next_index < len(canonical):
        next_content = canonical[next_index].get('content', '?')
        emit_advisory(next_index, next_content, next_call)


def parse_stdin() -> tuple:
    """Parse stdin JSON. Returns (tool_name, session_id) or exits."""
    try:
        data = json.load(sys.stdin)
        return data.get('tool_name', ''), data.get('session_id', 'default')
    except Exception:
        sys.exit(0)


def mark_subagent_called(state, step_index, bookmark_path):
    """Pre-mark subagent as called when Agent tool is invoked."""
    calls = state.get('subagent_calls', {})
    calls[str(step_index)] = True
    state['subagent_calls'] = calls
    try:
        bookmark_path.write_text(json.dumps(state))
    except Exception:
        pass


def handle_agent_tool(session_id):
    """When Agent tool is invoked, pre-mark bookmark so subagent is unblocked."""
    state, bookmark_path = load_bookmark(session_id)
    if state is None:
        return
    cmd_name = state.get('command', '')
    last_todos = state.get('last_todos')
    if not cmd_name or not last_todos:
        return
    canonical = run_todo_script(cmd_name)
    if not canonical:
        return
    ip_index = find_in_progress_index(last_todos)
    if ip_index is None:
        return
    if get_subagent_call(canonical, ip_index):
        mark_subagent_called(state, ip_index, bookmark_path)


def main():
    tool_name, session_id = parse_stdin()

    if tool_name in ALWAYS_ALLOWED:
        if tool_name == 'Agent':
            handle_agent_tool(session_id)
        sys.exit(0)

    state, bookmark_path = load_bookmark(session_id)
    if state is None:
        sys.exit(0)

    cmd_name = state.get('command', '')
    last_todos = state.get('last_todos')
    if not cmd_name or not last_todos:
        sys.exit(0)

    canonical = run_todo_script(cmd_name)
    if not canonical:
        sys.exit(0)

    ip_index = find_in_progress_index(last_todos)
    if ip_index is None:
        sys.exit(0)

    check_current_step(state, bookmark_path, last_todos, canonical, ip_index)
    check_next_step_advisory(canonical, ip_index)
    sys.exit(0)


if __name__ == '__main__':
    main()
