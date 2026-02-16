# Plan: Unified Data Validation Script (`qa-validate-all.py`)

## Context

The project has 4 separate QA scripts (`qa-schema-audit.py`, `qa-final-audit.py`, `qa-field-name-diagnostic.py`, `qa-timeline-segments-check.py`) plus 2 additional validators (`validate-agent-outputs.py`, `validate-china-trip-data.py`). They have overlapping but incomplete checks — none covers all 6 validation categories. We need ONE unified, schema-driven script that replaces all of them.

## What the script checks (6 categories)

| # | Category | Severity | Example |
|---|----------|----------|---------|
| 1 | **Schema Structure** | HIGH | Envelope (agent/status/data.days[]), day-level keys (breakfast/lunch/dinner) |
| 2 | **Field Presence** | HIGH (required) / LOW (optional) | `currency_local` missing, `coordinates` missing |
| 3 | **Field Type & Format** | MEDIUM | cost not a number, currency_local not `^[A-Z]{3}$`, time not `{start,end}` |
| 4 | **Semantic/Content** | MEDIUM | name_local contains English, type_base not Title Case, currency mismatch for region |
| 5 | **Legacy Field Detection** | INFO | `currency` exists but `currency_local` doesn't (or both exist) |
| 6 | **Cross-Agent Consistency** | MEDIUM/HIGH | Day count mismatch, date mismatch, budget sum != total |

## Architecture

```
qa-validate-all.py  (~500 lines)
├── SchemaRegistry        — Load schemas, resolve $ref, expose field definitions
├── AGENT_CONFIGS         — Dict mapping agent → nesting pattern (reuse from qa-final-audit.py)
├── extract_items()       — Extract items from agent data (port from qa-final-audit.py:136-195)
├── Validators (functions, not classes — keep it simple):
│   ├── check_envelope()          — Category 1
│   ├── check_day_structure()     — Category 1
│   ├── check_field_presence()    — Category 2 (port from qa-final-audit.py:202-224)
│   ├── check_field_format()      — Category 3 (port from validate-agent-outputs.py)
│   ├── check_semantics()         — Category 4 (timeline overlaps, budget sums, currency region)
│   ├── check_legacy_fields()     — Category 5 (port from qa-final-audit.py:80-88)
│   └── check_cross_agent()       — Category 6 (day count/date/location consistency)
├── run_pipeline()        — Orchestrate all checks for all trips
├── format_table()        — Human-readable output (port table format from qa-final-audit.py)
└── main()               — CLI with argparse

Design: Functions over classes. One file. Schema-driven where possible but with
hardcoded fallbacks for nesting patterns (since nesting differs per agent).
```

## Key design decisions

1. **Schema-driven field lists**: Read required/optional fields from `schemas/*.schema.json` `$defs` rather than hardcoding them (current qa-final-audit.py hardcodes SCHEMA_FIELDS dict)
2. **$ref resolution**: Port the `load_schemas()` pattern from `validate-agent-outputs.py:46-74` using `referencing.Registry`
3. **Nesting patterns still hardcoded**: Each agent has unique nesting (meals=singular keys, attractions=array, etc.) — no way to derive from schema
4. **Functional style**: Use plain functions + dataclasses, not class hierarchy — keeps the file compact
5. **Dual output**: Human-readable table to stdout + JSON report to file (optional `--json`)
6. **Exit code**: 0 = PASS, 1 = FAIL (any HIGH issues)

## Files involved

| File | Action |
|------|--------|
| `scripts/qa-validate-all.py` | **CREATE** — the unified script |
| `scripts/qa-final-audit.py` | Reference — port extraction logic, field checks, legacy detection, table format |
| `scripts/validate-agent-outputs.py` | Reference — port schema loading, $ref resolution, semantic checks |
| `schemas/*.schema.json` | Read — extract field definitions at runtime |
| `schemas/poi-common.schema.json` | Read — resolve $ref pointers |

## CLI interface

```bash
# Validate all trips (default)
python3 scripts/qa-validate-all.py

# Validate one trip
python3 scripts/qa-validate-all.py china-feb-15-mar-7-2026-20260202-195429

# JSON output
python3 scripts/qa-validate-all.py --json

# Filter by severity
python3 scripts/qa-validate-all.py --min-severity MEDIUM

# Filter by agent
python3 scripts/qa-validate-all.py --agent meals
```

## Output format

```
========================================================================
UNIFIED DATA VALIDATION REPORT — 2026-02-10
========================================================================

AGENT           | TRIP        | ITEMS | REQ%   | OPT%   | HIGH | MED | LOW | INFO
----------------|-------------|-------|--------|--------|------|-----|-----|-----
meals           | itinerary   |    63 | 100.0% |  88.4% |    0 |   0 |  51 |  126
...
TOTAL           |             |       | 100.0% |  88.3% |    0 |  14 | 307 |   28

[HIGH issues listed if any]
[MEDIUM issues listed]
[LEGACY field summary table]
[COMPLETENESS metrics]

VERDICT: PASS / FAIL
```

## Verification

1. Run the script on both trips — should produce same required-field compliance numbers as `qa-final-audit.py` (100% required)
2. Verify all 6 categories produce output
3. Exit code 0 (since current data passes all HIGH checks)
4. Compare legacy field detection output with `qa-field-name-diagnostic.py`
5. Compare semantic checks (timeline overlaps, budget sums) with `validate-agent-outputs.py`
