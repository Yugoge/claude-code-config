# Continuation: Fix bare python3 invocations introduced in dev-20260524-170335

**Parent task**: dev-20260524-170335  
**Close verdict**: CLOSE: NO (style violations — Standard 3 bare python3)  
**Close report**: docs/dev/close-report-dev-20260524-170335.md

## Problem

The `/close --codex` review found 3 provably-new Standard 3 (use-source-venv) violations introduced by dev-20260524-170335:

1. `commands/close.md:170` — `python3 scripts/aggregate-dev-report.py --task-id $TASK_ID` (Case 1, no venv)
2. `commands/close.md:177` — same pattern (Case 2)
3. `commands/dev.md:709` — `python3 scripts/aggregate-dev-report.py --task-id $TASK_ID` (Step 9)

These are operational instructions in `.md` command specs. The style-inspector Standard 3 explicitly covers `.md` files. A `venv/` directory exists at project root.

## Required fix

Replace all 3 bare `python3 scripts/aggregate-dev-report.py` invocations with the venv-activated form:

```
source venv/bin/activate && python scripts/aggregate-dev-report.py --task-id $TASK_ID
```

**Files to change**: `commands/close.md` (lines 170 and 177), `commands/dev.md` (line 709)

No functional logic changes. No new files needed.

## Acceptance criteria

1. `grep "python3 scripts/aggregate-dev-report" commands/close.md` → 0 results
2. `grep "python3 scripts/aggregate-dev-report" commands/dev.md` → 0 results  
3. `grep "source venv/bin/activate && python scripts/aggregate-dev-report" commands/close.md` → 2 results
4. `grep "source venv/bin/activate && python scripts/aggregate-dev-report" commands/dev.md` → 1 result
5. Style inspector passes with 0 critical violations on these 3 files
6. `source venv/bin/activate && python scripts/aggregate-dev-report.py --task-id dev-20260524-170335 --dry-run` → exit 0

## Constraints

- NO hardcoding — only these 3 textual substitutions
- NO inline scripts
- Changes limited to commands/close.md and commands/dev.md only
