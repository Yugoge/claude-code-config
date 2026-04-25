#!/usr/bin/env python3
"""
PreToolUse Hook: Overnight session file modification guard.

Activation: Session-specific — only the session owning an overnight state file
is subject to worktree enforcement. Global security checks (hooks/state
protection) apply when any overnight session is active.

Enforcement layers:
  1. Global: Block modifications to .claude/hooks/ and overnight-state files.
  2. Session: Block file writes where path lacks "worktree" string.
  3. Session: Block file writes outside the worktree realpath boundary.

Exit codes:
  0: Allow tool use
  2: Block tool use
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _end_time_passed(end_time_str: str) -> bool:
    """Return True when the ISO end_time has passed (mixed naive/aware)."""
    if not end_time_str:
        return False
    try:
        end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
    except (ValueError, OSError):
        return False
    if end_time.tzinfo is None:
        return datetime.now() > end_time
    return datetime.now(timezone.utc) > end_time


def _is_session_live(state: dict) -> bool:
    """Check if session is still live (not complete and end_time not passed)."""
    phase = state.get("current_phase", "")
    if phase in ("complete", "completed"):
        return False
    if _end_time_passed(state.get("end_time", "")):
        return False
    return True


def _cleanup_expired_state(sf: Path, state: dict) -> None:
    """No-op retained for call-site compatibility.

    Changed 2026-04-21: previously unlinked expired overnight-state files;
    now retains them on disk as post-mortem evidence. Enforcement naturally
    stands down because `_is_session_live()` already returns False once the
    end_time has passed.
    """
    return


def _file_age_seconds(sf: Path) -> float:
    """Return seconds since sf was last modified, or 0.0 on OSError."""
    try:
        return time.time() - sf.stat().st_mtime
    except OSError:
        return 0.0


def _is_orphaned_state(sf: Path, state: dict) -> bool:
    """Detect orphaned state: appears live but has no backing session."""
    wt = state.get('worktree_path')
    if wt and not Path(wt).is_dir():
        return True
    if wt:
        return False
    return _file_age_seconds(sf) > 7200


def _load_state(sf: Path) -> dict | None:
    """Read and JSON-parse a state file; return None on any failure."""
    try:
        if sf.stat().st_size == 0:
            return None
        return json.loads(sf.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _extract_live_worktree_path(sf: Path) -> str:
    """Return worktree_path from a live, non-orphaned state file; else empty."""
    state = _load_state(sf)
    if state is None:
        return ""
    if not _is_session_live(state):
        return ""
    return state.get("worktree_path", "") or ""


def _get_active_worktree_paths() -> list[str]:
    """Return worktree_paths from all live overnight sessions."""
    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    state_files = list((project_dir / ".claude").glob("overnight-state-*.json"))
    paths = []
    for sf in state_files:
        wt = _extract_live_worktree_path(sf)
        if wt:
            paths.append(wt)
    return paths


def _is_path_exempt(file_path: str) -> bool:
    """Check if path is exempt from overnight worktree restrictions (/tmp, /dev/null)."""
    abs_path = os.path.realpath(os.path.abspath(file_path))
    if abs_path == "/dev/null":
        return True
    return abs_path.startswith("/tmp/") or abs_path == "/tmp"


def _is_path_allowed_during_overnight(file_path: str, worktree_paths: list[str]) -> bool:
    """Check if a file path is allowed during overnight (inside worktree or /tmp)."""
    if _is_path_exempt(file_path):
        return True
    abs_path = os.path.realpath(os.path.abspath(file_path))
    for wt in worktree_paths:
        abs_wt = os.path.realpath(os.path.abspath(wt))
        if abs_path.startswith(abs_wt + os.sep) or abs_path == abs_wt:
            return True
    return False


def _block_global_worktree(tool_name: str, target: str, worktree_paths: list[str]) -> None:
    """Emit the shared OVERNIGHT WORKTREE ENFORCEMENT block message."""
    allowed = ", ".join(worktree_paths)
    _block(
        '\nOVERNIGHT WORKTREE ENFORCEMENT: All writes must target '
        'the overnight worktree during active sessions.\n'
        f'Allowed worktrees: {allowed}\n'
        f'Attempted: {tool_name} to {target}\n'
    )


def _enforce_write_edit_all_sessions(tool_name: str, tool_input: dict, worktree_paths: list[str]) -> None:
    """Block Write/Edit outside active overnight worktrees for all sessions."""
    if tool_name not in ('Write', 'Edit'):
        return
    fp = tool_input.get('file_path', '')
    if not fp:
        return
    if _is_path_allowed_during_overnight(fp, worktree_paths):
        return
    _block_global_worktree(tool_name, fp, worktree_paths)


def _enforce_bash_all_sessions(tool_name: str, tool_input: dict, worktree_paths: list[str]) -> None:
    """Block Bash writes outside active overnight worktrees for all sessions."""
    if tool_name != 'Bash':
        return
    command = tool_input.get('command', '')
    # Allow docker compose build/up -- QA needs to rebuild containers
    if _is_docker_compose_safe(command):
        return
    for path in _extract_bash_write_paths(command):
        if not _is_path_allowed_during_overnight(path, worktree_paths):
            _block_global_worktree('Bash', path, worktree_paths)


def apply_global_worktree_enforcement(tool_name: str, tool_input: dict, worktree_paths: list[str]) -> None:
    """Block ALL sessions from writing outside active overnight worktrees.

    This catches subagents that have different session_ids from the
    parent overnight agent but should still be confined to the worktree.
    """
    if not worktree_paths:
        return
    _enforce_write_edit_all_sessions(tool_name, tool_input, worktree_paths)
    _enforce_bash_all_sessions(tool_name, tool_input, worktree_paths)


def _any_live_state(sf: Path) -> bool:
    """Return True if sf describes a live, non-orphaned overnight session.

    Calls `_cleanup_expired_state` for expired/orphaned entries (now a
    no-op per 2026-04-21) to keep the legacy call graph intact.
    """
    state = _load_state(sf)
    if state is None:
        return False
    if not _is_session_live(state):
        _cleanup_expired_state(sf, state)
        return False
    if _is_orphaned_state(sf, state):
        _cleanup_expired_state(sf, state)
        return False
    return True


def is_overnight_active() -> bool:
    """Check if any overnight session is still live."""
    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    state_files = list((project_dir / ".claude").glob("overnight-state-*.json"))
    if not state_files:
        return False
    return any(_any_live_state(sf) for sf in state_files)


def get_overnight_state_for_session(project_dir: Path, session_id: str) -> dict | None:
    """Load overnight state file for the specific session."""
    if not session_id:
        return None
    state_path = project_dir / '.claude' / f'overnight-state-{session_id}.json'
    if not state_path.exists():
        return None
    try:
        return json.loads(state_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def is_hooks_path(file_path: str) -> bool:
    """Check if a file path targets the .claude/hooks/ directory."""
    normalized = file_path.replace('\\', '/')
    return '.claude/hooks/' in normalized or '.claude/hooks\\' in normalized


def is_commands_path(file_path: str) -> bool:
    """Check if a file path targets the .claude/commands/ directory.

    Mirrors `is_hooks_path()` structure (R4.1, spec-20260424-233926 §5.2.4).
    Added 2026-04-25 to close the gap that allowed b5d447e-style sweep
    commits to silently rewrite slash-command files during overnight
    sessions.
    """
    normalized = file_path.replace('\\', '/')
    return '.claude/commands/' in normalized or '.claude/commands\\' in normalized


def is_state_file_path(file_path: str) -> bool:
    """Check if a file path targets an overnight state file."""
    normalized = file_path.replace('\\', '/')
    return 'overnight-state-' in normalized and normalized.endswith('.json')


def is_outside_worktree(file_path: str, worktree_path: str) -> bool:
    """Check if a file path is outside the worktree directory."""
    abs_file = os.path.realpath(os.path.abspath(file_path))
    abs_wt = os.path.realpath(os.path.abspath(worktree_path))
    return not abs_file.startswith(abs_wt + os.sep) and abs_file != abs_wt


def path_outside_session_worktree(file_path: str, worktree_path: str) -> bool:
    """Check if file_path is outside the session worktree_path.

    Uses realpath comparison instead of naive 'worktree' substring matching.
    Falls back to legacy string check if worktree_path is not available.
    """
    if not worktree_path:
        return 'worktree' not in file_path.lower()
    abs_file = os.path.realpath(os.path.abspath(file_path))
    abs_wt = os.path.realpath(os.path.abspath(worktree_path))
    return not abs_file.startswith(abs_wt + os.sep) and abs_file != abs_wt


def _matches_any(command: str, patterns: list[str]) -> bool:
    """Return True if command matches any regex pattern."""
    return any(re.search(p, command) for p in patterns)


def check_bash_targets_state(command: str) -> bool:
    """Check if bash command modifies/deletes overnight state files."""
    # Whitelist: update-overnight-state.sh is the sanctioned state mutation tool
    if 'update-overnight-state.sh' in command:
        return False
    return _matches_any(command, [
        r'rm\s+.*overnight-state-',
        r'rm\s+-f\s+.*overnight-state-',
        r'rm\s+-rf\s+.*overnight-state-',
        r'>\s*.*overnight-state-',
        r'>>\s*.*overnight-state-',
        r'mv\s+.*overnight-state-',
        r'cp\s+.*overnight-state-.*\.json\s',
        r'echo\s+.*>\s*.*overnight-state-',
        r'cat\s+.*>\s*.*overnight-state-',
        r'tee\s+.*overnight-state-',
    ])


def check_bash_targets_hooks(command: str) -> bool:
    """Check if a bash command writes to .claude/hooks/ directory."""
    return _matches_any(command, [
        r'(?:echo|printf)\s+.*>\s*.*\.claude/hooks/',
        r'cat\s+.*>\s*.*\.claude/hooks/',
        r'cp\s+.*\.claude/hooks/',
        r'mv\s+.*\.claude/hooks/',
        r'tee\s+.*\.claude/hooks/',
        r'>\s*.*\.claude/hooks/',
        r'>>\s*.*\.claude/hooks/',
    ])


def check_bash_targets_commands(command: str) -> bool:
    r"""Check if a bash command writes to .claude/commands/ directory.

    Mirrors `check_bash_targets_hooks()` (R4.1, spec-20260424-233926 §5.2.4).
    Pattern matches `\.claude/commands/[A-Za-z0-9_.-]+\.md` reachable via
    echo/printf/cat/cp/mv/tee/>/>> redirects.
    """
    return _matches_any(command, [
        r'(?:echo|printf)\s+.*>\s*.*\.claude/commands/',
        r'cat\s+.*>\s*.*\.claude/commands/',
        r'cp\s+.*\.claude/commands/',
        r'mv\s+.*\.claude/commands/',
        r'tee\s+.*\.claude/commands/',
        r'>\s*.*\.claude/commands/',
        r'>>\s*.*\.claude/commands/',
    ])


def _block(message: str) -> None:
    """Write message to stderr and exit 2."""
    sys.stderr.write(message)
    sys.exit(2)


def _check_write_edit_security(tool_name: str, file_path: str) -> None:
    """Block Write/Edit to hooks, commands, or state files during overnight."""
    if is_hooks_path(file_path):
        _block(
            '\nOVERNIGHT HOOK PROTECTION: Modifying .claude/hooks/ '
            'is blocked during overnight sessions.\n'
            f'Blocked: {tool_name} to {file_path}\n'
        )
    if is_commands_path(file_path):
        _block(
            '\nOVERNIGHT COMMANDS PROTECTION: Modifying .claude/commands/ '
            'is blocked during overnight sessions (R4.1; closes the gap '
            'that allowed b5d447e-style sweep commits to silently rewrite '
            'slash-command files).\n'
            f'Blocked: {tool_name} to {file_path}\n'
        )
    if is_state_file_path(file_path):
        _block(
            '\nOVERNIGHT STATE PROTECTION: Direct modification of '
            'overnight-state files is blocked.\n'
            f'Blocked: {tool_name} to {file_path}\n'
        )


def _check_bash_security(command: str) -> None:
    """Block Bash commands targeting hooks, commands, or state files."""
    if 'update-overnight-state.sh' in command:
        return  # Sanctioned state update tool
    if check_bash_targets_hooks(command):
        _block(
            '\nOVERNIGHT HOOK PROTECTION: Writing to .claude/hooks/ '
            'via Bash is blocked during overnight sessions.\n'
        )
    if check_bash_targets_commands(command):
        _block(
            '\nOVERNIGHT COMMANDS PROTECTION: Writing to .claude/commands/ '
            'via Bash is blocked during overnight sessions (R4.1; references '
            'b5d447e style regression).\n'
        )
    if check_bash_targets_state(command):
        _block(
            '\nOVERNIGHT STATE PROTECTION: Modifying or deleting '
            'overnight-state-*.json via Bash is blocked.\n'
            'The state file can only be removed after end-time expires.\n'
        )


def apply_global_security_checks(tool_name: str, tool_input: dict) -> None:
    """Block hooks/state modifications for ALL sessions during any overnight."""
    if tool_name in ('Write', 'Edit'):
        _check_write_edit_security(tool_name, tool_input.get('file_path', ''))
    if tool_name == 'Bash':
        _check_bash_security(tool_input.get('command', ''))


def _is_docker_compose_safe(command: str) -> bool:
    """Check if command is a safe docker compose build/up (not down/restart)."""
    return bool(re.search(r'docker[\s-]compose\s+(build|up)', command))


def _extract_bash_write_paths(command: str) -> list[str]:
    """Extract file paths from common Bash write patterns."""
    paths = []
    # Redirect: > /path, >> /path  (skip fd redirects like 2>/dev/null)
    for m in re.finditer(r'(?<!\d)>{1,2}\s*(/[^\s;|&]+)', command):
        paths.append(m.group(1))
    # tee /path
    for m in re.finditer(r'tee\s+(?:-a\s+)?(/[^\s;|&]+)', command):
        paths.append(m.group(1))
    # cp source /dest, mv source /dest
    for m in re.finditer(r'(?:cp|mv)\s+\S+\s+(/[^\s;|&]+)', command):
        paths.append(m.group(1))
    # sed -i ... /path
    for m in re.finditer(r'sed\s+-i[^\s]*\s+\S+\s+(/[^\s;|&]+)', command):
        paths.append(m.group(1))
    return paths


def _block_worktree_string_violation(tool_name: str, path: str) -> None:
    """Block operation on path lacking 'worktree' string."""
    _block(
        f'\nWORKTREE STRING ENFORCEMENT: Path does not contain "worktree".\n'
        f'Overnight sessions can only modify files in worktree directories.\n'
        f'Attempted: {tool_name} to {path}\n'
    )


def _block_worktree_violation(tool_name: str, path: str, wt: str) -> None:
    """Block operation outside worktree with exit 2."""
    _block(
        f'\nWORKTREE ENFORCEMENT: File is outside the overnight worktree.\n'
        f'Overnight changes MUST stay inside: {wt}\n'
        f'Attempted: {tool_name} to {path}\n'
        f'Use absolute paths inside the worktree.\n'
    )


def _enforce_write_edit_worktree(tool_name: str, tool_input: dict, wt: str) -> None:
    """Check Write/Edit file_path against worktree boundary."""
    file_path = tool_input.get('file_path', '')
    if file_path and not _is_path_exempt(file_path) and is_outside_worktree(file_path, wt):
        _block_worktree_violation(tool_name, file_path, wt)


def _enforce_bash_worktree(command: str, wt: str) -> None:
    """Check Bash write targets against worktree boundary."""
    for path in _extract_bash_write_paths(command):
        if not _is_path_exempt(path) and is_outside_worktree(path, wt):
            _block_worktree_violation('Bash', path, wt)


def _check_write_edit_string(tool_name: str, tool_input: dict, worktree_path: str) -> None:
    """Emit string-fallback block for Write/Edit outside session worktree."""
    file_path = tool_input.get('file_path', '')
    if not file_path or _is_path_exempt(file_path):
        return
    if path_outside_session_worktree(file_path, worktree_path):
        _block_worktree_string_violation(tool_name, file_path)


def _check_bash_string(tool_input: dict, worktree_path: str) -> None:
    """Emit string-fallback block for Bash writes outside session worktree."""
    command = tool_input.get('command', '')
    for path in _extract_bash_write_paths(command):
        if _is_path_exempt(path):
            continue
        if path_outside_session_worktree(path, worktree_path):
            _block_worktree_string_violation('Bash', path)


def apply_worktree_string_check(tool_name: str, tool_input: dict, worktree_path: str = '') -> None:
    """Block when overnight session writes outside worktree_path (or lacks 'worktree' string as fallback)."""
    if tool_name in ('Write', 'Edit'):
        _check_write_edit_string(tool_name, tool_input, worktree_path)
    if tool_name == 'Bash':
        _check_bash_string(tool_input, worktree_path)


def apply_worktree_enforcement(tool_name: str, tool_input: dict, wt: str) -> None:
    """Hard-block when overnight session writes outside its worktree."""
    if tool_name in ('Write', 'Edit'):
        _enforce_write_edit_worktree(tool_name, tool_input, wt)
    if tool_name == 'Bash':
        _enforce_bash_worktree(tool_input.get('command', ''), wt)


def _parse_hook_input() -> tuple[str, dict, str]:
    """Read the PreToolUse JSON from stdin; exit 0 on parse failure."""
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    return (
        data.get('tool_name', ''),
        data.get('tool_input', {}),
        data.get('session_id', ''),
    )


def _is_cwd_in_worktree(worktree_paths: list[str]) -> bool:
    """Return True if cwd realpath is inside any active overnight worktree."""
    cwd_real = os.path.realpath(os.getcwd())
    return any(cwd_real.startswith(os.path.realpath(wt)) for wt in worktree_paths)


def _apply_session_enforcement(state: dict, tool_name: str, tool_input: dict) -> None:
    """Apply session-specific worktree string + realpath enforcement."""
    wt = state.get('worktree_path', '')
    apply_worktree_string_check(tool_name, tool_input, wt)
    if wt:
        apply_worktree_enforcement(tool_name, tool_input, wt)


def main():
    """Entry point: apply global + session-specific overnight enforcement."""
    tool_name, tool_input, session_id = _parse_hook_input()

    if is_overnight_active():
        apply_global_security_checks(tool_name, tool_input)

    project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
    state = get_overnight_state_for_session(project_dir, session_id) if session_id else None
    is_overnight_session = state is not None and _is_session_live(state)

    wt_paths = _get_active_worktree_paths()
    is_in_worktree = _is_cwd_in_worktree(wt_paths)

    if not is_overnight_session and not is_in_worktree:
        sys.exit(0)

    if wt_paths:
        apply_global_worktree_enforcement(tool_name, tool_input, wt_paths)

    if is_overnight_session:
        _apply_session_enforcement(state, tool_name, tool_input)

    sys.exit(0)


if __name__ == '__main__':
    main()
