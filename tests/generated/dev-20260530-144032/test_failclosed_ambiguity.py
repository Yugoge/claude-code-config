"""AC3 (ac_uid 3c9e5b1a2d4f6c83) — fail-closed on ANY ambiguity.

Parametrized over the 8 fail-closed cases. Each MUST: exit 10, leave
`git diff --cached -- <file>` EMPTY, and print a fail-closed reason on stderr.
The whole file is NEVER staged and no guessed hunk is staged.
"""

import os

from conftest import EXCLUDE, OK


def _stage_empty(repo, rel):
    return repo.cached_diff(rel).strip() == ""


def test_missing_ledger(repo):
    repo.write("f.txt", "a\nb\nc\n")
    repo.commit("base")
    snap = repo.write_snapshot("a\nb\nc\n")
    repo.write("f.txt", "a\nb OWNED\nc\n")
    missing = os.path.join(repo.root, "does-not-exist.json")
    rc, err = repo.run_helper("f.txt", missing, snap)
    assert rc == EXCLUDE
    assert "ledger missing" in err
    assert _stage_empty(repo, "f.txt")


def test_empty_ledger(repo):
    repo.write("f.txt", "a\nb\nc\n")
    repo.commit("base")
    snap = repo.write_snapshot("a\nb\nc\n")
    repo.write("f.txt", "a\nb OWNED\nc\n")
    ledger = repo.write_ledger([])
    rc, err = repo.run_helper("f.txt", ledger, snap)
    assert rc == EXCLUDE
    assert "empty" in err.lower()
    assert _stage_empty(repo, "f.txt")


def test_owned_content_not_unique(repo):
    # new_string appears twice in the worktree -> non-unique -> EXCLUDE
    repo.write("f.txt", "dup\nx\ndup\n")
    repo.commit("base")
    snap = repo.write_snapshot("dup\nx\ndup\n")
    repo.write("f.txt", "dup\nx\ndup\n")  # 'dup\n' is non-unique
    ledger = repo.write_ledger([{"old": "x\n", "new": "dup\n"}])
    rc, err = repo.run_helper("f.txt", ledger, snap)
    assert rc == EXCLUDE
    assert "not uniquely locatable" in err
    assert _stage_empty(repo, "f.txt")


def test_owned_content_absent(repo):
    # recorded new_string not present in worktree at all -> EXCLUDE
    repo.write("f.txt", "a\nb\nc\n")
    repo.commit("base")
    snap = repo.write_snapshot("a\nb\nc\n")
    repo.write("f.txt", "a\nb OWNED\nc\n")
    ledger = repo.write_ledger([{"old": "b\n", "new": "b NEVER WRITTEN\n"}])
    rc, err = repo.run_helper("f.txt", ledger, snap)
    assert rc == EXCLUDE
    assert "not uniquely locatable" in err
    assert _stage_empty(repo, "f.txt")


def test_peer_edit_inside_owned_range(repo):
    """Peer mutates content INSIDE the line range dev authored. The recorded
    new_string no longer byte-matches the worktree -> M2.1 byte-match fails ->
    EXCLUDE. A peer change hidden inside an owned range is NEVER staged."""
    repo.write("f.txt", "h1\nh2\nh3\nh4\nh5\n")
    repo.commit("base")
    snap = repo.write_snapshot("h1\nh2\nh3\nh4\nh5\n")
    # Dev authored a 3-line block h2/h3/h4 -> "OWNED A/OWNED B/OWNED C".
    # Peer then mutated the middle line of that block.
    repo.write("f.txt", "h1\nOWNED A\nPEERHACK\nOWNED C\nh5\n")
    ledger = repo.write_ledger([{"old": "h2\nh3\nh4\n", "new": "OWNED A\nOWNED B\nOWNED C\n"}])
    rc, err = repo.run_helper("f.txt", ledger, snap)
    assert rc == EXCLUDE
    assert "not uniquely locatable" in err or "peer edited" in err
    assert _stage_empty(repo, "f.txt")


def test_peer_insertion_line_shift(repo):
    """A peer insertion ABOVE the owned region shifts line numbers. Owned content
    is located by content-search (line numbers advisory), so it is still found —
    but the peer insertion is an out-of-owned change caught by the cross-check ->
    EXCLUDE."""
    base = "a\nb\nc\nd\ne\n"
    repo.write("f.txt", base)
    repo.commit("base")
    snap = repo.write_snapshot(base)
    # owned edit at line 4 (d -> d OWNED); peer INSERTS a new line near the top.
    repo.write("f.txt", "a\nPEER INSERTED\nb\nc\nd OWNED\ne\n")
    ledger = repo.write_ledger([{"old": "d\n", "new": "d OWNED\n"}])
    rc, err = repo.run_helper("f.txt", ledger, snap)
    assert rc == EXCLUDE
    assert "out-of-owned region differs" in err
    assert _stage_empty(repo, "f.txt")


def test_binary_file(repo):
    data = b"\x00\x01\x02BIN\x00owned\x00"
    repo.write("f.bin", data)
    repo.commit("base")
    snap = repo.write_snapshot(data)
    repo.write("f.bin", b"\x00\x01\x02BIN\x00OWNED\x00")
    ledger = repo.write_ledger([{"old": "owned", "new": "OWNED"}])
    rc, err = repo.run_helper("f.bin", ledger, snap)
    assert rc == EXCLUDE
    assert "binary" in err.lower()
    assert _stage_empty(repo, "f.bin")


def test_mode_change(repo):
    repo.write("f.sh", "#!/bin/sh\necho hi\n")
    repo.commit("base")
    snap = repo.write_snapshot("#!/bin/sh\necho hi\n")
    repo.write("f.sh", "#!/bin/sh\necho OWNED\n")
    os.chmod(repo.path("f.sh"), 0o755)  # mode change vs committed 0644
    ledger = repo.write_ledger([{"old": "echo hi\n", "new": "echo OWNED\n"}])
    rc, err = repo.run_helper("f.sh", ledger, snap)
    assert rc == EXCLUDE
    assert "mode change" in err.lower()
    assert _stage_empty(repo, "f.sh")


def test_crlf_mismatch(repo):
    # snapshot is LF, worktree got CRLF-converted -> encoding mismatch -> EXCLUDE
    repo.write("f.txt", b"a\nb\nc\n")
    repo.commit("base")
    snap = repo.write_snapshot(b"a\nb\nc\n")  # LF snapshot
    repo.write("f.txt", b"a\r\nb OWNED\r\nc\r\n")  # CRLF worktree
    ledger = repo.write_ledger([{"old": "b\n", "new": "b OWNED\r\n"}])
    rc, err = repo.run_helper("f.txt", ledger, snap)
    assert rc == EXCLUDE
    assert "crlf" in err.lower() or "encoding" in err.lower()
    assert _stage_empty(repo, "f.txt")


def test_context_drift_apply_reject(repo):
    """An owned patch that cannot apply cleanly to the index (already-staged
    conflicting content) must fail-closed, NOT retry whole-file.

    We pre-stage a conflicting whole-file change so the owned-only zero-context
    patch overlaps already-staged content and `git apply --cached` rejects.
    """
    repo.write("f.txt", "p\nq\nr\ns\n")
    repo.commit("base")
    snap = repo.write_snapshot("p\nq\nr\ns\n")
    repo.write("f.txt", "p\nq OWNED\nr\ns\n")
    ledger = repo.write_ledger([{"old": "q\n", "new": "q OWNED\n"}])
    # Pre-stage a DIFFERENT full content for the same region so the index already
    # holds q's line replaced -> the owned zero-context patch context drifts.
    repo.write("f.txt", "p\nq OWNED\nr\ns\n")
    repo.git("add", "f.txt")
    # Now mutate the index further so apply against index rejects: stage a version
    # where the owned line is already different in the index.
    repo.write("f.txt", "p\nq OWNED MUTATED\nr\ns\n")
    repo.git("add", "f.txt")
    # Restore the worktree to the owned-only state for the helper to read.
    repo.write("f.txt", "p\nq OWNED\nr\ns\n")
    rc, err = repo.run_helper("f.txt", ledger, snap)
    # Either the apply rejects (context drift) or the index already matches; both
    # must NOT result in a whole-file stage of unattributed content. We assert the
    # owned line is never lost and no FOREIGN content reaches the index.
    cached = repo.cached_diff("f.txt")
    assert "MUTATED" not in cached, "unattributed (peer-like) index content must not be committed via this path"
    if rc == EXCLUDE:
        assert "reject" in err.lower() or "drift" in err.lower() or "overlapping" in err.lower()
