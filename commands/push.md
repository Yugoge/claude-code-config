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
context, the agent's correct response is to execute the **Agentic dispatch
protocol** documented below (Steps 0-5), then call `push.sh` ONLY after
push-analyst grant validation passes. Do NOT call `push.sh` directly
without first dispatching `push-analyst` — the analyst gate is mandatory.
Do NOT bounce the work back to the user with "please run X manually" —
that violates the harness's delegation design.

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

## Agentic dispatch protocol (pre-execution)

Before calling `push.sh`, the orchestrator MUST execute the following steps in order:

**Step 0: Parse arguments and resolve remote**

Parse user-supplied arguments (optional `<remote>`, optional `--auto`). Resolve the push
target remote using the same fork-prefer-origin logic as push.sh lines 38-42:

```bash
if git remote get-url fork >/dev/null 2>&1; then
    RESOLVED_REMOTE="fork"
else
    RESOLVED_REMOTE="origin"
fi
# Explicit user-provided remote argument overrides the above
```

**Step 1: Validate push-gate token (Chain A — existing, unchanged)**

This is the existing session commit prerequisite check. Verify the push-gate token at
`/tmp/agentic-commit/push/<repo-hash>/<branch-encoded>.json` exists and that its
`commit_sha` matches the current `git rev-parse HEAD`. If the token is absent or
mismatched, abort and instruct the user to run `/commit` first.

**Step 2: Compute pre-push snapshot**

```bash
PRE_HEAD=$(git rev-parse HEAD)
BRANCH=$(git rev-parse --abbrev-ref HEAD)
REMOTE_URL=$(git remote get-url "${RESOLVED_REMOTE}" 2>/dev/null || echo "unknown")
REPO_HASH=$(printf '%s' "$(realpath "$(git rev-parse --show-toplevel)")" | sha256sum | cut -c1-16)
REQUEST_ID=$(openssl rand -hex 16)
SESSION_ID="${CLAUDE_SESSION_ID}"
```

If `SESSION_ID` is empty or unset, abort immediately with:
"Cannot dispatch push-analyst: CLAUDE_SESSION_ID not set. Invoke /push from within a Claude Code session."

**Step 3: Dispatch push-analyst subagent**

Dispatch the `push-analyst` subagent with the following context:

```
BRANCH=<BRANCH>
PRE_HEAD=<PRE_HEAD>
REMOTE_NAME=<RESOLVED_REMOTE>
REMOTE_URL=<REMOTE_URL>
REQUEST_ID=<REQUEST_ID>
SESSION_ID=<SESSION_ID>
REPO_HASH=<REPO_HASH>
```

Wait for the subagent to complete before proceeding.

**Step 4: Read and validate push-analyst grant (Chain B)**

Read the grant at:
```
/tmp/agentic-commit/push-analyst/<REPO_HASH>/<SESSION_ID>/<REQUEST_ID>.json
```

Validate the following fields:
- File exists (if absent: abort with "push-analyst did not write a grant — aborting push")
- Grant is valid JSON (if not: abort with "push-analyst grant is not valid JSON — aborting push")
- `nonce` field matches `REQUEST_ID`
- `branch` field matches current `BRANCH`
- `head_sha` field matches current `git rev-parse HEAD` (must still equal `PRE_HEAD`)
- `remote_name` field matches `RESOLVED_REMOTE`
- `session_id` field matches `SESSION_ID`
- `verdict` field is one of: `"approved"`, `"warn"`, `"blocked"` (reject unknown verdicts)
- `risks` field is a JSON array (even if empty)
- `expires_at` is in the future (parse ISO-8601, compare to current UTC time)

If any field mismatches, is absent, has wrong type, or grant is expired: abort with a descriptive error message naming the failing field.

Consume (unlink) the grant:
```bash
rm -f "/tmp/agentic-commit/push-analyst/${REPO_HASH}/${SESSION_ID}/${REQUEST_ID}.json"
```

Act on verdict:
- `verdict=blocked`: display `risks[]` to the user and abort. Do NOT call push.sh.
- `verdict=warn`: display `risks[]` to the user with a warning, then proceed.
- `verdict=approved`: proceed.

**Step 5: Call push.sh via the single-process pattern (Chain A push-gate token consumed here)**

Per task 20260519-211515 R1 / AC1, validate-push and the actual push MUST be a
**single-process exec pattern** — the validator wrapper writes a Chain-B success
sentinel at
`/tmp/agentic-commit/push-analyst/<REPO_HASH>/<BRANCH>-chainB.validated.sentinel.json`
(atomic temp+rename, mtime ≤ 60s, bound to `request_id` + `head` + `branch` + `remote`)
and then `exec`s `~/.claude/hooks/push.sh` so both commands run as ONE PID. Read
the sentinel ONLY once from inside push.sh; missing / expired / FAIL / mismatched
sentinel triggers `exit 1` BEFORE any executable `git push` is reached.

Do **NOT** chain validate + push.sh with `&&` from the orchestrator. The orchestrator
chaining model has a window where the validator passes but the agent dispatch is
re-entered with stale state — the push-analyst grant Chain-B bypass. The
single-process pattern (one PID, unconditional short-circuit) eliminates the
window by construction.

```bash
# HEAD-drift check: abort if HEAD has moved since pre-push snapshot
CURRENT_HEAD=$(git rev-parse HEAD)
if [ "$CURRENT_HEAD" != "$PRE_HEAD" ]; then
  echo "ERROR: HEAD drifted since push-analyst grant — aborting push" >&2
  exit 1
fi

# Write Chain-B success sentinel (atomic temp+rename)
BRANCH_ENCODED="${BRANCH//\//__}"
CHAIN_B_SENTINEL_DIR="/tmp/agentic-commit/push-analyst/${REPO_HASH}"
CHAIN_B_SENTINEL_PATH="${CHAIN_B_SENTINEL_DIR}/${BRANCH_ENCODED}-chainB.validated.sentinel.json"
mkdir -p "${CHAIN_B_SENTINEL_DIR}"
CHAIN_B_TMP=$(mktemp "${CHAIN_B_SENTINEL_DIR}/.sentinel-XXXXXX.tmp")
printf '{"result":"PASS","request_id":"%s","head":"%s","branch":"%s","remote":"%s"}' \
  "${REQUEST_ID}" "${CURRENT_HEAD}" "${BRANCH}" "${RESOLVED_REMOTE}" > "${CHAIN_B_TMP}"
mv -f "${CHAIN_B_TMP}" "${CHAIN_B_SENTINEL_PATH}"

# Single-process pattern: exec push.sh in same PID so sentinel stays fresh
CLAUDE_PUSH_REQUEST_ID="${REQUEST_ID}" exec ~/.claude/hooks/push.sh "${RESOLVED_REMOTE}"
```

If `--auto` is required, append it to the `exec` line. The legacy
`bash ~/.claude/hooks/push.sh "${RESOLVED_REMOTE}"` form is acceptable ONLY when
called from a validator wrapper that has already written the Chain-B sentinel in
the SAME process tree; the sentinel-gate at hooks/push.sh:84 enforces that
constraint and self-aborts if violated.

## Push-analyst grant TTL

The push-analyst writes its Chain-B grant with a default TTL of
`PUSH_ANALYST_GRANT_TTL_SECONDS = 180` seconds — raised from 120 to 180 in
task 20260519-211515 R4 / AC4 to absorb subagent dispatch latency observed on
cold-path invocations where the orchestrator → push-analyst → grant-write
round-trip exceeded the prior 120s window. Rationale: subagent dispatch latency
on first invocation can take 60s+; combining with grant validation + sentinel
write puts the effective end-to-end deadline above the 120s threshold, causing
intermittent Chain-B grant expirations. The 180s TTL is the named constant
defined in `agents/push-analyst.md` Phase 7. The commit-grant mechanism at
`scripts/write-commit-grant.py` (`GRANT_TTL_MINUTES = 10`) is a DIFFERENT
mechanism and was not changed.

## Related

- `/commit <task-id>` — automatic semantic commit for a closed task.
- Direct `git push` — agents must use `/push` via the wrapper script; the privilege guard is registered and enforces commit authorization before push is meaningful.
