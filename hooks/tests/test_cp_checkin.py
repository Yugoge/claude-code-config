#!/usr/bin/env python3
"""Tests for pretool-cp-checkin.py and .claude/scripts/spec-check.py covering ACs 1-10
of ba-spec-20260427-194324.md (P1 view-trigger removal + P2 generation field).

Each test runs the hook or spec-check.py as a subprocess with synthesized
stdin JSON and CLAUDE_PROJECT_DIR pointed at a tempfile.TemporaryDirectory.
Tests do NOT mutate live /root/.claude/specs/* files. No external framework.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path


HOOK = Path("/root/.claude/hooks/pretool-cp-checkin.py")
SPEC_CHECK = Path("/root/.claude/scripts/spec-check.py")


# -------------------- helpers ---------------------

def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _make_cp_state(project_dir: Path, spec_id: str, agent: str,
                   payload: dict) -> Path:
    cp_dir = project_dir / ".claude" / "specs" / spec_id
    cp_dir.mkdir(parents=True, exist_ok=True)
    cp_path = cp_dir / f"cp-state-{agent}.json"
    cp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return cp_path


def _run_hook(project_dir: Path, stdin_obj, raw_stdin=None):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)}
    inp = raw_stdin if raw_stdin is not None else json.dumps(stdin_obj)
    return subprocess.run(["python3", str(HOOK)], input=inp, text=True,
                          capture_output=True, env=env, timeout=15)


def _run_spec_check(project_dir: Path, args):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)}
    return subprocess.run(["python3", str(SPEC_CHECK)] + list(args),
                          text=True, capture_output=True, env=env, timeout=15)


def _read_cp(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _baseline_payload(spec_id, agent, *, generation=None, checkpoints=None,
                      agent_id=None, is_running=False):
    p = {
        "spec_id": spec_id,
        "agent_type": agent,
        "instance_id": None,
        "agent_id": agent_id,
        "is_running": is_running,
        "checked_in_at": None,
        "checked_out_at": None,
        "checkpoints": checkpoints or [],
        "terminal_artifact": {"path": None, "exists": False, "validated_at": None},
    }
    if generation is not None:
        p["generation"] = generation
    return p


def _cp(cp_id, *, state="pending", waived_reason=None):
    return {
        "id": cp_id, "action": f"do-{cp_id}", "state": state,
        "waived_reason": waived_reason, "updated_at": _now_iso(),
    }


# -------------------- result tracking ---------------------

RESULTS: list[tuple[str, bool, str]] = []


def expect(label, ok, detail=""):
    RESULTS.append((label, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f": {detail}" if not ok else ""))


def assert_no_traceback(label, rc):
    expect(f"{label}.exit-0", rc.returncode == 0,
           f"rc={rc.returncode} stderr={rc.stderr!r}")
    expect(f"{label}.no-traceback", "Traceback" not in (rc.stderr or ""),
           f"stderr={rc.stderr!r}")


# -------------------- AC1: view-file Read MUST be no-op ---------------------

def _setup_ac1(td):
    spec_id, agent = "spec-test-ac1", "ba"
    cp_path = _make_cp_state(td, spec_id, agent, _baseline_payload(
        spec_id, agent, checkpoints=[_cp("cp-01", state="done")]))
    view = td / "docs" / "dev" / "specs" / spec_id / "views" / f"{agent}.md"
    view.parent.mkdir(parents=True, exist_ok=True)
    view.write_text("# view", encoding="utf-8")
    return cp_path, view


def test_ac1_view_read_does_not_mutate(td):
    cp_path, view = _setup_ac1(td)
    before = cp_path.read_bytes()
    rc = _run_hook(td, {"tool_name": "Read",
                        "tool_input": {"file_path": str(view)},
                        "agent_id": "explore-aaaa"})
    expect("AC1.exit-0", rc.returncode == 0, f"rc={rc.returncode}")
    expect("AC1.cp-byte-identical", before == cp_path.read_bytes(),
           "cp-state mutated by view-file Read; expected byte-identical")


# -------------------- AC2: cp-state direct Read registers + preserves ---------------------

def _setup_ac2(td):
    spec_id, agent = "spec-test-ac2", "ba"
    return _make_cp_state(td, spec_id, agent, _baseline_payload(
        spec_id, agent, generation=1,
        checkpoints=[_cp("cp-01", state="done"),
                     _cp("cp-02", state="waived-with-reason",
                         waived_reason="qa-asked-for-this")]))


def test_ac2_direct_read_registers_and_preserves(td):
    cp_path = _setup_ac2(td)
    rc = _run_hook(td, {"tool_name": "Read",
                        "tool_input": {"file_path": str(cp_path)},
                        "agent_id": "real-abcd1234"})
    assert_no_traceback("AC2", rc)
    after = _read_cp(cp_path)
    expect("AC2.is_running", after.get("is_running") is True, str(after))
    expect("AC2.agent_id", after.get("agent_id") == "real-abcd1234",
           str(after.get("agent_id")))
    cps = after["checkpoints"]
    expect("AC2.cp-01-done", cps[0].get("state") == "done", str(cps[0]))
    expect("AC2.cp-02-waived",
           cps[1].get("state") == "waived-with-reason"
           and cps[1].get("waived_reason") == "qa-asked-for-this", str(cps[1]))


# -------------------- AC3: dev-sentinel updates index ---------------------

def test_ac3_dev_sentinel_updates_index(td):
    sid, agent = "dev-test-sid", "ba"
    sentinel = td / ".claude" / "dev-registry" / sid / f"{agent}.json"
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text("{}", encoding="utf-8")
    rc = _run_hook(td, {"tool_name": "Read",
                        "tool_input": {"file_path": str(sentinel)},
                        "agent_id": "abc-real"})
    assert_no_traceback("AC3", rc)
    idx = td / ".claude" / "dev-registry" / "agent-index.json"
    expect("AC3.index-exists", idx.exists(), "agent-index.json missing")
    if idx.exists():
        m = json.loads(idx.read_text(encoding="utf-8"))
        expect("AC3.mapping", m.get("abc-real") == agent, str(m))


# -------------------- AC4: SECOND ACTION protocol still works ---------------------

def _check_one_agent_ac4(td, spec_id, agent):
    cp_path = _make_cp_state(td, spec_id, agent, _baseline_payload(
        spec_id, agent, generation=1, checkpoints=[_cp("cp-01")]))
    rc = _run_hook(td, {"tool_name": "Read",
                        "tool_input": {"file_path": str(cp_path)},
                        "agent_id": f"id-{agent}"})
    expect(f"AC4.{agent}.exit-0", rc.returncode == 0, f"rc={rc.returncode}")
    after = _read_cp(cp_path)
    expect(f"AC4.{agent}.registered",
           after.get("is_running") is True
           and after.get("agent_id") == f"id-{agent}", str(after))


def test_ac4_second_action_still_registers(td):
    for agent in ("ba", "dev", "qa"):
        _check_one_agent_ac4(td, "spec-test-ac4", agent)


# -------------------- AC5: missing generation -> 1, no implicit reset ---------------------

def _setup_ac5(td):
    spec_id, agent = "spec-test-ac5", "ba"
    payload = _baseline_payload(spec_id, agent,
                                checkpoints=[_cp("cp-01", state="done")])
    return _make_cp_state(td, spec_id, agent, payload)


def test_ac5_missing_generation_no_reset(td):
    cp_path = _setup_ac5(td)
    rc = _run_hook(td, {"tool_name": "Read",
                        "tool_input": {"file_path": str(cp_path)},
                        "agent_id": "id-ac5"})
    assert_no_traceback("AC5", rc)
    after = _read_cp(cp_path)
    expect("AC5.cp-01-still-done",
           after["checkpoints"][0].get("state") == "done", str(after))
    # OBJ-2: hook MUST NOT silently back-fill the generation field on rewrite.
    expect("AC5.no-implicit-backfill", "generation" not in after,
           f"generation field silently back-filled: {after!r}")


# -------------------- AC6: takeover inherits done states ---------------------

def _setup_ac6(td):
    spec_id, agent = "spec-test-ac6", "ba"
    return _make_cp_state(td, spec_id, agent, _baseline_payload(
        spec_id, agent, generation=1, agent_id="prev-zzz", is_running=False,
        checkpoints=[_cp("cp-01", state="done"),
                     _cp("cp-02", state="done"),
                     _cp("cp-03", state="done")]))


def test_ac6_takeover_inherits_done(td):
    cp_path = _setup_ac6(td)
    rc = _run_hook(td, {"tool_name": "Read",
                        "tool_input": {"file_path": str(cp_path)},
                        "agent_id": "next-bbb"})
    assert_no_traceback("AC6", rc)
    after = _read_cp(cp_path)
    expect("AC6.is_running", after.get("is_running") is True, str(after))
    expect("AC6.agent_id", after.get("agent_id") == "next-bbb",
           str(after.get("agent_id")))
    states = [cp.get("state") for cp in after.get("checkpoints", [])]
    expect("AC6.all-still-done", states == ["done", "done", "done"],
           f"states={states!r}")


# -------------------- AC7: --bump-generation resets ---------------------

def _setup_ac7(td):
    spec_id, agent = "spec-test-ac7", "ba"
    payload = _baseline_payload(
        spec_id, agent, generation=1, agent_id="prev-zzz",
        checkpoints=[_cp("cp-01", state="done"),
                     _cp("cp-02", state="waived-with-reason",
                         waived_reason="qa-blocked"),
                     _cp("cp-03", state="pending")])
    payload["updated_at"] = "2026-04-27T10:00:00Z"  # cp-state-level marker
    return _make_cp_state(td, spec_id, agent, payload), spec_id, agent


def _assert_ac7_post(after):
    expect("AC7.generation-2", after.get("generation") == 2,
           f"generation={after.get('generation')!r}")
    states = [cp.get("state") for cp in after.get("checkpoints", [])]
    expect("AC7.all-pending", states == ["pending"] * 3, str(states))
    reasons = [cp.get("waived_reason") for cp in after.get("checkpoints", [])]
    expect("AC7.reasons-cleared", reasons == [None, None, None], str(reasons))
    expect("AC7.is_running", after.get("is_running") is True, "")
    # OBJ-3: cp-state-level updated marker refreshed on bump.
    expect("AC7.cp-state-updated-refreshed",
           after.get("updated_at") not in (None, "", "2026-04-27T10:00:00Z"),
           f"updated_at={after.get('updated_at')!r}")


def test_ac7_bump_generation(td):
    cp_path, spec_id, agent = _setup_ac7(td)
    rc = _run_spec_check(td, ["check-in", "--spec-id", spec_id,
                              "--agent", agent, "--agent-id", "fresh-aaa",
                              "--bump-generation"])
    assert_no_traceback("AC7", rc)
    _assert_ac7_post(_read_cp(cp_path))


# -------------------- AC8: waived survives normal takeover ---------------------

def test_ac8_waived_survives_takeover(td):
    spec_id, agent = "spec-test-ac8", "ba"
    cp_path = _make_cp_state(td, spec_id, agent, _baseline_payload(
        spec_id, agent, generation=1, is_running=False, agent_id="old",
        checkpoints=[_cp("cp-01", state="waived-with-reason",
                         waived_reason="qa-asked-for-this")]))
    rc = _run_hook(td, {"tool_name": "Read",
                        "tool_input": {"file_path": str(cp_path)},
                        "agent_id": "new-takeover"})
    assert_no_traceback("AC8", rc)
    cp = _read_cp(cp_path)["checkpoints"][0]
    expect("AC8.state-waived", cp.get("state") == "waived-with-reason",
           str(cp))
    expect("AC8.reason-preserved",
           cp.get("waived_reason") == "qa-asked-for-this", str(cp))


# -------------------- AC10a-c: negative tests ---------------------

def test_ac10a_malformed_stdin(td):
    rc = _run_hook(td, None, raw_stdin="not-json{")
    assert_no_traceback("AC10a", rc)


def test_ac10b_missing_tool_name(td):
    rc = _run_hook(td, {"tool_input": {"file_path": "/tmp/anything"},
                        "agent_id": "x"})
    assert_no_traceback("AC10b", rc)


def test_ac10c_missing_agent_id_for_sentinel(td):
    sentinel = td / ".claude" / "dev-registry" / "dev-no-id" / "ba.json"
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text("{}", encoding="utf-8")
    rc = _run_hook(td, {"tool_name": "Read",
                        "tool_input": {"file_path": str(sentinel)}})
    assert_no_traceback("AC10c", rc)
    idx = td / ".claude" / "dev-registry" / "agent-index.json"
    expect("AC10c.no-index-update", not idx.exists(),
           "agent-index.json should not exist when agent_id is missing")


# -------------------- AC10d: concurrent --bump-generation ---------------------

def _bump_one(td, spec_id, agent, tag, results):
    results[tag] = _run_spec_check(td, [
        "check-in", "--spec-id", spec_id, "--agent", agent,
        "--agent-id", f"id-{tag}", "--bump-generation"])


def test_ac10d_concurrent_bump_generation(td):
    spec_id, agent = "spec-test-ac10d", "ba"
    cp_path = _make_cp_state(td, spec_id, agent, _baseline_payload(
        spec_id, agent, generation=1,
        checkpoints=[_cp("cp-01", state="done")]))
    results = {}
    threads = [threading.Thread(target=_bump_one,
                                args=(td, spec_id, agent, t, results))
               for t in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)
    expect("AC10d.both-rc-0",
           all(results[t].returncode == 0 for t in ("a", "b")),
           f"a.stderr={results['a'].stderr!r} b.stderr={results['b'].stderr!r}")
    final = _read_cp(cp_path)
    expect("AC10d.final-generation-3", final.get("generation") == 3,
           f"final generation={final.get('generation')!r} (expected 3); "
           f"OBJ-2 invariant: read-modify-write must be under exclusive lock")


# -------------------- runner ---------------------

ALL_TESTS = [
    test_ac1_view_read_does_not_mutate,
    test_ac2_direct_read_registers_and_preserves,
    test_ac3_dev_sentinel_updates_index,
    test_ac4_second_action_still_registers,
    test_ac5_missing_generation_no_reset,
    test_ac6_takeover_inherits_done,
    test_ac7_bump_generation,
    test_ac8_waived_survives_takeover,
    test_ac10a_malformed_stdin,
    test_ac10b_missing_tool_name,
    test_ac10c_missing_agent_id_for_sentinel,
    test_ac10d_concurrent_bump_generation,
]


def _run_one(fn):
    with tempfile.TemporaryDirectory() as tmp:
        try:
            fn(Path(tmp))
        except Exception as e:
            expect(f"{fn.__name__}.unhandled", False, repr(e))


def main():
    for fn in ALL_TESTS:
        _run_one(fn)
    print()
    print("=== summary ===")
    failures = sum(1 for _, ok, _ in RESULTS if not ok)
    total = len(RESULTS)
    print(f"{total - failures}/{total} assertions passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
