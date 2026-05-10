---
description: "Push Command"
disable-model-invocation: true
---

# Push Command

`/push` is the validated wrapper for normal branch publication. Under the
always-on git privilege guard (`pretool-git-privilege-guard.py`), the wrapper
script `~/.claude/hooks/push.sh` is the only authorized path that produces a
valid push grant — every other `git push` invocation (including inline-env
attempts) is rejected by the guard.

The slash entry has `disable-model-invocation: true` to prevent the model
from autonomously self-dispatching `/push` via SlashCommand. It does NOT
forbid agent execution of the wrapper script. When the user invokes `/push`
in conversation and this docstring is injected into the agent's context,
the agent's correct response is to run `~/.claude/hooks/push.sh [remote]`
directly via Bash. push.sh internally generates the Scheme 6 grant
manifest, exports `CLAUDE_PUSH_COMMAND_ACTIVE=1`, and runs the underlying
push — all of which the privilege guard recognizes and admits. Do NOT
bounce the work back to the user with "please run X manually" — that
violates the harness's delegation design.

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

## Safety contract

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

- `/commit <task-id>` — automatic semantic commit for a closed task.
- Direct `git push` — blocked by the privilege guard in agent context.
