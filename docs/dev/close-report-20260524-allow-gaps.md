---
# Close Debate Report (FORCED)
Task-id: 20260524-allow-gaps
Mode: --force (user override)
Closed at: 2026-05-24T20:38:12Z
Reason: compound-command guard moved before Pass 1 in match_sentinel_grant_for_bash_command; all 20 test assertions pass; Codex subagent verified CONFIRMED_FIXED; developed with /do (no formal dev artifacts)

**Verdict**: **CLOSE: YES — FORCED by user override**

No multi-round debate occurred. The user explicitly invoked /close with
--force, accepting full responsibility for any defects this verdict masks.

## Forced Override Audit
- Timestamp: 2026-05-24T20:38:12Z
- Task-id: 20260524-allow-gaps
- Invoker: human user (model cannot self-invoke /close; disable-model-invocation: true)
- Workflow Integrity Dimension: ALL bullets OVERRIDDEN — not evaluated
  1. Downstream consumability: OVERRIDDEN
  2. task-id chain consistency: OVERRIDDEN
  3. Pre-existing-defect rule: OVERRIDDEN
  4. Self-deployability: OVERRIDDEN
- Rationale (from invoker): compound-command guard moved before Pass 1; all 20 test assertions pass; CONFIRMED_FIXED by Codex subagent; /do cycle (no formal artifacts)
- User explicitly accepts the risk of closing without debate.

## Summary of Changes

Task 20260524-allow-gaps fixes the compound-command injection gap in the /allow sentinel grant mechanism.

The compound-command guard (`if len(subcommands) != 1: return None`) in
`match_sentinel_grant_for_bash_command` (hooks/lib/allowlist.py) was previously
placed only in Pass 2 (structural entries). Pass 1 (regex entries, op="*") had
no such guard, allowing commands like `git push origin; echo PWNED` to be
authorized when the sentinel contained `{"op":"*","regex":"^git\\\\s+push"}`.

Fix: moved the compound guard to before both passes. Any compound command
(separated by `;`, `&&`, `||`, `|`) now returns None regardless of whether
the grant is regex or structural.

Verified by: 20 test assertions across test_allow_gaps.py, test_allow_gapAB.py,
test_inject.py, test_compound.py, plus inline regex+compound tests.
Codex subagent review verdict: CONFIRMED_FIXED.

---
CLOSE: YES (FORCED)
---
