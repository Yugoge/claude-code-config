<!-- spec-continuation-of: dev-20260524-205811 -->
<!-- close-report: docs/dev/close-report-dev-20260524-205811.md -->

# Spec: Cross-SID Legacy Grant Leak — Follow-on Cycle

**Pipeline**: ba → dev → qa  
**Status**: ready-for-dev  
**Created**: 2026-05-25  
**Continuation of**: task dev-20260524-205811  
**Close verdict source**: `docs/dev/close-report-dev-20260524-205811.md` (CLOSE: NO)

---

## Section 1: User Requirement

Fully close the legacy grant subagent leak, including the cross-SID production case.

**Verbatim security property** (from close-report): "The main agent cannot reuse the legacy grant after a subagent executes the authorized Bash command."

This property must hold regardless of whether the subagent's `session_id` (from the PostToolUse payload) matches the orchestrator's `session_id` (used when `/allow` wrote the legacy grant).

---

## Section 2: Root Cause

### Prior cycle (dev-20260524-205811) — what was fixed

Task dev-20260524-205811 fixed the same-SID case:

- **Edit 3**: Removed the `if not is_subagent_context(data):` guard so `consume_grant_for_posttool()` is now unconditional.
- **Edit 4**: Added an unconditional unlink of `/tmp/claude-bash-allowlist-{session_id}.json` after sentinel consumption.

Both edits key their unlink on `session_id`, where `session_id` comes from the PostToolUse hook payload (`data.get("session_id")`).

### Residual gap — cross-SID case

In production subagent flows (documented at `hooks/pretool-git-privilege-guard.py:232-234` and `:453-457`), the subagent carries a **different** `session_id` than the orchestrator:

- `/allow` writes the legacy grant at: `/tmp/claude-bash-allowlist-{ORCH_SID}.json`
- PostToolUse fires with the subagent's payload `session_id = SUB_SID`
- Edit 3 calls `consume_grant_for_posttool(SUB_SID, ...)` — unlinks `/tmp/claude-bash-allowlist-{SUB_SID}.json` (does not exist, or unrelated)
- Edit 4 unlinks `/tmp/claude-bash-allowlist-{SUB_SID}.json` — same miss
- **Result**: `/tmp/claude-bash-allowlist-{ORCH_SID}.json` survives
- The main agent (IS_SUBAGENT=0) subsequently calls `pretool-bash-safety.sh:541-557` legacy fallback, reads the grant, emits `permissionDecision: allow` — **grant reused**

### Root cause statement

`posttool-allowlist-consume.py` Edit 4 unlinks the legacy grant only by the subagent's `session_id` (from payload). When the orchestrator's SID differs from the subagent's SID, the orchestrator-SID legacy grant is never unlinked. The `CLAUDE_SESSION_ID` environment variable holds the orchestrator's SID at PostToolUse hook execution time and is available but unused.

---

## Section 3: Fix Direction

In the sentinel consumption block of `hooks/posttool-allowlist-consume.py`, after `should_consume` becomes true, unlink legacy grants for **both** session IDs:

1. The subagent's `session_id` from the PostToolUse payload (covers same-SID case, maintains existing behavior)
2. The orchestrator's `session_id` from `os.environ.get("CLAUDE_SESSION_ID")` (covers cross-SID case)

Both unlink calls must use fail-open `except (FileNotFoundError, OSError): pass` blocks — no panic if either file is absent.

Deduplication: if `session_id == CLAUDE_SESSION_ID`, the second unlink path is redundant. The fail-open except block handles this naturally (second unlink hits FileNotFoundError after first unlink succeeds). No explicit dedup logic is required.

**Files to modify**: `hooks/posttool-allowlist-consume.py` only.

**Files explicitly excluded** (Won't Have):
- `hooks/userprompt-consent-allowlist.sh` — write firewall; must remain unchanged
- `hooks/pretool-bash-safety.sh` — read path; no changes needed
- `hooks/lib/allowlist.py` — library; no new helpers needed for this fix
- `agents/subagent.py` — subagent runner; out of scope

---

## Section 4: Acceptance Criteria

### AC1 — Regression: same-SID case continues to work

**Setup**: sentinel grant written with `session_id = SID_A`; PostToolUse payload `session_id = SID_A`; legacy grant exists at `/tmp/claude-bash-allowlist-{SID_A}.json`.

**After hook fires**:
- Sentinel file absent
- `/tmp/claude-bash-allowlist-{SID_A}.json` absent
- A subsequent simulated main-agent pretool check (IS_SUBAGENT=0) against `SID_A` finds no usable grant

### AC2 — Core fix: cross-SID case

**Setup**:
- Orchestrator SID = `ORCH_SID`; subagent SID = `SUB_SID` (different values)
- Legacy grant exists at `/tmp/claude-bash-allowlist-{ORCH_SID}.json`
- Sentinel grant written with `session_id = ORCH_SID`; `CLAUDE_SESSION_ID` env var = `ORCH_SID`
- PostToolUse payload `session_id = SUB_SID`

**After hook fires**:
- Sentinel file absent
- `/tmp/claude-bash-allowlist-{ORCH_SID}.json` absent
- `/tmp/claude-bash-allowlist-{SUB_SID}.json` absent (never existed; verify no panic)
- A subsequent simulated main-agent pretool check (IS_SUBAGENT=0) against `ORCH_SID` finds no usable grant

### AC3 — No double-unlink panic

**Scenario A** (same-SID): both the payload-SID unlink and the env-SID unlink target the same path — second unlink hits FileNotFoundError; hook exits 0.

**Scenario B** (cross-SID): payload-SID file does not exist; env-SID file does exist — both unlinks attempt; neither raises; hook exits 0.

**Scenario C** (neither file exists): both unlinks hit FileNotFoundError; hook exits 0.

### AC4 — Write firewall unchanged

`hooks/userprompt-consent-allowlist.sh` file content is byte-for-byte identical to the pre-cycle baseline (verified via `git diff hooks/userprompt-consent-allowlist.sh` returning empty).

---

## Section 5: Test Requirements

The test script (`tests/scripts/validate-posttool-ac-cross-sid.py` or appended to the existing posttool test script) must exercise all four ACs with direct subprocess invocations of `posttool-allowlist-consume.py`.

**Mandatory cross-SID test shape** (per Codex PROPOSED_FIX R3):
```
legacy_grant_path = /tmp/claude-bash-allowlist-{ORCH_SID}.json  (written)
sentinel grant: session_id = ORCH_SID, task_id = <tid>
env: CLAUDE_SESSION_ID = ORCH_SID, CLAUDE_TASK_ID = <tid>
PostToolUse payload: session_id = SUB_SID, tool_name = Bash
  → hook fires
assert: sentinel absent
assert: /tmp/claude-bash-allowlist-{ORCH_SID}.json absent
assert: pretool legacy-fallback for ORCH_SID finds no grant
```

---

## Section 6: Diff Budget

Expected change: 3–6 lines in `hooks/posttool-allowlist-consume.py`.

The existing `should_consume` block at lines 138–148 already unlinks `legacy_path = Path(f"/tmp/claude-bash-allowlist-{session_id}.json")`. The fix adds a parallel unlink block immediately below it for `Path(f"/tmp/claude-bash-allowlist-{orch_sid}.json")` where `orch_sid = os.environ.get("CLAUDE_SESSION_ID", "")`.

No new functions, no new imports, no refactoring. This is a targeted 5-line addition.

---

## Section 7: What Must Be Done (Next Cycle)

1. Read `hooks/posttool-allowlist-consume.py` lines 138–148 (the existing `should_consume` unlink block).
2. After the existing `try: legacy_path.unlink() / except: pass` block, add:
   ```python
   orch_sid = os.environ.get("CLAUDE_SESSION_ID", "")
   if orch_sid and orch_sid != session_id:
       orch_legacy_path = Path(f"/tmp/claude-bash-allowlist-{orch_sid}.json")
       try:
           orch_legacy_path.unlink()
       except (FileNotFoundError, OSError):
           pass
   ```
3. Write a test script covering AC1 (same-SID regression) and AC2 (cross-SID fix), AC3 (no panic), AC4 (write firewall unchanged).
4. Verify `git diff hooks/userprompt-consent-allowlist.sh` is empty.
5. Run `python -m py_compile hooks/posttool-allowlist-consume.py` — zero errors.

---

## Section 8: References

- Prior cycle dev-report: `docs/dev/dev-report-dev-20260524-205811.json`
- Prior cycle BA spec: `docs/dev/ticket-dev-20260524-205811.md`
- Close report: `docs/dev/close-report-dev-20260524-205811.md`
- Cross-SID documentation: `hooks/pretool-git-privilege-guard.py:232-234`, `:453-457`
- Sentinel grant library: `hooks/lib/allowlist.py` (`match_sentinel_grant_for_bash_command`, `consume_sentinel_grant_on_terminal_result`)
- Legacy fallback path: `hooks/pretool-bash-safety.sh:541-557`
