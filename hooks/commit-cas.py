#!/usr/bin/env python3
"""
commit-cas.py -- CAS commit engine for /commit slash command.

Called by commit.sh after arg parse and M3 lint.
Reads environment: SID, LEDGER_FILE, CONSUMED_FILE, AUDIT_BASE, MSG.
Performs steps 5 through 20 of the commit algorithm.

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


# Step 5: Always-aggregate entry loading across all *.jsonl files.
# Backward-compatible consumed decoder: handles three formats from *.consumed.json:
#   (a) new dict:  {"source_sid": "...", "seq": N}  -> (source_sid, seq)
#   (b) legacy int in consumed_seqs list: N          -> (file_sid, N)
#   (c) legacy consumed_seq_range: [lo, hi]          -> (file_sid, n) for n in range
# consumed_pairs is a set of (source_sid, seq) tuples — namespace-scoped to prevent
# session B's own seq=1 from being falsely matched against session A's consumed seq=1.
consumed_pairs: set[tuple[str, int]] = set()
for cf in glob.glob(os.path.join(LEDGER_BASE, "*.consumed.json")):
    file_sid = os.path.basename(cf).replace(".consumed.json", "")
    try:
        data = json.loads(open(cf).read())
        for item in data:
            if isinstance(item, dict):
                if "source_sid" in item and "seq" in item:
                    # (a) new tuple format
                    consumed_pairs.add((item["source_sid"], int(item["seq"])))
                elif "consumed_seqs" in item:
                    for v in item["consumed_seqs"]:
                        if isinstance(v, dict) and "source_sid" in v and "seq" in v:
                            # (a) new format nested inside consumed_seqs list
                            consumed_pairs.add((v["source_sid"], int(v["seq"])))
                        elif isinstance(v, int):
                            # (b) legacy bare integer
                            consumed_pairs.add((file_sid, v))
                elif "consumed_seq_range" in item:
                    # (c) legacy range
                    lo, hi = item["consumed_seq_range"]
                    for n in range(int(lo), int(hi) + 1):
                        consumed_pairs.add((file_sid, n))
    except Exception:
        pass

# Scan ALL *.jsonl files; primary SID file opened first (FileNotFoundError = empty).
# Aggregate mode is always-on: entries from every SID with matching repo_root are included.
all_raw_entries: list[dict] = []
primary_loaded = False
try:
    with open(LEDGER_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                all_raw_entries.append(e)
            except json.JSONDecodeError:
                continue
    primary_loaded = True
except FileNotFoundError:
    primary_loaded = False  # missing primary SID ledger is not fatal in aggregate mode
except Exception as exc:
    die(f"nothing to commit -- cannot read primary ledger: {exc}")

# Load all other *.jsonl files (skip primary to avoid double-loading).
for lf in glob.glob(os.path.join(LEDGER_BASE, "*.jsonl")):
    if lf == LEDGER_FILE:
        continue
    try:
        with open(lf) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    all_raw_entries.append(e)
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass

# Emit aggregate summary for debuggability (R6).
contributing_sids = sorted({e.get("sid", "") for e in all_raw_entries if e.get("sid")})
sys.stderr.write(f"INFO: aggregate mode: found entries from SIDs {contributing_sids}\n")

# Apply repo_root filter and consumed filter to get unconsumed_entries.
rroot_pre = repo_root()  # needed for repo_root filter before Step 8 re-checks
entries: list[dict] = [
    e for e in all_raw_entries
    if e.get("repo_root") == rroot_pre
    and (e.get("sid"), e.get("seq", 0)) not in consumed_pairs
]

if not entries:
    die("nothing to commit -- no unconsumed ledger entries for this repo")

# Step 6: Recovery scan
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

# Step 7: Corruption check
corrupted = [e["path"] for e in entries if e.get("corruption_flag")]
if corrupted:
    die("BLOCKED: corrupted ledger entries for paths:\n  " + "\n  ".join(corrupted))

# Step 8: Repo identity check
rroot = repo_root()
entries = [e for e in entries if e.get("repo_root") == rroot]
if not entries:
    die("nothing to commit -- no ledger entries match current repo root")

# Step 9: Two-phase deduplication by path.
# Epoch filter is BYPASSED in aggregate mode — consumed-pair check is the sole
# "already committed" gate. Using all unconsumed entries regardless of epoch field.
#
# Phase 1 (within-SID): per-SID max-seq entry per path + first-touch tracking.
# Phase 2 (cross-SID): select winner by ledger ts tiebreaker (later ts wins).
# first_touch_preimage_sha is ALWAYS taken from the same SID as the winner entry.

by_path_for_sid: dict[str, dict[str, dict]] = {}   # sid -> path -> max-seq entry
first_touch_for_sid: dict[str, dict[str, str | None]] = {}  # sid -> path -> first_touch
# Also track all same-SID same-path superseded (lower-seq) entries for consumed marking.
superseded_by_sid: dict[str, list[dict]] = {}  # sid -> list of superseded entries

for e in sorted(entries, key=lambda x: x.get("seq", 0)):
    sid_e = e.get("sid", "")
    p = e["path"]
    ft = e.get("first_touch_preimage_sha")
    if sid_e not in by_path_for_sid:
        by_path_for_sid[sid_e] = {}
        first_touch_for_sid[sid_e] = {}
        superseded_by_sid[sid_e] = []
    if p not in first_touch_for_sid[sid_e]:
        first_touch_for_sid[sid_e][p] = ft  # lowest-seq entry's first_touch for this SID
    if p in by_path_for_sid[sid_e]:
        # Current entry supersedes the previous one for this path within this SID.
        superseded_by_sid[sid_e].append(by_path_for_sid[sid_e][p])
    by_path_for_sid[sid_e][p] = e  # later seq wins within this SID

# Phase 2: cross-SID winner by ts tiebreaker.
by_path: dict[str, dict] = {}
for sid_e, path_map in by_path_for_sid.items():
    for p, e in path_map.items():
        if p not in by_path:
            by_path[p] = e
        else:
            existing_ts = by_path[p].get("ts", "")
            candidate_ts = e.get("ts", "")
            if candidate_ts > existing_ts:
                by_path[p] = e

# Patch first_touch_preimage_sha from the SAME SID as the winning entry (not cross-SID).
for p, e in by_path.items():
    winner_sid = e.get("sid", "")
    e["first_touch_preimage_sha"] = first_touch_for_sid.get(winner_sid, {}).get(p)

if not by_path:
    die("nothing to commit -- no entries after deduplication")

# Step 9b: Filter out paths whose first component is a symlink in the repo tree.
# Example: if .claude is tracked as a symlink (mode 120000) in the parent repo,
# git cannot stage paths like .claude/scripts/foo.sh inside it.
def _first_component(path: str) -> str:
    return path.split("/")[0]

_symlink_prefixes: set[str] = set()
_checked_prefixes: set[str] = set()
_unstageable_paths: list[str] = []
for _p in list(by_path.keys()):
    _first = _first_component(_p)
    if _first not in _checked_prefixes:
        _checked_prefixes.add(_first)
        _ls = run(["git", "ls-tree", "HEAD", "--", _first])
        if _ls.stdout.strip().startswith("120000"):
            _symlink_prefixes.add(_first)
    if _first in _symlink_prefixes:
        _unstageable_paths.append(_p)

if _unstageable_paths:
    for _p in _unstageable_paths:
        sys.stderr.write(f"WARNING: skipping {_p} — inside symlinked directory '{_first_component(_p)}'\n")
        del by_path[_p]

if not by_path:
    die("nothing to commit -- all entries are inside symlinked directories")

# Pin parent SHA now; all validation and tree ops use this exact commit.
branch = current_branch()
parent = run(["git", "rev-parse", "HEAD"]).stdout.strip()
if not parent:
    die("BLOCKED: cannot resolve HEAD")


# Step 10: Triple validation
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

        # (b) disk-freshness: file must exist and match ledger blob.
        # In aggregate mode spanning multiple sessions, blob_sha may be stale
        # (a later session modified the file). Auto-rehash from disk instead of
        # blocking — the CAS ref update (Step 16) remains the commit-level guard.
        abs_path = os.path.join(rroot, path)
        entry_mode = e.get("mode")
        if entry_mode == 120000:
            # Symlink: use lexists (does NOT follow the link) so dangling symlinks
            # are not prematurely rejected; the link-file itself must exist
            if not os.path.lexists(abs_path):
                die(f"BLOCKED: disk content has changed since last Edit for {path}"
                    " (symlink no longer exists)")
            link_target = os.readlink(abs_path)
            disk_result = subprocess.run(
                ["git", "hash-object", "--stdin"],
                input=link_target.encode(),
                capture_output=True
            )
            disk_sha = disk_result.stdout.strip().decode() if disk_result.returncode == 0 else ""
            if disk_sha != blob_sha:
                sys.stderr.write(f"WARNING: aggregate re-hash {path}: "
                                 f"{blob_sha[:8]} → {disk_sha[:8]}\n")
                e["blob_sha"] = disk_sha
                blob_sha = disk_sha
        else:
            # Regular file: os.path.exists follows symlinks (correct — actual file must exist)
            if not os.path.exists(abs_path):
                die(f"BLOCKED: disk content has changed since last Edit for {path}"
                    " (file no longer exists)")
            disk = run(["git", "hash-object", "-w", abs_path])
            if disk.returncode != 0:
                die(f"BLOCKED: cannot hash {path}: {disk.stderr.strip()}")
            disk_sha = disk.stdout.strip()
            if disk_sha != blob_sha:
                sys.stderr.write(f"WARNING: aggregate re-hash {path}: "
                                 f"{blob_sha[:8]} → {disk_sha[:8]}\n")
                e["blob_sha"] = disk_sha
                blob_sha = disk_sha

        # (c) branch-base CAS preimage (against pinned parent).
        # Relaxation for aggregate mode: if first_touch is None (new file) and
        # parent_blob already matches blob_sha, the file is already correctly
        # committed (e.g., via auto-bulk). Step 11 will detect no net change.
        # Only block when parent_blob has DIFFERENT content from what we want to commit.
        first_touch = e.get("first_touch_preimage_sha")
        parent_blob = ls_tree_blob(path)
        if first_touch is None and parent_blob is not None and parent_blob != blob_sha:
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

# Step 11: Empty commit check
all_no_change = all(
    (e.get("action") == "delete" and ls_tree_blob(p) is None) or
    (e.get("action") != "delete" and e.get("blob_sha") == ls_tree_blob(p))
    for p, e in by_path.items()
)
if all_no_change:
    die("no net changes -- edit reverted to parent content")

# Step 12: Nonce + grant manifest
nonce = secrets.token_hex(16)
grant_path = f"/tmp/claude-commit-grant-{SID}-{nonce}.json"

open(grant_path, "w").write(json.dumps({
    "sid": SID, "nonce": nonce, "branch": branch, "parent": parent,
    "created_at": datetime.now(timezone.utc).isoformat(),
}))
os.environ["CLAUDE_COMMIT_COMMAND_ACTIVE"] = "1"

# Step 13: Temp index construction
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

# Step 14: Tree + commit
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

# Step 15: Pre-CAS audit + build consumed_by_sid.
# consumed_by_sid: dict[source_sid -> list of {source_sid, seq} dicts] for entries to mark.
# Rules:
#   (a) winning by_path entry for each path -> add to consumed_by_sid[winner_sid]
#   (b) same-SID same-path superseded (lower-seq) entries -> also add to consumed_by_sid
#   (c) cross-SID losing entries with different blob_sha -> NOT added (other session can still commit)
consumed_by_sid: dict[str, list[dict]] = {}

for p, winner_e in by_path.items():
    winner_sid = winner_e.get("sid", "")
    winner_blob = winner_e.get("blob_sha")
    # (a) winning entry
    if winner_sid not in consumed_by_sid:
        consumed_by_sid[winner_sid] = []
    consumed_by_sid[winner_sid].append({"source_sid": winner_sid, "seq": winner_e["seq"]})
    # (b) within-SID superseded entries for this path
    for sup_e in superseded_by_sid.get(winner_sid, []):
        if sup_e["path"] == p:
            consumed_by_sid[winner_sid].append({"source_sid": winner_sid, "seq": sup_e["seq"]})

# Cross-SID losers: check each SID's by_path_for_sid entry for this path.
# If the losing SID's entry has the SAME blob_sha as winner, mark it consumed too
# (both sessions wrote the same content — safe to mark consumed for both).
# If different blob_sha, skip (other session's version should remain committable).
for p, winner_e in by_path.items():
    winner_sid = winner_e.get("sid", "")
    winner_blob = winner_e.get("blob_sha")
    for sid_e, path_map in by_path_for_sid.items():
        if sid_e == winner_sid:
            continue
        if p not in path_map:
            continue
        loser_e = path_map[p]
        if loser_e.get("blob_sha") == winner_blob:
            # Same content: safe to mark consumed for the losing SID too.
            if sid_e not in consumed_by_sid:
                consumed_by_sid[sid_e] = []
            consumed_by_sid[sid_e].append({"source_sid": sid_e, "seq": loser_e["seq"]})
        # Different blob_sha: do NOT add — other session must still be able to commit.

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
    "consumed_by_sid": {k: v for k, v in consumed_by_sid.items()},
    "ts": datetime.now(timezone.utc).isoformat(),
}
open(pre_cas_path, "w").write(json.dumps(pre_cas_data, indent=2))

# Step 16: CAS ref update
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

# Step 17: Audit finalize
final_data = dict(pre_cas_data, status="committed")
open(os.path.join(audit_sid_dir, f"{commit_sha}.json"), "w").write(
    json.dumps(final_data, indent=2)
)
try:
    os.unlink(pre_cas_path)
except Exception:
    pass

# Step 18: Mark consumed per source SID.
# Each source SID's entries are written to that SID's own <source_sid>.consumed.json,
# not only to the primary SID's file. This ensures cross-session aggregate mode
# correctly excludes already-committed entries from future scans.
commit_ts = datetime.now(timezone.utc).isoformat()
for source_sid, sid_consumed_list in consumed_by_sid.items():
    if not sid_consumed_list:
        continue
    source_consumed_file = os.path.join(LEDGER_BASE, f"{source_sid}.consumed.json")
    source_lock_path = os.path.join(LEDGER_BASE, f"{source_sid}.jsonl.lock")
    with open(source_lock_path, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            existing: list[dict] = []
            if os.path.exists(source_consumed_file):
                try:
                    existing = json.loads(open(source_consumed_file).read())
                except Exception:
                    existing = []
            # Append one record per {source_sid, seq} tuple (new tuple format).
            for consumed_item in sid_consumed_list:
                existing.append({
                    "source_sid": consumed_item["source_sid"],
                    "seq": consumed_item["seq"],
                    "commit_sha": commit_sha,
                    "ts": commit_ts,
                })
            open(source_consumed_file, "w").write(json.dumps(existing, indent=2))
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)

# Step 19: Cleanup
_cleanup_temps()

# Step 20: Report
print(f"committed {commit_sha} to refs/heads/{branch}")
