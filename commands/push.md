---
description: "Push Command"
disable-model-invocation: true
---

# Push Command

`/push` is the validated human-triggered wrapper for normal branch publication.
The always-on git privilege guard rejects direct agent `git push` calls and
inline env-var attempts.

## Usage

```bash
/push
/push <remote>
```

No force, delete, or ref-rewrite mode is available through `/push`. The wrapper
accepts only an optional remote and `--auto` for non-interactive lock handling.

## Behavior summary

1. Refuse detached HEAD.
2. Print staged / modified / untracked files for context only.
3. Treat dirty worktree state as non-blocking; only committed objects push.
4. Exit cleanly when there is nothing ahead of upstream.
5. Emit a single-use push grant binding branch, current HEAD, remote, SID,
   nonce, ppid, and timestamp.
6. Export the wrapper-only push env var for the child process.
7. Run a normal branch push, with `-u` only when setting an upstream.
8. Append the push audit log on success.

## V3 safety contract

- `/push` never stages, commits, resets, deletes branches, force-publishes, or
  mutates refs directly.
- `--force`, `-f`, `--force-with-lease`, `--delete`, `-d`, and `--mirror`
  fail with exit 2 before any grant is written.
- Automatic post-commit backup is separate from `/push` and uses only
  `refs/backups/claude/<branch>/<short-sha>` recovery refs. It never publishes
  `refs/heads/<branch>` in the background.

## Pre-conditions for success

- On a real branch.
- Branch has commits ahead of upstream, or has no upstream yet.
- The selected remote exists locally.

## Exit codes

| Exit | Meaning |
|------|---------|
| 0    | Push succeeded, or nothing to push |
| 1    | Detached HEAD, missing remote, or normal push failure |
| 2    | Blocked option such as force/delete/ref-rewrite mode |

## Related

- `/commit <task-id> -m "<session-summary>"` — v3 semantic commit; the agent creates the internal manifest automatically.
- Direct `git push` — blocked by the privilege guard in agent context.
