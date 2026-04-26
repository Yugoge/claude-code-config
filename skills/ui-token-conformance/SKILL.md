---
name: ui-token-conformance
description: Conditional capability — measure design-token conformance (color/spacing/typography) of computed CSS values against a project's declared token source (DTCG / tailwind.config.js / theme.ts). If no token source is detected, emit capability_unavailable to unknowns and DO NOT raise findings on guesses. Use during ui-specialist Phase 5 (Aesthetic).
---

# ui-token-conformance

Layer: **Deterministic (L1)** when a token source exists; **capability_unavailable** otherwise.
Output channel: `automated_findings[]` with `rule_id` of `token.off-palette` / `token.off-spacing-scale` / `token.off-typography`, plus `tokenConformance` summary block.

## Trigger Conditions

Invoke this skill when:

- ui-specialist enters **Phase 5 (Visual Design Quality Assessment)** for any page.
- The subagent has not yet run token-conformance for this page in this session.

This skill is **conditional**, not mandatory (per spec 5.22.3 row 6). It probes for a token source first; if none is found it does NOT fabricate a "fake palette" — it emits `capability_unavailable` to `unknowns[]` and returns.

## Inputs

```
{
  "project_path": "string (filesystem root of project under review)",
  "page_url": "string (URL of currently-loaded Playwright page)",
  "viewport": "mobile|desktop",
  "sample_strategy": "primary_chrome | full_page (default primary_chrome — buttons, nav, headings, body)"
}
```

## Outputs

A single ```json fenced block:

```
{
  "skill": "ui-token-conformance",
  "page_url": "<url>",
  "capability": "available | unavailable",
  "token_source": "dtcg|tailwind|theme.ts|css-vars|none",
  "samples_examined": <integer>,
  "tokenConformance": {
    "color_token_match_rate": <0.0-1.0 | null>,
    "spacing_token_match_rate": <0.0-1.0 | null>,
    "typography_token_match_rate": <0.0-1.0 | null>,
    "overall_match_rate": <0.0-1.0 | null>
  },
  "automated_findings": [
    {
      "rule_id": "token.off-palette | token.off-spacing-scale | token.off-typography",
      "description": "<computed value> not in declared scale",
      "location": "<page_url> + CSS selector",
      "severity": "minor|major (capped at major per 5.1 binding decision #4)",
      "evidence_mode": "deterministic",
      "computed_value": "<measured>",
      "expected_value": "<closest token>",
      "false_positive_risk": "medium"
    }
  ],
  "unknowns": [
    {
      "thing_not_tested": "design-token conformance",
      "reason": "no token source detected (no DTCG/tailwind/theme.ts/css-vars in project)",
      "rule_id": "token.capability-unavailable"
    }
  ],
  "needs_review": []
}
```

## Capability Probe (mandatory FIRST step)

Detection priority:

1. **DTCG** — look for `tokens.json` / `*.tokens.json` / `design-tokens/*.json` matching the W3C DTCG spec.
2. **Tailwind** — look for `tailwind.config.{js,ts,cjs,mjs}` and parse `theme.colors`, `theme.spacing`, `theme.fontSize`, `theme.extend`.
3. **theme.ts / theme.js** — look for a top-level `theme` export (Stitches/Vanilla Extract/Emotion/Material).
4. **CSS Custom Properties** — look for `:root { --color-*: ...; --space-*: ...; }` or equivalent in any global CSS.
5. **Project CLAUDE.md role-table** — look for an authoritative role→token table (per project-claude-md convention).

If NONE of the five sources is found, set `capability="unavailable"`, emit ONE entry to `unknowns[]` with `rule_id="token.capability-unavailable"`, and STOP. Do not extract computed colors. Do not flag anything. Do not guess what the palette "should" be.

## Severity Cap (binding decision #4)

`token.off-palette` / `token.off-spacing-scale` / `token.off-typography` findings are CAPPED AT `severity=major` even when overall_match_rate is below 90%. They MAY be raised to `critical` ONLY through the task-success / readability / consistency triple gate at the subagent aggregator level (see ui-specialist.md conflict reconciliation lex).

## Fallback Strategy

Single-tier: if the capability probe finds a source but parsing fails (malformed tailwind.config, etc.), emit one `unknowns[]` entry referencing the parse error. Do not partially-flag findings using a half-parsed palette.

## Example Invocation

ui-specialist Phase 5 prompt fragment: *"Use the ui-token-conformance skill on the current page; if no token source exists, accept the capability_unavailable shortcut and proceed."*

---

Your final message MUST be a single ```json fenced block, nothing else
