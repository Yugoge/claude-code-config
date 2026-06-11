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

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.bash_write_targets import (  # noqa: E402
    command_without_heredoc_bodies,
    extract_bash_write_paths,
)

try:  # T2.4: optional contract runtime + agent resolver for self_repair grant.
    from lib import contract_runtime as _contract_runtime  # noqa: E402
    from lib.agent_resolver import resolve_agent_type as _resolve_agent_type  # noqa: E402
    from lib.agent_resolver import resolve_dev_registry_entry as _resolve_dev_registry_entry  # noqa: E402
except Exception:  # pragma: no cover - fail-soft when modules missing
    _contract_runtime = None  # type: ignore[assignment]
    _resolve_agent_type = None  # type: ignore[assignment]
    _resolve_dev_registry_entry = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# T2.4: Contract-driven self-repair grant (BUG-B-Q0E-CONTRACT-SELF-REPAIR-GAP)
# ---------------------------------------------------------------------------

SELF_REPAIR_AUDIT_LOG = Path('/root/.claude/logs/overnight-self-repair.jsonl')


def _self_repair_block(contract: dict | None) -> dict | None:
    """Return cycle-contract.self_repair object iff enabled, else None."""
    if not isinstance(contract, dict):
        return None
    sr = contract.get('self_repair')
    if not isinstance(sr, dict):
        return None
    if not sr.get('enabled', False):
        return None
    return sr


def _expires_passed(expires_at: str) -> bool:
    """True when ISO-8601 expires_at has passed; True on parse failure (fail-closed)."""
    if not expires_at or not isinstance(expires_at, str):
        return True
    try:
        dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return True
    if dt.tzinfo is None:
        return datetime.now() > dt
    return datetime.now(timezone.utc) > dt


def _path_under_prefix(target: str, prefix: str) -> bool:
    """Boundary-aware prefix match using realpath comparison."""
    try:
        abs_target = os.path.realpath(os.path.abspath(target))
        abs_prefix = os.path.realpath(os.path.abspath(prefix))
    except (OSError, ValueError):
        return False
    if abs_target == abs_prefix:
        return True
    return abs_target.startswith(abs_prefix.rstrip('/') + os.sep)
_HARNESS_STATE_DIR_PREFIXES = (
    '.claude/dev-registry/',
    '.claude/specs/',
    '.claude/todos/',
)
_HARNESS_STATE_FILE_PFX_REL = ('.claude/overnight-state-',)


def _harness_state_dirs() -> list[str]:
    """Resolved directory-prefix list (M6: 3 project dirs + project file pfx = harness-state set).

    M6/M7/M8/M9 harness-fixes 20260428: worktree-boundary exemption for
    harness-state path prefixes, gated on falsy stdin agent_id
    (orchestrator-only). Reuses _path_under_prefix for symlink-realpath
    symmetry. Inserted at worktree-boundary layer only;
    apply_global_security_checks line 652 is untouched per arch-6.
    Direct overnight-state-*.json writes remain blocked by is_state_file_path.
    """
    proj = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
    home = Path.home()
    out = []
    for p in _HARNESS_STATE_DIR_PREFIXES:
        out.append(str(proj / p))
        out.append(str(home / p))
    return out


def _harness_state_file_pfx_resolved() -> list[str]:
    """Realpath-resolved filename prefixes (matched via startswith)."""
    proj = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
    return [os.path.realpath(str(proj / p)) for p in _HARNESS_STATE_FILE_PFX_REL]


def _harness_dir_match(target: str) -> bool:
    """True iff target falls under a harness-state directory prefix."""
    return any(_path_under_prefix(target, pfx) for pfx in _harness_state_dirs())


def _harness_file_match(target: str) -> bool:
    """True iff target's realpath starts with a harness-state filename prefix."""
    try:
        abs_target = os.path.realpath(os.path.abspath(target))
    except (OSError, ValueError):
        return False
    return any(abs_target.startswith(pfx) for pfx in _harness_state_file_pfx_resolved())


def _is_harness_state_path(target: str) -> bool:
    """True iff target matches any harness-state prefix (M9 dir + file pfx)."""
    return _harness_dir_match(target) or _harness_file_match(target)


def _is_orchestrator_actor() -> bool:
    """M8: True iff stdin payload's agent_id is falsy (orchestrator/main-agent)."""
    payload = _REQUEST_CTX.get('payload') or {}
    return not payload.get('agent_id')


def _is_harness_state_exempt(target: str) -> bool:
    """Combined M6+M8+M9 gate: 5-prefix match AND orchestrator actor."""
    if not target:
        return False
    if not _is_orchestrator_actor():
        return False
    return _is_harness_state_path(target)


def _payload_pipeline_id(payload: dict) -> str:
    """Extract pipeline_id from payload (tool_input direct, then prompt regex)."""
    if not isinstance(payload, dict):
        return ''
    ti = payload.get('tool_input', {}) or {}
    pid = ti.get('pipeline_id') or ti.get('pipelineId')
    if isinstance(pid, str) and pid:
        return pid
    prompt = ti.get('prompt', '')
    if not isinstance(prompt, str):
        return ''
    m = re.search(r'pipeline[_-]?id[\s:=]+["\']?([A-Za-z0-9_.\-]+)', prompt)
    return m.group(1) if m else ''


def _try_resolve_agent_type(payload: dict) -> str:
    """Call lib.agent_resolver.resolve_agent_type; return '' on any failure."""
    if _resolve_agent_type is None or not isinstance(payload, dict):
        return ''
    try:
        role = _resolve_agent_type(payload)
    except Exception:
        return ''
    return role if isinstance(role, str) else ''


def _resolve_role(payload: dict) -> str:
    """Resolve acting subagent role: agent_resolver lib first, env var fallback."""
    role = _try_resolve_agent_type(payload)
    if role:
        return role
    env_role = os.environ.get('CLAUDE_AGENT_TYPE', '')
    return env_role if isinstance(env_role, str) else ''


def _load_active_contract(state: dict) -> dict | None:
    """Load cycle-contract for the active overnight session, if available."""
    if _contract_runtime is None or not isinstance(state, dict):
        return None
    sid = state.get('session_id') or state.get('sid') or ''
    cycle_id = state.get('cycle_id') or state.get('current_cycle')
    if not sid or cycle_id is None:
        return None
    try:
        cid_int = int(cycle_id)
    except (TypeError, ValueError):
        return None
    try:
        return _contract_runtime.load_contract(sid, cid_int)
    except Exception:
        return None


def _check_role(role: str, sr: dict) -> tuple[bool, str]:
    """Sub-check: role membership in allowed_roles."""
    allowed = sr.get('allowed_roles') or ['dev']
    return (role in allowed, f'role_not_allowed:{role}')


def _check_target_prefix(target: str, sr: dict) -> tuple[bool, str]:
    """Sub-check: target startswith one of allowed_path_prefixes."""
    prefixes = sr.get('allowed_path_prefixes') or []
    if not prefixes:
        return False, 'no_prefixes_declared'
    ok = any(_path_under_prefix(target, p) for p in prefixes)
    return ok, 'target_outside_prefixes'


def _check_pipeline(pipeline_id: str, sr: dict) -> tuple[bool, str]:
    """Sub-check: pipeline_id matches when declared."""
    declared = sr.get('pipeline_id')
    if not isinstance(declared, str) or not declared:
        return True, 'pipeline_unconstrained'
    return (pipeline_id == declared, f'pipeline_mismatch:{pipeline_id}!={declared}')


def _grant_decision_for(target: str, role: str, pipeline_id: str, sr: dict) -> tuple[bool, str]:
    """Pure decision: combine role/prefix/pipeline/expiry sub-checks."""
    ok, reason = _check_role(role, sr)
    if not ok:
        return False, reason
    ok, reason = _check_target_prefix(target, sr)
    if not ok:
        return False, reason
    ok, reason = _check_pipeline(pipeline_id, sr)
    if not ok:
        return False, reason
    if _expires_passed(sr.get('expires_at', '')):
        return False, 'expired'
    return True, 'granted'


def _hash_tool_input(payload: dict) -> str:
    """SHA-256 (truncated) of tool_input dict for audit traceability."""
    ti = payload.get('tool_input', {}) if isinstance(payload, dict) else {}
    if not ti:
        return ''
    raw = json.dumps(ti, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode('utf-8', errors='replace')).hexdigest()[:16]


def _build_audit_row(state: dict, payload: dict, role: str, target: str, sr: dict, reason: str) -> dict:
    """Construct the JSONL audit row dict."""
    sid = state.get('session_id') or payload.get('session_id') or ''
    cycle_id = state.get('cycle_id') or state.get('current_cycle')
    return {
        'ts': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
        'session_id': sid,
        'cycle_id': cycle_id,
        'role': role,
        'pipeline_id': _payload_pipeline_id(payload),
        'target': target,
        'tool_name': payload.get('tool_name', '') if isinstance(payload, dict) else '',
        'command_or_input_hash': _hash_tool_input(payload),
        'decision': 'grant',
        'decision_reason': reason,
        'reason_text': sr.get('reason', ''),
        'remaining_max_files': sr.get('max_files', 50),
        'expires_at': sr.get('expires_at', ''),
    }


def _persist_audit_row(row: dict) -> bool:
    """Append a single JSONL row to the audit log; True iff fsync succeeded."""
    try:
        SELF_REPAIR_AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with SELF_REPAIR_AUDIT_LOG.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(row, default=str) + '\n')
            fh.flush()
            os.fsync(fh.fileno())
        return True
    except OSError:
        return False


def _audit_grant(state: dict, payload: dict, role: str, target: str, sr: dict, reason: str) -> bool:
    """Build + persist audit row. True iff fully persisted."""
    row = _build_audit_row(state, payload, role, target, sr, reason)
    return _persist_audit_row(row)


def is_self_repair_allowed(target: str, state: dict, payload: dict) -> bool:
    """True iff cycle-contract grants self_repair for (target, role, pipeline).

    Fail-closed: missing contract / disabled grant / role mismatch /
    target outside prefixes / pipeline mismatch / expired / audit append
    failure (when audit_required) all collapse to False.
    """
    contract = _load_active_contract(state)
    sr = _self_repair_block(contract)
    if sr is None:
        return False
    role = _resolve_role(payload)
    pipeline_id = _payload_pipeline_id(payload)
    granted, reason = _grant_decision_for(target, role, pipeline_id, sr)
    if not granted:
        return False
    audit_required = sr.get('audit_required', True)
    audit_ok = _audit_grant(state, payload, role, target, sr, reason)
    if audit_required and not audit_ok:
        return False
    return True


# Module-level request context; populated by main() so existing helper
# call sites (security checks, worktree enforcement) can consult the
# self_repair grant without changing their signatures. Empty dict = no
# context (e.g. unit tests calling helpers directly).
_REQUEST_CTX: dict = {}


def _set_request_ctx(state: dict | None, payload: dict | None) -> None:
    """Populate the per-request context for grant-aware block sites."""
    _REQUEST_CTX['state'] = state or {}
    _REQUEST_CTX['payload'] = payload or {}


def _grant_skips_block(target: str) -> bool:
    """Helper used by block sites: True iff self_repair grants this target."""
    if not _REQUEST_CTX:
        return False
    state = _REQUEST_CTX.get('state') or {}
    payload = _REQUEST_CTX.get('payload') or {}
    if not state:
        return False
    return is_self_repair_allowed(target, state, payload)


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
    """Check if the overnight session is still live (M9 liveness fix).

    Liveness is keyed on the isolation window (`isolation_active_until`, falling
    back to `end_time`) and an explicit `isolation_released_at` — NOT on
    `current_phase`. Previously `current_phase in (complete, completed)` stood
    isolation down, which let a state write release isolation prematurely
    (round-3 §5). `current_phase=complete` may be stored but MUST NOT release
    isolation; only the user `/stop` path sets `isolation_released_at`.
    """
    if state.get("isolation_released_at"):
        return False
    window = state.get("isolation_active_until") or state.get("end_time", "")
    if _end_time_passed(window):
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
    if _is_path_exempt(file_path) or _is_harness_state_exempt(file_path):
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
    """Block Write/Edit outside active overnight worktrees for all sessions (T2.4-aware)."""
    if tool_name not in ('Write', 'Edit', 'MultiEdit'):
        return
    fp = tool_input.get('file_path', '')
    if not fp or _is_path_allowed_during_overnight(fp, worktree_paths) or _grant_skips_block(fp):
        return
    _block_global_worktree(tool_name, fp, worktree_paths)


def _enforce_bash_all_sessions(tool_name: str, tool_input: dict, worktree_paths: list[str]) -> None:
    """Block Bash writes outside active overnight worktrees for all sessions (T2.4-aware)."""
    if tool_name != 'Bash':
        return
    command = tool_input.get('command', '')
    if _is_docker_compose_safe(command):  # docker compose build/up needed for QA
        return
    for path in _extract_bash_write_paths(command):
        if _is_path_allowed_during_overnight(path, worktree_paths) or _grant_skips_block(path):
            continue
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
    """Check if bash command modifies/deletes overnight state files.

    Heredoc payload bodies are stripped before regex matching so a
    heredoc body that merely *mentions* an overnight-state path string
    (e.g. inside a JSON document being written elsewhere) is not a false
    positive. Only the heredoc OPENER line and out-of-heredoc content
    are scanned for actual state-file write/delete idioms.
    """
    stripped = command_without_heredoc_bodies(command)
    # Whitelist: update-overnight-state.sh is the sanctioned state mutation tool
    if 'update-overnight-state.sh' in stripped:
        return False
    return _matches_any(stripped, [
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
    """Check if a bash command writes to .claude/hooks/ directory.

    Heredoc payload bodies are stripped before regex matching so a
    heredoc body that merely mentions a `.claude/hooks/` path literal
    (e.g. JSON value or documentation text) is not a false positive.
    Only real redirect/copy/move/tee targets in the heredoc OPENER or
    outside any heredoc trigger this check.
    """
    stripped = command_without_heredoc_bodies(command)
    return _matches_any(stripped, [
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

    Heredoc payload bodies are stripped before regex matching so a
    heredoc body mentioning `.claude/commands/` paths in payload content
    (documentation, JSON, etc.) is not a false positive. Only the
    opener line and non-heredoc content trigger this check.
    """
    stripped = command_without_heredoc_bodies(command)
    return _matches_any(stripped, [
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
    """Block Write/Edit to hooks, commands, or state files during overnight.

    T2.4: A contract-authorized self_repair grant short-circuits the block
    for this exact file_path. Overnight-state files are NEVER grantable
    (state-file integrity is non-negotiable).
    """
    if is_hooks_path(file_path) and not _grant_skips_block(file_path):
        _block(
            '\nOVERNIGHT HOOK PROTECTION: Modifying .claude/hooks/ '
            'is blocked during overnight sessions.\n'
            f'Blocked: {tool_name} to {file_path}\n'
        )
    if is_commands_path(file_path) and not _grant_skips_block(file_path):
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


def _all_bash_targets_granted(command: str) -> bool:
    """T2.4: True iff every extracted Bash write target is grant-authorized."""
    targets = _extract_bash_write_paths(command)
    return bool(targets) and all(_grant_skips_block(t) for t in targets)


def _maybe_block_bash(command: str, predicate, message: str, grantable: bool) -> None:
    """Run predicate; block with message unless (grantable and all targets granted)."""
    if not predicate(command):
        return
    if grantable and _all_bash_targets_granted(command):
        return
    _block(message)


def _check_bash_security(command: str) -> None:
    """Block Bash commands targeting hooks, commands, or state files (T2.4-aware)."""
    stripped = command_without_heredoc_bodies(command)
    if 'update-overnight-state.sh' in stripped:
        return
    _maybe_block_bash(command, check_bash_targets_hooks,
                      '\nOVERNIGHT HOOK PROTECTION: Writing to .claude/hooks/ '
                      'via Bash is blocked during overnight sessions.\n', True)
    _maybe_block_bash(command, check_bash_targets_commands,
                      '\nOVERNIGHT COMMANDS PROTECTION: Writing to .claude/commands/ '
                      'via Bash is blocked during overnight sessions (R4.1).\n', True)
    _maybe_block_bash(command, check_bash_targets_state,
                      '\nOVERNIGHT STATE PROTECTION: Modifying or deleting '
                      'overnight-state-*.json via Bash is blocked.\n', False)


def apply_global_security_checks(tool_name: str, tool_input: dict) -> None:
    """Block hooks/state modifications for ALL sessions during any overnight."""
    if tool_name in ('Write', 'Edit', 'MultiEdit'):
        _check_write_edit_security(tool_name, tool_input.get('file_path', ''))
    if tool_name == 'Bash':
        _check_bash_security(tool_input.get('command', ''))


def _is_docker_compose_safe(command: str) -> bool:
    """Check if command is a safe docker compose build/up (not down/restart)."""
    return bool(re.search(r'docker[\s-]compose\s+(build|up)', command))


def _extract_bash_write_paths(command: str) -> list[str]:
    """Extract file paths from common Bash write patterns.

    Thin wrapper around lib.bash_write_targets.extract_bash_write_paths
    (T2.1). The library helper strips heredoc PAYLOAD lines before
    extracting redirect/tee/cp/mv/sed-i/install targets, so a heredoc
    body that mentions paths or redirect-like syntax cannot produce
    spurious write-target hits. The OPENER line is preserved so an
    actual `cat > /protected/path << EOF` opener still surfaces its
    redirect target.
    """
    return extract_bash_write_paths(command)


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
    """Check Write/Edit file_path against worktree boundary (T2.4-aware)."""
    file_path = tool_input.get('file_path', '')
    if file_path and not _is_path_exempt(file_path) and not _is_harness_state_exempt(file_path) and is_outside_worktree(file_path, wt) and not _grant_skips_block(file_path):
        _block_worktree_violation(tool_name, file_path, wt)


def _enforce_bash_worktree(command: str, wt: str) -> None:
    """Check Bash write targets against worktree boundary (T2.4-aware)."""
    for path in _extract_bash_write_paths(command):
        if not _is_path_exempt(path) and not _is_harness_state_exempt(path) and is_outside_worktree(path, wt) and not _grant_skips_block(path):
            _block_worktree_violation('Bash', path, wt)


def _check_write_edit_string(tool_name: str, tool_input: dict, worktree_path: str) -> None:
    """Emit string-fallback block for Write/Edit outside session worktree (T2.4-aware)."""
    file_path = tool_input.get('file_path', '')
    if not file_path or _is_path_exempt(file_path) or _is_harness_state_exempt(file_path) or _grant_skips_block(file_path):
        return
    if path_outside_session_worktree(file_path, worktree_path):
        _block_worktree_string_violation(tool_name, file_path)


def _check_bash_string(tool_input: dict, worktree_path: str) -> None:
    """Emit string-fallback block for Bash writes outside session worktree (T2.4-aware)."""
    command = tool_input.get('command', '')
    for path in _extract_bash_write_paths(command):
        if _is_path_exempt(path) or _is_harness_state_exempt(path) or _grant_skips_block(path):
            continue
        if path_outside_session_worktree(path, worktree_path):
            _block_worktree_string_violation('Bash', path)


def apply_worktree_string_check(tool_name: str, tool_input: dict, worktree_path: str = '') -> None:
    """Block when overnight session writes outside worktree_path (or lacks 'worktree' string as fallback)."""
    if tool_name in ('Write', 'Edit', 'MultiEdit'):
        _check_write_edit_string(tool_name, tool_input, worktree_path)
    if tool_name == 'Bash':
        _check_bash_string(tool_input, worktree_path)


def apply_worktree_enforcement(tool_name: str, tool_input: dict, wt: str) -> None:
    """Hard-block when overnight session writes outside its worktree."""
    if tool_name in ('Write', 'Edit', 'MultiEdit'):
        _enforce_write_edit_worktree(tool_name, tool_input, wt)
    if tool_name == 'Bash':
        _enforce_bash_worktree(tool_input.get('command', ''), wt)


def _parse_hook_input() -> tuple[str, dict, str, dict]:
    """Parse PreToolUse JSON; T2.4 also returns full payload for grant resolution."""
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    return (data.get('tool_name', ''), data.get('tool_input', {}),
            data.get('session_id', ''), data)


def _payload_cwd(payload: dict) -> str:
    """M9/round-3: effective cwd = payload['cwd'] -> $PWD -> os.getcwd()."""
    if isinstance(payload, dict):
        c = payload.get('cwd')
        if isinstance(c, str) and c:
            return c
    env_pwd = os.environ.get('PWD', '')
    if env_pwd:
        return env_pwd
    return os.getcwd()


def _is_cwd_in_worktree(worktree_paths: list[str], cwd: str | None = None) -> bool:
    """C8/M9: True if the effective cwd is inside an overnight worktree."""
    base = cwd if cwd else os.getcwd()
    cwd_real = os.path.realpath(base)
    return any(_path_under_prefix(cwd_real, wt) for wt in worktree_paths)


def _resolve_child_session(payload: dict) -> dict | None:
    """M9/round-3 overnight_child: payload.agent_id -> agent-index.json
    dev_session_id -> overnight state, if that state is live + validated."""
    if not isinstance(payload, dict):
        return None
    agent_id = payload.get('agent_id')
    if not agent_id:
        return None
    project_dir = str(Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())))
    if _resolve_dev_registry_entry is None:
        return None
    try:
        entry = _resolve_dev_registry_entry(agent_id, project_dir)
    except Exception:
        return None
    if not entry:
        return None
    dev_sid = entry.get('dev_session_id')
    if not dev_sid:
        return None
    return _load_session_state(dev_sid)


def _classify_actor(payload: dict, owner_state: dict | None,
                    wt_paths: list[str], cwd: str) -> tuple[str, dict | None]:
    """Classify the actor: overnight_owner | overnight_child | worktree_context
    | normal. Returns (classification, governing_state_or_None).

    A `normal` actor (concurrent user session on main) is NOT enforced, so the
    user's concurrent main session is never false-blocked (round-3 honest
    limitation: ambiguous unregistered subagents fall back to `normal`)."""
    if owner_state is not None and _is_session_live(owner_state):
        return ('overnight_owner', owner_state)
    child_state = _resolve_child_session(payload)
    if child_state is not None and _is_session_live(child_state):
        return ('overnight_child', child_state)
    if _is_cwd_in_worktree(wt_paths, cwd):
        return ('worktree_context', None)
    return ('normal', None)


def _apply_session_enforcement(state: dict, tool_name: str, tool_input: dict) -> None:
    """Apply session-specific worktree string + realpath enforcement."""
    wt = state.get('worktree_path', '')
    apply_worktree_string_check(tool_name, tool_input, wt)
    if wt:
        apply_worktree_enforcement(tool_name, tool_input, wt)


def _load_session_state(session_id: str) -> dict | None:
    """Load overnight state for the given session_id (None if missing)."""
    project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
    return get_overnight_state_for_session(project_dir, session_id) if session_id else None


_ENV_ASSIGN_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*=')
# Command-wrappers that may precede the real git token (VECTOR-1, Cycle-3):
# `command git …`, `exec git …`, `env git …`, `nice git …`, `stdbuf … git …`,
# `nohup git …`, `time git …`, `builtin git …`. Each may itself take leading
# flags / VAR=val operands we must skip to reach the real argv[0].
_CMD_WRAPPERS = {'command', 'exec', 'env', 'nice', 'nohup', 'time',
                 'stdbuf', 'builtin', 'setsid', 'ionice'}


def _strip_leading_wrappers(toks: list[str]) -> int:
    """VECTOR-1 (Cycle-3): return the index of the real argv[0] after skipping
    any leading `VAR=val` environment assignments and command/exec wrappers
    (`command`, `exec`, `env`, `nice`, `nohup`, `time`, `stdbuf`, …). A wrapper's
    own option flags and VAR=val operands are skipped too. Returns len(toks) when
    nothing executable remains."""
    i = 0
    n = len(toks)
    while i < n:
        t = toks[i]
        if _ENV_ASSIGN_RE.match(t):
            i += 1
            continue
        base = os.path.basename(t)
        if base in _CMD_WRAPPERS:
            i += 1
            # skip the wrapper's own leading flags / VAR=val operands
            while i < n and (toks[i].startswith('-') or _ENV_ASSIGN_RE.match(toks[i])):
                i += 1
            continue
        break
    return i


def _segment_cd_target(toks: list[str]) -> str | None:
    """VECTOR-1: if a shell segment is a `cd <dir>` / `pushd <dir>` (optionally
    after leading env-assignments), return its target dir; else None. A bare
    `cd` / `cd -` / `cd ~` is treated as non-deterministic -> returns '' so the
    caller can fail closed on a subsequent HEAD-move."""
    i = 0
    while i < len(toks) and _ENV_ASSIGN_RE.match(toks[i]):
        i += 1
    if i >= len(toks):
        return None
    if os.path.basename(toks[i]) in ('cd', 'pushd'):
        j = i + 1
        # skip flags like `-P`
        while j < len(toks) and toks[j].startswith('-'):
            j += 1
        if j < len(toks):
            return toks[j].strip('\'"')
        return ''  # bare cd -> ambiguous
    return None


def _iter_git_invocations(command: str):
    """VECTOR-1 (Cycle-3): shell-aware iterator over git invocations.

    Splits `command` on shell separators IN ORDER, tracks the effective cwd
    across `cd`/`pushd` segments, strips leading `VAR=val` assignments and
    command/exec wrappers (`command`, `exec`, `env`, …) before identifying the
    git token by BASENAME, and yields one tuple per git invocation:
        (subtoks, cwd_override, cwd_ambiguous)
    where `cwd_override` is the cwd in effect for that git op when a prior `cd`
    changed it (None if unchanged from the payload cwd), and `cwd_ambiguous` is
    True when a preceding `cd` target could not be statically resolved (bare cd /
    `cd -` / `cd $VAR`) -> the caller fails closed for HEAD-moving ops."""
    # Split on shell separators while preserving order. We split on ; & | && ||.
    segs = re.split(r'(?:&&|\|\||[;&|])', command)
    cwd_override = None      # str path set by a resolvable cd; None = unchanged
    cwd_ambiguous = False    # a cd target we could not resolve statically
    for seg in segs:
        toks = seg.split()
        if not toks:
            continue
        cd_tgt = _segment_cd_target(toks)
        if cd_tgt is not None:
            if cd_tgt == '' or '$' in cd_tgt or cd_tgt == '-' or cd_tgt.startswith('~'):
                cwd_ambiguous = True
                cwd_override = None
            else:
                cwd_override = cd_tgt
                cwd_ambiguous = False
            # a `cd && git` lives in ONE segment under `&&`; the regex split
            # already separated them, so fall through to also scan for git here.
        k = _strip_leading_wrappers(toks)
        if k >= len(toks):
            continue
        first = toks[k]
        if os.path.basename(first) == 'git':
            yield (toks[k + 1:], cwd_override, cwd_ambiguous)


def _normalize_git_basename_cmds(command: str) -> list[str]:
    """Back-compat shim: return only the subtoks for each git invocation.

    Retained for any external caller / test; the shell-aware effective-cwd data
    is consumed via `_iter_git_invocations`."""
    return [subtoks for subtoks, _cwd, _amb in _iter_git_invocations(command)]


_GIT_HOOK_SUPPRESS_RE = re.compile(
    r'(-c\s+core\.hooksPath\s*=|--config-env|GIT_CONFIG_(COUNT|KEY|VALUE|GLOBAL|SYSTEM|NOSYSTEM)|'
    r'\bGIT_CONFIG\s*=|-c\s+core\.hooksPath=)', re.IGNORECASE)

# fix-2 (Cycle-2): interpreter / subprocess launchers. The 2026-06-03 incident
# vector is a python-subprocess `git -C <main> checkout other`. On git 2.43 the
# keystone does NOT fire for a symref branch-switch (codex empirically confirmed),
# so the ONLY env-independent BEFORE-block on this host is the PreTool hook-guard
# reading the OUTER Bash command string. These launchers can carry a hidden git
# main-targeting op (inline `-c`, a script file, or a heredoc).
_INTERPRETER_LAUNCHER_RE = re.compile(
    r'(?<![\w./-])(?:/[\w./-]*/)?(python3?|perl|ruby|node|nodejs|sh|bash|zsh|env)\b')

# fix-2: dangerous/mutating git subcommands that can move HEAD off master or
# write the main worktree (codex #2 main-targeting dangerous-op predicate).
_DANGEROUS_GIT_SUBCMDS = {
    'checkout', 'switch', 'reset', 'restore', 'clean', 'stash',
    'update-ref', 'symbolic-ref', 'branch', 'merge', 'rebase', 'pull',
    'cherry-pick', 'am', 'worktree',
}
# fix-2: any mention of git inside an interpreter payload (covers /usr/bin/git,
# /usr/lib/git-core/git, `command git`, `env … git`, the literal `'git'`).
_GIT_TOKEN_RE = re.compile(r'(?<![\w./-])(?:/[\w./-]*/)?git\b')
_DANGEROUS_GIT_OP_RE = re.compile(
    r'\b(checkout|switch|reset|restore|clean|stash|update-ref|symbolic-ref|'
    r'branch|merge|rebase|pull|cherry-pick|am|worktree)\b')


def _path_targets_main(tgt_dir: str, main_real: str) -> bool:
    """fix-3: True iff tgt_dir resolves UNDER main_root but OUTSIDE every active
    overnight worktree. Replaces the exact-root equality (which let a main-subdir
    target evade). A worktree physically lives under .claude/worktrees but is an
    independent checkout, so it is NOT main-targeting."""
    if not main_real or not tgt_dir:
        return False
    if not _path_under_prefix(tgt_dir, main_real):
        return False
    for wt in _get_active_worktree_paths():
        if _path_under_prefix(tgt_dir, wt):
            return False
    return True


def _gitdir_into_main(command: str, main_real: str, main_git_dir: str) -> bool:
    """fix-3/codex#6: True iff --git-dir / GIT_DIR / GIT_COMMON_DIR redirect into
    the main repo's git dir (a way to operate on main without a -C)."""
    if not main_real:
        return False
    main_gd = os.path.realpath(main_git_dir) if main_git_dir else os.path.join(main_real, '.git')
    candidates = []
    for m in re.finditer(r'--git-dir(?:=|\s+)(\S+)', command):
        candidates.append(m.group(1))
    for m in re.finditer(r'GIT_DIR=(\S+)', command):
        candidates.append(m.group(1))
    for m in re.finditer(r'GIT_COMMON_DIR=(\S+)', command):
        candidates.append(m.group(1))
    for c in candidates:
        c = c.strip('\'"')
        try:
            cr = os.path.realpath(c)
        except Exception:
            cr = c
        if cr == main_gd or cr == main_real or cr.startswith(main_gd.rstrip('/') + os.sep):
            return True
    return False


def _scan_script_files_for_main_git(command: str, main_real: str) -> bool:
    """fix-2/codex#3: cover `python3 script.py` where the OUTER command does not
    mention git. Scan readable script-file operands (and any main_root mention)
    for a dangerous main-targeting git op. Cooperative threat model: a readable
    script is scanned; an unreadable script that runs an interpreter and mentions
    main_root (or whose content cannot be proven git-free) fails closed."""
    if not _INTERPRETER_LAUNCHER_RE.search(command):
        return False
    # If the command itself names main_root + a dangerous git op, the inline scan
    # already covers it; here we focus on file operands.
    for tok in command.split():
        t = tok.strip('\'"')
        if not t or t.startswith('-'):
            continue
        # heuristically a script operand: a path ending in a known script ext OR
        # an existing readable file under the project.
        looks_script = bool(re.search(r'\.(py|sh|bash|rb|pl|js|mjs|cjs)$', t))
        try:
            is_file = os.path.isfile(t)
        except Exception:
            is_file = False
        if not (looks_script or is_file):
            continue
        if is_file and os.access(t, os.R_OK):
            try:
                body = Path(t).read_text(errors='replace')
            except Exception:
                body = ''
            if _GIT_TOKEN_RE.search(body) and _DANGEROUS_GIT_OP_RE.search(body):
                if (main_real and main_real in body) or 'master' in body \
                   or re.search(r'-C\s+\S', body) or 'checkout' in body or 'switch' in body:
                    return True
        else:
            # script operand we cannot read; fail closed if it mentions main_root
            if main_real and main_real in command:
                return True
    return False


def _interpreter_hides_main_git(command: str, main_real: str, main_git_dir: str) -> bool:
    """fix-2 PRIMARY: True iff the OUTER Bash command launches an interpreter /
    subprocess whose payload carries a dangerous MAIN-TARGETING git op. This is
    the env-independent block for the git-2.43 symref-switch incident shape (the
    keystone provably cannot catch it on 2.43; the policy shim is bypassed by an
    env-scrubbed / absolute-git subprocess). Scoped to main-targeting so a
    worktree-local `subprocess.run(['git','add','.'])` is NOT blocked."""
    if not _INTERPRETER_LAUNCHER_RE.search(command):
        return False
    has_git = bool(_GIT_TOKEN_RE.search(command))
    if not has_git:
        # The git op may live in a script file (no `git` token in the outer cmd).
        return _scan_script_files_for_main_git(command, main_real)
    if not _DANGEROUS_GIT_OP_RE.search(command):
        return False
    # A dangerous git op is present in an interpreter payload. Now require a
    # main-targeting signal so worktree-local ops are allowed (codex #2):
    #   * a -C / --git-dir / GIT_DIR / GIT_WORK_TREE / GIT_COMMON_DIR into main
    #   * an explicit main_root path operand
    #   * a `master` / refs/heads/master ref operand (protected ref move)
    #   * checkout/switch/reset with NO -C and NO worktree path == ambiguous HEAD
    #     move -> fail closed (cannot prove it targets the worktree)
    if _gitdir_into_main(command, main_real, main_git_dir):
        return True
    if main_real and main_real in command:
        # mentions the main root path AND a dangerous op.
        return True
    if re.search(r'\b(master|refs/heads/master)\b', command):
        return True
    # No qualifying target proven worktree-local; for HEAD-moving ops that lack a
    # -C/path the destination is the process cwd which the launcher controls and
    # we cannot statically prove is the worktree -> fail closed for the exact
    # incident shape (checkout/switch/reset/restore of HEAD).
    if re.search(r'\b(checkout|switch|reset|restore)\b', command) \
       and not re.search(r'-C\s+\S', command) and not _mentions_worktree_path(command):
        return True
    return False


def _mentions_worktree_path(command: str) -> bool:
    """True iff the command text mentions an active worktree path (so a
    worktree-qualified op is not falsely flagged main-targeting)."""
    for wt in _get_active_worktree_paths():
        if wt and wt in command:
            return True
    return False


def _enforce_overnight_git_command(command: str, main_root: str, worktree_path: str,
                                   main_git_dir: str = '') -> None:
    """M13/M14a/M15 + fix-2/fix-3 (Cycle-2): for an overnight actor, block
    (a) hook-suppression/config overrides (M14a),
    (b) branch-switch / worktree / master ops targeting main_root (M13/M15) with
        a realpath-under-main-but-outside-worktree predicate (fix-3),
    (c) --git-dir/GIT_DIR/GIT_COMMON_DIR redirection into main (fix-3),
    (d) an interpreter/subprocess that hides a main-targeting git op — the
        env-independent block for the git-2.43 python-subprocess incident vector
        (fix-2 PRIMARY)."""
    if not command:
        return
    main_real = os.path.realpath(main_root) if main_root else ''
    # M14a: hook-suppression / config firewall (never relaxes).
    if _GIT_HOOK_SUPPRESS_RE.search(command):
        _block(
            '\nOVERNIGHT CONFIG FIREWALL: git hook-suppression / config-override '
            '(-c core.hooksPath, GIT_CONFIG_*, --config-env) is forbidden for '
            'overnight actors — it would bypass the reference-transaction keystone.\n'
        )
    # fix-3/codex#6: --git-dir / GIT_DIR / GIT_COMMON_DIR into the main repo.
    if _gitdir_into_main(command, main_real, main_git_dir):
        _block(
            '\nOVERNIGHT GIT-DIR REDIRECT BLOCK: a git op redirected into the '
            'main repo (--git-dir / GIT_DIR / GIT_COMMON_DIR -> main/.git) is '
            'forbidden for overnight actors.\n'
        )
    # fix-2 PRIMARY: interpreter/subprocess hiding a main-targeting git op.
    if _interpreter_hides_main_git(command, main_real, main_git_dir):
        _block(
            '\nOVERNIGHT SUBPROCESS GIT BLOCK: an interpreter/subprocess that '
            'could run a main-targeting git op (checkout/switch/reset/master '
            'ref-move against the main working directory) is forbidden for '
            'overnight actors. This is the exact 2026-06-03 python-subprocess '
            'incident vector; on git 2.43 the reference-transaction keystone '
            'cannot catch a symref branch-switch, so it is blocked here before '
            'execution. Run git ops INSIDE the isolated worktree instead.\n'
        )
    payload_cwd = _payload_cwd(_REQUEST_CTX.get('payload') or {})
    for subtoks in _normalize_git_basename_cmds(command):
        if not subtoks:
            continue
        # find the subcommand, any -C target, and the positional branch arg
        eff_dir = None
        sub = None
        positionals = []
        j = 0
        while j < len(subtoks):
            t = subtoks[j]
            if t == '-C' and j + 1 < len(subtoks):
                eff_dir = subtoks[j + 1]; j += 2; continue
            if t.startswith('-C') and len(t) > 2:
                eff_dir = t[2:]; j += 1; continue
            if sub is None and t.startswith('-'):
                j += 1; continue
            if sub is None:
                sub = t; j += 1; continue
            # after the subcommand, collect positionals (skip flags)
            if not t.startswith('-'):
                positionals.append(t)
            j += 1

        # Resolve the EFFECTIVE directory the op runs in: explicit -C, else the
        # actor's cwd (payload). This is the round-3 effective-target resolver.
        resolve_base = eff_dir if eff_dir else payload_cwd
        try:
            tgt_dir = os.path.realpath(resolve_base) if resolve_base else ''
        except Exception:
            tgt_dir = resolve_base or ''
        # fix-3: under-main-but-outside-worktree main-targeting (was exact-root).
        targets_main = _path_targets_main(tgt_dir, main_real)
        switches_master = any(p == 'master' or p == 'refs/heads/master'
                              for p in positionals)

        # M13: any git op whose effective dir is main-targeting -> block.
        if targets_main:
            _block(
                '\nOVERNIGHT MAIN-ROOT BLOCK: git op targeting the main '
                'working directory (effective -C/cwd under main_root, outside '
                'the isolated worktree) is forbidden for overnight actors.\n'
            )

        in_worktree = any(_path_under_prefix(tgt_dir, w)
                          for w in _get_active_worktree_paths()) if tgt_dir else False

        # M15: branch-switch / switch -c is the exact incident when it could move
        # the MAIN worktree's HEAD. A checkout/switch whose effective dir is the
        # overnight worktree and target is NOT master is LEGITIMATE and ALLOWED.
        if sub in ('checkout', 'switch'):
            if targets_main or switches_master or not in_worktree:
                _block(
                    f'\nOVERNIGHT BRANCH-SWITCH BLOCK: git {sub} that could move '
                    "the main worktree's HEAD off master is forbidden for "
                    'overnight actors (the exact 2026-06-03 incident shape). '
                    'Branch ops INSIDE the isolated worktree (non-master target) '
                    'are allowed.\n'
                )
        # fix-3: reset/restore that could write the main worktree.
        if sub in ('reset', 'restore', 'clean'):
            if targets_main or switches_master or not in_worktree:
                _block(
                    f'\nOVERNIGHT MAIN-WRITE BLOCK: git {sub} that could write '
                    'the main working directory is forbidden for overnight '
                    'actors. Run it inside the isolated worktree instead.\n'
                )
        # fix-3: stash apply/pop against main.
        if sub == 'stash':
            applyish = any(p in ('apply', 'pop') for p in positionals)
            if applyish and (targets_main or not in_worktree):
                _block(
                    '\nOVERNIGHT MAIN-WRITE BLOCK: git stash apply/pop against '
                    'the main working directory is forbidden for overnight '
                    'actors.\n'
                )
        # fix-3: master ref-move (branch -f master / update-ref refs/heads/master).
        if sub == 'branch':
            forcey = any(p in ('-f', '--force', '-D', '--delete', '-M', '--move')
                         for p in subtoks)
            if forcey and (switches_master or targets_main):
                _block(
                    '\nOVERNIGHT MASTER REF-MOVE BLOCK: git branch force/move/'
                    'delete of master is forbidden for overnight actors.\n'
                )
        if sub in ('update-ref', 'symbolic-ref'):
            if switches_master or targets_main:
                _block(
                    f'\nOVERNIGHT MASTER REF-MOVE BLOCK: git {sub} touching '
                    'master / HEAD is forbidden for overnight actors.\n'
                )
        if sub == 'worktree':
            _block(
                '\nOVERNIGHT WORKTREE BLOCK: an overnight actor may not manage '
                'git worktrees.\n'
            )


def _block_invalid_isolation(classification: str) -> None:
    """M9: a null/missing worktree in an owner/child state is INVALID isolation
    and BLOCKS the actor (it must not silently no-op into no-enforcement)."""
    _block(
        '\nOVERNIGHT ISOLATION INVALID: the governing overnight state has no '
        f'valid worktree_path (actor={classification}). Refusing the operation; '
        'the overnight actor must run inside a validated isolated worktree.\n'
    )


def main():
    """Entry point: apply global + actor-scoped overnight enforcement (M9)."""
    tool_name, tool_input, session_id, payload = _parse_hook_input()
    state = _load_session_state(session_id)
    _set_request_ctx(state, payload)  # T2.4: enable self_repair grant lookup
    if is_overnight_active():
        apply_global_security_checks(tool_name, tool_input)
    cwd = _payload_cwd(payload)
    wt_paths = _get_active_worktree_paths()
    classification, gov_state = _classify_actor(payload, state, wt_paths, cwd)

    # M9: a `normal` concurrent user session on main is NOT enforced — exit 0 so
    # the user's main session is never false-blocked.
    if classification == 'normal':
        sys.exit(0)

    # M9: owner/child with a null/missing worktree = invalid isolation = BLOCK.
    if classification in ('overnight_owner', 'overnight_child'):
        wt = (gov_state or {}).get('worktree_path') if gov_state else None
        if not wt:
            _block_invalid_isolation(classification)

    # M13/M14a/M15: for overnight actors, block hook-suppression + branch-switch
    # + main-root git ops (the exact-incident layered block; AC11).
    if classification in ('overnight_owner', 'overnight_child') and tool_name == 'Bash':
        main_root = (gov_state or {}).get('main_root', '') if gov_state else ''
        worktree_path = (gov_state or {}).get('worktree_path', '') if gov_state else ''
        main_git_dir = (gov_state or {}).get('main_git_dir', '') if gov_state else ''
        _enforce_overnight_git_command(
            tool_input.get('command', ''), main_root, worktree_path, main_git_dir)

    if wt_paths:
        apply_global_worktree_enforcement(tool_name, tool_input, wt_paths)
    if classification in ('overnight_owner', 'overnight_child') and gov_state is not None:
        _apply_session_enforcement(gov_state, tool_name, tool_input)
    sys.exit(0)


def _self_test() -> int:
    """T2.4 AC8: simulated overnight + self_repair-enabled contract grant test."""
    sr = {'enabled': True, 'reason': 'ac8', 'allowed_roles': ['dev'],
          'allowed_path_prefixes': ['/tmp/t24-ac8/'],
          'expires_at': '2099-01-01T00:00:00Z', 'audit_required': False}
    assert _self_repair_block({'self_repair': sr}) is sr, 'enabled grant returns dict'
    assert _self_repair_block({'self_repair': dict(sr, enabled=False)}) is None, 'disabled = None'
    assert _expires_passed('2020-01-01T00:00:00Z') and not _expires_passed('2099-01-01T00:00:00Z')
    assert _path_under_prefix('/tmp/t24-ac8/x', '/tmp/t24-ac8/')
    assert not _path_under_prefix('/etc/passwd', '/tmp/t24-ac8/')
    g, _ = _grant_decision_for('/tmp/t24-ac8/x.py', 'dev', '', sr); assert g, 'dev grant ok'
    g, _ = _grant_decision_for('/tmp/t24-ac8/x.py', 'qa', '', sr); assert not g, 'qa role denied'
    g, _ = _grant_decision_for('/etc/passwd', 'dev', '', sr); assert not g, 'outside-prefix denied'
    g, _ = _grant_decision_for('/tmp/t24-ac8/x.py', 'dev', '',
                               dict(sr, expires_at='2020-01-01T00:00:00Z')); assert not g, 'expired denied'
    print('T2.4 self-test: PASS (8 grant-logic assertions)'); return 0


if __name__ == '__main__':
    if '--self-test' in sys.argv:
        sys.exit(_self_test())
    main()
