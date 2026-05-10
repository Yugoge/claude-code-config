# /commit — Automatic Semantic Commit

`/commit <task-id>` is the human-triggered wrapper for a closed development
cycle. The wrapper derives an internal semantic plan from same-task artifacts and
live repository state, commits only task-owned changes through a private index,
and preserves unrelated work.

## Usage

```bash
/commit <task-id>
/commit <task-id> -m "optional semantic summary"
```

`-m` is optional for the normal closed-task path. When omitted, the wrapper
builds a Conventional-Commit-style message from the task artifacts and close
verdict. The user and agents do not prepare plan files, choose paths, or
hand-edit commit inputs.

## Inputs the wrapper reads

For the supplied `<task-id>`, the wrapper resolves `docs/dev/` using the
project-local-first lookup and reads same-task artifacts when present:

1. `close-report-<task-id>.md`
2. `dev-report-<task-id>.json`
3. `qa-report-<task-id>.json`
4. `completion-<task-id>.md`
5. `context-<task-id>.json`
6. `ticket-<task-id>.md` or legacy BA spec

Those artifacts are evidence only; commit content is derived from the target
repository's current dirty state and task ownership signals in the artifacts.

## Behavior summary

1. Parse `<task-id>` and echo `TASK-ID: <task-id>`.
2. Require closure evidence: PRIMARY close-report with a recognized `CLOSE: YES`
   verdict, or SECONDARY completion plus passing QA evidence.
3. Treat `CLOSE: NO` as authoritative and fail closed.
4. Build an internal semantic plan that classifies dirty candidates as
   `task_owned`, `unrelated`, `garbage/generated`, `other_session`, or
   `ambiguous_overlap`.
5. Include only `task_owned` changes. Preserve unrelated and other-session work.
6. Refuse ambiguous ownership, mixed planned-path overlap, detached HEAD, empty
   plan, cross-repo ambiguity, or conflict.
7. Seed a private index from the expected parent and apply only planned patches.
8. Verify the real shared index did not mutate during private-index preparation.
9. Create the commit object from the private-index tree.
10. Advance the branch with expected-parent compare-and-swap.
11. Reconcile only planned paths in the shared index and verify staged-file list
    preservation.
12. Write audit JSON/log records and a backup-only recovery ref under
    `refs/backups/claude/...`.

## Safety contract

- Direct low-level commits remain blocked in agent context; use this wrapper.
- The shared index is never the content authority for closed-task commits.
- The wrapper refuses planned paths that are already staged by another session.
- The branch moves only through expected-parent CAS.
- Automatic recovery uses backup-only refs and never background-publishes
  `refs/heads/<branch>`.
- `--auto-bulk-bridge` remains a separate end-of-cycle path with its fixed
  `auto-bulk: end-of-cycle commit for <branch>` message.

## Exit codes

| Exit | Meaning |
|------|---------|
| 0    | Commit created and backup ref queued |
| 1    | Underlying git operation failed unexpectedly |
| 2    | Closure, ownership, overlap, conflict, or safety refusal |

## Related

- `/close` writes the machine-readable `CLOSE:` verdict consumed here.
- `/push` publishes committed branch tips only; it does not create commits.
