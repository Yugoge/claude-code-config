---
name: ui-contextual-heuristics
description: Five LLM-driven contextual accessibility insights that axe cannot detect (heading hierarchy, link text, focus order, color reliance, decorative-as-interactive). MUST receive axe findings as input and dedup against them. Use during ui-specialist Phase 6 (Accessibility) AFTER ui-axe-injector.
---

# ui-contextual-heuristics

Layer: **Contextual (L2)**.
Output channel: `contextual_findings[]` with `rule_id="ctx.<insight>"`, each carrying `requires_human` + `reasoning` per spec 5.15.5.

## Trigger Conditions

Invoke this skill when:

- ui-specialist enters **Phase 6 (Accessibility Audit)** AND `ui-axe-injector` has already returned for the same page.
- The subagent has the axe automated_findings available to pass in as `axe_findings_to_dedupe`.

Invocation order MATTERS: this skill MUST run AFTER ui-axe-injector (per spec 5.19 #2). Running it before axe means the dedup is impossible and contextual findings will double-count axe-detectable defects.

## Inputs

```
{
  "page_url": "string",
  "viewport": "mobile|desktop",
  "axe_findings_to_dedupe": [
    { "rule_id": "axe.<rule>", "location": "<selector>", "description": "..." }
  ],
  "snapshot_text": "result of recent browser_snapshot (accessibility tree)",
  "page_html": "optional: outerHTML of <main> region for source review"
}
```

## Outputs

A single ```json fenced block:

```
{
  "skill": "ui-contextual-heuristics",
  "page_url": "<url>",
  "viewport": "mobile|desktop",
  "insights_evaluated": 5,
  "deduped_against_axe": <integer count of items dropped because axe already raised>,
  "contextual_findings": [
    {
      "rule_id": "ctx.heading-hierarchy-broken | ctx.link-text-ambiguous | ctx.focus-order-illogical | ctx.color-only-information | ctx.decorative-as-interactive",
      "description": "...",
      "location": "<page_url> + selector",
      "severity": "minor|major (capped per rule-map.json)",
      "evidence_mode": "contextual",
      "requires_human": true,
      "reasoning": "<one-paragraph justification — what was observed, why it concerns the LLM, what risk it implies>",
      "deduped_against": "axe.<rule> | null",
      "false_positive_risk": "medium|medium-high"
    }
  ],
  "needs_review": [],
  "unknowns": []
}
```

## The Five Insights (per spec 5.15.5)

### 1. ctx.heading-hierarchy-broken

Beyond axe.heading-order (which catches strict ascending violations), evaluate whether the heading structure is **semantically meaningful**: are h2/h3 placements aligned with content sections? Is there a single h1 that names the page? Are h4s used as styling shortcuts rather than for outline depth?

Dedup: drop if axe.heading-order already raised on the same selector chain.

### 2. ctx.link-text-ambiguous

Beyond axe.link-name (which checks for non-empty accessible name), evaluate whether the link text is **contextually meaningful** when read out of context (screen-reader rotor, voice control). "Read more" / "Click here" / "Learn more" without an aria-label or surrounding context = flag.

Dedup: drop if axe.link-name already raised on the exact element.

### 3. ctx.focus-order-illogical

Tab through interactive elements with `browser_press_key("Tab")` and compare the visual reading order (left-to-right, top-to-bottom) to the actual tab order. If the visual flow says A→B→C but Tab goes A→C→B, flag — keyboard users will be lost.

Dedup: no axe overlap (axe does not evaluate visual-vs-DOM order).

### 4. ctx.color-only-information

Beyond axe.color-contrast, evaluate whether color is the SOLE channel conveying information (e.g., a status badge that uses only red/green with no icon, label, or pattern). Color-blind users cannot distinguish.

Dedup: drop if axe.color-contrast raised AND the element has no extra information layer at all.

### 5. ctx.decorative-as-interactive

Find SVG/icon elements that present as clickable (cursor:pointer + onclick) but are decorative-only in semantics (no aria-label, no role=button, not in a focusable element). Touch users will tap and nothing will happen.

Dedup: no direct axe overlap.

## Dedup Algorithm (mandatory)

For each candidate finding the LLM identifies, before adding it to `contextual_findings`:

1. Iterate `axe_findings_to_dedupe[]`.
2. If any axe finding matches on (a) same CSS selector OR (b) same accessible-name region AND (c) addresses the same defect class → drop the contextual finding and increment `deduped_against_axe`.
3. Otherwise emit the contextual finding with `deduped_against` set to the closest axe rule_id you considered (or `null` if no near-overlap).

## Severity Cap & requires_human

All contextual findings have `requires_human: true` per spec 5.15.5 — they are LLM judgement, not deterministic measurement. The subagent aggregator should NOT auto-elevate any contextual finding to `critical` without explicit task-success/readability/consistency triple-gate justification.

## Fallback Strategy

Single-tier: if `axe_findings_to_dedupe` is empty (e.g., axe soft-failed for this page), proceed with insight evaluation but emit a `needs_review[]` warning: `{ "question": "axe baseline missing; contextual findings on <page> may double-count axe-detectable defects", "false_positive_risk": "medium-high" }`. Set every emitted finding's `false_positive_risk` to `medium-high` for the page.

## Example Invocation

ui-specialist Phase 6 prompt fragment: *"Use the ui-contextual-heuristics skill on the current page; pass the axe findings just returned as axe_findings_to_dedupe."*

---

Your final message MUST be a single ```json fenced block, nothing else
