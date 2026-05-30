#!/usr/bin/env python3
"""Line-precise (hunk-filtered) staging primitive — fail-closed.

Stages ONLY this cycle's owned hunks within a single already-authorized file,
leaving any peer (unattributed) hunks unstaged in the working tree. Ownership is
derived from dev's own authored content (the owned-edits ledger), NOT from a
file-state snapshot — so it is immune to peer timing/interleaving. A pre-edit
snapshot is used ONLY for a fail-closed out-of-owned-region cross-check.

Usage:
  stage-owned-hunks.py --git-root <root> --file <repo-rel-path> \
      --ledger <ledger.json> --snapshot <snapshot-file>

  --ledger    JSON file: list of {"old": "...", "new": "..."} owned edits for THIS
              file, in the order dev applied them. Line numbers (if present) are
              ADVISORY only and ignored by ownership logic.
  --snapshot  Path to a file holding the EXACT pre-edit (pre-first-edit) bytes of
              the worktree file (the cross-check trust anchor).

Exit codes:
  0   owned hunks staged (or empty owned diff -> no-op, nothing to stage)
  10  EXCLUDED (fail-closed) — ambiguity, peer entanglement, or apply reject.
      Reason printed to stderr. Caller MUST warn-and-skip (NEVER whole-file stage).
  2   hard/usage error (also treated as EXCLUDE by the caller)

Design invariant (PROCEED iff): the file is staged ONLY when reconstructing the
worktree with every owned range reverted to its recorded `old_string` yields bytes
BYTE-IDENTICAL to the pre-edit snapshot. Any unattributed byte change must occupy
either owned bytes (caught by the byte-match check) or non-owned bytes (caught by
the cross-check) -> EXCLUDE. There is no fail-open path.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

# Exit codes
OK = 0
EXCLUDE = 10
HARD = 2


def _excluded(reason):
    sys.stderr.write("EXCLUDE (fail-closed): %s\n" % reason)
    return EXCLUDE


def _read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def _git(git_root, args, input_bytes=None):
    """Run a git command; return (returncode, stdout_bytes, stderr_text)."""
    proc = subprocess.run(
        ["git", "-C", git_root] + args,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.returncode, proc.stdout, proc.stderr.decode("utf-8", "replace")


def _is_binary(data):
    # A NUL byte is git's own heuristic for "binary".
    return b"\x00" in data


def _count_occurrences(haystack, needle):
    """Count non-overlapping occurrences of needle in haystack (bytes)."""
    if not needle:
        return -1  # empty needle is never uniquely locatable
    count = 0
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx == -1:
            break
        count += 1
        start = idx + len(needle)
    return count


def _locate_unique(haystack, needle):
    """Return the unique byte offset of needle in haystack, or None if absent
    or non-unique."""
    n = _count_occurrences(haystack, needle)
    if n != 1:
        return None
    return haystack.find(needle)


def main(argv):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--git-root", required=True)
    ap.add_argument("--file", required=True, help="repo-relative path")
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--snapshot", required=True)
    try:
        ns = ap.parse_args(argv)
    except SystemExit as exc:
        # --help / -h exits 0; a genuine usage error exits non-zero.
        return 0 if exc.code in (0, None) else HARD

    git_root = ns.git_root
    rel = ns.file

    # --- Load inputs -------------------------------------------------------
    if not os.path.isdir(git_root):
        return _excluded("git root not a directory: %s" % git_root)

    abspath = os.path.join(git_root, rel)
    if not os.path.isfile(abspath):
        return _excluded("worktree file missing: %s" % rel)

    # Missing-signal: ledger absent or unreadable -> EXCLUDE
    if not os.path.isfile(ns.ledger):
        return _excluded("owned-edits ledger missing for %s" % rel)
    try:
        with open(ns.ledger, "r", encoding="utf-8") as fh:
            edits = json.load(fh)
    except (ValueError, OSError) as exc:
        return _excluded("owned-edits ledger unreadable: %s" % exc)

    if not isinstance(edits, list) or not edits:
        return _excluded("owned-edits ledger empty/invalid for %s" % rel)

    if not os.path.isfile(ns.snapshot):
        return _excluded("pre-edit snapshot missing for %s" % rel)
    snapshot = _read_bytes(ns.snapshot)

    worktree = _read_bytes(abspath)

    # --- Reject non-hunk-splittable files ----------------------------------
    if _is_binary(worktree) or _is_binary(snapshot):
        return _excluded("binary file (not safely hunk-splittable): %s" % rel)

    # CRLF / encoding mismatch: if line-ending style differs between snapshot and
    # worktree, byte-level reconstruction is unsafe -> EXCLUDE.
    if (b"\r\n" in snapshot) != (b"\r\n" in worktree):
        return _excluded("CRLF/encoding mismatch between snapshot and worktree: %s" % rel)

    # Mode change: a staged-vs-worktree mode delta is not hunk-splittable.
    rc, out, _ = _git(git_root, ["diff", "--numstat", "--", rel])
    rc_mode, mode_out, _ = _git(git_root, ["diff", "--summary", "--", rel])
    if rc_mode == 0 and b"mode change" in mode_out:
        return _excluded("mode change present (not hunk-splittable): %s" % rel)

    # --- Locate each owned edit by UNIQUE CONTENT search -------------------
    # Line numbers in the ledger (if any) are advisory and ignored here.
    owned_ranges = []  # list of (start_offset, end_offset, old_bytes, new_bytes)
    for i, edit in enumerate(edits):
        if not isinstance(edit, dict) or "old" not in edit or "new" not in edit:
            return _excluded("ledger entry %d malformed (need old+new) for %s" % (i, rel))
        new_b = edit["new"].encode("utf-8") if isinstance(edit["new"], str) else edit["new"]
        old_b = edit["old"].encode("utf-8") if isinstance(edit["old"], str) else edit["old"]

        # (M2.1a) Locate recorded new_string by UNIQUE content search in worktree.
        offset = _locate_unique(worktree, new_b)
        if offset is None:
            return _excluded(
                "owned new_string for edit %d not uniquely locatable in worktree "
                "(absent or duplicated) -> ambiguous: %s" % (i, rel)
            )
        # (M2.1b) Byte-match: worktree bytes at located range == recorded new_string.
        # _locate_unique guarantees this by construction, but assert defensively:
        if worktree[offset:offset + len(new_b)] != new_b:
            return _excluded(
                "worktree bytes in owned range != recorded new_string (peer edited "
                "inside owned range) for edit %d: %s" % (i, rel)
            )
        owned_ranges.append((offset, offset + len(new_b), old_b, new_b))

    # Sort by start offset; reject overlapping owned ranges (ambiguous).
    owned_ranges.sort(key=lambda r: r[0])
    for a, b in zip(owned_ranges, owned_ranges[1:]):
        if a[1] > b[0]:
            return _excluded("owned ranges overlap (ambiguous) for %s" % rel)

    # --- Cross-check (fail-closed): reconstruct worktree with owned ranges --
    # reverted to old_string; result MUST be byte-identical to the pre-edit
    # snapshot. Any out-of-owned divergence => post-capture peer edit => EXCLUDE.
    recon = bytearray()
    cursor = 0
    for (start, end, old_b, new_b) in owned_ranges:
        recon += worktree[cursor:start]
        recon += old_b
        cursor = end
    recon += worktree[cursor:]

    if bytes(recon) != snapshot:
        return _excluded(
            "out-of-owned region differs from pre-edit snapshot (post-capture peer "
            "edit detected) for %s" % rel
        )

    # --- Build owned-only patch -------------------------------------------
    # We stage exactly: snapshot (a == pre-edit) -> worktree-with-only-owned-edits
    # (b). Because `recon == snapshot`, the ONLY differences between snapshot and
    # the reconstructed "owned-applied" target are dev's recorded new_string blocks.
    # The b-side target is the worktree itself (recon + owned edits == worktree,
    # since recon reverts exactly those ranges). So a == snapshot, b == worktree,
    # and a..b contains ONLY owned hunks. We let `git diff --no-index -U0` compute
    # the minimal zero-context hunks, then `git apply --cached --recount --unidiff-zero`.
    #
    # Staging from snapshot->worktree (rather than the current index state) means a
    # peer hunk baked into the snapshot is on BOTH sides and never appears in the
    # patch (cannot be staged). Empty diff => nothing owned to stage => no-op (NOT
    # a whole-file fallback).
    with tempfile.TemporaryDirectory() as td:
        a_path = os.path.join(td, "a")
        b_path = os.path.join(td, "b")
        with open(a_path, "wb") as fh:
            fh.write(snapshot)
        with open(b_path, "wb") as fh:
            fh.write(worktree)

        # git diff --no-index returns exit 1 when files differ (expected), 0 when
        # identical, >1 on error.
        # NB: `git diff --no-index` accepts `-U0` (zero context) but NOT the
        # `git apply` spelling `--unidiff-zero`. Zero context isolates an owned
        # line even from an immediately-adjacent peer hunk.
        proc = subprocess.run(
            ["git", "diff", "--no-index", "-U0",
             "--src-prefix=a/", "--dst-prefix=b/", "--", a_path, b_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if proc.returncode not in (0, 1):
            return _excluded("git diff failed building owned patch: %s"
                             % proc.stderr.decode("utf-8", "replace"))
        patch = proc.stdout

    if not patch.strip():
        # Empty owned diff: nothing to stage. No-op, NOT a whole-file fallback.
        sys.stderr.write("NO-OP: empty owned diff for %s (nothing to stage)\n" % rel)
        return OK

    # Rewrite the temp-file paths in the patch headers to the real repo-relative
    # path so `git apply --cached` targets the tracked file.
    patch = _rewrite_patch_paths(patch, rel)

    # --- Stage via git apply --cached (never git add, never -A/.) ----------
    rc, out, err = _git(
        git_root,
        ["apply", "--cached", "--recount", "--unidiff-zero", "-"],
        input_bytes=patch,
    )
    if rc != 0:
        # Context drift / reject / overlapping with already-staged content.
        # Do NOT retry whole-file. Roll back any partial staging of this file.
        _git(git_root, ["restore", "--staged", "--", rel])
        return _excluded("git apply --cached rejected owned patch (context drift / "
                         "overlapping) for %s: %s" % (rel, err.strip()))

    return OK


def _rewrite_patch_paths(patch, rel):
    """Rewrite the a/<tmp> and b/<tmp> path tokens in a unified diff to a/<rel>
    and b/<rel> so the patch targets the real tracked file."""
    lines = patch.split(b"\n")
    out = []
    rel_b = rel.encode("utf-8")
    for line in lines:
        if line.startswith(b"diff --git "):
            out.append(b"diff --git a/" + rel_b + b" b/" + rel_b)
        elif line.startswith(b"--- "):
            out.append(b"--- a/" + rel_b)
        elif line.startswith(b"+++ "):
            out.append(b"+++ b/" + rel_b)
        else:
            out.append(line)
    return b"\n".join(out)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
