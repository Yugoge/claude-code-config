# Plan: Fix Systemic Orchestrator-Script Separation Violation

## Context

**User Discovery**: During /review testing, user observed orchestrator directly reading files and parsing data instead of using scripts. User asked to "justify" this behavior and investigate the systemic error.

**Problem Statement**: Both review.md and plan.md contain a systemic architectural violation where orchestrators are instructed to:
1. Call load.py to write data to /tmp file (`--output /tmp/day-N-data.json`)
2. Use Read tool to read the /tmp file
3. Parse data themselves using jq or direct manipulation

This violates the core principle: **Orchestrators should use scripts, not read files directly**.

**Root Cause**:
- review.md line 413: `Read /tmp/day-${current_day_index}-data.json`
- plan.md line 737: `Read /tmp/day-${current_day_index}-data.json`

Both commands instruct orchestrator to read intermediate files created by load.py, when load.py can output directly to stdout.

**Desired Outcome**: Orchestrators call load.py ONCE with stdout output, receive formatted data, and present to user. No intermediate files, no Read tool, clean separation of concerns.

---

## Root Cause Analysis

### Current Violation Pattern (Both Files)

**review.md lines 376-414**:
```bash
# Step 1: Write to temp file
source /root/.claude/venv/bin/activate && python /root/travel-planner/scripts/load.py \
  --trip {destination-slug} \
  --agents timeline,meals,attractions,entertainment,shopping,budget \
  --level 2 \
  --day $current_day_index \
  --output /tmp/day-${current_day_index}-data.json

# Step 2: Orchestrator reads temp file (LINE 413 - VIOLATION)
Read /tmp/day-${current_day_index}-data.json
```

**plan.md lines 700-738**: Identical pattern, line 737 has same Read violation

### Why This Is Wrong

1. **Unnecessary intermediate files**: /tmp/day-N-data.json serves no purpose
2. **Orchestrator reads files**: Violates "use scripts, not Read" principle
3. **Two-step process**: load.py write → orchestrator read, should be one step
4. **Manual parsing**: Orchestrator then uses jq to parse data load.py already understands

### Correct Pattern

```bash
# Single call, stdout output, orchestrator receives data directly
day_data=$(source /root/.claude/venv/bin/activate && python /root/travel-planner/scripts/load.py \
  --trip {destination-slug} \
  --agents timeline,meals,attractions,entertainment,shopping,budget \
  --level 3 \
  --day $current_day_index \
  --pretty)

# Orchestrator now has formatted JSON in $day_data variable
# Parse specific fields as needed for presentation
echo "$day_data" | jq '.timeline.data.days[0].timeline | keys'
```

**Key differences**:
- ✅ No --output flag (stdout instead)
- ✅ No Read tool needed
- ✅ Single bash command captures output
- ✅ No temp files to manage/cleanup
- ✅ Orchestrator uses script (load.py), doesn't read files directly

---

## Implementation Plan

**Total Changes**: 2 files, ~10 lines modified per file

### Change 1: review.md Lines 376-414 and 423

**File**: `.claude/commands/review.md`

**Line 376-381: Remove --output flag**

Current:
```bash
source /root/.claude/venv/bin/activate && python /root/travel-planner/scripts/load.py \
  --trip {destination-slug} \
  --agents timeline,meals,attractions,entertainment,shopping,budget \
  --level 2 \
  --day $current_day_index \
  --output /tmp/day-${current_day_index}-data.json
```

Replace with:
```bash
# Extract day data directly to stdout (no temp file)
day_data=$(source /root/.claude/venv/bin/activate && python /root/travel-planner/scripts/load.py \
  --trip {destination-slug} \
  --agents timeline,meals,attractions,entertainment,shopping,budget \
  --level 3 \
  --day $current_day_index \
  --pretty)
```

**Lines 411-414: Remove Read instruction**

Delete these lines:
```bash
Then read the extracted day data:
\`\`\`bash
Read /tmp/day-${current_day_index}-data.json
\`\`\`
```

Add instead:
```bash
# Data is now in $day_data variable, parse as needed
# Example: Extract timeline for presentation
echo "$day_data" | jq -r '.timeline.data.days[0].timeline | to_entries | sort_by(.value.start_time) | .[] | "- \(.value.start_time): \(.key)"'
```

**Line 423: Update validation to use variable**

Current:
```bash
timeline_entry_count=$(jq '.timeline.data.days[0].timeline | keys | length' /tmp/day-${current_day_index}-data.json)
```

Replace with:
```bash
timeline_entry_count=$(echo "$day_data" | jq '.timeline.data.days[0].timeline | keys | length')
```

### Change 2: plan.md Lines 700-738 and 747

**File**: `.claude/commands/plan.md`

**Same changes as review.md**:
1. Lines 700-705: Remove `--output` flag, capture stdout in `$day_data` variable
2. Lines 735-738: Remove `Read /tmp/...` instruction, add parsing example
3. Line 747: Update validation to use `echo "$day_data" | jq` instead of `jq ... /tmp/file`

---

## Verification

After implementation, verify architectural compliance:

1. **Test review command**:
   ```bash
   /review 重庆旅行计划第一天
   ```
   Expected:
   - ✅ load.py called once with stdout output
   - ✅ No Read tool invocations in logs
   - ✅ No /tmp files created
   - ✅ Day 1 data displays correctly with drone show

2. **Test plan command**:
   ```bash
   /plan 重庆旅行计划
   ```
   Expected:
   - ✅ Same load.py pattern as review
   - ✅ No Read violations

3. **Grep verification**:
   ```bash
   # Should return ZERO results
   grep -n "Read /tmp/day-" .claude/commands/{review,plan}.md
   ```

---

## Critical Files

- `.claude/commands/review.md` (1397 lines) - Lines 376-414, 423
- `.claude/commands/plan.md` (1543 lines) - Lines 700-738, 747

---

## Summary

**Problem**: Systemic architectural violation where orchestrators read intermediate files instead of using script output directly

**Root Cause**: Commands use `--output /tmp/file` + `Read /tmp/file` pattern when load.py can output to stdout

**Solution**: Remove `--output` flag, capture stdout in bash variable, remove all `Read` tool usage

**Impact**:
- ✅ Orchestrators use scripts correctly (load.py)
- ✅ No intermediate temp files
- ✅ No Read tool violations
- ✅ Simpler, cleaner code
- ✅ Same functionality, better architecture

**Why this matters**: Enforces clean separation between orchestrator (coordinates) and scripts (execute), making system more maintainable and testable.
