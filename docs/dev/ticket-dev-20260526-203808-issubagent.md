# BA Specification: IS_SUBAGENT Gate on BLESSED_BRIDGE_RE Commit Path

**Request ID**: dev-20260526-203808-issubagent
**Task ID**: dev-20260526-203808-issubagent
**Tier**: SMALL
**Created**: 2026-05-26T20:38:08Z

## Goal

Add an IS_SUBAGENT check inside `_evaluate_commit` in `hooks/pretool-git-privilege-guard.py` so that any subagent attempting a git commit with the `auto-bulk:` prefix is blocked, even when a valid bulk-commit sentinel exists on disk. Only the /commit orchestrator (running as main agent, no `agent_id` in payload) may use the BLESSED_BRIDGE_RE path.

## Context

The `_evaluate_commit` function (lines 546-589) has a BLESSED_BRIDGE_RE branch that checks for a valid bulk-commit sentinel before allowing the commit. The sentinel is currently multi-use and globally discoverable — any subagent that knows the prefix and observes a sentinel on disk could commit. The guard already gates the `/do` bypass on `agent_id` absence (`_has_do_consent`, line 132), but the BLESSED_BRIDGE_RE path has no equivalent subagent check.

The original /commit --bulk design dispatched changelog-analyst (a subagent) to execute the actual `git commit -F` calls. This spec intentionally breaks that flow: the /commit orchestrator must now run commits from main-agent context directly. Migration of commit.md and changelog-analyst to reflect this change is a separate follow-on cycle (recorded in Out-of-Scope Observations).

## Setup / Environment

- **applicability**: N/A
- **reason**: non-UI -- hook; cycle modifies a PreToolUse hook only. Does not produce (1) rendered UI changes, (2) browser interaction, (3) Playwright invocation, (4) screenshot evidence, or (5) any change to user-triggered UI code paths.

## Evidence (Contract A)

- **Observed**: "The M5 allowlist that permits `source venv/bin/activate && python3 /root/.claude/scripts/write-bulk-commit-sentinel.py` is available to ALL callers including subagents. An IS_SUBAGENT gate on the BLESSED_BRIDGE_RE path would add a second layer of defense."
- **Measured**: `_evaluate_commit` at `hooks/pretool-git-privilege-guard.py:548-561` — the BLESSED_BRIDGE_RE branch calls `_has_bulk_commit_sentinel(data)` with no prior check of `data.get('agent_id')`.
- **Expected**: after IS_SUBAGENT gate lands, `data.get('agent_id')` truthy => block with exit 2 before sentinel check is reached.
- **Gap**: one guard call missing at the start of the BLESSED_BRIDGE_RE branch.

## Scope (Contract B)

- **Search pattern**: `BLESSED_BRIDGE_RE`, `_evaluate_commit`, `agent_id`
- **Search scope**: `hooks/pretool-git-privilege-guard.py`
- **User reported**: `hooks/pretool-git-privilege-guard.py` lines 546-562
- **Additional found via grep**: `hooks/tests/test_bulk_commit_sentinel.py` (existing tests must be updated to cover new gate); `_evaluate_command` line 776 has an early allowlist fast-path that must be explicitly addressed (codex finding 1).
- **All occurrences**: `hooks/pretool-git-privilege-guard.py:548` (BLESSED_BRIDGE_RE branch); `hooks/pretool-git-privilege-guard.py:776` (early allowlist fast path in `_evaluate_command`).

## Reference Source (Contract C)

- **Tier**: tier_2_verified
- **Source**: source code read in this session — `hooks/pretool-git-privilege-guard.py` lines 130-141 (`_has_do_consent` pattern using `data.get('agent_id')` truthiness)
- **Location**: `hooks/pretool-git-privilege-guard.py:132`
- **Copy allowed**: yes — replicate the exact same `bool(data.get('agent_id'))` idiom
- **Dev constraint**: use the same truthiness check pattern `data.get('agent_id')` (no extra `.strip()` or special-casing of empty string) to remain consistent with the rest of the guard. An empty string is equivalent to absent for the purposes of subagent detection.

## Requirements (MoSCoW)

### Must Have

- In `_evaluate_commit`, after `BLESSED_BRIDGE_RE.search(msg)` is truthy, check `data.get('agent_id')` before calling `_has_bulk_commit_sentinel`. If truthy, call `_block(...)` with a message containing the token `BLOCKED: auto-bulk commit from subagent context` and exit 2.
- The new check must precede the `_has_bulk_commit_sentinel` call so even a valid, unexpired sentinel cannot bypass the gate.
- The error message must reference the task-id of this spec so it is traceable: `dev-20260526-203808-issubagent`.

### Should Have

- Update the module-level docstring revision history block to record this change with today's date.
- Update `hooks/tests/test_bulk_commit_sentinel.py` to add a test asserting: subagent + auto-bulk + valid sentinel => exit 2 + expected token in stderr, AND that `_has_bulk_commit_sentinel` is NOT called when `agent_id` is present.

### Could Have

- Extract a small `_is_subagent(data)` helper that returns `bool(data.get('agent_id'))` if the pattern is repeated elsewhere in a future cycle.

### Won't Have (Non-Goals)

- Modifying `commands/commit.md` or `agents/changelog-analyst.md` to reflect the new orchestrator-direct-commit model (separate cycle — see Out-of-Scope Observations).
- Changing the early allowlist fast path in `_evaluate_command` (line 776). That path is for non-commit commands; commit falls through to `_evaluate_commit` regardless. No structural change needed there; the fast-path only short-circuits when a valid `/allow` grant matches, and the subagent-auto-bulk block happens inside `_evaluate_commit` AFTER the fast-path exits early for allowed non-commit commands. Codex finding 1 is addressed by documentation only: a sentinel-based `/allow` grant that matches `git commit ... auto-bulk ...` would still route through `_check_git_allowlist` before reaching `_evaluate_commit`, so if a user explicitly `/allow`s an auto-bulk commit from a subagent context, that bypass is by definition user-authorized. This is acceptable per the threat model.

## Requirements Decomposition

| ID | Source phrase (verbatim from user) | Classification | Acceptance criterion |
|----|-------------------------------------|----------------|---------------------|
| R1 | "if a subagent tries to commit with the `auto-bulk:` prefix, the privilege guard should reject it even if a valid bulk-commit sentinel exists" | user-need clause | AC1 below |
| R2 | "only the /commit orchestrator (not a subagent) should legitimately use that code path" | user-need clause (same fix, same AC) | AC2 below (main-agent preserve) |

## Edge Cases & Risks

- **changelog-analyst regression**: The current `/commit --bulk` flow dispatches changelog-analyst (a subagent) to run `git commit -F`. This gate WILL block that flow. The sentinel was previously the only guard; adding the subagent gate means existing `/commit --bulk` sessions will start failing. The follow-on migration cycle (see Out-of-Scope Observations) must ship before or concurrently.
- **agent_id empty string**: The payload may contain `"agent_id": ""` in some edge cases. The `data.get('agent_id')` truthiness check treats empty string as not-a-subagent (same as `_has_do_consent` at line 132). This is consistent and intentional.
- **_evaluate_command early allowlist**: If a user creates a `/allow` grant for a `git commit auto-bulk:...` command, the early fast-path at line 776 would short-circuit before `_evaluate_commit` is reached. This is intentional user-authorized behavior per the threat model.

## Out-of-Scope Observations

| ts | file:line | observation | security_relevant |
|----|-----------|-------------|-------------------|
| 2026-05-26T20:38:08Z | commands/commit.md:1 | The /commit --bulk flow currently dispatches changelog-analyst subagent to run git commit -F. The new IS_SUBAGENT gate will break this flow. A forward-fix cycle must migrate commit.md + changelog-analyst.md so that the /commit orchestrator runs the commits directly from main-agent context rather than delegating to a subagent. | false |

## Acceptance Criteria

### AC1: Subagent auto-bulk commit is blocked even with valid sentinel

- GIVEN a PreToolUse Bash payload with `agent_id` set to a non-empty string (subagent context)
- WHEN `_evaluate_commit` is called with a command containing `auto-bulk: end-of-cycle commit for master`
- AND a valid non-expired bulk-commit sentinel exists in `/tmp`
- THEN the hook exits 2
- AND stderr contains the token `BLOCKED: auto-bulk commit from subagent context`
- AND `_has_bulk_commit_sentinel` is NOT called (ordering proof: patch it to raise an exception; the test passes because the subagent block fires first)

### AC2: Main-agent auto-bulk commit with valid sentinel is still allowed

- GIVEN a PreToolUse Bash payload with `agent_id` absent or falsy (main-agent / orchestrator context)
- WHEN `_evaluate_commit` is called with a command containing `auto-bulk: end-of-cycle commit for master`
- AND a valid non-expired bulk-commit sentinel exists in `/tmp`
- AND no active single-use commit grant (`_has_active_commit_grant()` returns False)
- THEN the hook exits 0 (allow)

### AC3: Subagent non-auto-bulk commit with no grant remains default-denied

- GIVEN a PreToolUse Bash payload with `agent_id` set (subagent context)
- WHEN `_evaluate_commit` is called with a command whose message does NOT match `BLESSED_BRIDGE_RE`
- AND no matching `/commit` grant or `/allow` sentinel-grant exists
- THEN the hook exits 2
- AND stderr contains `BLOCKED: agent git commit` (the existing default-deny token — unchanged behavior, no double-block)

## Technical Hints

- Affected files: `hooks/pretool-git-privilege-guard.py` (lines 546-562), `hooks/tests/test_bulk_commit_sentinel.py`
- The new block goes at line 549 (immediately inside `if msg and BLESSED_BRIDGE_RE.search(msg):`, before `if _has_bulk_commit_sentinel(data):`).
- Block message template: `'\nBLOCKED: auto-bulk commit from subagent context — only the /commit orchestrator (main-agent, no agent_id) may use the auto-bulk: prefix.\nSubagent agent_id: %r\nSpec: dev-20260526-203808-issubagent.\n' % data.get('agent_id')`
- Follow existing `_has_do_consent` pattern (line 132) for the `agent_id` check: `if data.get('agent_id'):`.
- Verification harness cleanup contract (R10 cross-reference): any AC harness spawning background processes must install `trap '<cleanup>' EXIT INT TERM` per `agents/qa.md`.
