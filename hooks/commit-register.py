#!/usr/bin/env python3
"""
commit-register.py -- Manually register a Bash-written file into the session ledger.

Usage:
  python3 commit-register.py <absolute-or-relative-path>
  python3 commit-register.py --delete <absolute-or-relative-path>

Options:
  --delete  Register an intentional file deletion (action=delete, blob_sha=null).
            Use when the file has already been removed from disk.

Exit codes:
  0  Entry appended to ledger successfully.
  2  Error: file not in git repo, SID not set, path not resolvable,
     or file does not exist on disk without --delete.

Mirrors posttool-ledger-writer.py locking and schema exactly.
Adds source=manual_register for audit traceability.
"""

from __future__ import annotations

import fcntl
import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

LEDGER_BASE = Path(os.environ.get("CLAUDE_LEDGER_BASE", "/var/lib/claude/ledger"))


def _die(msg: str) -> None:
    sys.stderr.write(msg + "\n")
    sys.exit(2)


def _ensure_dirs() -> None:
    LEDGER_BASE.mkdir(parents=True, exist_ok=True)
    os.chmod(LEDGER_BASE, 0o700)


def _repo_root(cwd: str) -> str:
    r = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, cwd=cwd
    )
    return r.stdout.strip() if r.returncode == 0 else ""


def _git_hash_object_write(content: bytes) -> str:
    """Write blob to git object store. Returns 40-char SHA or empty on error."""
    r = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        input=content, capture_output=True
    )
    if r.returncode != 0:
        return ""
    return r.stdout.strip().decode()


def _git_ls_tree_blob(repo_root: str, rel_path: str) -> str:
    """Return HEAD tree blob SHA for path, or empty string if not tracked."""
    r = subprocess.run(
        ["git", "ls-tree", "HEAD", rel_path],
        capture_output=True, text=True, cwd=repo_root
    )
    if r.returncode != 0 or not r.stdout.strip():
        return ""
    parts = r.stdout.strip().split()
    return parts[2] if len(parts) >= 3 else ""


def _get_mode(abs_path: str) -> tuple[int, bool]:
    """Return (git_mode, corruption_flag). Reads lstat only."""
    try:
        st = os.lstat(abs_path)
    except OSError:
        return 100644, False
    if stat.S_ISLNK(st.st_mode):
        return 120000, False
    if (stat.S_ISFIFO(st.st_mode) or stat.S_ISBLK(st.st_mode) or
            stat.S_ISCHR(st.st_mode) or stat.S_ISSOCK(st.st_mode)):
        return 100644, True
    if st.st_mode & stat.S_IXUSR:
        return 100755, False
    return 100644, False


def _get_epoch(sid: str) -> int:
    """Epoch = count of entries in consumed.json sidecar."""
    consumed = LEDGER_BASE / f"{sid}.consumed.json"
    if not consumed.exists():
        return 0
    try:
        data = json.loads(consumed.read_text())
        if isinstance(data, list):
            return len(data)
    except Exception:
        pass
    return 0


def _get_max_seq(ledger_path: Path, sid: str) -> int:
    """Return current max seq for this sid, or 0."""
    if not ledger_path.exists():
        return 0
    max_seq = 0
    with open(ledger_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("sid") == sid:
                max_seq = max(max_seq, entry.get("seq", 0))
    return max_seq


def _get_first_touch_preimage(
    ledger_path: Path, sid: str, rel_path: str, epoch: int, repo_root: str
) -> str | None:
    """
    Return first_touch_preimage_sha for this path in this epoch.
    If already written in this epoch, return None (not first touch).
    Otherwise return HEAD blob SHA.
    """
    if ledger_path.exists():
        with open(ledger_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (entry.get("sid") == sid and
                        entry.get("path") == rel_path and
                        entry.get("epoch") == epoch):
                    return None  # not first touch in this epoch
    blob = _git_ls_tree_blob(repo_root, rel_path)
    return blob if blob else None


def main() -> None:
    args = sys.argv[1:]
    delete_mode = False

    if "--delete" in args:
        delete_mode = True
        args = [a for a in args if a != "--delete"]

    if not args:
        _die(
            "Usage: commit-register.py [--delete] <path>\n"
            "  --delete  Register an intentional file deletion."
        )

    raw_path = args[0]

    # Resolve to absolute path
    abs_path = os.path.abspath(raw_path)

    # SID check
    sid = (os.environ.get("CLAUDE_SESSION_ID") or
           os.environ.get("CLAUDE_CODE_SESSION_ID") or "")
    if not sid:
        _die("Error: CLAUDE_SESSION_ID not set -- cannot identify session ledger.")

    # Repo root check
    path_dir = os.path.dirname(abs_path) if not os.path.isdir(abs_path) else abs_path
    repo = _repo_root(path_dir if os.path.isdir(path_dir) else os.getcwd())
    if not repo:
        _die(f"Error: {abs_path} is not inside a git repository.")

    # Repo-relative path
    try:
        rel_path = str(Path(abs_path).relative_to(repo))
    except ValueError:
        _die(f"Error: {abs_path} is not inside repo root {repo}.")

    if delete_mode:
        action = "delete"
        blob_sha = None
        git_mode = 100644
        corruption_flag = False
    else:
        # File must exist on disk for upsert registration
        if not os.path.lexists(abs_path):
            _die(
                f"Error: {abs_path} does not exist on disk.\n"
                "If this is an intentional deletion, use --delete flag."
            )
        action = "upsert"
        git_mode, corruption_flag = _get_mode(abs_path)

        if git_mode == 120000:
            try:
                link_target = os.readlink(abs_path)
                content = link_target.encode()
            except OSError:
                content = b""
        else:
            try:
                with open(abs_path, "rb") as f:
                    content = f.read()
            except OSError:
                content = b""
        blob_sha = _git_hash_object_write(content) or None
        if not blob_sha and not corruption_flag:
            _die(f"Error: failed to hash {abs_path} into git object store.")

    _ensure_dirs()
    ledger_path = LEDGER_BASE / f"{sid}.jsonl"
    lock_path = LEDGER_BASE / f"{sid}.jsonl.lock"

    with open(lock_path, "w") as lock_f:
        fcntl.flock(lock_f, fcntl.LOCK_EX)
        try:
            epoch = _get_epoch(sid)
            seq = _get_max_seq(ledger_path, sid) + 1
            first_touch = _get_first_touch_preimage(
                ledger_path, sid, rel_path, epoch, repo
            )

            entry = {
                "sid": sid,
                "seq": seq,
                "epoch": epoch,
                "path": rel_path,
                "action": action,
                "mode": git_mode,
                "blob_sha": blob_sha,
                "first_touch_preimage_sha": first_touch,
                "tool_call_id": None,
                "ts": datetime.now(timezone.utc).isoformat(),
                "repo_root": repo,
                "corruption_flag": corruption_flag,
                "source": "manual_register",
            }

            with open(ledger_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)

    sys.stdout.write(
        f"Registered {action} for {rel_path} (seq={seq}, blob_sha={blob_sha})\n"
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
