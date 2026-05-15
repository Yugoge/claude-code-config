#!/usr/bin/env python3
"""
commit-cas.py -- CAS commit engine for /commit slash command.

Called by commit.sh after arg parse and M3 lint.
Reads environment: SID, LEDGER_FILE, CONSUMED_FILE, AUDIT_BASE, MSG.
Performs steps 4b through 19 of the commit algorithm.

No flags. No modes. No helpers. Content-bound authority via ledger blob SHAs.
"""
from __future__ import annotations

import fcntl
import glob
import hashlib
import json
import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

AUDIT_BASE = os.environ.get("AUDIT_BASE", "/var/lib/claude/audit")
LEDGER_FILE = os.environ.get("LEDGER_FILE", "")
CONSUMED_FILE = os.environ.get("CONSUMED_FILE", "")
SID = os.environ.get("SID", os.environ.get("CLAUDE_SESSION_ID", ""))
MSG = os.environ.get("MSG", "")
LEDGER_BASE = str(Path(LEDGER_FILE).parent) if LEDGER_FILE else "/var/lib/claude/ledger"


def run(cmd, **kw):
    return subprocess.run(cmd, **{"capture_output": True, "text": True, **kw})


def repo_root() -> str:
    return run(["git", "rev-parse", "--show-toplevel"]).stdout.strip()


def current_branch() -> str:
    return run(["git", "branch", "--show-current"]).stdout.strip()


def die(msg: str) -> None:
    sys.stderr.write(msg + "\n")
    sys.exit(2)


# Step 4b: Filter unconsumed ledger entries
consumed_seqs: set[int] = set()
try:
    data = json.loads(open(CONSUMED_FILE).read())
    for entry in data:
        # New format: explicit list
        if "consumed_seqs" in entry:
            consumed_seqs.update(entry["consumed_seqs"])
        # Legacy format: min/max range (backward compat)
        elif "consumed_seq_range" in entry:
            lo, hi = entry.get("consumed_seq_range", [0, 0])
            consumed_seqs.update(range(lo, hi + 1))
except Exception:
    pass

entries: list[dict] = []
try:
    with open(LEDGER_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("sid") != SID:
                continue
            if e.get("seq", 0) in consumed_seqs:
                continue
            entries.append(e)
except Exception as exc:
    die(f"nothing to commit -- cannot read ledger: {exc}")

if not entries:
    die("nothing to commit -- ledger is empty for this session")

# Step 5: Recovery scan
audit_sid_dir = os.path.join(AUDIT_BASE, SID)
os.makedirs(audit_sid_dir, mode=0o700, exist_ok=True)

for pre_cas in glob.glob(os.path.join(audit_sid_dir, "pre-cas-*.json")):
    try:
        adat = json.loads(open(pre_cas).read())
        csha = adat.get("commit_sha")
        if not csha or len(csha) != 40:
            continue
        branch = adat.get("branch", current_branch())
        result = run(["git", "merge-base", "--is-ancestor", csha,
                      f"refs/heads/{branch}"])
        if result.returncode == 0:
            adat["status"] = "committed"
            target = os.path.join(audit_sid_dir, f"{csha}.json")
        else:
            adat["status"] = "orphaned"
            target = os.path.join(audit_sid_dir, f"{csha}.orphaned.json")
        open(target, "w").write(json.dumps(adat, indent=2))
        os.unlink(pre_cas)
    except Exception:
        pass

# Step 6: Corruption check
corrupted = [e["path"] for e in entries if e.get("corruption_flag")]
if corrupted:
    die("BLOCKED: corrupted ledger entries for paths:\n  " + "\n  ".join(corrupted))

# Step 7: Repo identity check
rroot = repo_root()
entries = [e for e in entries if e.get("repo_root") == rroot]
if not entries:
    die("nothing to commit -- no ledger entries match current repo root")

# Step 8: Group by path, max seq per path per current epoch.
# Carry forward the epoch's first-touch preimage so multiple edits to the
# same file in one epoch don't falsely look like "new file vs tracked HEAD".
epoch = 0
try:
    epoch = len(json.loads(open(CONSUMED_FILE).read()))
except Exception:
    pass

epoch_entries = [e for e in entries if e.get("epoch") == epoch]
if not epoch_entries:
    epoch_entries = entries  # use all unconsumed if no epoch match

# Build by_path with max seq per path, but carry first_touch from earliest entry.
by_path: dict[str, dict] = {}
first_touch_by_path: dict[str, str | None] = {}
for e in sorted(epoch_entries, key=lambda x: x.get("seq", 0)):
    p = e["path"]
    ft = e.get("first_touch_preimage_sha")
    if p not in first_touch_by_path:
        first_touch_by_path[p] = ft  # earliest entry's first_touch (may be None)
    by_path[p] = e  # later seq wins for action/blob_sha

# Patch first_touch into the by_path entries using the earliest non-None value.
for p, e in by_path.items():
    e["first_touch_preimage_sha"] = first_touch_by_path.get(p)

if not by_path:
    die("nothing to commit -- ledger is empty for this session")

# Pin parent SHA now; all validation and tree ops use this exact commit.
branch = current_branch()
parent = run(["git", "rev-parse", "HEAD"]).stdout.strip()
if not parent:
    die("BLOCKED: cannot resolve HEAD")


# Step 9: Triple validation
def ls_tree_blob(path: str, ref: str = parent) -> str | None:
    ls = run(["git", "ls-tree", ref, path])
    if not ls.stdout.strip():
        return None
    parts = ls.stdout.strip().split()
    return parts[2] if len(parts) >= 3 else None


for path, e in by_path.items():
    action = e.get("action", "upsert")

    if action == "upsert":
        blob_sha = e.get("blob_sha")
        if not blob_sha:
            die(f"BLOCKED: missing blob_sha for path {path}")

        # (a) blob existence
        cat = run(["git", "cat-file", "-t", blob_sha])
        if cat.returncode != 0 or cat.stdout.strip() != "blob":
            die(f"BLOCKED: blob {blob_sha} not in object store for {path}"
                " -- gc may have pruned it")

        # (b) disk-freshness: file must exist and match ledger blob
        abs_path = os.path.join(rroot, path)
        if not os.path.exists(abs_path):
            die(f"BLOCKED: disk content has changed since last Edit for {path}"
                " (file no longer exists)")
        disk = run(["git", "hash-object", abs_path])
        if disk.returncode != 0 or disk.stdout.strip() != blob_sha:
            die(f"BLOCKED: disk content has changed since last Edit for {path}")

        # (c) branch-base CAS preimage (against pinned parent)
        first_touch = e.get("first_touch_preimage_sha")
        parent_blob = ls_tree_blob(path)
        if first_touch is None and parent_blob is not None:
            die(f"BLOCKED: another commit has changed {path} since session start")
        if first_touch is not None and parent_blob != first_touch:
            die(f"BLOCKED: another commit has changed {path} since session start")

    elif action == "delete":
        # Verify path is still absent on disk
        abs_path = os.path.join(rroot, path)
        if os.path.exists(abs_path):
            die(f"BLOCKED: disk content has changed since delete for {path}"
                " (file was recreated)")
        first_touch = e.get("first_touch_preimage_sha")
        parent_blob = ls_tree_blob(path)
        if first_touch is not None and parent_blob != first_touch:
            die(f"BLOCKED: another commit has changed {path} since session start")

# Step 10: Empty commit check
all_no_change = all(
    (e.get("action") == "delete" and ls_tree_blob(p) is None) or
    (e.get("action") != "delete" and e.get("blob_sha") == ls_tree_blob(p))
    for p, e in by_path.items()
)
if all_no_change:
    die("no net changes -- edit reverted to parent content")

# Step 11: Nonce + grant manifest
nonce = secrets.token_hex(16)
grant_path = f"/tmp/claude-commit-grant-{SID}-{nonce}.json"

open(grant_path, "w").write(json.dumps({
    "sid": SID, "nonce": nonce, "branch": branch, "parent": parent,
    "created_at": datetime.now(timezone.utc).isoformat(),
}))
os.environ["CLAUDE_COMMIT_COMMAND_ACTIVE"] = "1"

# Step 12: Temp index construction
idx_path = f"/tmp/claude-idx-{SID}-{nonce}"
env = os.environ.copy()
env["GIT_INDEX_FILE"] = idx_path


def _cleanup_temps() -> None:
    for f in [idx_path, grant_path]:
        try:
            os.unlink(f)
        except Exception:
            pass


r = subprocess.run(["git", "read-tree", parent], env=env, capture_output=True)
if r.returncode != 0:
    _cleanup_temps()
    die(f"BLOCKED: git read-tree failed: {r.stderr.decode().strip()}")

for path, e in by_path.items():
    if e.get("action") == "upsert":
        mode = str(e.get("mode", 100644))
        r = subprocess.run(
            ["git", "update-index", "--add", "--cacheinfo",
             f"{mode},{e['blob_sha']},{path}"],
            env=env, capture_output=True
        )
        if r.returncode != 0:
            _cleanup_temps()
            die(f"BLOCKED: update-index failed for {path}: "
                f"{r.stderr.decode().strip()}")
    else:
        subprocess.run(
            ["git", "update-index", "--remove", path],
            env=env, capture_output=True
        )

# Step 13: Tree + commit
r = subprocess.run(["git", "write-tree"], env=env, capture_output=True, text=True)
if r.returncode != 0:
    _cleanup_temps()
    die(f"BLOCKED: git write-tree failed: {r.stderr.strip()}")
tree_sha = r.stdout.strip()

r = subprocess.run(
    ["git", "commit-tree", tree_sha, "-p", parent, "-m", MSG],
    capture_output=True, text=True
)
if r.returncode != 0:
    _cleanup_temps()
    die(f"BLOCKED: git commit-tree failed: {r.stderr.strip()}")
commit_sha = r.stdout.strip()

# Step 14: Pre-CAS audit
# Consume ALL unconsumed entries for committed paths in this epoch (not just max-seq),
# so earlier superseded edits don't linger as unconsumed and cause stale future commits.
all_epoch_seqs = sorted(
    e["seq"] for e in epoch_entries if e["path"] in by_path
)
pre_cas_path = os.path.join(audit_sid_dir, f"pre-cas-{nonce}.json")
pre_cas_data = {
    "status": "pre-cas",
    "sid": SID,
    "nonce": nonce,
    "branch": branch,
    "parent": parent,
    "tree_sha": tree_sha,
    "commit_sha": commit_sha,
    "msg_sha256": hashlib.sha256(MSG.encode()).hexdigest(),
    "consumed_seq": all_epoch_seqs,
    "ts": datetime.now(timezone.utc).isoformat(),
}
open(pre_cas_path, "w").write(json.dumps(pre_cas_data, indent=2))

# Step 15: CAS ref update
r = subprocess.run(
    ["git", "update-ref", f"refs/heads/{branch}", commit_sha, parent],
    capture_output=True, text=True
)
if r.returncode != 0:
    try:
        os.unlink(pre_cas_path)
    except Exception:
        pass
    _cleanup_temps()
    die("branch moved during commit -- retry /commit")

# Step 16: Audit finalize
final_data = dict(pre_cas_data, status="committed")
open(os.path.join(audit_sid_dir, f"{commit_sha}.json"), "w").write(
    json.dumps(final_data, indent=2)
)
try:
    os.unlink(pre_cas_path)
except Exception:
    pass

# Step 17: Mark consumed (this IS the epoch increment)
lock_path = os.path.join(LEDGER_BASE, f"{SID}.jsonl.lock")
with open(lock_path, "w") as lf:
    fcntl.flock(lf, fcntl.LOCK_EX)
    try:
        existing: list[dict] = []
        if os.path.exists(CONSUMED_FILE):
            try:
                existing = json.loads(open(CONSUMED_FILE).read())
            except Exception:
                existing = []
        existing.append({
            "consumed_seqs": all_epoch_seqs,
            "commit_sha": commit_sha,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        open(CONSUMED_FILE, "w").write(json.dumps(existing, indent=2))
    finally:
        fcntl.flock(lf, fcntl.LOCK_UN)

# Step 18: Cleanup
_cleanup_temps()

# Step 19: Report
print(f"committed {commit_sha} to refs/heads/{branch}")
