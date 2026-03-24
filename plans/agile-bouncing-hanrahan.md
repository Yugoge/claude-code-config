# Plan: Story Plan Restructure + Designer Layout-Only + Dynamic char_limit

## Context

Three architectural issues:
1. **Story plan is flat**: Each experience entry has a flat bullets array with no overall STAR summary. The story expert has no "entry-level narrative overview" — just a list of per-bullet plans.
2. **Designer is not layout-only**: designer.md contains content guidance (education description text, skills content). The designer is supposed to be a pure layout artist — section selection, line budgets, title lines, height estimation only.
3. **char_limit is hardcoded as a single value**: All bullets use the same 95-char limit regardless of whether a story needs 1 or 2 lines. Multi-line bullets should have `lines × chars_per_line` as their budget.

---

## Change 1: Story Plan Structure

### New structure for professional/project entries

```json
{
  "entry_id": "exp_0",
  "summary": "Complete STAR overview of this experience entry — the full narrative arc: what challenge existed, what was done across all bullets, what the overall business impact was.",
  "bullets": {
    "1": {
      "story": "STAR story for this specific bullet...",
      "depth_markers": ["Python", "OIS/SOFR", "DV01"],
      "stakeholder_context": "escalated by quant team...",
      "impact_context": "restoring trading desk risk metrics...",
      "lines": 1
    },
    "2": {
      "story": "...",
      "depth_markers": [...],
      "stakeholder_context": "...",
      "impact_context": "...",
      "lines": 2
    }
  }
}
```

**Key rules for story expert**:
- `summary`: One paragraph, full STAR for the whole experience. No length limit.
- `bullets`: Dict keyed by bullet_index string ("1", "2", ...). Each value = content dict + `lines` field.
- `lines`: 1 (default), 2 (needs more detail), 3 (rarely, only for complex stories).
- **Constraint**: `sum(bullet["lines"] for bullet in bullets.values()) == line_budget from design spec`
- Designer now gives `line_budget` (total lines), not `bullet_count`. Story expert decides how to distribute those lines across bullets.

### Education description

`story-expert-education.md` is now responsible for writing the `description` field for each entry:
- Reads YAML + JD context
- Writes actual description text: "GPA: 3.64/4.0 | 2nd in major | ..." or "Relevant Coursework: X, Y, Z"
- Outputs `description` in each entry (alongside `bullets: {}`)

---

## Change 2: Designer — Layout Only

### Remove from designer.md
- Education description writing (the `### How to decide education description` section and all examples of writing description text)
- Remove `selected_courses`, `selected_honors`, `description_type` from output schema — already done in prior commits, need to also remove the "write `description` directly" instruction added in last commit
- Any other content guidance

### Add/change in designer.md
- Change `bullet_count` → `line_budget` per experience entry (total lines for that entry)
- Remove education `description` field from output schema — education entry just has `title_line` + `estimated_lines: 2`
- Keep: section selection logic, title line format, height estimation formula, simulation loop

### Updated education entry in design spec
```json
{
  "id": "edu_0",
  "institution": "HEC Paris",
  "title_line": "HEC Paris | MSc International Finance | Sep 2023 - Mar 2025 | Paris, FR",
  "estimated_lines": 2
}
```
No `description`, no `bullet_count`, no `description_type`. Just layout.

### Updated experience entry
```json
{
  "id": "exp_0",
  "company": "Orchestrade",
  "title_line": "Orchestrade | Pricing & Risk Business Analyst | Sep 2025 - Present | Paris, FR",
  "line_budget": 15,
  "relevance_score": 99,
  "estimated_lines": 16
}
```
`line_budget: 15` means 15 lines of bullets (some may be 2-line bullets).

---

## Change 3: Dynamic char_limit

### How char_limit flows currently
- `simulate_layout.py` computes `chars_per_line` from the template (already template-derived)
- `generate_bullet_manifest.py` calls `extract_char_limit(simulation)` → reads `line_char_limits.bullet.single[1]` from simulation result
- Manifest top-level `char_limit: 95` is already NOT hardcoded — it comes from the template

### The actual problem
All bullets use the same top-level `char_limit` even if `lines: 2`. Need per-bullet char_limit.

### Fix
In `generate_bullet_manifest.py`, when building each bullet entry:
```python
single_limit = char_limit  # from simulation (template-derived)
bullet_lines = bullet.get("lines", 1)
per_bullet_char_limit = bullet_lines * single_limit
bullets.append({
    ...,
    "lines": bullet_lines,
    "char_limit": per_bullet_char_limit,
    ...
})
```

In `generate-writing-prompts.py`, payload uses per-bullet `char_limit` from the bullet entry (already there since we read `bullet.get("char_limit", char_limit)`)... actually need to update this.

In `validate-bullet-charlimits.py` draft mode: already uses global `char_limit`. Update to use per-entry `char_limit` if present (already done in revision mode — apply same pattern to draft mode).

---

## Files to Change

| File | Change |
|------|--------|
| `.claude/agents/designer.md` | Remove ALL content guidance. Change `bullet_count` → `line_budget`. Remove `description` from education entry. Remove description writing instructions. |
| `.claude/agents/story-expert-professional.md` | Add `summary` at entry level. Change `bullets` list → dict. Add `lines` per bullet. Read `line_budget` from design spec. `sum(lines) == line_budget`. |
| `.claude/agents/story-expert-project.md` | Same as professional: add summary, dict bullets with lines, use line_budget. |
| `.claude/agents/story-expert-education.md` | Add responsibility to write `description` for each entry (reads YAML + JD). |
| `scripts/assemble_resume.py` | Read education description from story plan entry (`story_entry.get('description', '')`) instead of design spec. |
| `scripts/simulate_layout.py` | Change `entry.get("bullet_count", 0)` → `entry.get("line_budget", 0)` for professional/project entries. |
| `scripts/generate_bullet_manifest.py` | Handle dict `bullets`. Add `lines` field. Compute per-bullet `char_limit = lines × single_limit`. |
| `scripts/generate-writing-prompts.py` | Use per-bullet `char_limit` from bullet entry (not top-level global). |
| `scripts/validate-bullet-charlimits.py` | Draft mode: use per-entry `char_limit` if present, else fall back to global. |
| `.claude/agents/writing-expert.md` | Update char limit rule for multi-line. Update dual-line strategy. Extract `lines` from entry file. |

---

## Data Flow After Changes

```
designer → line_budget per experience (layout only, no content)
         → title lines (layout only)
         → education: just title_line + estimated_lines: 2

story-expert-education → description text per education entry (content)
story-expert-professional → summary + bullets dict with lines (content)
story-expert-project → summary + bullets dict with lines (content)

simulate_layout.py: uses line_budget directly (total lines for experience)

generate_bullet_manifest.py:
  - iterates bullets dict (sorted by int(key))
  - per-bullet char_limit = lines × single_limit

generate-writing-prompts.py:
  - passes per-bullet char_limit to each prompt file

assemble_resume.py:
  - education description from story plan, not design spec
```

---

## Verification

1. Run `python scripts/generate_bullet_manifest.py ...` with a test story plan that has dict bullets — verify output has per-bullet `char_limit` and `lines` fields
2. Run `python scripts/generate-writing-prompts.py ...` — verify prompt files have correct per-bullet char_limit
3. Run `python scripts/validate-bullet-charlimits.py ... draft` — verify per-entry char_limit is used
4. Run `python scripts/simulate_layout.py ...` with a design spec using `line_budget` — verify height_ratio computed correctly
5. Run `python scripts/assemble_resume.py ...` with a story plan that has education `description` — verify description present in output

No full end-to-end run needed — applies to future /generate runs.
