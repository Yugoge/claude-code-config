#!/usr/bin/env python3
"""
Tests for arch-3 phase 2 micro-fix: LOCK_FILE EISDIR stderr leak fix.
Task: 20260524-205459
ACs: AC_SRC, AC7c, AC7_regression, AC7b_regression
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
HOOK_PRESSURE = REPO / "hooks" / "userprompt-tmpfs-pressure.sh"


# ── AC_SRC: redirect order is correct in source ──────────────────────────────

def test_ac_src_redirect_order_correct():
    """AC_SRC: file contains '} 2>/dev/null 9> \"$LOCK_FILE\"' and bash -n exits 0."""
    content = HOOK_PRESSURE.read_text()
    assert '} 2>/dev/null 9> "$LOCK_FILE"' in content, (
        "Expected '} 2>/dev/null 9> \"$LOCK_FILE\"' in userprompt-tmpfs-pressure.sh"
    )
    # Old (incorrect) order must not be present
    assert '} 9> "$LOCK_FILE" 2>/dev/null' not in content, (
        "Old redirect order '} 9> \"$LOCK_FILE\" 2>/dev/null' must not be present after patch"
    )
    result = subprocess.run(
        ["bash", "-n", str(HOOK_PRESSURE)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"bash -n failed: {result.stderr!r}"


# ── AC7c: LOCK_FILE pre-created as directory → rc=0, stdout='', stderr='' ────

def test_ac7c_lockfile_eisdir_stderr_silenced():
    """AC7c: LOCK_FILE pre-created as directory (EISDIR); hook must exit 0 with
    empty stdout and empty stderr (9> failure is silenced by leading 2>/dev/null)."""
    session_id = "test-enospc-ac7c"
    lock_file = f"/tmp/claude-pressure-warn-{session_id}.lock"

    # Pre-create LOCK_FILE as a directory to trigger EISDIR on 9> open
    if os.path.isdir(lock_file):
        pass  # already a dir
    elif os.path.exists(lock_file):
        os.remove(lock_file)
    os.makedirs(lock_file, exist_ok=True)

    # Also pre-create the COUNTER_FILE as a regular file (not a dir)
    # so the COUNTER_FILE EISDIR path is NOT triggered — only the LOCK_FILE path
    counter_file = f"/tmp/claude-pressure-warn-{session_id}"
    if os.path.isdir(counter_file):
        try:
            os.rmdir(counter_file)
        except OSError:
            pass
    # Leave counter_file absent (fresh session, n=0 via absent cat output)

    with tempfile.TemporaryDirectory() as tmpdir:
        # df shim: emit >75% for /tmp and /dev/shm to activate the pressure branch
        shim_df = os.path.join(tmpdir, "df")
        with open(shim_df, "w") as f:
            f.write("#!/bin/bash\necho 'Use%'\necho '76%'\necho '77%'\n")
        os.chmod(shim_df, 0o755)

        env = os.environ.copy()
        env["PATH"] = tmpdir + ":" + env.get("PATH", "")

        stdin_data = json.dumps({"session_id": session_id})
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
        if os.path.isdir(lock_file):
            os.rmdir(lock_file)
        elif os.path.exists(lock_file):
            os.remove(lock_file)
    except Exception:
        pass
    try:
        if os.path.isdir(counter_file):
            os.rmdir(counter_file)
        elif os.path.exists(counter_file):
            os.remove(counter_file)
    except Exception:
        pass

    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}. stderr={result.stderr!r}"
    )
    assert result.stdout == "", f"Expected empty stdout, got: {result.stdout!r}"
    assert result.stderr == "", f"Expected empty stderr, got: {result.stderr!r}"


# ── AC7_regression: COUNTER_FILE EISDIR increment branch still exits 0 ───────

def test_ac7_regression_eisdir_increment_branch_exits_0():
    """AC7_regression: COUNTER_FILE pre-created as directory (EISDIR) in increment
    branch. Verifies arch-3 Cycle 3 (AC7) fix was not regressed."""
    counter_file = "/tmp/claude-pressure-warn-test-enospc-ac7"
    lock_file = counter_file + ".lock"

    # Pre-create COUNTER_FILE as directory
    if os.path.isdir(counter_file):
        pass
    elif os.path.exists(counter_file):
        os.remove(counter_file)
    os.makedirs(counter_file, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
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

    assert result.returncode == 0, (
        f"AC7 regression: Expected exit 0, got {result.returncode}. stderr={result.stderr!r}"
    )
    assert result.stdout == "", f"AC7 regression: Expected empty stdout, got: {result.stdout!r}"
    assert result.stderr == "", f"AC7 regression: Expected empty stderr, got: {result.stderr!r}"


# ── AC7b_regression: COUNTER_FILE EISDIR saturated branch still exits 0 ─────

def test_ac7b_regression_eisdir_saturated_branch_exits_0():
    """AC7b_regression: COUNTER_FILE pre-created as directory; cat shim emits '3'
    (RATE_LIMIT) to trigger mtime-refresh branch. Verifies arch-3 Cycle 3 (AC7b)
    fix was not regressed."""
    counter_file = "/tmp/claude-pressure-warn-test-enospc-ac7b"
    lock_file = counter_file + ".lock"

    # Pre-create COUNTER_FILE as directory
    if os.path.isdir(counter_file):
        pass
    elif os.path.exists(counter_file):
        os.remove(counter_file)
    os.makedirs(counter_file, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
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

    assert result.returncode == 0, (
        f"AC7b regression: Expected exit 0, got {result.returncode}. stderr={result.stderr!r}"
    )
    assert result.stdout == "", f"AC7b regression: Expected empty stdout, got: {result.stdout!r}"
    assert result.stderr == "", f"AC7b regression: Expected empty stderr, got: {result.stderr!r}"
