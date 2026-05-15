#!/usr/bin/env python3
"""
PreToolUse Hook: Content preimage verification guard.

Triggered before Edit, Write, or NotebookEdit tool calls.
Refuses the operation if the file on disk does not match the expected preimage
(session's last staged postimage, or HEAD blob for first touch).

Exit 2 = refuse the tool call (BLOCKED).
Exit 0 = allow.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

LEDGER_BASE = Path("/var/lib/claude/ledger")


def _git_hash_object_no_write(path: str) -> str:
    """Return git blob SHA for file on disk without writing to object store."""
    r = subprocess.run(
        ["git", "hash-object", path],
        capture_output=True, text=True
    )
    return r.stdout.strip() if r.returncode == 0 else ""


def _git_ls_tree_blob(path: str) -> str:
    """Return HEAD tree blob SHA for path, or empty string if not tracked."""
    r = subprocess.run(
        ["git", "ls-tree", "HEAD", path],
        capture_output=True, text=True
    )
    if r.returncode != 0 or not r.stdout.strip():
        return ""
    parts = r.stdout.strip().split()
    return parts[2] if len(parts) >= 3 else ""


def _git_ls_files_check(path: str) -> bool:
    """Return True if path is tracked by git (in HEAD or index)."""
    r = subprocess.run(
        ["git", "ls-files", "--error-unmatch", path],
        capture_output=True
    )
    return r.returncode == 0


def _resolve_path(tool_name: str, tool_input: dict) -> str | None:
    if tool_name == "NotebookEdit":
        raw = tool_input.get("notebook_path", "")
    else:
        raw = tool_input.get("file_path", "")
    if not raw:
        return None
    return str(Path(raw).resolve())


def _check_special_file(abs_path: str) -> bool:
    """Return True if path is a special file (FIFO/device/socket)."""
    try:
        st = os.lstat(abs_path)
    except OSError:
        return False
    return (stat.S_ISFIFO(st.st_mode) or stat.S_ISBLK(st.st_mode) or
            stat.S_ISCHR(st.st_mode) or stat.S_ISSOCK(st.st_mode))


def _get_expected_preimage(sid: str, rel_path: str) -> str | None:
    """
    Return expected preimage SHA for (sid, path):
    - Latest blob_sha from ledger (postimage of last write = preimage of next)
    - Or HEAD blob SHA if no ledger entry exists for this path in this sid
    - Or None if path is new (not in HEAD, no ledger entry)
    """
    ledger_path = LEDGER_BASE / f"{sid}.jsonl"
    if ledger_path.exists():
        best_seq = -1
        best_blob = None
        with open(ledger_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("path") == rel_path and entry.get("sid") == sid:
                    seq = entry.get("seq", 0)
                    if seq > best_seq:
                        best_seq = seq
                        best_blob = entry.get("blob_sha")
        if best_seq >= 0:
            return best_blob  # may be None for delete entries

    # No ledger entry: use HEAD blob
    return _git_ls_tree_blob(rel_path) or None


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name not in ("Edit", "Write", "NotebookEdit"):
        sys.exit(0)

    tool_input = data.get("tool_input") or {}
    sid = data.get("session_id") or os.environ.get("CLAUDE_SESSION_ID", "unknown")

    abs_path = _resolve_path(tool_name, tool_input)
    if not abs_path:
        sys.exit(0)

    # Special file check
    if _check_special_file(abs_path):
        sys.stderr.write(
            f"BLOCKED: special file type rejected: {abs_path}\n"
            "Cannot stage FIFO, device, or socket files.\n"
        )
        sys.exit(2)

    # If file doesn't exist on disk and is untracked, it's a new file — allow
    if not Path(abs_path).exists():
        sys.exit(0)

    # Get repo root and relative path
    r = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        sys.exit(0)
    repo_root = r.stdout.strip()

    try:
        rel_path = str(Path(abs_path).relative_to(repo_root))
    except ValueError:
        sys.exit(0)

    # If new untracked file (not in HEAD, no ledger entry): allow
    is_tracked = _git_ls_files_check(rel_path)
    expected = _get_expected_preimage(sid, rel_path)

    if expected is None and not is_tracked:
        # Truly new file, never touched before
        sys.exit(0)

    if expected is None:
        # Tracked in HEAD but no preimage info — allow (e.g., brand new session)
        sys.exit(0)

    # Compute disk SHA (no write)
    actual = _git_hash_object_no_write(abs_path)

    if actual != expected:
        sys.stderr.write(
            f"BLOCKED: preimage mismatch on {rel_path}.\n"
            f"Expected {expected} got {actual}.\n"
            "Another session or manual edit has changed this file since your last write.\n"
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
