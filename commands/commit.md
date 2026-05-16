---
description: Create a content-bound commit from session ledger
disable-model-invocation: true
---

# /commit

`/commit "<message>"` consumes this session's staging ledger and advances the
branch via expected-parent CAS. Exactly one positional argument (the commit
message). No flags, no modes, no helpers.

## Usage

```
/commit "feat(scope): description of change"
```

## Message format — M3 Conventional Commits (required)

```
<type>(<optional-scope>): <description>
```

Allowed types: `feat` `fix` `refactor` `docs` `test` `chore` `build` `ci` `perf` `style` `revert`

Set `CLAUDE_COMMIT_SKIP_TYPE_LINT=1` to bypass the type check.

## What the harness does automatically

1. Reads `/var/lib/claude/ledger/<sid>.jsonl` to find unconsumed edits for this session.
2. Verifies each blob still exists in the object store, matches disk content, and matches the branch-base preimage recorded at first-touch time.
3. Builds a private temp index seeded from `HEAD` (untouched files are preserved).
4. Creates the commit via `git commit-tree` + expected-parent CAS `git update-ref`.
5. Writes an audit JSON to `/var/lib/claude/audit/<sid>/<commit-sha>.json`.
6. Marks the consumed ledger entries so the epoch increments for subsequent edits.

## What /commit does NOT accept

- Any flag (`-m`, `--message`, `--force`, `--manifest`, `--plan`, or any other)
- Zero or more than one positional argument
- A task-id or artifact path
- An auto-generated message (the agent writes the message)

## Edge cases — all refuse with exit 2

| Situation | Response |
|-----------|----------|
| Empty ledger for this session | "nothing to commit" |
| Blob pruned from object store | "gc may have pruned it" |
| Disk file changed since last Edit | "disk content has changed" |
| Another commit changed the path | "another commit has changed this path" |
| Edit reverted to original content | "no net changes" |
| Two concurrent /commit same branch | "branch moved during commit -- retry" |
| Corrupted ledger entry | "corrupted ledger entries" |
| Pre-CAS crash recovery | finalized or orphaned on next /commit startup |

## Install-time setup (required before first use)

```bash
mkdir -p /var/lib/claude/ledger /var/lib/claude/audit
chmod 700 /var/lib/claude/ledger /var/lib/claude/audit
git config --global gc.auto 0
git config --global gc.pruneExpire never
```

Register hooks in `.claude/settings.json` PreToolUse (Edit/Write/NotebookEdit):
  `pretool-content-preimage-guard.py`

Register in PostToolUse (Edit/Write/NotebookEdit):
  `posttool-ledger-writer.py`

## Exit codes

| Exit | Meaning |
|------|---------|
| 0 | Commit created successfully |
| 2 | Refused: see stderr for reason |
