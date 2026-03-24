# Plan: Fix generate.md Shell Variable Architecture (Issue E)

## Context

`generate.md` is a 1,725-line orchestrator that instructs Claude through a 12-step resume + cover letter pipeline. It currently tells Claude to set shell variables in Step 1 (`JOB_ID`, `TIMESTAMP`, all path variables) and reuse them in Steps 2–12 across ~38 separate Bash blocks.

**The bug**: Claude Code's Bash tool creates a **new shell for every call** — variables set in one call are gone in the next. When Claude follows `generate.md` literally, Steps 2–12 receive empty strings for all path arguments, causing scripts to fail with bad paths.

**The fix**: update `generate.md` so each Bash block is self-contained — it recovers its needed variables from the on-disk state file at the start of each block. The state file `data/work/00_state_{job_id}.json` already contains all 27+ paths; we just need a reliable bootstrap (JOB_ID) to find it.

---

## Solution Design

### The Bootstrap Problem
To read the state file, you need `JOB_ID`. To get `JOB_ID` across Bash calls, we write it to a **sentinel file** in Step 1:
```
data/work/.current_job_id   ← written once in Step 1, read in all subsequent steps
```

### New Script: `scripts/export_state.sh`
A shell script that reads the sentinel file and exports all state variables as `KEY=VALUE` lines for use with `eval`:
```bash
#!/bin/bash
# Usage: eval "$(bash scripts/export_state.sh)"
JOB_ID=$(cat data/work/.current_job_id)
STATE_FILE="data/work/00_state_${JOB_ID}.json"
printf 'JOB_ID="%s"\n'           "${JOB_ID}"
printf 'TIMESTAMP="%s"\n'        "$(jq -r '.timestamp'          "${STATE_FILE}")"
printf 'CANDIDATE_NAME="%s"\n'   "$(jq -r '.candidate_name'     "${STATE_FILE}")"
printf 'JOB_DATA_FILE="%s"\n'    "$(jq -r '.paths.job_data'     "${STATE_FILE}")"
printf 'DESIGN_SPEC_FILE="%s"\n' "$(jq -r '.paths.design_spec'  "${STATE_FILE}")"
# ... all other paths
```

### Designer Iteration Recovery (Step 2)
The `DESIGNER_ITERATION` counter cannot survive Bash call boundaries. Instead of a counter variable, **derive it from the filesystem**:
```bash
# Count existing simulation result files to determine last completed iteration
DESIGNER_ITERATION=$(ls "data/work/03_simulation_result_${JOB_ID}_${TIMESTAMP}_iter"*.json \
  2>/dev/null | wc -l | tr -d ' ')
# Find the latest simulation result file
SIMULATION_RESULT_FILE=$(ls "data/work/03_simulation_result_${JOB_ID}_${TIMESTAMP}_iter"*.json \
  2>/dev/null | sort | tail -1)
```

---

## Files to Modify

### 1. `scripts/export_state.sh` (NEW)
- Reads `data/work/.current_job_id` for bootstrap
- Reads `data/work/00_state_{job_id}.json` for all paths
- Outputs `KEY="VALUE"` lines covering: `JOB_ID`, `TIMESTAMP`, `CANDIDATE_NAME`, `JOB_DATA_FILE`, `DESIGN_SPEC_FILE`, and all `paths.*` keys from state file

### 2. `.claude/commands/generate.md`
Changes are surgical — two patterns applied throughout:

**Pattern A — Step 1 Setup Block (end of block)**:
```bash
# Write sentinel for subsequent Bash blocks
echo "${JOB_ID}" > data/work/.current_job_id
```

**Pattern B — Steps 2–12 Bash Blocks (start of each block)**:
```bash
# Recover state (shell variables don't persist across Bash tool calls)
eval "$(bash scripts/export_state.sh)"
```
This replaces all hardcoded `$JOB_ID`, `$TIMESTAMP` etc. references that assumed persistence.

**Designer loop iteration (Step 2)**:
Replace `DESIGNER_ITERATION` counter with filesystem-derived count (see above).

---

## Critical Files

- `.claude/commands/generate.md` — orchestrator to update (~38 Bash blocks)
- `scripts/export_state.sh` — new helper script (create)
- `data/work/00_state_{job_id}.json` — state file (unchanged, read-only)
- `data/work/.current_job_id` — sentinel file (created at runtime by Step 1)
- `scripts/generate_file_paths.py` — already writes state file (unchanged)

---

## Implementation Steps

1. **Create `scripts/export_state.sh`**
   - Read `data/work/.current_job_id`
   - Read `data/work/00_state_${JOB_ID}.json`
   - Print all variables as `KEY="VALUE"\n` lines
   - Include error exit if sentinel file missing

2. **Update `generate.md` Step 1 setup Bash block**
   - After the `generate_file_paths.py` call, add: `echo "${JOB_ID}" > data/work/.current_job_id`

3. **Update `generate.md` Steps 2–12 Bash blocks**
   - Add `eval "$(bash scripts/export_state.sh)"` at the start of each Bash block that uses path variables
   - Replace designer iteration tracking with filesystem-based derivation

4. **Verify the designer loop in Step 2**
   - Ensure the loop variable is derived from files, not a counter that spans Bash calls

---

## Verification

```bash
# 1. Verify export_state.sh works
echo "deutsche-bank-quant-analyst" > data/work/.current_job_id
bash scripts/export_state.sh
# Expected: prints KEY="VALUE" lines for all state variables

# 2. Verify eval pattern works
eval "$(bash scripts/export_state.sh)"
echo "JOB_ID=${JOB_ID}, TIMESTAMP=${TIMESTAMP}"
# Expected: correct values from state file

# 3. Manual smoke test: run a step that previously failed
# Start a new generate run and verify Step 2+ Bash blocks get correct paths
```

---

## Scope

**In scope**:
- `export_state.sh` creation
- `generate.md` Bash block updates (sentinel write + eval pattern)
- Designer iteration filesystem-based derivation

**Out of scope**:
- Changing script argument patterns (scripts remain positional-arg based)
- Modifying the state file format
- Any changes to Step 1 logic (only add the sentinel file write)
