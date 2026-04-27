---
description: "Overnight cycle commit + merge + push composite"
disable-model-invocation: true
---

# /ship-overnight - Overnight cycle commit + merge + push composite

Composite slash command that ships an overnight worktree branch back to the
default branch and to origin in three sequential steps. Composes the existing
`commit.sh` (bridge mode) + `merge` + `push.sh` wrappers without
reimplementing their logic.

Authority:
- `/root/docs/dev/ba-spec-20260426-redev6.md` (P-SHIP, work item B)
- `/root/docs/dev/context-20260426-redev6.json`

`disable-model-invocation: true` mirrors `/commit` and `/push` - this surface
is human-only. The model cannot self-invoke `/ship-overnight` to obtain
unilateral commit + merge + push authority. The four always-on security
layers (disable-model-invocation, inline-env literal-substring rejection,
bulk-commit-detector, per-call grant manifest) all remain engaged because
each underlying wrapper invocation passes through them unchanged.

## Usage

```
/ship-overnight <worktree-branch>
```

- `<worktree-branch>` - the overnight worktree branch to ship (e.g.
  `cycle-2-redev`, `overnight-20260426-abc12345`).

The command chains three steps in order: **bridge commit -> merge -> push**.
Each step calls an existing audited wrapper. ship-overnight does not bypass
any guard.

## Sequence

### Step 1: bridge-mode commit on the worktree branch

```bash
bash ~/.claude/hooks/commit.sh --auto-bulk-bridge "<branch>"
```

If the working tree is clean (`git status --porcelain` empty), this step is
skipped and the pipeline proceeds to Step 2 directly. If commit.sh exits
non-zero, ship-overnight reports the failure, leaves the worktree state
unchanged, and exits non-zero. Recovery: inspect `git status` on the
worktree branch and re-run `/ship-overnight` once fixed.

### Step 2: merge to the default branch

```bash
export CLAUDE_MERGE_COMMAND_ACTIVE=1
git checkout <default-branch>   # main / master, resolved dynamically
git merge --no-ff <branch>
```

The default branch is resolved dynamically via `refs/remotes/origin/HEAD`
(same pattern as `/merge`). On merge conflict, ship-overnight exits with:

```
ship-overnight: merge conflict; resolve manually then re-run /ship-overnight
to continue with push only
```

The conflicting file list is printed for triage. ship-overnight does NOT
auto-resolve conflicts.

### Step 3: push origin

```bash
bash ~/.claude/hooks/push.sh
```

If push.sh exits non-zero, ship-overnight exits with:

```
ship-overnight: merge committed locally; push failed; re-run push.sh
manually after fixing remote state
```

The default branch has already advanced locally - re-running
`bash ~/.claude/hooks/push.sh` retries the push only (steps 1+2 are not
re-run).

## Partial-failure recovery (intentional non-rollback)

ship-overnight is fail-fast and does NOT auto-rollback. Each partial state
is recoverable by the user:

- **After Step 1 OK + Step 2 FAIL** (merge conflict)
  - State: worktree branch advanced; no merge applied.
  - Recovery: resolve conflicts manually, then re-run `/ship-overnight
    <branch>`. Step 1 will skip (clean tree), Step 2 will retry the merge,
    Step 3 will push.

- **After Step 2 OK + Step 3 FAIL** (push failed - remote state, network,
  auth)
  - State: default branch advanced locally; not on origin.
  - Recovery: fix the remote-side issue, then re-run
    `bash ~/.claude/hooks/push.sh` manually. Do NOT re-run
    `/ship-overnight` - that would attempt a no-op merge of an already-
    merged branch.

Audit-log entries persist for every step at
`/root/.claude/logs/git-privilege-grants.log` with
`mode=ship-overnight, step=commit|merge|push, status=ok|fail|skip`. This
gives forensics enough to reconstruct partial state without re-reading git
reflog.

## Implementation

```bash
bash ~/.claude/hooks/ship-overnight.sh "<branch>"
```

The slash command authors a `<branch>` argument from the user-supplied
worktree branch name, then invokes the wrapper. The wrapper script handles
argument validation, branch shell-metacharacter rejection, default-branch
resolution, the three sequential steps, and audit logging.

## Out of scope

- **Cross-repo orchestration.** ship-overnight operates on the current
  repository only. Multi-repo monorepos that need synchronized ship steps
  must be invoked once per repository.
- **Automatic conflict resolution.** Merge conflicts in Step 2 are
  surfaced to the user; ship-overnight does not pick a side.
- **Automatic remote-side recovery.** If push fails because the remote
  diverged, the user is responsible for `git pull --rebase` (or whatever
  remediation fits) before re-running `bash ~/.claude/hooks/push.sh`.
  ship-overnight will not force-push, will not auto-rebase.
- **Per-cycle ship.** Bridge-mode commits during the overnight loop stay
  per-cycle (commit only, no merge/push). ship-overnight is intended for
  the FINAL post-loop transition, not per-cycle. See
  `commands/dev-overnight.md` Step 13 for per-cycle commit semantics.
- **`-m` message override.** ship-overnight delegates the commit step to
  bridge mode, which uses the fixed `auto-bulk: end-of-cycle commit for
  <branch>` message format (locked by `BLESSED_BRIDGE_RE` in
  `pretool-git-privilege-guard.py`). To author a custom commit message on
  the default branch after the merge, use `/commit --force -m "<msg>"`
  separately.

## Security model (unchanged)

ship-overnight does not extend or weaken the four always-on security
layers. Each underlying wrapper retains its full guard contract:

1. **disable-model-invocation: true** on `/commit`, `/push`, and now
   `/ship-overnight` - all four are human-only invocation surfaces.
2. **Inline-env literal-substring rejection** in
   `pretool-git-privilege-guard.py` - blocks
   `CLAUDE_*_COMMAND_ACTIVE=1 git ...` injection.
3. **bulk-commit-detector** - independent downstream gate; bridge-mode
   commits go through it just like any other commit.
4. **Per-call grant manifest** - commit.sh writes a fresh nonce-bound
   grant; push.sh writes a fresh nonce-bound grant. ship-overnight does
   NOT share or replay grants between steps.

The merge step in Step 2 runs `git merge --no-ff` directly (not through a
wrapper) but exports `CLAUDE_MERGE_COMMAND_ACTIVE=1` first - the same env
contract `/merge` uses today, so the privilege guard treats it
identically.
