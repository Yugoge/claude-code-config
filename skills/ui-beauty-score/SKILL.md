---
name: ui-beauty-score
description: Aggregate aesthetic_findings, automated_findings, and alignment_measurements into a single 1.0-10.0 beauty_score plus 7 weighted sub-scores and a 0.0-1.0 consistencyScore. Pure calculation step — never fails. Use during ui-specialist Phase 7 (Aggregation) AFTER all other ui-* skills have completed and BEFORE writing the final 6-channel report.
---

# ui-beauty-score

Layer: **Aesthetic (Aggregation)**.
Output channel: feeds into the final report's `beauty_score`, `sub_scores`, and `consistencyScore` fields per spec 5.15.7 + 5.16.

## Trigger Conditions

Invoke this skill when:

- ui-specialist has finished Phases 4 / 4.5 / 5 / 6 / 6.5 — i.e., every other ui-* skill has emitted its findings for the page (or page set).
- The orchestrator is about to write the final report and needs aggregate scoring.

Do NOT invoke when:

- Any per-phase skill is still mid-execution (race risk: missing inputs).
- The page failed to navigate at all and there are zero findings of any channel — emit `beauty_score=null` directly without invoking the skill.

## Inputs

```
{
  "aesthetic_findings": [ { "rule_id": "...", "category": "hard_defect|taste_heuristic", "severity": "critical|major|minor|cosmetic", "advisory": true|false, ... } ],
  "automated_findings":  [ { "rule_id": "axe.* | apca.* | token.* | state.* | infra.*", "severity": "...", ... } ],
  "alignment_measurements": [ { "type": "grid|baseline|spacing", "deviation_px": <number>, "axis": "x|y|both", ... } ] (optional; empty array allowed),
  "scope": "page | flow | session"
}
```

## Outputs

A single ```json fenced block with this shape:

```
{
  "skill": "ui-beauty-score",
  "scope": "page|flow|session",
  "beauty_score": <float 1.0-10.0, 1 decimal>,
  "sub_scores": {
    "alignment_grid_discipline":   <float 1.0-10.0>,   // weight 0.30
    "color_harmony_token_adherence": <float 1.0-10.0>, // weight 0.20
    "typography_beauty":           <float 1.0-10.0>,   // weight 0.15
    "whitespace_rhythm":           <float 1.0-10.0>,   // weight 0.10
    "glass_morphism_quality":      <float 1.0-10.0>,   // weight 0.10
    "animation_polish":            <float 1.0-10.0>,   // weight 0.10
    "accessibility_advisory":      <float 1.0-10.0>    // weight 0.05
  },
  "weights": {
    "alignment_grid_discipline":   0.30,
    "color_harmony_token_adherence": 0.20,
    "typography_beauty":           0.15,
    "whitespace_rhythm":           0.10,
    "glass_morphism_quality":      0.10,
    "animation_polish":            0.10,
    "accessibility_advisory":      0.05
  },
  "consistencyScore": <float 0.0-1.0, 2 decimals>,
  "calculation_basis": {
    "aesthetic_finding_count": <int>,
    "automated_finding_count": <int>,
    "alignment_measurement_count": <int>,
    "missing_inputs": [ "alignment_measurements" ] // any input arrays not provided
  },
  "rationale": "<one short sentence per sub-score; cite rule_ids that drove deductions>",
  "unknowns": [],
  "needs_review": []
}
```

## Calculation Rules (Aggregator semantics)

**Each sub-score starts at 10.0 and is reduced by weighted finding penalties.** Per spec 5.15.7, missing inputs default to 9.0 (NOT 10.0 — 10.0 requires positive evidence that the relevant rules were checked AND zero penalties accrued).

### Sub-score → finding rule_id prefix mapping

| sub_score                          | weight | drawn from                                                                                       |
|------------------------------------|--------|--------------------------------------------------------------------------------------------------|
| `alignment_grid_discipline`        | 0.30   | `alignment_measurements[]` deviations + aesthetic rules `spacing.*`, `layout.*`                  |
| `color_harmony_token_adherence`    | 0.20   | `token.color.*`, aesthetic `color.*`, `apca.*` informing palette discipline                      |
| `typography_beauty`                | 0.15   | `token.typography.*`, aesthetic `typography.*`                                                   |
| `whitespace_rhythm`                | 0.10   | `token.spacing.*`, aesthetic `spacing.*`, baseline-grid measurements                             |
| `glass_morphism_quality`           | 0.10   | aesthetic `glass.*`                                                                              |
| `animation_polish`                 | 0.10   | aesthetic `motion.*`                                                                             |
| `accessibility_advisory`           | 0.05   | `axe.*`, `apca.*`, `ctx.*` — ADVISORY contribution only; never a hard cap on beauty_score        |

### Penalty per finding by severity

- `critical`  → −2.5 from the relevant sub-score (floor 1.0)
- `major`     → −1.5
- `minor`     → −0.7
- `cosmetic`  → −0.3
- `advisory:true` taste-heuristic findings → −0.3 max (capped, regardless of declared severity, per spec 5.16 schema-enforced cap)

### `beauty_score` formula

```
beauty_score = sum(sub_score_i * weight_i for i in 7 categories)
             clamped to [1.0, 10.0]
             rounded to 1 decimal
```

### `consistencyScore` formula

```
consistencyScore = 1.0 - (count_of_token_violations / max(1, count_of_token_checks))
                   clamped to [0.0, 1.0]
                   rounded to 2 decimals
```

If the `ui-token-conformance` skill emitted `capability_unavailable`, `consistencyScore = null` and add `"consistencyScore_basis": "capability_unavailable"` to `calculation_basis`.

## Fallback Strategy

**Pure calculation never fails.** If any input array is missing or empty:
- The associated sub-scores default to **9.0** (per spec 5.15.7 — NOT 10.0; 10.0 requires positive zero-finding evidence).
- The missing input names are added to `calculation_basis.missing_inputs[]`.
- `unknowns[]` gets one entry per missing channel: `{ "thing_not_tested": "<channel>", "reason": "input not provided to ui-beauty-score" }`.

There is no Tier-2 / Tier-3 fallback because there is no external dependency.

## Example Invocation

ui-specialist Phase 7 prompt fragment: *"All earlier ui-* skills have emitted their findings. Use the ui-beauty-score skill to compute the final beauty_score, sub_scores, and consistencyScore from aesthetic_findings + automated_findings + alignment_measurements before writing the report."*

---

Your final message MUST be a single ```json fenced block, nothing else
