---
description: Commit session changes via changelog-analyst subagent
disable-model-invocation: true
---

# /commit

Agentic commit command. Validates the close-gate (unless `--force`), then dispatches
the `changelog-analyst` subagent to classify files, stage them, and create a real
branch commit. Handles nested repo (`/dev/shm/dev-workspace/dot-claude/`) automatically.

## Usage

```
/commit [<task-id>] [--force] [--bulk] [--dry-run]
```

| Flag | Meaning |
|------|---------|
| `<task-id>` | Required unless `--force` or `--bulk`. Task-id from the completed `/dev` cycle (e.g. `20260516-212024`). |
| `--force` | Bypass close-gate check. Human-only (enforced by `disable-model-invocation: true`). Audited. |
| `--bulk` | Batch mode — explore full diff, group by subsystem, commit until zero diff. |
| `--dry-run` | Print what would be staged/committed; do not execute. |

## Step-by-step workflow

### Step 1: Parse arguments

Parse `$ARGUMENTS`:
- Strip `--force` if present → set `FORCE=true`; else `FORCE=false`
- Strip `--bulk` if present → set `BULK=true`; else `BULK=false`
- Strip `--dry-run` if present → set `DRYRUN=true`; else `DRYRUN=false`
- Remaining token (if any) is `TASK_ID`

### Step 2: Resolve task-id (unless --bulk)

If `BULK=false`:
- If `TASK_ID` was supplied, use it directly.
- If `TASK_ID` is empty: exit with: `No task-id provided. Supply an explicit task-id (/commit <task-id>), use --force to bypass close-gate, or use --bulk for batch mode.` Do NOT scan close-reports by mtime — mtime-scan picks up unrelated reports from other sessions and causes close-gate failures on unrelated tasks.

If `BULK=true`: `TASK_ID` may remain empty; changelog-analyst operates in bulk mode.

### Step 3: Close-gate validation (skip if FORCE=true or BULK=true)

If `FORCE=false` AND `BULK=false`:

```
CONTROL_ROOT=/root
CLOSE_REPORT="${CONTROL_ROOT}/docs/dev/close-report-${TASK_ID}.md"
```

Run these checks (abort on first failure with a clear error message):

1. **File exists**: `CLOSE_REPORT` must exist. Error: `Close-gate: no close-report for task ${TASK_ID} at ${CLOSE_REPORT}. Run /close first.`
2. **Last non-empty line starts with CLOSE: YES**: extract the last non-empty line from the file and verify it begins with `CLOSE: YES`. Accepted variants:
   - `CLOSE: YES`
   - `CLOSE: YES — FORCED`
   - `CLOSE: YES - degraded codex consultation: codex_status=<...>`
   - `CLOSE: YES — codex disabled by user`
   - `CLOSE: YES (FORCED)`
   Error: `Close-gate: task ${TASK_ID} close-report does not end with CLOSE: YES (found: <last-line>). Run /close to produce a passing verdict.`
3. **Mtime recency**: close-report mtime must be within 86400 seconds (24 h) of now. Error: `Close-gate: close-report for task ${TASK_ID} is older than 24h (mtime: <mtime>). Re-run /close or use --force.`
4. **Task-id in filename matches argument**: the task-id derived from the filename must equal `TASK_ID`. Error: `Close-gate: filename task-id mismatch (file has <file-task-id>, argument is ${TASK_ID}).`

### Step 4: Force-bypass audit (only when FORCE=true)

If `FORCE=true`: create `~/.claude/logs/` and append a line with ISO timestamp, task-id, and mode=force to `~/.claude/logs/commit-overrides.log`. Best-effort; proceed even if log append fails.

Print: `WARNING: --force bypasses close-gate. Audit entry written to ~/.claude/logs/commit-overrides.log.`

### Step 5: Write commit grant and dispatch-snapshot manifest

Before dispatching changelog-analyst, write a single-use commit grant (skip this entire grant-write block when `BULK=true` — BULK commits use the `auto-bulk:` prefix which bypasses the guard via `BLESSED_BRIDGE_RE`; no grant is needed or written): activate venv and run Python to write the grant. First, resolve the session ID: `sid = os.environ.get("CLAUDE_SESSION_ID")`. If `sid` is empty or `None`, abort immediately with: `Cannot write commit grant: CLAUDE_SESSION_ID not set. Invoke /commit from within a Claude Code session.` Do NOT proceed to dispatch changelog-analyst. If `sid` is set, generate `grant_path = /tmp/claude-commit-grant-{sid}-{nonce}.json` containing `task_id`, `sid`, `nonce`, `expires_at` (10 minutes), and `created_at`. The guard IS registered and active — grant absence WILL block the changelog-analyst commit.

Also write the dispatch-snapshot manifest (non-bulk mode only): activate venv and run Python to capture `git status --porcelain=v1` from both repos, then write `manifest_path = /tmp/claude-commit-manifest-{sid}.json` containing `session_id`, `task_id`, `dispatched_at`, and `files_at_dispatch`. Best-effort; skip entirely in bulk mode.

### Step 6: Dispatch changelog-analyst

Use the Agent tool with `subagent_type: changelog-analyst`. Pass a structured prompt:

```
CONTROL_ROOT=/root
TASK_ID=<resolved task-id or empty for bulk>
BULK=<true|false>
DRYRUN=<true|false>
FORCE=<true|false>

You are the changelog-analyst subagent. Execute the commit workflow as specified
in your agent definition (agents/changelog-analyst.md). Use the variables above
to guide your behavior.

Constraints:
- CONTROL_ROOT is the fallback root for dev-report resolution; changelog-analyst MUST apply the subproject path-walk (dirname-of-changed-files → commonpath → walk up to docs/dev/) and check the subproject docs/dev/ first before falling back to ${CONTROL_ROOT}/docs/dev/
- GIT_ROOT must be computed per repo via `git rev-parse --show-toplevel`; never conflate with CONTROL_ROOT
- Stage only files in the classified set; never use `git add -A` or `git add .`
- Commit message must NOT match: `\bsync\b.*\buncommitted\b` or `chore\(claude\)\s*:\s*sync`
- Handle nested repo at /dev/shm/dev-workspace/dot-claude/ independently
- Write push-gate token after each successful commit
- Push-gate token path MUST be: `/tmp/agentic-commit/push/<sha256(os.path.realpath(GIT_ROOT))[:16]>/<BRANCH with / replaced by __>.json`
- Push-gate validates commit_sha only; expires_at is no longer written or checked
- **BULK mode commit message prefix (REQUIRED when BULK=true)**: every commit message MUST begin with `auto-bulk: end-of-cycle commit for <current-branch>` where `<current-branch>` is the actual current git branch of the repo being committed (run `git rev-parse --abbrev-ref HEAD`). This prefix matches `BLESSED_BRIDGE_RE` and bypasses the privilege guard — no grant file is needed. Do NOT use this prefix when BULK=false.
```

Wait for changelog-analyst to complete. Echo its final status to the user.

## Close-gate verification reference

The close-gate is the only guard this command owns. All git operations (staging, committing,
nested-repo handling, push-gate write) are delegated entirely to `changelog-analyst`.

## Privilege guard compatibility note

`pretool-git-privilege-guard.py` is REGISTERED in `settings.json` (PreToolUse, Bash matcher).

Authorization flow for changelog-analyst commits:

1. `/commit` writes `/tmp/claude-commit-grant-<SID>-<nonce>.json` before dispatching changelog-analyst (Step 5).
2. `_evaluate_commit(command, data)` calls `_find_grant('commit', sid)` using the subagent's session_id from the PreToolUse payload.
3. If SID-specific grant not found (subagent session_id differs from orchestrator's CLAUDE_SESSION_ID), falls back to `_find_grant_any('commit')` — any valid unexpired commit grant is accepted.
4. Grant validates: expires_at (10 min window), single-use unlink. No message-hash validation.

**DO NOT extend `BLESSED_BRIDGE_RE` with conventional commit patterns** (e.g. `^feat\(`, `^fix\(`).
This would allow any agent that learns the commit format to bypass the guard — destroying the
security model. The grant-file mechanism provides the correct narrow authorization.

auto-bulk bridge commits (matching BLESSED_BRIDGE_RE) do NOT need a grant. changelog-analyst
commits use the grant-file path. The BLESSED_BRIDGE_RE check runs first in `_evaluate_commit`.

## Related

- `/close <task-id>` — must run before `/commit` (produces the close-report gate token)
- `/push` — must run after `/commit` (reads the push-gate token written by changelog-analyst)
- `agents/changelog-analyst.md` — the subagent that does all git work
