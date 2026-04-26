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

This slash command is a thin shim over `~/.claude/hooks/commit.sh`:

```bash
bash ~/.claude/hooks/commit.sh "$ARGUMENTS"
```

The script handles closure detection, dev-report parsing, grant emission, narrow staging, the blessed `git commit`, and audit-log writes. See `pretool-git-privilege-guard.py` Scheme 6 manifest-validation logic for the receiving end.

## Out of scope

- Free-form / model-driven commits — see `/quick-commit` (kept independent; different threat model).
- Branch HEAD advancement for non-closed tasks — refused; user must close the task first.
- `git push` — see `/push`.
