#!/usr/bin/env python3
"""
Tests for arch-6 (pretool-gitignore-preflight.py) and arch-3 (userprompt-tmpfs-pressure.sh)
Task: 20260524-171714
ACs: AC1a, AC1b, AC2, AC3, AC4a, AC4b, AC5, AC6, AC7, AC7b, AC8, AC9, AC10, AC11
"""

import json
import os
import stat
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
HOOK_PREFLIGHT = REPO / "hooks" / "pretool-gitignore-preflight.py"
HOOK_PRESSURE = REPO / "hooks" / "userprompt-tmpfs-pressure.sh"


def run_preflight(stdin_payload: dict, tmp_path=None) -> subprocess.CompletedProcess:
    """Invoke pretool-gitignore-preflight.py with the given stdin payload."""
    return subprocess.run(
        ["python3", str(HOOK_PREFLIGHT)],
        input=json.dumps(stdin_payload),
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )


def make_report(tmp_path, task_id, files_modified=None, files_created=None, waiver=None):
    """Write a dev-report JSON to a path under docs/dev/ in REPO and return the relative path."""
    report = {
        "request_id": task_id,
        "task_id": task_id,
        "dev": {
            "files_modified": files_modified if files_modified is not None else [],
            "files_created": files_created if files_created is not None else [],
        },
    }
    if waiver is not None:
        report["gitignore_waiver"] = waiver

    report_path = REPO / "docs" / "dev" / f"dev-report-{task_id}.json"
    report_path.write_text(json.dumps(report))
    return f"docs/dev/dev-report-{task_id}.json"


def make_stdin(report_rel_path):
    """Build the standard nested stdin fixture for the hook."""
    return {
        "tool_name": "Agent",
        "tool_input": {
            "prompt": f"QA agent running. Dev report file: {report_rel_path} please verify."
        },
    }


# ── AC1a: files_modified with gitignored path → exit 2 ──────────────────────

def test_ac1a_files_modified_gitignored_exits_2(tmp_path):
    """AC1a: files_modified contains gitignored path → hook exits 2 with BLOCKED in stderr."""
    task_id = "test-ac1a-20260524"
    report_rel = make_report(
        tmp_path,
        task_id,
        files_modified=["docs/some-doc.md"],
        files_created=[],
    )
    try:
        result = run_preflight(make_stdin(report_rel))
        assert result.returncode == 2, f"Expected exit 2, got {result.returncode}. stderr={result.stderr!r}"
        assert "BLOCKED" in result.stderr, f"Expected 'BLOCKED' in stderr, got: {result.stderr!r}"
        assert "docs/some-doc.md" in result.stderr, f"Expected path in stderr, got: {result.stderr!r}"
    finally:
        report_path = REPO / report_rel
        report_path.unlink(missing_ok=True)


# ── AC1b: files_created with gitignored path → exit 2 ───────────────────────

def test_ac1b_files_created_gitignored_exits_2(tmp_path):
    """AC1b: files_created contains gitignored path → hook exits 2 with BLOCKED in stderr."""
    task_id = "test-ac1b-20260524"
    report_rel = make_report(
        tmp_path,
        task_id,
        files_modified=[],
        files_created=["docs/new-doc.md"],
    )
    try:
        result = run_preflight(make_stdin(report_rel))
        assert result.returncode == 2, f"Expected exit 2, got {result.returncode}. stderr={result.stderr!r}"
        assert "BLOCKED" in result.stderr
        assert "docs/new-doc.md" in result.stderr
    finally:
        report_path = REPO / report_rel
        report_path.unlink(missing_ok=True)


# ── AC2: non-gitignored paths → exit 0 ──────────────────────────────────────

def test_ac2_non_gitignored_paths_exit_0(tmp_path):
    """AC2: files_modified and files_created contain only non-gitignored paths → exit 0."""
    task_id = "test-ac2-20260524"
    report_rel = make_report(
        tmp_path,
        task_id,
        files_modified=["hooks/pretool-gitignore-preflight.py"],
        files_created=["settings.json"],
    )
    try:
        result = run_preflight(make_stdin(report_rel))
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}. stderr={result.stderr!r}"
    finally:
        report_path = REPO / report_rel
        report_path.unlink(missing_ok=True)


# ── AC3: dev-report does not exist on disk → exit 0 (no-op) ─────────────────

def test_ac3_missing_report_exits_0():
    """AC3: Agent prompt references a dev-report that does not exist on disk → exit 0."""
    stdin_payload = {
        "tool_name": "Agent",
        "tool_input": {
            "prompt": "Dev report file: docs/dev/dev-report-nonexistent-999.json please check."
        },
    }
    result = run_preflight(stdin_payload)
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"


# ── AC4a: files_modified gitignored but waiver present → exit 0 ─────────────

def test_ac4a_files_modified_with_waiver_exits_0(tmp_path):
    """AC4a: files_modified has gitignored path but non-empty waiver → exit 0."""
    task_id = "test-ac4a-20260524"
    report_rel = make_report(
        tmp_path,
        task_id,
        files_modified=["docs/some-doc.md"],
        files_created=[],
        waiver="tracked via explicit exception",
    )
    try:
        result = run_preflight(make_stdin(report_rel))
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}. stderr={result.stderr!r}"
    finally:
        report_path = REPO / report_rel
        report_path.unlink(missing_ok=True)


# ── AC4b: files_created gitignored but waiver present → exit 0 ──────────────

def test_ac4b_files_created_with_waiver_exits_0(tmp_path):
    """AC4b: files_created has gitignored path but non-empty waiver → exit 0."""
    task_id = "test-ac4b-20260524"
    report_rel = make_report(
        tmp_path,
        task_id,
        files_modified=[],
        files_created=["docs/new-doc.md"],
        waiver="tracked via explicit exception",
    )
    try:
        result = run_preflight(make_stdin(report_rel))
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}. stderr={result.stderr!r}"
    finally:
        report_path = REPO / report_rel
        report_path.unlink(missing_ok=True)


# ── AC5: no dev-report path in prompt → exit 0 (no-op) ──────────────────────

def test_ac5_no_report_path_in_prompt_exits_0():
    """AC5: Agent prompt has no docs/dev/dev-report-*.json reference → exit 0."""
    stdin_payload = {
        "tool_name": "Agent",
        "tool_input": {
            "prompt": "Run the QA suite and check the results"
        },
    }
    result = run_preflight(stdin_payload)
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"


# ── AC6: registration in settings.json + executable bit ─────────────────────

def test_ac6_registered_in_settings_and_executable():
    """AC6: settings.json has Agent matcher entry with pretool-gitignore-preflight.py;
    hook file exists with executable bit set."""
    settings_path = REPO / "settings.json"
    with open(settings_path) as f:
        settings = json.load(f)

    pre_tool_use = settings.get("hooks", {}).get("PreToolUse", [])
    agent_entry = None
    for entry in pre_tool_use:
        matcher = entry.get("matcher", "")
        if "Agent" in matcher:
            agent_entry = entry
            break

    assert agent_entry is not None, "No PreToolUse entry with matcher containing 'Agent' found"

    commands = [h.get("command", "") for h in agent_entry.get("hooks", [])]
    found = any("pretool-gitignore-preflight.py" in cmd for cmd in commands)
    assert found, f"pretool-gitignore-preflight.py not found in Agent matcher hooks: {commands}"

    hook_path = REPO / "hooks" / "pretool-gitignore-preflight.py"
    assert hook_path.exists(), f"Hook file does not exist: {hook_path}"
    mode = hook_path.stat().st_mode
    assert mode & 0o111 != 0, f"Hook file is not executable: mode={oct(mode)}"


# ── AC7: EISDIR harness — increment branch (n=0) fails gracefully → exit 0 ──

def test_ac7_eisdir_increment_branch_exits_0():
    """AC7: COUNTER_FILE pre-created as directory (EISDIR) causes write failure in
    increment branch. Hook must exit 0 with empty stdout and empty stderr."""
    counter_file = "/tmp/claude-pressure-warn-test-enospc-ac7"
    lock_file = counter_file + ".lock"

    # Pre-create COUNTER_FILE as directory
    if os.path.isdir(counter_file):
        pass  # already a dir
    elif os.path.exists(counter_file):
        os.remove(counter_file)
    os.makedirs(counter_file, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        # df shim: emit >75% for both /tmp and /dev/shm
        shim_df = os.path.join(tmpdir, "df")
        with open(shim_df, "w") as f:
            f.write("#!/bin/bash\necho 'Use%'\necho '76%'\necho '77%'\n")
        os.chmod(shim_df, 0o755)

        env = os.environ.copy()
        env["PATH"] = tmpdir + ":" + env.get("PATH", "")

        stdin_data = json.dumps({"session_id": "test-enospc-ac7"})
        result = subprocess.run(
            ["bash", str(HOOK_PRESSURE)],
            input=stdin_data,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(REPO),
        )

    # Cleanup
    try:
        if os.path.isdir(counter_file):
            os.rmdir(counter_file)
        if os.path.exists(lock_file):
            os.remove(lock_file)
    except Exception:
        pass

    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}. stderr={result.stderr!r}"
    assert result.stdout == "", f"Expected empty stdout, got: {result.stdout!r}"
    assert result.stderr == "", f"Expected empty stderr, got: {result.stderr!r}"


# ── AC7b: EISDIR harness — saturated branch (n=3, cat shim) fails gracefully ─

def test_ac7b_eisdir_saturated_branch_exits_0():
    """AC7b: COUNTER_FILE pre-created as directory; cat shim emits '3' (RATE_LIMIT)
    to trigger the mtime-refresh branch. Write fails with EISDIR; hook must exit 0
    with empty stdout and empty stderr."""
    counter_file = "/tmp/claude-pressure-warn-test-enospc-ac7b"
    lock_file = counter_file + ".lock"

    # Pre-create COUNTER_FILE as directory
    if os.path.isdir(counter_file):
        pass
    elif os.path.exists(counter_file):
        os.remove(counter_file)
    os.makedirs(counter_file, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        # df shim
        shim_df = os.path.join(tmpdir, "df")
        with open(shim_df, "w") as f:
            f.write("#!/bin/bash\necho 'Use%'\necho '76%'\necho '77%'\n")
        os.chmod(shim_df, 0o755)

        # cat shim: emits '3' (the RATE_LIMIT value) so n >= RATE_LIMIT fires
        shim_cat = os.path.join(tmpdir, "cat")
        with open(shim_cat, "w") as f:
            f.write("#!/bin/bash\necho 3\n")
        os.chmod(shim_cat, 0o755)

        env = os.environ.copy()
        env["PATH"] = tmpdir + ":" + env.get("PATH", "")

        stdin_data = json.dumps({"session_id": "test-enospc-ac7b"})
        result = subprocess.run(
            ["bash", str(HOOK_PRESSURE)],
            input=stdin_data,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(REPO),
        )

    # Cleanup
    try:
        if os.path.isdir(counter_file):
            os.rmdir(counter_file)
        if os.path.exists(lock_file):
            os.remove(lock_file)
    except Exception:
        pass

    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}. stderr={result.stderr!r}"
    assert result.stdout == "", f"Expected empty stdout, got: {result.stdout!r}"
    assert result.stderr == "", f"Expected empty stderr, got: {result.stderr!r}"


# ── AC8: source contains 'if ! printf' at counter-increment line ─────────────

def test_ac8_source_contains_if_not_printf():
    """AC8: patched file contains 'if ! printf' (failure-aware increment write)
    and bash -n exits 0."""
    content = HOOK_PRESSURE.read_text()
    assert "if ! printf" in content, "Expected 'if ! printf' in userprompt-tmpfs-pressure.sh"
    assert "echo $((n + 1)) >" not in content, "Bare 'echo $((n + 1)) >' must not exist after patch"

    result = subprocess.run(
        ["bash", "-n", str(HOOK_PRESSURE)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"bash -n failed: {result.stderr!r}"


# ── AC9: source contains mtime-refresh guard with || ────────────────────────

def test_ac9_mtime_refresh_guard_present():
    """AC9: patched file contains the || { printf 'skip'; exit 0; } guard on the
    mtime-refresh write line (~115); bash -n exits 0."""
    content = HOOK_PRESSURE.read_text()
    # Check that $COUNTER_FILE appears in context with || on the mtime-refresh line
    assert '$COUNTER_FILE" ||' in content or '$COUNTER_FILE" 2>/dev/null > "$COUNTER_FILE" ||' in content or \
        ('$COUNTER_FILE' in content and '||' in content and 'printf \'skip\'' in content), \
        "Expected || { printf 'skip'; exit 0; } guard after mtime-refresh write to $COUNTER_FILE"

    # More specific: the line with n (not n+1) and $COUNTER_FILE must have ||
    lines = content.splitlines()
    found = False
    for line in lines:
        if '$COUNTER_FILE' in line and '||' in line and '"$n"' in line:
            found = True
            break
    assert found, "No line with '$n' write to '$COUNTER_FILE' followed by '||' found"

    result = subprocess.run(
        ["bash", "-n", str(HOOK_PRESSURE)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"bash -n failed: {result.stderr!r}"


# ── AC10: negation-excepted path (logs/lifecycle.jsonl) → exit 0 ─────────────

def test_ac10_negation_excepted_path_exits_0():
    """AC10: logs/lifecycle.jsonl is caught by logs/* rule but excepted by
    !logs/lifecycle.jsonl; git check-ignore returns rc=1 (not ignored).
    Hook must exit 0."""
    # Precondition: verify the negation exception is active in this repo
    git_check = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", "--", "logs/lifecycle.jsonl"],
        capture_output=True,
        cwd=str(REPO),
    )
    if git_check.returncode == 0:
        pytest.skip("logs/lifecycle.jsonl is currently gitignored in this repo; negation exception not present")

    task_id = "test-ac10-20260524"
    report_rel = make_report(
        None,
        task_id,
        files_modified=["logs/lifecycle.jsonl"],
        files_created=[],
    )
    try:
        result = run_preflight(make_stdin(report_rel))
        assert result.returncode == 0, f"Expected exit 0 for negation-excepted path, got {result.returncode}. stderr={result.stderr!r}"
    finally:
        report_path = REPO / report_rel
        report_path.unlink(missing_ok=True)


# ── AC11: empty-string waiver is rejected → exit 2 ───────────────────────────

def test_ac11_empty_waiver_not_accepted_exits_2():
    """AC11: gitignore_waiver="" (empty string) is not accepted; hook must exit 2."""
    task_id = "test-ac11-20260524"
    report_rel = make_report(
        None,
        task_id,
        files_modified=["docs/some-doc.md"],
        files_created=[],
        waiver="",
    )
    try:
        result = run_preflight(make_stdin(report_rel))
        assert result.returncode == 2, f"Expected exit 2 for empty waiver, got {result.returncode}. stderr={result.stderr!r}"
        assert "BLOCKED" in result.stderr
    finally:
        report_path = REPO / report_rel
        report_path.unlink(missing_ok=True)
