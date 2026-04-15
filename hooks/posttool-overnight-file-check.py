#!/usr/bin/env python3
"""
PostToolUse:Agent Hook: Verify overnight subagent output files exist.

Fires after every Agent tool call during an overnight session.
Checks that the subagent produced its expected output files.
Prints warnings to stderr if missing. Does NOT block (exit 0 always).
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

OVERNIGHT_AGENTS = {
    'pm', 'user', 'product-owner', 'architect',
    'ui-specialist', 'ba', 'dev', 'qa',
}


def _try_load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _load_overnight_state(session_id: str):
    project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
    claude_dir = project_dir / '.claude'
    if session_id:
        exact = claude_dir / f'overnight-state-{session_id}.json'
        state = _try_load_json(exact)
        if state:
            return state, exact
    for p in sorted(claude_dir.glob('overnight-state-*.json')):
        state = _try_load_json(p)
        if state:
            return state, p
    return None, None


def _is_live(state: dict) -> bool:
    if state.get('current_phase') in ('complete', 'completed'):
        return False
    et_str = state.get('end_time', '')
    if et_str:
        try:
            et = datetime.fromisoformat(et_str)
            now = datetime.now(timezone.utc) if et.tzinfo else datetime.now()
            return now <= et
        except (ValueError, TypeError):
            pass
    return True


def _resolve_dirs(state: dict):
    project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
    sid = state.get('session_id', '')
    wt = state.get('worktree_path')
    bases = [Path(wt)] if wt else []
    bases.append(project_dir)
    sd = dd = None
    for b in bases:
        if sd is None and (b / 'docs' / 'dev' / 'overnight' / sid).is_dir():
            sd = b / 'docs' / 'dev' / 'overnight' / sid
        if dd is None and (b / 'docs' / 'dev').is_dir():
            dd = b / 'docs' / 'dev'
    return sd, dd


def _validate_json_fields(path: Path, required: list[str]) -> list[str]:
    data = _try_load_json(path)
    if data is None:
        return [f'{path.name} is not valid JSON']
    return [f'{path.name} missing "{f}"' for f in required if f not in data]


def _find_latest(d: Path, pattern: str) -> Path | None:
    matches = sorted(d.glob(pattern))
    return matches[-1] if matches else None


def _check_pm(sd, dd, st):
    if sd is None:
        return ['Session dir missing — PM should create it']
    p = _find_latest(sd, 'test-plan-*.json')
    if p is None:
        p = sd / 'test-plan.json'
        if not p.exists():
            return ['test-plan*.json not found in session dir']
    return _validate_json_fields(p, ['plan_id', 'agent_assignments'])


def _check_specialist(agent, sd, dd, st):
    if sd is None:
        return ['Session directory missing']
    p = _find_latest(sd, f'{agent}-report*.json')
    if p is None:
        return [f'{agent}-report*.json not found in session dir']
    required = ['issues', 'plan_id']
    if agent == 'user':
        required.append('core_flow_completed')
    return _validate_json_fields(p, required)


def _check_ba(sd, dd, st):
    if dd is None:
        return ['docs/dev/ missing']
    issues = []
    if not list(dd.glob('ba-spec-*.md')):
        issues.append('ba-spec-*.md not found')
    if not list(dd.glob('context-*.json')):
        issues.append('context-*.json not found')
    return issues


def _check_dev(sd, dd, st):
    if dd is None:
        return ['docs/dev/ missing']
    p = _find_latest(dd, 'dev-report-*.json')
    if p is None:
        return ['dev-report-*.json not found']
    data = _try_load_json(p)
    if data is None:
        return [f'{p.name} not valid JSON']
    dev = data.get('dev', {})
    if not dev.get('status'):
        return [f'{p.name} missing dev.status']
    return []


def _check_qa(sd, dd, st):
    if dd is None:
        return ['docs/dev/ missing']
    p = _find_latest(dd, 'qa-report-*.json')
    if p is None:
        return ['qa-report-*.json not found']
    data = _try_load_json(p)
    if data is None:
        return [f'{p.name} not valid JSON']
    if not data.get('qa', {}).get('status'):
        return [f'{p.name} missing qa.status']
    return []


DISPATCH = {
    'pm': _check_pm,
    'user': lambda s, d, t: _check_specialist('user', s, d, t),
    'product-owner': lambda s, d, t: _check_specialist('product-owner', s, d, t),
    'architect': lambda s, d, t: _check_specialist('architect', s, d, t),
    'ui-specialist': lambda s, d, t: _check_specialist('ui-specialist', s, d, t),
    'ba': _check_ba,
    'dev': _check_dev,
    'qa': _check_qa,
}


def _emit_warning(agent_type: str, state: dict, missing: list[str]):
    sid = state.get('session_id', '?')
    cycle = state.get('cycle_count', 0)
    sys.stderr.write(
        f'\nOVERNIGHT FILE CHECK WARNING: {agent_type} '
        f'(session={sid}, cycle={cycle})\n'
    )
    for item in missing:
        sys.stderr.write(f'  - {item}\n')
    sys.stderr.write('Investigate before proceeding.\n\n')


def _run_check(data: dict) -> None:
    agent_type = data.get('tool_input', {}).get('subagent_type', '')
    if agent_type not in OVERNIGHT_AGENTS:
        return

    session_id = data.get('session_id', '')
    state, _ = _load_overnight_state(session_id)
    if state is None or not _is_live(state):
        return

    sd, dd = _resolve_dirs(state)
    checker = DISPATCH.get(agent_type)
    if not checker:
        return

    missing = checker(sd, dd, state)
    if not missing:
        print(f'OVERNIGHT FILE CHECK: {agent_type} output OK.')
        return

    _emit_warning(agent_type, state, missing)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    _run_check(data)
    sys.exit(0)


if __name__ == '__main__':
    main()
