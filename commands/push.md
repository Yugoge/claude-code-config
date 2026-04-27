---
description: "Push Command"
disable-model-invocation: true
---

# Push Command

Validated `git push` wrapper. Under the always-on git-privilege guard
(`pretool-git-privilege-guard.py`), this wrapper is the **only** authorized
path for an agent context to push to a remote. The guard rejects every other
`git push` invocation, including inline-env attempts.

## Usage

```
/push                # push current branch to "origin" (default)
/push <remote>       # push current branch to the named remote
```

The optional `<remote>` argument is forwarded into both the Scheme 6 grant
manifest's `remote` field AND the underlying `git push <remote> <branch>`
invocation, so the privilege-guard's `_validate_push_grant_remote` check
(grant.remote vs cmd-line remote token) admits the push. Useful for
fork-based workflows where `origin` points at an upstream you cannot write
to (e.g., `slopus/happy`) and a separate remote (e.g., `fork`) points at
your own writable fork (e.g., `Yugoge/happy`).

If the named remote is not configured locally, the wrapper exits 1 with a
helpful message and prints `git remote -v` so you can correct the typo or
add the remote.

The command is gated with `disable-model-invocation: true`: only the human
user can trigger it. The model cannot self-invoke `/push` as a way around
the guard.

## Behavior summary

1. **Detached HEAD check**: refuses to push if not on a branch.
2. **Status report**: prints staged / modified / untracked files for context.
3. **Dirty-tree informational warning** (NON-BLOCKING): if
   `git status --porcelain` is non-empty, the wrapper prints a yellow
   informational notice with the dirty-file count and continues. Working-tree
   drift (modified, staged, or untracked files) does NOT block `/push`. Only
   already-committed commits get pushed — staged and unstaged working-tree
   files are NOT pushed. To push your local changes, commit them via
   `/commit` first.
4. **Nothing-to-push exit**: if the tree is clean and there are zero commits
   ahead of the upstream, the wrapper prints "Nothing to push" and exits 0
   without writing a grant or contacting the remote.
5. **Scheme 6 grant emission**: when there is real work to push, the wrapper
   writes a single-use grant manifest at
   `/tmp/claude-push-grant-${CLAUDE_SESSION_ID:-default}-${NONCE}.json`
   (per-nonce filename so two concurrent wrappers under the same SID cannot
   collide; close-report-20260425-push-commit-debate.md §1-2). The manifest
   contains:
   - `branch` — current branch name
   - `expected_head` — output of `git rev-parse HEAD` at grant time
   - `remote` — `"origin"`
   - `nonce` — 32-hex-char value from `secrets.token_hex(16)`
   - `sid` — session id
   - `ppid` — wrapper's PID
   - `created_at` — ISO-8601 timestamp
6. **Env-var export**: the wrapper exports `CLAUDE_PUSH_COMMAND_ACTIVE=1`
   into the `git push` child's environment. The privilege-guard requires
   BOTH the env-var AND a matching grant file on disk before admitting the
   push. The env-var alone is insufficient; the grant alone is insufficient.
7. **Push**: invokes `git push` (with `-u` if no upstream is set). The
   privilege-guard validates the grant against the branch and HEAD on the
   live repo, then unlinks the grant on first consumption (single-use).
8. **Audit log**: on success, appends a line to
   `~/.claude/logs/git-privilege-grants.log` recording timestamp, sid,
   `command_kind=push`, branch, head, nonce, ppid.

## Scheme 6 mechanism (why this works)

The privilege-guard `pretool-git-privilege-guard.py` is always-on and ships
with two defenses against agent-issued pushes:

- **Literal-substring rejection**: the raw command string is searched for
  the substring `CLAUDE_PUSH_COMMAND_ACTIVE=`. If present (i.e., the agent
  typed `CLAUDE_PUSH_COMMAND_ACTIVE=1 git push origin master` on a single
  Bash call), the push is rejected before any other check. This neutralizes
  the inline-env injection vector that reproduced the b5d447e attack shape.
- **Wrapper-set env + grant**: only `CLAUDE_PUSH_COMMAND_ACTIVE=1` set by a
  parent process (this wrapper, via `export`) combined with a valid grant
  manifest on disk admits the push. The grant binds the push to a specific
  branch + HEAD + remote + sid + ppid; a forged or stale grant is rejected.

This means the agent cannot push by manipulating env vars in command text,
cannot replay an old grant, and cannot push a different branch or HEAD than
the wrapper observed when it wrote the grant. The wrapper is the only
authorized path; everything else exits 2 from the guard.

## Pre-conditions for a successful push

- On a real branch (not detached HEAD).
- Branch has commits ahead of upstream (or no upstream is set yet).
- Working-tree drift (modified, staged, or untracked files) is **allowed** —
  it does NOT block `/push`. Only already-committed commits get pushed.
  Staged and unstaged working-tree files are NOT pushed; only commits
  already on `<branch>` are pushed. If you want to ship local edits, run a
  real semantic commit first (e.g., via `/commit <task-id>` for closed dev
  tasks, or by hand for ad-hoc work). Automated snapshots on
  `refs/checkpoints/<branch>` are out of scope here — `/push` never
  advances HEAD.

## Exit codes

| Exit | Meaning |
|------|---------|
| 0    | Push succeeded, OR nothing to push (clean tree, zero commits ahead) |
| 1    | Detached HEAD, or `git push` failed |

## Failure modes

- **Detached HEAD**: checkout a real branch first.
- **Push rejected by remote** (e.g., remote ahead): pull first
  (`git pull --rebase`).
- **Guard rejection**: if the wrapper itself was invoked correctly but the
  guard still refuses, inspect `~/.claude/logs/git-privilege-grants.log`,
  the grant file matching
  `/tmp/claude-push-grant-${CLAUDE_SESSION_ID:-default}-*.json` (per-nonce),
  and the guard's stderr. The guard's stderr names the specific rule violated
  (head mismatch, branch mismatch, missing env, missing grant, inline-env
  injection).

## Related

- `/commit <task-id>` — Wrapper that commits a closed dev task, also under
  Scheme 6 (separate grant, separate env-var, same architecture).
- `/merge <branch>` — Wrapper that merges an overnight worktree under a
  different env-var precedent (`CLAUDE_MERGE_COMMAND_ACTIVE=1`).
- `git push` directly — blocked by the always-on privilege-guard.

## Script location

The implementation is `~/.claude/hooks/push.sh`. The command frontmatter
sets `disable-model-invocation: true` so the agent cannot trigger it
through `SlashCommand`.

## Notes

- This document supersedes the older description that referenced an
  auto-staging env var and an auto-staging prompt. That behavior was
  removed when `b5d447e` ratified the snapshots-off-HEAD design; the
  wrapper no longer auto-stages or auto-commits.
- The grant file lives in `/tmp` and is single-use: the privilege-guard
  unlinks it on first valid consumption. A second `git push` in the same
  session needs a new grant (i.e., a new `/push` invocation).
- **redev7 removed the dirty-tree hard gate**. The gate was a leftover from
  the earlier auto-staging design (pre-`b5d447e`). Since `/push` no longer
  auto-commits, working-tree state cannot leak to HEAD via `/push`, and the
  gate is unnecessary. Working-tree drift (modified, staged, or untracked
  files) does NOT block `/push`. Only already-committed commits get pushed.
  To push your local changes, commit them via `/commit` first.
