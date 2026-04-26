---
name: ui-apca-contrast
description: Run APCA Lc text-contrast measurement on a Playwright page in BOTH light and dark color schemes. Returns deterministic apca.* findings against rule-map.json. Use during ui-specialist Phase 6 (Accessibility).
---

# ui-apca-contrast

Layer: **Deterministic (L1)**.
Output channel: `automated_findings[]` with `rule_id="apca.lc-below-threshold"` or `rule_id="apca.dark-mode-regressed"`.

## Trigger Conditions

Invoke this skill when:

- ui-specialist enters **Phase 6 (Accessibility Audit)** for a page that has been navigated successfully via Playwright.
- After (or in parallel with) ui-axe-injector. APCA is more nuanced than axe color-contrast and replaces it — record both, then dedup in the subagent aggregator using axe → APCA preference for text-contrast claims.

## Inputs

```
{
  "page_url": "string (URL of currently-loaded Playwright page)",
  "viewport": "mobile|desktop",
  "thresholds": {
    "body_lc_min": 75,
    "large_text_lc_min": 60,
    "non_text_lc_min": 45
  },
  "selectors_to_check": "optional: array of CSS selectors; defaults to all visible text elements"
}
```

## Outputs

A single ```json fenced block:

```
{
  "skill": "ui-apca-contrast",
  "page_url": "<url>",
  "viewport": "mobile|desktop",
  "runs": [
    { "color_scheme": "light", "samples": <n>, "violations": <n> },
    { "color_scheme": "dark",  "samples": <n>, "violations": <n> }
  ],
  "automated_findings": [
    {
      "rule_id": "apca.lc-below-threshold",
      "description": "<element text snippet> Lc <computed> < threshold <expected> (<color_scheme>)",
      "location": "<page_url> + CSS selector",
      "severity": "major|minor",
      "viewport": "mobile|desktop|both",
      "color_scheme": "light|dark",
      "evidence_mode": "deterministic",
      "computed_value": "Lc <n>",
      "expected_value": "Lc >= <threshold>",
      "browser_verified": true,
      "false_positive_risk": "low"
    }
  ],
  "unknowns": [],
  "needs_review": []
}
```

## Dark-Mode Dual-Run (MANDATORY per spec 5.20 + 5.15.2)

APCA contrast MUST be measured TWICE per page — once in the page's default color scheme and once after switching to the opposite scheme via Playwright's `page.emulateMedia({colorScheme:'dark'})`.

### Light pass

1. Ensure the page is in light mode: `page.emulateMedia({colorScheme:'light'})`.
2. Wait for a paint cycle (`browser_wait_for({ time: 0.3 })`).
3. For every visible text element, extract computed `color` and effective background `background-color`, walking up the DOM until a non-transparent surface is found.
4. Compute APCA Lc using the W3C APCA formula (sRGB → Y luminance with non-linear contrast polarity adjustment).
5. Compare against thresholds:
   - body text (font-size < 18px): `body_lc_min` (default 75)
   - large text (font-size >= 18px or weight >= 600 + font-size >= 14px): `large_text_lc_min` (default 60)
   - non-text (icons, borders): `non_text_lc_min` (default 45)
6. Emit `apca.lc-below-threshold` finding with `color_scheme: "light"` for each violation.

### Dark pass

1. Switch to dark mode: `page.emulateMedia({colorScheme:'dark'})`.
2. Wait for a paint cycle (`browser_wait_for({ time: 0.3 })`) so CSS `prefers-color-scheme: dark` styles apply.
3. Re-extract computed `color` and `background-color` for the same text elements (the values WILL differ if dark-mode CSS exists).
4. Compute APCA Lc again — **dark mode requires the same Lc thresholds; dark backgrounds with insufficient contrast are still violations**.
5. Emit `apca.lc-below-threshold` finding with `color_scheme: "dark"` for each violation.
6. **Cross-mode regression check**: for each text element, if the dark-mode Lc is worse than the light-mode Lc by more than 10 units, emit a `apca.dark-mode-regressed` finding (severity major, false_positive_risk medium) — this catches dark themes that retained light-mode-tuned color tokens without re-balancing for the dark surface.

### Restore

After the dark pass, restore to the original scheme: `page.emulateMedia({colorScheme: <original>})` so subsequent skills see the page in the expected state.

## Fallback Strategy

Single-tier fallback: if `page.emulateMedia` is unavailable in the Playwright build, attempt to toggle dark mode by adding `class="dark"` to `<html>` (Tailwind convention) or setting the `data-theme="dark"` attribute (DTCG convention) via `browser_evaluate`. If neither succeeds, run the light pass only and emit one entry to `unknowns[]`: `{ "thing_not_tested": "dark-mode APCA on <page_url>", "reason": "color-scheme switch unavailable" }`.

## Example Invocation

ui-specialist Phase 6 prompt fragment: *"Use the ui-apca-contrast skill on the current page; perform the mandatory dual-run (light + dark via page.emulateMedia)."*

---

Your final message MUST be a single ```json fenced block, nothing else
