#!/usr/bin/env python3
"""
PostToolUse Hook: Session-scoped staging ledger writer.

Triggered after every Edit, Write, or NotebookEdit tool call.
Appends a JSONL entry to /var/lib/claude/ledger/<sid>.jsonl with full
content-bound authority fields. Exit 0 always (PostToolUse cannot block).

Ledger schema (all fields required):
  {sid, seq, epoch, path, action, mode, blob_sha, first_touch_preimage_sha,
   tool_call_id, ts, repo_root, corruption_flag}

TOCTOU safety: file bytes read once into memory, same bytes fed to
git hash-object --stdin. No second disk read between SHA compute and blob write.
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

LEDGER_BASE = Path("/var/lib/claude/ledger")


def _ensure_dirs() -> None:
    LEDGER_BASE.mkdir(parents=True, exist_ok=True)
    os.chmod(LEDGER_BASE, 0o700)


def _repo_root() -> str:
    r = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True
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


def _git_ls_tree_blob(repo_root: str, path: str) -> str:
    """Return HEAD tree blob SHA for path, or empty string if not tracked."""
    r = subprocess.run(
        ["git", "ls-tree", "HEAD", path],
        capture_output=True, text=True, cwd=repo_root
    )
    if r.returncode != 0 or not r.stdout.strip():
        return ""
    parts = r.stdout.strip().split()
    # format: <mode> <type> <sha>\t<path>
    return parts[2] if len(parts) >= 3 else ""


def _resolve_path(tool_name: str, tool_input: dict) -> str | None:
    """Extract and resolve file path from tool input."""
    if tool_name == "NotebookEdit":
        raw = tool_input.get("notebook_path", "")
    else:
        raw = tool_input.get("file_path", "")
    if not raw:
        return None
    return str(Path(raw).resolve())


def _get_mode(abs_path: str) -> tuple[int, bool]:
    """Return (git_mode, corruption_flag). Reads lstat only."""
    try:
        st = os.lstat(abs_path)
    except OSError:
        return 100644, False
    if stat.S_ISLNK(st.st_mode):
        return 120000, False
    if stat.S_ISFIFO(st.st_mode) or stat.S_ISBLK(st.st_mode) or \
       stat.S_ISCHR(st.st_mode) or stat.S_ISSOCK(st.st_mode):
        return 100644, True
    if st.st_mode & stat.S_IXUSR:
        return 100755, False
    return 100644, False


def _get_first_touch_preimage(
    ledger_path: Path, sid: str, rel_path: str, epoch: int, repo_root: str
) -> str | None:
    """
    Return first_touch_preimage_sha for this path in this epoch.
    If there is already a ledger entry for (sid, rel_path, epoch), return None
    (not first touch). If this is the first touch: return HEAD blob SHA or None.
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
    # First touch: use HEAD blob
    blob = _git_ls_tree_blob(repo_root, rel_path)
    return blob if blob else None


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
    max_seq = 0
    if not ledger_path.exists():
        return 0
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


def _tool_call_id_exists(ledger_path: Path, tool_call_id: str) -> bool:
    """Check if this tool_call_id already exists (idempotent retry guard)."""
    if not ledger_path.exists():
        return False
    with open(ledger_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("tool_call_id") == tool_call_id:
                return True
    return False


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name not in ("Edit", "Write", "NotebookEdit"):
        sys.exit(0)

    tool_input = data.get("tool_input") or {}
    tool_result = data.get("tool_response") or data.get("tool_result") or {}
    sid = data.get("session_id") or os.environ.get("CLAUDE_SESSION_ID", "unknown")
    tool_call_id = data.get("tool_call_id") or data.get("tool_use_id") or ""

    abs_path = _resolve_path(tool_name, tool_input)
    if not abs_path:
        sys.exit(0)

    repo_root = _repo_root()
    if not repo_root:
        sys.exit(0)

    # Compute repo-relative path
    try:
        rel_path = str(Path(abs_path).relative_to(repo_root))
    except ValueError:
        sys.exit(0)

    _ensure_dirs()
    ledger_path = LEDGER_BASE / f"{sid}.jsonl"
    lock_path = LEDGER_BASE / f"{sid}.jsonl.lock"

    # Determine action
    action = "upsert"
    if not Path(abs_path).exists():
        action = "delete"

    # Get mode and corruption flag before reading content
    git_mode, corruption_flag = _get_mode(abs_path)

    blob_sha = None
    if action == "upsert" and not corruption_flag:
        if git_mode == 120000:
            # Symlink: hash link target text, not followed file
            try:
                link_target = os.readlink(abs_path)
                content = link_target.encode()
            except OSError:
                content = b""
        else:
            # Single read into memory for TOCTOU safety
            try:
                with open(abs_path, "rb") as f:
                    content = f.read()
            except OSError:
                content = b""
        blob_sha = _git_hash_object_write(content) or None

    with open(lock_path, "w") as lock_f:
        fcntl.flock(lock_f, fcntl.LOCK_EX)
        try:
            # Idempotent retry: skip duplicate tool_call_id
            if tool_call_id and _tool_call_id_exists(ledger_path, tool_call_id):
                sys.exit(0)

            # Epoch read inside flock to avoid race with /commit marking consumed
            epoch = _get_epoch(sid)
            seq = _get_max_seq(ledger_path, sid) + 1
            first_touch = _get_first_touch_preimage(
                ledger_path, sid, rel_path, epoch, repo_root
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
                "tool_call_id": tool_call_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "repo_root": repo_root,
                "corruption_flag": corruption_flag,
            }

            with open(ledger_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)

    sys.exit(0)


if __name__ == "__main__":
    main()
