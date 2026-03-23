#!/usr/bin/env python3
"""
UserPromptSubmit Hook: Checklist Injection for Slash Commands

Phase A (slash command detected):
  - Runs scripts/todo/<command>.py to get the step list
  - Writes todos to Claude Code's official todos file
  - Writes {session_id, command} to .claude/workflow-{session_id}.json (bookmark only)
  - If /dev-overnight: also creates overnight-state.json with parsed end-time
  - Prints checklist-ready message + exact first TodoWrite call to use

Phase B (subsequent prompts, no slash command):
  - If overnight-state.json exists with future end_time: inject continuation context
  - Reads official todos file for current session
  - Injects current progress + exact next TodoWrite call template

State: only ~/.claude/todos/{sid}.json (official) + .claude/workflow-{session_id}.json (bookmark)
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_DIR = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))


def overnight_state_path() -> Path:
    """Path to the overnight session state file."""
    return PROJECT_DIR / '.claude' / 'overnight-state.json'


def extract_command_name(user_input: str) -> str:
    text = user_input.strip()
    if not text.startswith('/'):
        return ''
    parts = text.split()
    return parts[0][1:] if parts else ''


def official_todos_path(session_id: str) -> Path:
    return Path.home() / '.claude' / 'todos' / f'{session_id}-agent-{session_id}.json'


def workflow_bookmark_path(session_id: str) -> Path:
    return PROJECT_DIR / '.claude' / f'workflow-{session_id}.json'


def _strip_yaml_frontmatter(content: str) -> str:
    """Strip YAML frontmatter from markdown content."""
    if not content.startswith('---'):
        return content
    end = content.find('\n---', 3)
    if end == -1:
        return content
    return content[end + 4:].lstrip('\n')


def _try_read_spec(path: Path) -> str | None:
    """Try to read a command spec file. Returns None on failure."""
    try:
        content = path.read_text()
        return _strip_yaml_frontmatter(content).strip()
    except Exception:
        return None


def read_command_spec(cmd_name: str) -> str:
    """Read the command .md file, stripping YAML frontmatter."""
    for search_path in [
        PROJECT_DIR / '.claude' / 'commands' / f'{cmd_name}.md',
        Path.home() / '.claude' / 'commands' / f'{cmd_name}.md',
    ]:
        if not search_path.exists():
            continue
        result = _try_read_spec(search_path)
        if result is not None:
            return result
    return ''


def run_todo_script(cmd_name: str) -> list:
    todo_script = PROJECT_DIR / 'scripts' / 'todo' / f'{cmd_name}.py'
    if not todo_script.exists():
        global_todo = Path.home() / '.claude' / 'scripts' / 'todo' / f'{cmd_name}.py'
        if global_todo.exists():
            todo_script = global_todo
        else:
            return []
    result = subprocess.run(
        ['python3', str(todo_script)],
        capture_output=True, text=True, cwd=str(PROJECT_DIR)
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        return json.loads(result.stdout)
    except Exception:
        return []


def _set_first_pending_ip(todos: list) -> None:
    """Set the first pending todo to in_progress."""
    for t in todos:
        if t.get('status') == 'pending':
            t['status'] = 'in_progress'
            break


def build_next_todowrite_call(todos: list, mark_first: bool = False) -> str:
    """Generate the JSON array to pass to TodoWrite."""
    if not todos:
        return ''
    result = [t.copy() for t in todos]
    if mark_first:
        result[0]['status'] = 'in_progress'
    elif not any(t.get('status') == 'in_progress' for t in result):
        _set_first_pending_ip(result)
    return json.dumps(result, ensure_ascii=False, separators=(",", ": "))


def build_completion_template(todos: list) -> str:
    """When a step is in_progress, generate template for after."""
    result = [t.copy() for t in todos]
    idx = next(
        (i for i, t in enumerate(result) if t.get('status') == 'in_progress'),
        None,
    )
    if idx is None:
        return json.dumps(result, ensure_ascii=False, separators=(",", ": "))
    result[idx]['status'] = 'completed'
    _set_first_pending_ip(result[idx + 1:])
    return json.dumps(result, ensure_ascii=False, separators=(",", ": "))


def build_sequence_fix_call(last_todos: list) -> str:
    """For sequence violations: compute correct next state."""
    if not last_todos:
        return ''
    try:
        result = [t.copy() for t in last_todos]
        idx = next(
            (i for i, t in enumerate(result) if t.get('status') == 'in_progress'),
            None,
        )
        if idx is not None:
            result[idx]['status'] = 'completed'
            _set_first_pending_ip(result[idx + 1:])
        else:
            _set_first_pending_ip(result)
        return json.dumps(result, ensure_ascii=False, separators=(",", ": "))
    except Exception:
        return ''


def format_count_mismatch(canonical: list) -> str:
    """Format locked message for count mismatch violations."""
    return '\n'.join([
        'WORKFLOW LOCKED (count_mismatch): TodoWrite called with wrong step count.',
        f'You MUST re-call TodoWrite with ALL {len(canonical)} canonical steps.',
        'Call TodoWrite with this exact todos array:', '',
        build_next_todowrite_call(canonical, mark_first=False),
    ])


def _find_current_step(todos: list) -> str:
    """Find the content of the current in_progress step."""
    ip = next((t for t in todos if t.get('status') == 'in_progress'), None)
    return ip["content"] if ip else "current step"


def format_sequence_violation(todos: list, last_todos: list) -> str:
    """Format locked message for sequence violations."""
    if last_todos:
        current = _find_current_step(last_todos)
        fix_json = build_sequence_fix_call(last_todos)
    else:
        current = _find_current_step(todos)
        fix_json = ''
    lines = [
        'WORKFLOW LOCKED (sequence_violation): Steps skipped or out of order.',
        f'REQUIRED: complete "{current}" first, then advance ONE step.',
        'Call TodoWrite to fix the sequence.',
    ]
    if fix_json:
        lines += ['', 'Call TodoWrite with this exact todos array:', '', fix_json]
    return '\n'.join(lines)


def format_active_progress(todos: list, ack: bool) -> str:
    """Format progress message for active (non-locked) workflow."""
    total = len(todos)
    done = sum(1 for t in todos if t.get('status') == 'completed')
    ip = next((t for t in todos if t.get('status') == 'in_progress'), None)
    lines = [f'ACTIVE WORKFLOW: {done}/{total} steps completed.']
    if ip:
        lines.append(f'Currently in_progress: {ip["content"]}')
    else:
        nxt = next((t for t in todos if t.get('status') == 'pending'), None)
        if nxt:
            lines.append(f'Next step: {nxt["content"]}')
    if ack:
        return '\n'.join(lines)
    lines.append('')
    if ip:
        lines.append('Complete the work, THEN call TodoWrite with this array:')
        lines.append('')
        lines.append(build_completion_template(todos))
    else:
        lines.append('Call TodoWrite NOW with this array (pass as array, NOT string):')
        lines.append(build_next_todowrite_call(todos, mark_first=False))
    return '\n'.join(lines)


def format_progress(
    todos: list, lock_reason: str = '', canonical: list = None,
    todo_acknowledged: bool = False, last_todos: list = None,
) -> str:
    """Phase B: show current progress. Dispatches to formatters."""
    if lock_reason == 'count_mismatch' and canonical:
        return format_count_mismatch(canonical)
    if lock_reason == 'sequence_violation':
        return format_sequence_violation(todos, last_todos or [])
    return format_active_progress(todos, todo_acknowledged)


# --- Overnight helpers ---

def parse_overnight_endtime(prompt_text: str) -> str:
    """Extract HH:MM from /dev-overnight args, return ISO end time."""
    match = re.search(r'/dev-overnight\s+(.*)', prompt_text.strip())
    args = match.group(1).strip() if match else ''
    now = datetime.now()
    if not args:
        return (now + timedelta(hours=8)).isoformat()
    return _parse_time_arg(args, now)


def _parse_time_arg(args: str, now: datetime) -> str:
    """Parse a time argument string into an ISO-8601 future datetime."""
    time_match = re.match(
        r'^(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)?$', args.strip(),
    )
    if not time_match:
        return (now + timedelta(hours=8)).isoformat()
    hour = int(time_match.group(1))
    minute = int(time_match.group(2))
    ampm = time_match.group(3)
    hour = _apply_ampm(hour, ampm)
    if hour > 23 or minute > 59:
        return (now + timedelta(hours=8)).isoformat()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target.isoformat()


def _apply_ampm(hour: int, ampm: str | None) -> int:
    """Apply AM/PM modifier to hour value."""
    if not ampm:
        return hour
    ampm = ampm.upper()
    if ampm == 'PM' and hour < 12:
        return hour + 12
    if ampm == 'AM' and hour == 12:
        return 0
    return hour


def create_overnight_state(end_time_iso: str) -> bool:
    """Atomically write overnight-state.json with v3 schema."""
    state = {
        'session_id': os.environ.get('CLAUDE_SESSION_ID', 'default'),
        'end_time': end_time_iso,
        'start_time': datetime.now().isoformat(),
        'cycle_count': 0, 'issues_found': 0, 'issues_fixed': 0,
        'issues_skipped': 0, 'current_phase': 'initializing',
        'current_issue': None, 'failed_attempts': {},
        'addressed_issues': [], 'cycle_log': [],
        'worktree_path': None, 'worktree_branch': None,
        'schema_version': 3,
    }
    sp = overnight_state_path()
    tmp = sp.with_suffix('.tmp')
    try:
        sp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(state, indent=2))
        os.rename(str(tmp), str(sp))
        return True
    except Exception:
        return False


def load_overnight_state() -> dict | None:
    """Load overnight state file. Returns None if missing or corrupt."""
    sp = overnight_state_path()
    if not sp.exists():
        return None
    try:
        return json.loads(sp.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _build_worktree_instruction(state: dict) -> str:
    """Build worktree guard instruction based on state."""
    wt = state.get('worktree_path')
    if wt:
        return (
            f'CRITICAL: Worktree already exists at {wt}. '
            'DO NOT call EnterWorktree under any circumstances.'
        )
    return 'Worktree was not created yet. Call EnterWorktree in Step 1.'


def build_overnight_continuation(state: dict) -> str:
    """Build continuation context for overnight loop prompts."""
    cc = state.get('cycle_count', 0)
    phase = state.get('current_phase', 'unknown')
    log = state.get('cycle_log', [])
    last_entry = log[-1] if log else None
    last = f"Cycle {last_entry.get('cycle')}: {last_entry.get('status')}" if last_entry else 'N/A'
    cmd_spec = read_command_spec('dev-overnight')
    wt_instruction = _build_worktree_instruction(state)
    return '\n'.join([
        f'OVERNIGHT CONTINUATION - Cycle {cc + 1}', '',
        '--- COMMAND SPECIFICATION ---', '', cmd_spec, '',
        '--- CURRENT STATE ---', '',
        f'Phase: {phase} | Cycles: {cc} | Fixed: {state.get("issues_fixed", 0)}',
        f'End time: {state.get("end_time")} | Issue: {state.get("current_issue", "none")}',
        f'Last cycle: {last}', '',
        '--- CONTINUATION INSTRUCTIONS ---', '',
        'You are continuing an overnight session with FRESH context.',
        wt_instruction,
        'Loop is driven by todo completion detection -- when all 7 steps complete,',
        'the system automatically resets for a new cycle.',
        'Do NOT create state file.',
        f'Read {overnight_state_path()} and resume from phase="{phase}".',
        'Phase mapping: initializing/exploring->Step 2, selecting->Step 3,',
        'fixing->Step 4, verifying->Step 5, logging->Step 6',
    ])


def check_overnight_continuation() -> str | None:
    """Check if overnight continuation should be injected."""
    state = load_overnight_state()
    if state is None:
        return None
    et = state.get('end_time')
    if not et:
        return None
    try:
        end = datetime.fromisoformat(et)
    except (ValueError, TypeError):
        return None
    if datetime.now() >= end:
        return None
    return build_overnight_continuation(state)


# --- Main entry points ---

def read_bookmark_state(session_id: str) -> dict:
    """Read lock state and todo_acknowledged from bookmark file."""
    bookmark = workflow_bookmark_path(session_id)
    r = {
        'lock_reason': '', 'todo_acknowledged': False,
        'canonical': [], 'last_todos': [], 'command': '',
    }
    if not bookmark.exists():
        return r
    try:
        st = json.loads(bookmark.read_text())
    except Exception:
        return r
    r['lock_reason'] = st.get('lock_reason', '')
    r['todo_acknowledged'] = st.get('todo_acknowledged', False)
    r['command'] = st.get('command', '')
    if r['lock_reason'] == 'count_mismatch' and r['command']:
        r['canonical'] = run_todo_script(r['command'])
    if r['lock_reason'] == 'sequence_violation':
        r['last_todos'] = st.get('last_todos', [])
    return r


def handle_phase_b(session_id: str) -> None:
    """Phase B: inject overnight continuation and/or workflow progress."""
    overnight_ctx = check_overnight_continuation()
    if overnight_ctx:
        print(overnight_ctx)
    todos_file = official_todos_path(session_id)
    if not todos_file.exists():
        return
    try:
        todos = json.loads(todos_file.read_text())
    except Exception:
        return
    if not todos:
        return
    if all(t.get('status') == 'completed' for t in todos):
        return
    bm = read_bookmark_state(session_id)
    print(format_progress(
        todos, lock_reason=bm['lock_reason'], canonical=bm['canonical'],
        todo_acknowledged=bm['todo_acknowledged'], last_todos=bm['last_todos'],
    ))


def emit_checklist_message(cmd_name: str, todos: list) -> None:
    """Print the checklist initialization message with command spec."""
    first_call = build_next_todowrite_call(todos, mark_first=True)
    lines = [
        f'CHECKLIST PRE-INITIALIZED for /{cmd_name.upper()}:',
        f'Your workflow checklist ({len(todos)} steps) has been created.',
        '',
        'Each item: {"content": "...", "activeForm": "...", "status": "..."}',
        f'FIRST ACTION: call TodoWrite with the todos array below:',
        f'(you MUST pass ALL {len(todos)} items every TodoWrite call)',
        '',
        first_call,
    ]
    spec = read_command_spec(cmd_name)
    if spec:
        lines += ['', f'--- /{cmd_name} COMMAND SPECIFICATION ---', '', spec]
    print('\n'.join(lines))


def handle_phase_a(cmd_name: str, user_input: str, sid: str) -> None:
    """Phase A: slash command detected -- setup todos, state, inject spec."""
    todos = run_todo_script(cmd_name)
    if not todos:
        return
    tf = official_todos_path(sid)
    tf.parent.mkdir(parents=True, exist_ok=True)
    tf.write_text(json.dumps(todos, ensure_ascii=False))
    _write_bookmark(cmd_name, sid)
    if cmd_name == 'dev-overnight':
        end_time = parse_overnight_endtime(user_input)
        create_overnight_state(end_time)
    emit_checklist_message(cmd_name, todos)


def _write_bookmark(cmd_name: str, sid: str) -> None:
    """Write the workflow bookmark file."""
    bm = workflow_bookmark_path(sid)
    try:
        bm.parent.mkdir(parents=True, exist_ok=True)
        bm.write_text(json.dumps({
            'command': cmd_name, 'todo_acknowledged': False,
        }))
    except Exception:
        pass


def main():
    try:
        data = json.load(sys.stdin)
        user_input = data.get('prompt', '')
        session_id = data.get('session_id', 'default')
        cmd_name = extract_command_name(user_input)
        if not cmd_name:
            handle_phase_b(session_id)
        else:
            handle_phase_a(cmd_name, user_input, session_id)
    except Exception:
        pass
    sys.exit(0)


if __name__ == '__main__':
    main()
