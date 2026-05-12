#!/usr/bin/env python3
"""SubagentStop Hook: enforce per-spec checkpoint completion.

Activation gate (NOT matcher=*): this hook exits 0 unless BOTH conditions hold:
  1. The stopping subagent's agent_id is present in stdin data
  2. A cp-state file exists with is_running=true AND matching agent_id

Blocks (exit 2) iff any checkpoint is still pending AND no 30-minute timeout
has expired. Timeout auto-waives all pending with reason=timeout. PID liveness
is only a stale-cleanup signal after all checkpoints are done/waived; a dead
PID must never bypass pending checkpoint enforcement.
"""

import fcntl
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


AGE_TIMEOUT_SECONDS = 30 * 60


def _now_iso_z():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_iso_z(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _load_stdin():
    try:
        return json.load(sys.stdin)
    except Exception:
        return None


def _cp_root():
    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    return project_dir / ".claude" / "specs"


def _safe_read(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _match_agent(cp_file, agent_id):
    payload = _safe_read(cp_file)
    if not payload:
        return None
    if payload.get("agent_id") != agent_id:
        return None
    if not payload.get("is_running"):
        return None
    return payload


def _scan_spec_dir(spec_dir, agent_id):
    # Glob covers both primary (cp-state-<agent>.json) and numbered
    # auto-allocated slots (cp-state-<agent>-<N>.json, N>=2). Lock files
    # (cp-state-*.json.lock) are excluded by the .json suffix. The actual
    # agent-identity match is done in _match_agent via payload.agent_id,
    # which is an unambiguous, per-instance pin.
    for cp_file in spec_dir.glob("cp-state-*.json"):
        payload = _match_agent(cp_file, agent_id)
        if payload is not None:
            return cp_file, payload
    return None, None


def _find_active_state(agent_id):
    root = _cp_root()
    if not root.exists():
        return None, None
    for spec_dir in root.iterdir():
        if not spec_dir.is_dir():
            continue
        cp_file, payload = _scan_spec_dir(spec_dir, agent_id)
        if cp_file is not None:
            return cp_file, payload
    return None, None


def _collect_slots_in_dir(spec_dir, agent_id):
    """Return [(cp_file, payload), ...] for slots in spec_dir owned by agent_id."""
    out = []
    for cp_file in spec_dir.glob("cp-state-*.json"):
        payload = _safe_read(cp_file)
        if payload and payload.get("agent_id") == agent_id:
            out.append((cp_file, payload))
    return out


def _find_all_slots_for_agent(agent_id):
    """F15 idempotent cleanup: return ALL cp-state files owned by agent_id.

    Includes slots where is_running=false (unlike _match_agent which gates on
    is_running=true). Used to reconcile stale slots whose terminal-state was
    set without checked_out_at, OR to clean up multi-spec slots (rare but
    possible). Returns list of (cp_file, payload) tuples.
    """
    root = _cp_root()
    if not root.exists():
        return []
    found = []
    for spec_dir in root.iterdir():
        if spec_dir.is_dir():
            found.extend(_collect_slots_in_dir(spec_dir, agent_id))
    return found


def _idempotent_finalize(agent_id):
    """F15: ensure all terminal slots owned by agent_id have checked_out_at.

    No-op when is_running=false AND checked_out_at is already set. Otherwise,
    flip is_running=false and stamp checked_out_at. NEVER touches slots with
    pending checkpoints (M11).
    """
    for cp_file, payload in _find_all_slots_for_agent(agent_id):
        if _has_pending(payload):
            continue  # M11: pending enforcement is non-negotiable
        if not payload.get("is_running") and payload.get("checked_out_at"):
            continue  # already finalized: no-op
        _clean_exit(payload)
        _write_payload(cp_file, payload)


def _is_orphan_slot(payload):
    """AC-2 (spec-20260507-142952): true if slot is is_running=true with no
    pending checkpoints AND (agent_id is null OR recorded pid is dead).

    The agent_id-null case is the forensic shape from cp-state-ba.json
    (spec-20260506-203755): a slot whose agent_id field was clobbered to
    null while is_running was still true, leaving it invisible to
    _find_all_slots_for_agent's exact-equality filter. Once orphaned, no
    SubagentStop hook can finalize it via the normal agent_id-keyed path.

    M11 invariant preserved: pending checkpoints still block. This routine
    only touches slots whose checkpoints are terminal-or-empty.
    """
    if not payload.get("is_running"):
        return False
    if _has_pending(payload):
        return False
    if payload.get("agent_id") is None:
        return True
    pid = payload.get("pid")
    if pid is not None and not _is_pid_alive(pid):
        return True
    return False


def _emit_orphan_log(cp_file, prior_agent_id, prior_pid):
    sys.stderr.write(
        f"SUBAGENT STOP orphan-finalize: {cp_file} "
        f"(was is_running=true, agent_id={prior_agent_id}, "
        f"pid={prior_pid if prior_pid else 'none'})\n"
    )


def _try_finalize_under_lock(cp_file):
    """Re-read + re-validate + write inside lock; return (aid,pid) or None."""
    payload = _safe_read(cp_file)
    if payload is None or not _is_orphan_slot(payload):
        return None
    prior_agent_id = payload.get("agent_id")
    prior_pid = payload.get("pid")
    _clean_exit(payload)
    cp_file.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return (prior_agent_id, prior_pid)


def _run_under_lock(cp_file, fn):
    """Run fn(cp_file) holding the writer flock on cp_file.lock; OSError -> None."""
    lock_path = cp_file.with_suffix(cp_file.suffix + ".lock")
    try:
        with open(lock_path, "w") as lh:
            fcntl.flock(lh.fileno(), fcntl.LOCK_EX)
            result = fn(cp_file)
            fcntl.flock(lh.fileno(), fcntl.LOCK_UN)
        return result
    except OSError:
        return None


def _finalize_one_orphan(cp_file):
    """TOCTOU-safe orphan finalize. Codex AC-2 follow-up: re-read + write
    must both happen under the writer lock to avoid clobbering a
    concurrent spec-check.py mark/check-in landing between read & write.
    """
    log_args = _run_under_lock(cp_file, _try_finalize_under_lock)
    if log_args is not None:
        _emit_orphan_log(cp_file, *log_args)


def _iter_cp_files(root):
    """Yield every cp-state-*.json under root/<spec>/."""
    for spec_dir in root.iterdir():
        if not spec_dir.is_dir():
            continue
        for cp_file in spec_dir.glob("cp-state-*.json"):
            yield cp_file


def _finalize_orphans():
    """AC-2 backstop: scan ALL cp-state files; finalize orphan slots.

    Runs AFTER _dispatch returns 0 (clean exit) to avoid bypassing M11's
    pending block. Out-of-band finalizations are emitted to stderr so
    operators can see when a slot was reclaimed without a Stop owner.
    """
    root = _cp_root()
    if not root.exists():
        return
    for cp_file in _iter_cp_files(root):
        _finalize_one_orphan(cp_file)


def _write_payload(path, payload):
    lock_path = path.with_suffix(path.suffix + ".lock")
    with open(lock_path, "w") as lh:
        fcntl.flock(lh.fileno(), fcntl.LOCK_EX)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        fcntl.flock(lh.fileno(), fcntl.LOCK_UN)


def _is_pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError):
        return False


def _is_timed_out(payload):
    checked_in = _parse_iso_z(payload.get("checked_in_at"))
    if checked_in is None:
        return False
    age = (datetime.now(timezone.utc) - checked_in).total_seconds()
    return age > AGE_TIMEOUT_SECONDS


def _has_pending(payload):
    return any(cp.get("state") == "pending" for cp in payload.get("checkpoints", []))


def _list_pending(payload):
    return [cp for cp in payload.get("checkpoints", []) if cp.get("state") == "pending"]


def _waive_all_pending(payload, reason):
    for cp in payload.get("checkpoints", []):
        if cp.get("state") == "pending":
            cp["state"] = "waived-with-reason"
            cp["waived_reason"] = reason
            cp["updated_at"] = _now_iso_z()


def _auto_waive_timeout(payload):
    _waive_all_pending(payload, "timeout")
    payload["is_running"] = False
    payload["checked_out_at"] = _now_iso_z()


def _clean_exit(payload):
    payload["is_running"] = False
    payload["checked_out_at"] = _now_iso_z()


def _parse_cp_identity(cp_file, payload):
    """Return (spec_id, agent, instance_id) for diagnostics/commands."""
    spec_id = payload.get("spec_id") or cp_file.parent.name
    agent = payload.get("agent_type")
    instance_id = payload.get("instance_id")
    if not agent:
        name = cp_file.name
        if name.startswith("cp-state-") and name.endswith(".json"):
            body = name[len("cp-state-"):-len(".json")]
            if "-" in body:
                maybe_agent, maybe_instance = body.rsplit("-", 1)
                if maybe_instance.isdigit():
                    agent = maybe_agent
                    instance_id = int(maybe_instance)
                else:
                    agent = body
            else:
                agent = body
    return spec_id, agent or "<AGENT>", instance_id


def _instance_arg(instance_id):
    if instance_id in (None, ""):
        return ""
    return f" --instance-id {instance_id}"


def _agent_id_arg(payload):
    agent_id = payload.get("agent_id")
    if not agent_id:
        return ""
    return f" --agent-id {agent_id}"


def _emit_block_message(cp_file, payload, pending):
    names = ", ".join(cp.get("id", "?") for cp in pending)
    spec_id, agent, instance_id = _parse_cp_identity(cp_file, payload)
    instance = _instance_arg(instance_id)
    agent_id = _agent_id_arg(payload)
    sys.stderr.write(
        f"SUBAGENT STOP BLOCKED: {len(pending)} checkpoint(s) still pending: {names}\n"
        f"cp-state: {cp_file}\n"
        "Mark them done via:\n"
        f"  python3 /root/.claude/scripts/spec-check.py mark --spec-id {spec_id} "
        f"--agent {agent}{instance}{agent_id} --cp-id <CP>\n"
        "Or waive (auto-text records actor + ISO timestamp):\n"
        f"  python3 /root/.claude/scripts/spec-check.py waive --spec-id {spec_id} "
        f"--agent {agent}{instance}{agent_id} --cp-id <CP>\n"
    )


def _extract_stop_pid(data):
    if not isinstance(data, dict):
        return None
    return data.get("pid") or data.get("tool_input", {}).get("pid")


def _handle_timeout(cp_file, payload):
    _auto_waive_timeout(payload)
    _write_payload(cp_file, payload)
    return 0


def _handle_dead_pid(cp_file, payload):
    _clean_exit(payload)
    _write_payload(cp_file, payload)
    return 0


def _handle_pending(cp_file, payload):
    _emit_block_message(cp_file, payload, _list_pending(payload))
    return 2


def _handle_complete(cp_file, payload):
    _clean_exit(payload)
    _write_payload(cp_file, payload)
    return 0


def _handle_active_state(cp_file, payload, data):
    if _is_timed_out(payload):
        return _handle_timeout(cp_file, payload)
    if _has_pending(payload):
        return _handle_pending(cp_file, payload)
    pid = _extract_stop_pid(data) or payload.get("pid")
    if pid and not _is_pid_alive(pid):
        return _handle_dead_pid(cp_file, payload)
    return _handle_complete(cp_file, payload)


def _handle_no_active_state(agent_id):
    """F15 idempotent reconcile + AC-2 fall-through (return, do not exit)."""
    _idempotent_finalize(agent_id)
    return 0


def _find_blocking_pending(agent_id):
    """M11 global preflight: ANY active, non-timed-out, pending slot blocks Stop."""
    for sf, sp in _find_all_slots_for_agent(agent_id):
        if sp.get("is_running") and _has_pending(sp) and not _is_timed_out(sp):
            return sf, sp
    return None, None


def _finalize_with_siblings(cp_file, payload, data, agent_id):
    """F15: handle primary active slot, then reconcile siblings on rc=0."""
    rc = _handle_active_state(cp_file, payload, data)
    if rc == 0:
        _idempotent_finalize(agent_id)
    return rc


def _dispatch(agent_id, data):
    """M11 preflight, then per-slot finalize."""
    sf, sp = _find_blocking_pending(agent_id)
    if sf is not None:
        return _handle_pending(sf, sp)
    cp_file, payload = _find_active_state(agent_id)
    if cp_file is None:
        return _handle_no_active_state(agent_id)  # AC-2: return, not exit
    return _finalize_with_siblings(cp_file, payload, data, agent_id)


def _run_dispatch_with_orphan_backstop(agent_id, data):
    """AC-2: dispatch, then run orphan backstop only on clean exit (rc=0).
    Pending-block (rc=2) preserves M11 invariant and skips reconciliation.
    """
    rc = _dispatch(agent_id, data)
    if rc == 0:
        _finalize_orphans()
    return rc


def main():
    data = _load_stdin()
    if data is None:
        sys.exit(0)
    agent_id = data.get("agent_id")
    if not agent_id:
        sys.exit(0)
    sys.exit(_run_dispatch_with_orphan_backstop(agent_id, data))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
