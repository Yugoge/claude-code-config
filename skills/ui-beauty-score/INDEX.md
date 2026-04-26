# ui-beauty-score — Index

## Files

- `SKILL.md` — operational contract (frontmatter, trigger, inputs, outputs, calculation rules, fallback)
- `README.md` — purpose, role within ui-specialist pipeline, failure mode
- `INDEX.md` — this file

## Position in the ui-specialist pipeline

```
Phase 4    → ui-state-matrix
Phase 4.5  → ui-anti-pattern-catalog (interactive subset)
Phase 5    → ui-token-conformance, ui-anti-pattern-catalog (aesthetic)
Phase 6    → ui-axe-injector, ui-apca-contrast, ui-contextual-heuristics
Phase 6.5  → ui-anti-pattern-catalog (Nielsen + AI-slop subset)
Phase 7    → ui-beauty-score   ← THIS SKILL
            → report write
```

## Related shared artifacts

- `/root/.claude/skills/ui-shared/report-schema.json` — defines `beauty_score`, `sub_scores`, `consistencyScore` constraints
- `/root/.claude/skills/ui-shared/rule-map.json` — source for rule_id severity caps
- `/root/.claude/skills/ui-shared/anti-pattern-catalog.yml` — source of `aesthetic_findings` rule_ids
- `/root/.claude/skills/ui-shared/review-phases.yml` — phase ordering

## Related skills (consumers of this skill's output)

- ui-specialist (writes final report including this skill's output)

## Spec references

- §5.15.7 — sub-score weights and missing-input default (9.0)
- §5.16 — taste-heuristic advisory cap (−0.3 max regardless of severity)
- §5.6 — three-rule conflict reconciliation (advisory cap is rule #2)