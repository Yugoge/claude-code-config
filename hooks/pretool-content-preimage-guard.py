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

LEDGER_BASE = Path(os.environ.get("CLAUDE_LEDGER_BASE", "/var/lib/claude/ledger"))


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


def _git_ls_tree_mode(path: str) -> int | None:
    """Return HEAD tree mode (int) for path, or None if not tracked."""
    r = subprocess.run(
        ["git", "ls-tree", "HEAD", path],
        capture_output=True, text=True
    )
    if r.returncode != 0 or not r.stdout.strip():
        return None
    parts = r.stdout.strip().split()
    try:
        return int(parts[0]) if len(parts) >= 3 else None
    except ValueError:
        return None


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
    return os.path.abspath(raw)


def _check_special_file(abs_path: str) -> bool:
    """Return True if path is a special file (FIFO/device/socket)."""
    try:
        st = os.lstat(abs_path)
    except OSError:
        return False
    return (stat.S_ISFIFO(st.st_mode) or stat.S_ISBLK(st.st_mode) or
            stat.S_ISCHR(st.st_mode) or stat.S_ISSOCK(st.st_mode))


def _get_expected_preimage(sid: str, rel_path: str) -> tuple[str | None, int | None]:
    """
    Return (expected_preimage_sha, mode) for (sid, path):
    - Latest blob_sha and mode from ledger (postimage of last write = preimage of next)
    - Or HEAD blob SHA and mode if no ledger entry exists for this path in this sid
    - Or (None, None) if path is new (not in HEAD, no ledger entry)
    """
    ledger_path = LEDGER_BASE / f"{sid}.jsonl"
    if ledger_path.exists():
        best_seq = -1
        best_blob = None
        best_mode = None
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
                        best_mode = entry.get("mode")
        if best_seq >= 0:
            return (best_blob, best_mode)  # blob may be None for delete entries

    # No ledger entry: use HEAD blob and mode
    head_blob = _git_ls_tree_blob(rel_path) or None
    head_mode = _git_ls_tree_mode(rel_path) if head_blob else None
    return (head_blob, head_mode)


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

    # If file doesn't exist on disk (lexists=False means the path itself is absent) it's a new file — allow
    # Use lexists so dangling symlinks (link-file exists but target absent) proceed to the mode-aware SHA check
    if not os.path.lexists(abs_path):
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
    expected, expected_mode = _get_expected_preimage(sid, rel_path)

    if expected is None and not is_tracked:
        # Truly new file, never touched before
        sys.exit(0)

    if expected is None:
        # Tracked in HEAD but no preimage info — allow (e.g., brand new session)
        sys.exit(0)

    # Compute disk SHA (no write); mode-aware for symlinks (mode 120000)
    if expected_mode == 120000:
        try:
            link_target = os.readlink(abs_path)
            disk_result = subprocess.run(
                ["git", "hash-object", "--stdin"],
                input=link_target.encode(),
                capture_output=True
            )
            actual = disk_result.stdout.strip().decode() if disk_result.returncode == 0 else ""
        except OSError:
            sys.stderr.write(
                f"BLOCKED: preimage mismatch on {rel_path}.\n"
                "Expected symlink but os.readlink() failed.\n"
            )
            sys.exit(2)
    else:
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
