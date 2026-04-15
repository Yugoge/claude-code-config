# Plan: Phase 1 Quick Wins — 6 Overnight Agent Enhancements

## Context

Research identified 6 high-impact, low-effort enhancements across our overnight agents. All are **additive changes to agent definition files** — no structural changes to the orchestrator loop. Only #1 (pipeline_blocked) requires a small orchestrator tweak.

## Architecture Impact

```
dev-overnight.md (orchestrator)
  ├── pm.md ← #1 pipeline_blocked in TRIAGE output
  ├── product-owner.md ← #2 RICE scoring in roadmap_proposals
  ├── ui-specialist.md ← (already enhanced, no change)
  ├── user.md ← #5 persona definitions, #6 frustration signals
  ├── dev.md ← #3 TDD protocol
  └── qa.md ← #4 self-verification step
```

Only `dev-overnight.md` needs a 5-line addition to check `pipeline_blocked` after TRIAGE. Everything else is agent-internal.

---

## Quick Win 1: PM `pipeline_blocked` Quality Gate

**File**: `/root/.claude/agents/pm.md`
**Where**: TRIAGE output schema section

**What to add**:
- `pipeline_blocked: boolean` field to TRIAGE output
- `block_reasons: string[]` — list of reasons (build failure, security vuln, data corruption risk)
- Criteria: blocked when ANY of: build completely fails, security vulnerability in auth/payment, data corruption or loss possible

**Orchestrator change** (`/root/.claude/commands/dev-overnight.md`):
- After PM TRIAGE (Step 2), before creating pipelines (Step 3):
- Check if triage report has `pipeline_blocked: true`
- If blocked: log reason, skip to PM RETRO with `block_reason` in context, then loop to next cycle

---

## Quick Win 2: PO RICE Scoring

**File**: `/root/.claude/agents/product-owner.md`
**Where**: `roadmap_proposals` section in Output Format

**What to add** to each proposal object:
```json
{
  "rice_score": {
    "reach": "1-10 (users affected per week)",
    "impact": "0.25|0.5|1|2|3 (minimal|low|medium|high|massive)",
    "confidence": "0.5|0.8|1.0 (low|medium|high)",
    "effort": "1-10 (person-weeks)",
    "score": "(reach * impact * confidence) / effort"
  }
}
```
- Sort `roadmap_proposals` by `rice_score.score` descending
- Replace informal `priority` field with computed RICE score

---

## Quick Win 3: Dev TDD Protocol

**File**: `/root/.claude/agents/dev.md`
**Where**: After "Read Context" step, before implementation

**What to add** — new section "Step 0.5: Test-First Protocol":
1. From BA spec's acceptance criteria, write a minimal failing test (red)
2. Run it — verify it fails for the RIGHT reason
3. Implement the fix (green)
4. Run test again — verify it passes
5. If time allows, refactor (refactor)

**Rules**:
- Mandatory for bug fixes (test proves the bug exists before fix)
- Advisory for new features (write test if acceptance criteria are testable)
- Skip only when: pure CSS/styling changes, config changes, documentation
- Test goes in same script as verification (QA will run it)

---

## Quick Win 4: QA Self-Verification Loop

**File**: `/root/.claude/agents/qa.md`
**Where**: After Step 7 (Report Generation), add Step 8

**What to add** — "Step 8: Self-Verification":
1. List every claim in the report (e.g., "build passed", "criterion X verified", "no regressions")
2. For each claim, check: is there concrete evidence (screenshot, test output, measured value)?
3. Flag any claim backed only by "code looks correct" or "appears to work" — these are SUPERFICIAL
4. If any superficial claim found: go back and gather real evidence, or downgrade finding confidence
5. Add `self_verification` section to output:
```json
{
  "claims_total": 12,
  "claims_with_evidence": 11,
  "claims_superficial": 1,
  "superficial_details": ["Claim: 'form validation works' — only checked code, no browser test"]
}
```

---

## Quick Win 5: User Persona Definitions

**File**: `/root/.claude/agents/user.md`
**Where**: After "Your Role" section, before Step 0

**What to add** — "Persona-Based Testing" section:
- Define 4 personas:
  1. **First-Timer** — never used the app, expects clear onboarding, confused by jargon
  2. **Power User** — uses daily, expects keyboard shortcuts, batch operations, fast flows
  3. **Non-Technical** — low tech literacy, needs obvious affordances, fears "breaking things"
  4. **Impatient Mobile** — on phone, poor connection, wants task done in <30 seconds

- During Phase 4-6, mentally adopt each persona for at least 1 flow
- Tag each finding with `affected_personas: ["first-timer", "non-technical"]`
- Add `persona_coverage` to quality gates (minimum 2 personas tested)
- Add `personas_tested` array to output JSON

---

## Quick Win 6: User Frustration Signal Vocabulary

**File**: `/root/.claude/agents/user.md`
**Where**: After Persona section, before Phase protocol

**What to add** — "Frustration Signal Detection" section:
- Define vocabulary of signals to watch for:
  - `dead-end` — page with no forward action or next step
  - `circular-navigation` — navigating back to where you started without progress
  - `form-re-entry` — had to fill same data twice due to error/navigation
  - `unclear-next-step` — no visible CTA, user doesn't know what to do
  - `error-without-recovery` — error shown but no way to fix it or try again
  - `loading-without-feedback` — action triggered but no spinner/skeleton/progress
  - `hidden-action` — important action buried in menu/submenu/requires scroll
  - `inconsistent-pattern` — same action works differently on different pages

- Tag each issue with `frustration_signal: "dead-end"` (one of the above)
- Add `frustration_signals_detected` summary to output JSON

---

## Files Modified (Summary)

| File | Change Size | Risk |
|------|------------|------|
| `/root/.claude/agents/pm.md` | ~15 lines (TRIAGE output schema) | LOW |
| `/root/.claude/agents/product-owner.md` | ~20 lines (RICE schema + sorting) | LOW |
| `/root/.claude/agents/dev.md` | ~25 lines (TDD protocol section) | LOW |
| `/root/.claude/agents/qa.md` | ~25 lines (Step 8 self-verification) | LOW |
| `/root/.claude/agents/user.md` | ~50 lines (personas + frustration signals) | LOW |
| `/root/.claude/commands/dev-overnight.md` | ~8 lines (pipeline_blocked check) | LOW |
| **Total** | ~143 lines across 6 files | LOW |

## Verification

After implementation:
1. Read each modified file to confirm no syntax/formatting breaks
2. Verify the overnight orchestrator's Step 2→3 transition still works with the new pipeline_blocked check
3. Spot-check that new JSON fields in output schemas are valid
4. No runtime test needed — changes are agent prompt instructions, validated on next overnight run
