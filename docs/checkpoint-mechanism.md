# Auto-Commit / Checkpoint Mechanism

> Full reference for the `refs/checkpoints/*` snapshot system. Slim summary lives in `~/.claude/CLAUDE.md`.
> Last updated: 2026-04-16

---

## Overview

As of 2026-04-16, all automated snapshots (PostToolUse threshold, Stop
hooks, fswatch daemon, manual `/checkpoint`) are written to
`refs/checkpoints/<sanitized-branch>` via
`~/.claude/hooks/lib/checkpoint-core.sh`. Branch HEADs are **never**
advanced by automated snapshots. `git blame` on any line therefore points
to a real semantic commit.

---

## Key consequences for verifying subagent work

- `git diff` AND `git log HEAD` both show no evidence of the snapshot —
  the commit lives on a side-ref, not on HEAD.
- To see recent automated snapshots on the current branch:
    ```
    git log refs/checkpoints/<branch>
    ```
  (replace `/` in branch name with `-`; detached HEAD maps to
  `refs/checkpoints/detached-<short-sha>`.)
- To list all checkpoint refs:
    ```
    git for-each-ref refs/checkpoints/
    ```
- To confirm files are actually saved (not lost), inspect the latest
  checkpoint tree — NOT `git diff`:
    ```
    git show refs/checkpoints/<branch> --stat
    ```

---

## Recovery commands

```
# View full history of snapshots on current branch:
git log refs/checkpoints/master

# Restore a single file from the latest checkpoint:
git checkout refs/checkpoints/master -- path/to/file

# Read a file's content at a specific checkpoint:
git show refs/checkpoints/master:path/to/file

# Restore an entire tree snapshot into the working copy:
git checkout refs/checkpoints/master -- .
```

---

## Cross-machine recovery

Add to `.git/config` on any clone; **NOT** applied automatically, this is
document-only:

```
[remote "origin"]
    fetch = +refs/heads/*:refs/remotes/origin/*
    fetch = +refs/checkpoints/*:refs/remotes/origin/checkpoints/*
```

After adding the refspec, `git fetch` mirrors checkpoints into
`refs/remotes/origin/checkpoints/<branch>` on the cloning machine.

---

## Log file locations

- `~/.claude/logs/checkpoint.log` — CAS retries, build failures,
  empty-repo bootstraps.
- `~/.claude/logs/checkpoint-push.log` — background push failures. Push
  is rate-limited to once per 30 seconds per repo and never uses `-f`
  (CAS guarantees the ref chain is always fast-forward).

---

## Migration note (pre-existing HEAD pollution)

Commits with messages `Auto-commit: …` and `checkpoint: Auto-save at …`
that already exist on `master` are **not** rewritten automatically. If
you want a clean history you can excise them retroactively with
`git filter-repo`. Example (destructive — coordinate before running):

```
git filter-repo --commit-callback '
    if commit.message.startswith(b"Auto-commit:") or commit.message.startswith(b"checkpoint:"):
        commit.skip()
'
```

---

## `/push` behaviour change

`/push` no longer auto-commits. If the working tree is dirty, `/push`
exits non-zero with a "commit first" message. Use `/checkpoint`
(snapshot-only, no HEAD move) or `git commit` (real semantic commit)
before pushing.
