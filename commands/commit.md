---
description: Commit closed dev task to branch HEAD
disable-model-invocation: true
---

# /commit — Closed Dev Task Commit

One-shot commit for a single closed dev task, scoped to that task's `dev-report.files_modified` set, gated through the always-on privilege-guard via a single-use grant manifest.

This is the ONLY agent-authorized path that advances branch HEAD outside of `/merge`.

## Usage

```
/commit <task-id>
```

**Example**: `/commit dev-20260425-145411`

The argument is the same `<task-id>` used by `/dev`, `/qa`, `/close`, etc. It locates closure evidence in `docs/dev/` and the dev-report whose `files_modified` defines the staging set.

## Task-id resolution

Resolve the **task-id** the same way `/close` does (see `commands/close.md:32-39` for the reference pattern — `/commit` mirrors it for documentation parity per AC-INFER-5). The task-id is the SAME identifier used by the source `/dev` (or `/redev`) cycle (e.g. `dev-20260425-145411`, `redev3-p1p2-20260426`) — NOT a fresh `date +%Y%m%d-%H%M%S` at /commit invocation time. Using a fresh timestamp would break the artifact chain (`close-report-<task-id>.md`, `dev-report-<task-id>.json`) that closure detection and grant emission depend on.

Resolve in this priority order:

- **If `$ARGUMENTS` is non-empty**: treat it as the task-id directly (or as an explicit task-id-bearing token). The orchestrator passes it through unchanged. This is the explicit-form path — backwards-compatible with every `/commit <task-id>` invocation.
- **Else (no argument)**: the orchestrator invoking /commit MUST already know this conversation's dev artifacts from context (it just ran `/dev` or `/redev` in the same session). It identifies the active dev cycle's task-id from visible artifact filenames in the transcript (`ba-spec-<task-id>.md`, `dev-report-<task-id>.json`, `close-report-<task-id>.md`) and embeds the resolved task-id directly into Implementation's bash invocation, NOT a literal empty string. There is NO filesystem scan and NO default-to-newest.
- **Else (neither resolves)**: exit non-zero with: `No task-id resolved. Either run /commit within a conversation that just completed /dev or /redev, or pass /commit <task-id>.`

If the orchestrator cannot identify the task-id from context AND `$ARGUMENTS` is empty, /commit MUST exit with the error message above. /commit MUST NOT default to `date +%Y%m%d-%H%M%S` and MUST NOT invoke `commit.sh` with an empty positional argument — resolution failure is signaled at the orchestrator/slash-command layer, not at the wrapper layer (the wrapper's empty-arg guard remains as defense-in-depth, but it should never be reached under correct orchestrator behavior).

## Scheme 6 mechanism

The git-privilege-guard (`pretool-git-privilege-guard.py`) ships always-on per spec-20260424-233926 §5.2.4 R4.3. It rejects every agent-issued `git commit` except:

1. The `/merge` blessed-bridge regex (`^auto-bulk: end-of-cycle commit for `) — reserved for `/merge`.
2. **`/commit`** — env-var (set by wrapper, never inline) + single-use grant manifest at `/tmp/claude-commit-grant-<sid>-<nonce>.json` with `{nonce, sid, task_id, allowed_files, expected_message_sha256, created_at, ppid}` (per-nonce filename so two concurrent wrapper invocations under the same SID cannot collide on a shared file; close-report-20260425-push-commit-debate.md §1-2).

The guard validates: env=`CLAUDE_COMMIT_COMMAND_ACTIVE=1` AND grant exists AND `sha256(message) == grant.expected_message_sha256` AND `set(git diff --cached --name-only) == set(grant.allowed_files)`. On success it unlinks the grant and admits the commit; on failure it leaves the grant for forensics and blocks.

## Closed-task detection

Ordered, **fail-closed**:

1. **PRIMARY**: `docs/dev/close-report-<task-id>.md` exists AND its last non-empty line matches `^CLOSE:\s*YES\b` (allows both `CLOSE: YES` standalone and `CLOSE: YES — narrative`).
2. **SECONDARY** (only if PRIMARY missing): `docs/dev/completion-<task-id>.md` exists AND `docs/dev/qa-report-<task-id>.json` exists AND its `qa.status` field equals `"pass"`.
3. If neither holds, the wrapper exits non-zero with `task not closed: no close-report or completion+qa-pass evidence for <task-id>`.

The closure check is **necessary but not sufficient** — even if forged, the bulk-commit-detector (`pretool-bulk-commit-detector.py`) remains an independent gate that blocks the b5d447e shape (3+ subsystem prefixes + sync.* subject) regardless.

## Defense-in-depth

- `disable-model-invocation: true` — the model cannot self-invoke this slash command (AV-5 mitigation).
- Literal-substring rejection in privilege-guard catches inline injection (`CLAUDE_COMMIT_COMMAND_ACTIVE=1 git commit ...`).
- Single-use grant: unlinked on first valid consumption; replay blocked.
- Bulk-commit-detector is downstream and not bypassable by this wrapper.

## Implementation

This slash command is a thin shim over `~/.claude/hooks/commit.sh`. The orchestrator invoking /commit MUST already know this conversation's dev artifacts from context (per Task-id resolution rules above). It embeds the resolved task-id directly into:

```bash
bash ~/.claude/hooks/commit.sh <resolved-task-id>
```

NO filesystem scan, NO default-to-newest, NO literal empty-string pass-through. If the task-id cannot be resolved (no `$ARGUMENTS`, no identifiable /dev or /redev cycle in conversation context), exit with the error message defined in Task-id resolution; do NOT invoke `commit.sh` at all.

The script handles closure detection, dev-report parsing, grant emission, narrow staging, the blessed `git commit`, and audit-log writes. The wrapper itself still requires an explicit positional task-id (its empty-arg guard remains as defense-in-depth) — this slash-command layer is responsible for ensuring the wrapper is called with a real, resolved value. See `pretool-git-privilege-guard.py` Scheme 6 manifest-validation logic for the receiving end.

## Bridge mode (overnight integration)

For `/dev-overnight` per-cycle commits, `commit.sh` accepts a second invocation form:

```
bash ~/.claude/hooks/commit.sh --auto-bulk-bridge <branch>
```

This is **not** a user-facing entry point — normal users should always use `/commit <task-id>`. Bridge mode exists so `/dev-overnight` cycles can land HEAD commits without producing a per-cycle close-report (which would not be meaningful for bulk multi-issue cycles).

What bridge mode does differently:

- Skips closure detection entirely (no PRIMARY/SECONDARY check; no close-report or completion+qa-pass evidence required).
- Reads the pre-staged file set via `git diff --cached --name-only` (caller is responsible for `git add` before invoking).
- Emits commit message `auto-bulk: end-of-cycle commit for <branch>` — this format matches `BLESSED_BRIDGE_RE` in `pretool-git-privilege-guard.py:92`, so the privilege-guard's existing early-return continues to admit the commit (preserving in-flight overnight compatibility; AC-P3-4 in `ba-spec-20260426-redev3.md`).
- STILL writes a per-nonce grant manifest with `allowed_files` + `expected_message_sha256` + `branch`. The privilege-guard observes this manifest and warns on staged-set / hash drift (defense-in-depth, observation-only this cycle; AC-P3-2).
- Audit-log entries carry `mode=auto-bulk-bridge branch=<branch>` so post-hoc forensics can distinguish bridge-mode commits from closed-task commits.

Bridge mode and closed-task mode are mutually exclusive — `commit.sh` parses `$1` to decide which flow runs and exits early once it returns.

## Out of scope

- Free-form / model-driven commits — see `/quick-commit` (kept independent; different threat model).
- Branch HEAD advancement for non-closed tasks — refused; user must close the task first.
- `git push` — see `/push`.
