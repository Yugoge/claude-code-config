# Fix: JD Coverage Gap Handling in Resume Pipeline

## Context

When generating a resume for a KDB+/Q Developer role, the pipeline identified 3 uncovered JD skills (KDB+/q, Low-latency systems, High-performance computing) but:
1. **Skills story expert** ignored the gaps entirely -- only selected from YAML skills, no gap reporting
2. **Writing expert** never received `depth_markers` from story experts -- data dropped by manifest/prompt scripts
3. **Orchestrator** never surfaced the gaps to the user before proceeding

6 critique agents all flagged the KDB+/q gap loudly, but their feedback was not enforced. The professional story expert DID write correct "Frame as: transferable to KDB+" instructions in the `story` field, but the writing expert partially ignored them because `depth_markers` (the structured enforcement mechanism) was dropped.

## Changes

### Fix 1: `scripts/generate_bullet_manifest.py` (line 256)
Add `depth_markers` extraction from story plan bullets.

```python
# Add after line 256 ("exclusive_metrics": bullet.get("exclusive_metrics", []),)
"depth_markers": bullet.get("depth_markers", []),
```

### Fix 2: `scripts/generate-writing-prompts.py` (line 140)
Add `depth_markers` to the writing prompt payload.

```python
# Add after line 140 ("stakeholder_context": bullet.get("stakeholder_context", ""),)
"depth_markers": bullet.get("depth_markers", []),
```

### Fix 3: `.claude/agents/story-expert-skills.md`
Add Step 3b and Rule 6 for coverage gap handling.

**Step 3b (after Step 3, before Step 4)**: "Analyze Coverage Gaps"
- Read `coverage_report` from jd_scores
- For each `covered: false` item:
  - Check if candidate has a transferable skill in YAML (skills, experience, projects)
  - Classify as `critical` (no transferable skill at all) or `addressable` (has related skills)
- Do NOT fabricate skills the candidate doesn't have
- Report gaps in output JSON `coverage_gaps` field

**Rule 6**: "Coverage Gap Reporting"
- Must read coverage_report, identify all `covered: false` items
- Search YAML for transferable skills
- Write `coverage_gaps` array to output JSON
- Never add skills candidate doesn't possess

**Output schema addition**:
```json
"coverage_gaps": [
  {"skill": "KDB+/q", "covered": false, "transferable_skills": [], "severity": "critical"},
  {"skill": "Low-latency systems", "covered": false, "transferable_skills": ["C++"], "severity": "addressable"}
]
```

### Fix 4: `.claude/commands/generate.md` (after Step 2.6 verification, before Step 3)
Add coverage gap check that pauses pipeline and asks user when critical gaps exist.

Insert after line 574 ("echo "[SUCCESS] JD scores created""):

```bash
# Check for critical JD gaps
CRITICAL_GAPS=$(source venv/bin/activate && python3 -c "
import json
with open('${JD_SCORES}') as f:
    data = json.load(f)
report = data.get('coverage_report', {})
gaps = [skill for skill, info in report.items() if not info.get('covered', True)]
if gaps:
    print('GAPS_FOUND')
    for g in gaps:
        print(f'  - {g}')
else:
    print('ALL_COVERED')
")
```

If GAPS_FOUND: Use AskUserQuestion to show uncovered skills and ask whether to continue or abort to update YAML first.

## Files to Modify

1. `scripts/generate_bullet_manifest.py` -- 1 line addition at line 256
2. `scripts/generate-writing-prompts.py` -- 1 line addition at line 140
3. `.claude/agents/story-expert-skills.md` -- Add Step 3b, Rule 6, update output schema, update checklist
4. `.claude/commands/generate.md` -- Add gap check block after Step 2.6 verification

## Verification

1. Run `python scripts/generate_bullet_manifest.py` on existing story plans and verify `depth_markers` appears in manifest JSON
2. Run `python scripts/generate-writing-prompts.py` on the manifest and verify `depth_markers` appears in prompt files
3. Re-run `/generate` for the same JD and confirm:
   - Pipeline pauses after JD scoring to show coverage gaps
   - Skills story expert output includes `coverage_gaps` field
   - Writing expert prompt files contain `depth_markers` arrays
