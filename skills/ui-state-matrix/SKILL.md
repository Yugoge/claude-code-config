---
name: ui-state-matrix
description: Verify presence of 7 interactive states (default / hover / focus / active / disabled / loading / error / success) on key interactive elements. Returns deterministic state.* findings + state_coverage_pct + not_applicable[]. Use during ui-specialist Phase 4 (Interactive Element Visual Testing).
---

# ui-state-matrix

Layer: **Deterministic (L1)**.
Output channel: `automated_findings[]` with `rule_id="state.missing-<state>"` plus a `state_coverage_pct` summary.

## Trigger Conditions

Invoke this skill when:

- ui-specialist enters **Phase 4 (Interactive Element Visual Testing)** for any page.
- The page has interactive elements visible (buttons, links, inputs, toggles, switches, comboboxes).

## Inputs

```
{
  "page_url": "string",
  "viewport": "mobile|desktop",
  "elements_to_check": "optional: array of CSS selectors; defaults to all visible interactive elements",
  "states_to_check": "optional: subset of [default,hover,focus,active,disabled,loading,error,success]; defaults to all 7 except success"
}
```

## Outputs

A single ```json fenced block:

```
{
  "skill": "ui-state-matrix",
  "page_url": "<url>",
  "viewport": "mobile|desktop",
  "elements_examined": <integer>,
  "state_coverage_pct": <0.0-100.0>,
  "automated_findings": [
    {
      "rule_id": "state.missing-<state>",
      "description": "<element selector> has no observable <state> state",
      "location": "<page_url> + selector",
      "severity": "minor|major (focus state missing => major; others minor)",
      "evidence_mode": "deterministic",
      "evidence": "<screenshot filename>",
      "false_positive_risk": "low|medium"
    }
  ],
  "not_applicable": [
    { "selector": "<sel>", "state": "hover", "reason": "touch-only viewport" },
    { "selector": "<sel>", "state": "loading", "reason": "synchronous action; no async load" }
  ],
  "needs_review": [],
  "unknowns": []
}
```

## State Detection Method

For each interactive element and each state to check:

| State    | Trigger                                                        | Verification |
|----------|----------------------------------------------------------------|--------------|
| default  | element in normal rendered state                               | screenshot baseline |
| hover    | `browser_hover` on element (desktop only)                      | computed style differs from default |
| focus    | `browser_press_key("Tab")` until element is `document.activeElement` | computed outline / box-shadow / ring differs from default |
| active   | `browser_press_key(" ")` or mousedown via evaluate             | computed style during pressed state |
| disabled | element has `disabled` attribute / aria-disabled / pointer-events:none | computed style + opacity reduced or distinct |
| loading  | element has `aria-busy=true` / `data-loading` / spinner child  | observable spinner / disabled style / aria-busy |
| error    | element has `aria-invalid=true` / `data-error` / red border    | distinctive error styling |
| success  | element has `aria-checked=true` (toggle) / data-success / green border | distinctive success styling |

## N/A Handling (per spec 5.20 A4 + 5.15.4)

A state may be legitimately N/A:

- `hover` is N/A on `viewport=mobile` (touch-only).
- `loading` is N/A on a synchronous action (e.g., navigation link with no async work).
- `disabled` is N/A on read-only display elements (e.g., a label).
- `success` is N/A on stateless buttons.

When N/A, record the element + state + reason in `not_applicable[]` instead of `automated_findings[]`. Do NOT fabricate findings on N/A combinations.

## Loading-State Duration Extension (spec 5.20 A4)

When a `loading` state is observed:

- If the loading state persists < 5s and resolves: emit no finding (normal behaviour).
- If the loading state persists ≥ 5s but < 30s: emit `infra.loading-timeout` to `needs_review[]` (slow but not broken).
- If the loading state persists ≥ 30s without resolution: emit `infra.loading-timeout` to `needs_review[]` AND attempt to navigate-away to confirm not stuck; record observation in `evidence`.

## Severity Mapping

- `state.missing-focus` → `major` (keyboard accessibility violation)
- `state.missing-default` / `state.missing-disabled` / `state.missing-loading` / `state.missing-error` → `minor` (cap at major if user-flow blocking)
- `state.missing-hover` → `minor` (cosmetic on touch; major on desktop primary CTAs)
- `state.missing-active` → `minor`
- `state.missing-success` → `minor`

## Fallback Strategy

Single-tier: if Playwright cannot trigger a state via the documented method (e.g., `browser_hover` not supported), record the state in `not_applicable[]` with reason `cannot-trigger-state-in-current-environment`. Continue with remaining states.

## Example Invocation

ui-specialist Phase 4 prompt fragment: *"Use the ui-state-matrix skill on the current page with the default 7-state set."*

---

Your final message MUST be a single ```json fenced block, nothing else
