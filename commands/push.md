---
description: "Push Command"
disable-model-invocation: true
---

# Push Command

`/push` is the validated wrapper for normal branch publication. Note: pretool-git-privilege-guard.py is REGISTERED in settings.json (PreToolUse, Bash matcher) and enforces commit authorization — agents must hold a valid commit grant or use the `auto-bulk:` bridge prefix to commit. The wrapper
script `~/.claude/hooks/push.sh` produces a valid push grant recognized by the guard.

The slash entry has `disable-model-invocation: true` to prevent the model
from autonomously self-dispatching `/push` via SlashCommand. It does NOT
forbid agent execution of the wrapper script. When the user invokes
`/push` in conversation and this docstring is injected into the agent's
context, the agent's correct response is to run `~/.claude/hooks/push.sh
[remote]` directly via Bash. push.sh internally generates the grant
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

## Session commit prerequisite (push-gate)

`/push` requires a valid push-gate token written by a prior `/commit` in this session.

Token location: `/tmp/agentic-commit/push/<repo-hash>/<branch-encoded>.json`

- `repo-hash` = `sha256(os.path.realpath(repo_root)).hexdigest()[:16]`
- `branch-encoded` = branch name with `/` replaced by `__`
- Token content: `{"commit_sha": "<sha>", "branch": "<branch>", "repo_root": "<root>"}`

**Rejection conditions** (push is blocked if any hold):
- Token file is absent (no `/commit` ran in this session)
- Token `commit_sha` does not match current `git rev-parse HEAD` (HEAD moved since commit)

**Resolution**: run `/commit [<task-id>]` first. The `changelog-analyst` subagent writes
the token after a successful real-branch commit. The token is consumed (deleted) after
a successful push.

**Guard registration note**: `pretool-git-privilege-guard.py` is REGISTERED in `settings.json` (PreToolUse, Bash matcher). changelog-analyst commits require either a valid commit grant (written by `/commit` Step 5) or the `auto-bulk:` prefix (matched by `BLESSED_BRIDGE_RE`). Direct `git commit` by agents without a grant or blessed prefix is blocked.

## Pre-conditions for success

- On a real branch.
- Branch has commits ahead of upstream, or has no upstream yet.
- The selected remote exists locally.
- A valid push-gate token exists at the path above (see Session commit prerequisite).

## Exit codes

| Exit | Meaning |
|------|---------|
| 0    | Push succeeded, or nothing to push |
| 1    | Detached HEAD, missing remote, or normal push failure |
| 2    | Blocked option such as force/delete/ref-rewrite mode |

## Related

- `/commit <task-id>` — automatic semantic commit for a closed task.
- Direct `git push` — agents must use `/push` via the wrapper script; the privilege guard is registered and enforces commit authorization before push is meaningful.
