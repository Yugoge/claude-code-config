#!/usr/bin/env python3
"""PreToolUse Agent hook: daily-trade hard Agent fan-out governor.

Blocks the pathological failure mode from 2026-05-23: the daily-trade command
launched many trading subagents in one wave while codex consultation was also
required, exhausting memory/DB connections. This hook is intentionally narrow:
it only applies to daily-trade trading Agent/Task launches.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

TRADING_AGENT_TYPES = {
    "trading-news-scanner",
    "trading-bull",
    "trading-bear",
    "trading-synthesizer",
}
# Fallback only for malformed/older Agent payloads that lack subagent_type.
# Do NOT use generic terms like "daily-trade" here; this hook is global for
# all Agent calls and must not block ordinary review/debug agents in a session
# whose transcript mentions daily-trade.
TRADING_DESCRIPTION_RE = re.compile(
    r"^(bull news scan batch|bear news scan batch|bull analysis batch|"
    r"bear analysis batch|synthesize signals batch)\s+(\d+|\{i\})$"
)
STATE_DIR = Path(os.environ.get("DAILY_TRADE_AGENT_GUARD_DIR", "/tmp/daily-trade-agent-guard"))
TAIL_BYTES = int(os.environ.get("DAILY_TRADE_AGENT_TRANSCRIPT_TAIL_BYTES", str(2 * 1024 * 1024)))
RESERVATION_TTL_SECONDS = int(os.environ.get("DAILY_TRADE_AGENT_RESERVATION_TTL", "300"))
DEFAULT_CAP_WITH_CODEX = int(os.environ.get("DAILY_TRADE_AGENT_CAP_WITH_CODEX", "1"))
DEFAULT_CAP_NO_CODEX = int(os.environ.get("DAILY_TRADE_AGENT_CAP_NO_CODEX", "2"))


def _load_payload() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def _flatten_strings(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            out.extend(_flatten_strings(v))
    elif isinstance(value, list):
        for v in value:
            out.extend(_flatten_strings(v))
    return out


def _read_tail(path: str | None) -> tuple[str, float]:
    if not path:
        return "", 0.0
    try:
        p = Path(path)
        st = p.stat()
        with p.open("rb") as f:
            if st.st_size > TAIL_BYTES:
                f.seek(-TAIL_BYTES, os.SEEK_END)
            data = f.read()
        return data.decode("utf-8", errors="replace"), st.st_mtime
    except Exception:
        return "", 0.0


def _is_trading_launch(tool_input: dict[str, Any], current_text: str) -> bool:
    """Return true only for the current Agent launch, never because of transcript history."""
    subagent_type = str(tool_input.get("subagent_type") or "")
    if subagent_type in TRADING_AGENT_TYPES:
        return True
    description = str(tool_input.get("description") or "").strip().lower()
    if TRADING_DESCRIPTION_RE.fullmatch(description):
        return True
    # Do not infer from the free-form prompt body. Review/debug agents may
    # legitimately mention trading-news-scanner or daily-trade without being a
    # daily-trade execution wave. If future payloads omit subagent_type, add a
    # precise description pattern above instead of scanning arbitrary prompt text.
    return False


def _cap_for_context(combined: str) -> int:
    lowered = combined.lower()
    codex_markers = ("--codex", "codex_required", "codex required", "codex=true", "code_required: true")
    if any(m in lowered for m in codex_markers):
        return DEFAULT_CAP_WITH_CODEX
    return DEFAULT_CAP_NO_CODEX


def _active_trading_agent_tools(transcript_tail: str) -> int:
    """Count Agent tool_use IDs in the tail that have no matching tool_result yet."""
    started: set[str] = set()
    completed: set[str] = set()
    for line in transcript_tail.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        msg = obj.get("message") if isinstance(obj, dict) else None
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "tool_use" and item.get("name") == "Agent":
                tid = str(item.get("id") or "")
                if not tid:
                    continue
                inp = item.get("input") if isinstance(item.get("input"), dict) else {}
                text = "\n".join(_flatten_strings(inp))
                if _is_trading_launch(inp, text):
                    started.add(tid)
            elif item.get("type") == "tool_result":
                tid = str(item.get("tool_use_id") or "")
                if tid:
                    completed.add(tid)
    return max(0, len(started - completed))


def _state_key(payload: dict[str, Any], transcript_path: str | None) -> str:
    raw = str(payload.get("session_id") or payload.get("conversation_id") or transcript_path or "unknown")
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:24]


def main() -> int:
    payload = _load_payload()
    tool_name = str(payload.get("tool_name") or payload.get("name") or "Agent")
    if tool_name not in {"Agent", "Task"}:
        return 0
    tool_input = payload.get("tool_input") or payload.get("input") or {}
    if not isinstance(tool_input, dict):
        return 0

    transcript_path = payload.get("transcript_path") or payload.get("transcript")
    transcript_tail, transcript_mtime = _read_tail(str(transcript_path) if transcript_path else None)
    current_text = "\n".join(_flatten_strings(tool_input))
    context_for_cap = current_text + "\n" + transcript_tail[-200_000:]

    if not _is_trading_launch(tool_input, current_text):
        return 0

    cap = max(1, _cap_for_context(context_for_cap))
    active = _active_trading_agent_tools(transcript_tail)

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    key = _state_key(payload, str(transcript_path) if transcript_path else None)
    state_path = STATE_DIR / f"{key}.json"
    lock_path = STATE_DIR / f"{key}.lock"
    now = time.time()

    with lock_path.open("w") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        try:
            state = json.loads(state_path.read_text()) if state_path.exists() else {}
        except Exception:
            state = {}
        reservations = state.get("reservations") if isinstance(state, dict) else []
        if not isinstance(reservations, list):
            reservations = []

        # Expire stale reservations. If transcript advanced and no active Agent
        # remains in the tail, clear reservations so sequential waves are allowed.
        kept = []
        max_created_mtime = 0.0
        for r in reservations:
            if not isinstance(r, dict):
                continue
            ts = float(r.get("ts", 0.0) or 0.0)
            created_mtime = float(r.get("transcript_mtime", 0.0) or 0.0)
            max_created_mtime = max(max_created_mtime, created_mtime)
            if now - ts <= RESERVATION_TTL_SECONDS:
                kept.append(r)
        reservations = kept
        if active == 0 and transcript_mtime > max_created_mtime + 0.5:
            reservations = []

        effective = active + len(reservations)
        if effective >= cap:
            print(
                "BLOCKED daily-trade Agent concurrency: "
                f"active={active} reservations={len(reservations)} cap={cap}. "
                "Launch trading Tasks in throttled waves; wait for the current "
                "Task/Agent result before starting another wave.",
                file=sys.stderr,
            )
            state_path.write_text(json.dumps({
                "updated_at": now,
                "cap": cap,
                "active": active,
                "reservations": reservations,
                "last_blocked": now,
            }, indent=2, sort_keys=True))
            return 2

        reservations.append({
            "ts": now,
            "pid": os.getpid(),
            "tool": tool_name,
            "subagent_type": tool_input.get("subagent_type"),
            "description": tool_input.get("description"),
            "transcript_mtime": transcript_mtime,
        })
        state_path.write_text(json.dumps({
            "updated_at": now,
            "cap": cap,
            "active": active,
            "reservations": reservations,
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
