# Plan: Overnight PM Focus Mechanism & Authority Enhancement

## Context

The overnight dev workflow has run 4 sessions on Applio, fixing 70+ issues across security, UI, and accessibility. But the PM's original goal -- "run the full resume generation flow end-to-end" -- was never achieved because the 85% pipeline timeout (backend Step 3 Story Planning) was never addressed. Root cause: PM writes a test plan once and exits; specialists discover issues independently with no priority guidance; all pipelines run with equal resources; no cross-cycle continuity.

This plan adds **PM authority at three points per cycle** (Plan, Triage, Retrospective), **priority-aware specialist dispatch**, **strengthened core flow gate**, and **cross-cycle issue tracking**.

---

## Files to Modify (in order)

| # | File | Change |
|---|------|--------|
| 1 | `~/.claude/scripts/todo/dev-overnight.py` | 13 steps -> 14 steps (add PM Retrospective) |
| 2 | `~/.claude/agents/pm.md` | Add Triage + Retro protocols, schemas, blocker rules |
| 3 | `~/.claude/agents/user.md` | Strengthen core flow gate completion criteria |
| 4 | `~/.claude/commands/dev-overnight.md` | Add Step 2c, Step 13, modify Step 3, schema v7 |
| 5 | `~/.claude/hooks/posttool-overnight-loop.py` | Update message text for 14-step count |
| 6 | Specialist agents (product-owner, architect, ui-specialist) | Add `pm_tier` field + priority context reading |

---

## 1. Todo Script (`dev-overnight.py`)

**Must be updated FIRST** -- hooks enforce canonical step count.

```python
_STEPS = [
    ("Create worktree (first run only)", "Creating worktree"),
    ("Explore codebase for issues (PM plan + 4 specialists + PM triage)", "Exploring codebase for issues"),  # modified
    ("Create parallel pipelines from PM triage", "Creating parallel pipelines from PM triage"),  # modified
    ("Run all BA subagents (parallel)", "Running all BA subagents in parallel"),
    ("Validate all BA outputs", "Validating all BA outputs"),
    ("Run all Dev subagents (parallel)", "Running all Dev subagents in parallel"),
    ("Validate all Dev implementations", "Validating all Dev implementations"),
    ("Run all QA subagents (parallel)", "Running all QA subagents in parallel"),
    ("Process all QA results", "Processing all QA results"),
    ("Run iteration loops for failed pipelines", "Running iteration loops for failed pipelines"),
    ("Update settings.json permissions (aggregated)", "Updating settings.json permissions"),
    ("Log all cycle results and check time", "Logging all cycle results and checking time"),
    ("PM Retrospective (cycle summary + next-cycle handoff)", "Running PM Retrospective"),  # NEW
    ("Generate summary report or loop", "Generating summary report or looping"),  # renumbered 13->14
]
```

---

## 2. PM Agent (`pm.md`)

### 2a. Add Invocation Modes section (after Boundaries)

Three modes: PLAN (existing, enhanced), TRIAGE (new), RETRO (new). Prompt contains `PM_MODE: PLAN|TRIAGE|RETRO`.

### 2b. Enhance PLAN mode

- Read all previous `retro-report-cycle*.json` for cross-cycle continuity
- Add `priority_tiers` to test-plan.json (tier_1_blockers, tier_2_major, tier_3_minor)
- Add `unresolved_from_previous` array from last retro report
- Add `strategic_notes` from previous patterns

### 2c. Add TRIAGE protocol (new section)

Invoked after all 4 specialist reports arrive. Steps:
1. Read all 4 reports + own test-plan.json
2. Classify every issue into tiers using blocker rules (below)
3. Deduplicate (same issue from multiple agents = one entry, higher confidence)
4. Determine Focus Mode vs Normal Mode
5. Write `triage-report-cycle<N>.json`

**Blocker Classification Rules:**

| Condition | Tier | Recommendation |
|-----------|------|---------------|
| Core flow blocked (user core_flow_completed=false) | 1 | fix |
| >50% failure rate on core action | 1 | fix |
| Security vulnerability with active exposure | 1 | fix |
| Data loss/corruption risk | 1 | fix |
| Unresolved for 2+ cycles | 1 | fix |
| Feature broken, not blocking core flow | 2 | fix (normal) / defer (focus) |
| Flagged by 2+ agents, major severity | 2 | fix |
| Single-agent minor finding | 3 | fix (normal) / skip (focus) |
| Cosmetic, any source | 3 | fix (normal) / skip (focus) |
| Previously failed 3+ times | any | skip |

**Focus Mode** activates when: 3+ Tier 1 blockers, OR core flow gate failed, OR issue unresolved 2+ cycles. In Focus Mode: max 3 pipelines (all Tier 1), Tier 2/3 deferred.

**Normal Mode**: All tiers get pipelines, ordered Tier 1 -> 2 -> 3, within tier by agent consensus count.

**Triage Report Schema:**
```json
{
  "triage_id": "tr-YYYYMMDD-HHMMSS",
  "plan_id": "<matching>",
  "session_id": "<id>",
  "cycle_number": N,
  "mode": "focus|normal",
  "mode_reason": "string",
  "core_flow_status": "passed|failed|reliability_blocked",
  "issues": [{
    "triage_index": 0, "tier": 1,
    "description": "...", "location": "...",
    "severity": "critical", "category": "...",
    "agents_flagged": ["user", "architect"],
    "estimated_effort": "small",
    "pipeline_recommendation": "fix|skip|defer",
    "skip_reason": null,
    "unresolved_cycles": 0
  }],
  "pipeline_order": [0, 1, 2],
  "skipped_issues": [{"description": "...", "skip_reason": "..."}],
  "strategic_notes": "..."
}
```

### 2d. Add RETRO protocol (new section)

Invoked after Step 12 (log results). Steps:
1. Read own triage report + all pipeline QA/Dev reports + previous retro reports
2. Compare plan vs outcome for each triaged issue
3. Build `unresolved_issues` array (failed + deferred + still-open from previous)
4. If `FINAL_CYCLE: true`: add `final_summary` with goals achieved/not achieved

**Retro Report Schema:**
```json
{
  "retro_id": "rr-YYYYMMDD-HHMMSS",
  "session_id": "<id>", "cycle_number": N,
  "is_final_cycle": false,
  "plan_vs_outcome": [{
    "triage_index": 0, "description": "...",
    "tier": 1, "pipeline_recommendation": "fix",
    "actual_outcome": "fixed|failed|skipped|deferred",
    "iterations_used": 2, "failure_reason": null
  }],
  "cycle_stats": {
    "issues_triaged": 8, "issues_attempted": 6,
    "issues_fixed": 4, "issues_failed": 2,
    "fix_rate": 0.67, "focus_mode_used": false
  },
  "unresolved_issues": [{
    "description": "...", "severity": "critical",
    "cycles_unresolved": 2,
    "last_attempt_reason": "...",
    "recommended_approach": "..."
  }],
  "patterns_noticed": ["..."],
  "recommendations_for_next_cycle": ["..."],
  "final_summary": null
}
```

Final summary (only when `is_final_cycle: true`):
```json
{
  "final_summary": {
    "total_cycles": 3,
    "total_issues_fixed": 18,
    "total_issues_unresolved": 6,
    "goals_achieved": ["..."],
    "goals_not_achieved": ["..."],
    "needs_human_attention": [{"description": "...", "reason": "...", "cycles_attempted": 3}]
  }
}
```

---

## 3. User Agent (`user.md`)

### 3a. Strengthen core flow gate (Phase 4)

Add after existing core flow steps:

**`core_flow_completed: true` requires ALL of:**
1. Every step executed (not just started)
2. Async operations (generation, build) WAITED for completion
3. Final result is meaningful and correct (not empty/error)
4. Result persists across navigation (refresh, navigate away/back)

**"submitted" is NOT "completed"**: Seeing a loading spinner and moving on = `partial`, not `full`.

### 3b. Add completion depth to output schema

```json
"core_flow_completion_depth": "full|partial|blocked",
"core_flow_completion_evidence": {
  "steps_total": 5, "steps_completed_successfully": 5,
  "async_operations_awaited": true,
  "result_validated": true,
  "failure_point": null
},
"core_flow_reliability": {
  "attempts": 3, "successes": 2, "failure_rate": 0.33,
  "status": "reliable|flaky|unreliable",
  "reliability_blocked": false
}
```

### 3c. Add reliability testing

After first successful core flow: repeat 2 more times with different data. If >=50% fail: set `reliability_blocked: true`. PM triage treats this as Tier 1 blocker.

### 3d. Priority context awareness in Step 0

Read `priority_tiers` and `unresolved_from_previous` from test plan. Focus exploration on Tier 1 issues first.

---

## 4. Overnight Command (`dev-overnight.md`)

### 4a. Step 2 enhancement

Step 2 now has three sub-steps:
- **2a**: PM-Plan (existing, enhanced with cross-cycle continuity)
- **After 2a**: Main agent reads test-plan.json, extracts priority context string
- **2b**: 4 specialists launched with priority context appended to prompts
- **2c**: PM-Triage (NEW) -- reads all 4 reports, writes triage-report

### 4b. Step 3 rewrite

Replace mechanical merge/sort with:
1. Read PM triage report
2. Use `pipeline_order` as authoritative ordering
3. Only create pipelines for `pipeline_recommendation: "fix"`
4. Fallback: if triage report missing, use legacy mechanical sort

### 4c. New Step 13: PM Retrospective

Launch PM in RETRO mode. Input: triage report + pipeline results + previous retros. Output: retro-report-cycle<N>.json. If time expired: `FINAL_CYCLE: true` triggers final summary.

### 4d. Renumber Step 13 -> Step 14

Existing "Generate summary or loop" becomes Step 14.

### 4e. State file schema v7

New fields: `pm_triage_reports: []`, `pm_retro_reports: []`, `unresolved_issues: []`. New phase value: `"retrospective"`. Migration from v6: add empty arrays.

### 4f. Global updates

- All "13 steps" references -> "14 steps"
- Overview diagram updated
- Continuation mode phase mapping: `retrospective -> Step 13`
- Comparison table: Total steps 14
- IMPORTANT RULES: rule 3 mentions PM triage authority

---

## 5. Loop Hook (`posttool-overnight-loop.py`)

Cosmetic: Update `_print_loop_instructions` message:
```python
print(f'OVERNIGHT LOOP: Cycle {cc} complete (PM retro filed). Starting cycle {cc + 1}.')
```

---

## 6. Specialist Agents (product-owner, architect, ui-specialist)

Minor: Add to each agent's Step 0:
- Read inline priority context from prompt
- Add `pm_tier: 1|2|3|new` field to each reported issue
- Investigate Tier 1 areas first, Tier 2 second, then explore freely

---

## Verification

After implementation:
1. Run `python3 ~/.claude/scripts/todo/dev-overnight.py` -- verify 14 steps output
2. Verify pm.md has PLAN/TRIAGE/RETRO sections with complete schemas
3. Verify user.md has completion_depth, reliability testing, and "submitted != completed"
4. Verify dev-overnight.md has Step 2c, Step 13, updated Step 3, schema v7
5. Search dev-overnight.md for "13" to ensure no stale references remain
6. Run a test overnight session on Applio to validate the full cycle
