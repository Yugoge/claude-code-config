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
        "Or waive with a reason:\n"
        f"  python3 /root/.claude/scripts/spec-check.py waive --spec-id {spec_id} "
        f"--agent {agent}{instance}{agent_id} --cp-id <CP> --reason <TEXT>\n"
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


def main():
    data = _load_stdin()
    if data is None:
        sys.exit(0)
    agent_id = data.get("agent_id")
    if not agent_id:
        sys.exit(0)
    cp_file, payload = _find_active_state(agent_id)
    if cp_file is None:
        sys.exit(0)
    sys.exit(_handle_active_state(cp_file, payload, data))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
