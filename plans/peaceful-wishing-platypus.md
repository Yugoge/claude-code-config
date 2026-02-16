# Implementation Plan: Integrate fetch-image Scripts into Commands & Subagents

## Context

**Problem**: POI images are currently only fetched during HTML generation at the end of the plan workflow. Users want images to be fetched progressively as they review each day, and immediately after agents modify data, ensuring all POIs have images before final deployment.

**Current Behavior**:
- Images fetched once in `generate-and-deploy.sh` (Step 18 of plan.md)
- No image fetching during day-by-day review (Step 14)
- No image fetching after agent modifications (Step 15)
- Users see plans without images until final HTML generation

**Desired Behavior** (confirmed by user):
1. **Review/Plan commands**: Fetch images automatically after each day is confirmed "perfect" (non-force mode, uses cache)
2. **Subagent modifications**: Fetch images for new/modified POIs after agent saves (force mode, ignores cache)
3. **Error handling**: Block workflow if image fetching fails, provide retry options

**Impact**: Better user experience with progressive image loading, immediate visual feedback during review, and guaranteed image completeness for all POIs.

## Solution: Orchestrator-Side Integration

### Architecture Decision

**Approach**: Add image fetching as a workflow gate in plan.md and review.md commands, executed after each day confirmation.

**Why Orchestrator-Side** (not agent-side):
- Image fetching is a cross-cutting workflow concern, not domain-specific logic
- Single point of control vs 8x duplication across agents
- Batch fetch (1 call per day) faster than per-agent fetching (8 calls)
- Orchestrator already manages workflow gates (validation, sync)
- Agents own domain data; orchestrator coordinates workflow

### Strategy for POI-Level Fetching

**Challenge**: User wants "only new/modified POIs" after agent save, but `fetch-images-batch.py` only supports day-level filtering (`--day N`), not POI-level filtering.

**Solution**: Use `--day N --force` to re-fetch all POIs for the day. Accept ~30-90 seconds redundant fetching as pragmatic trade-off vs complex JSON diffing.

**Why This Works**:
- Zero new scripts needed (use existing fetch-images-batch.py)
- Simple, reliable implementation (single bash command)
- Fast enough for single-day operations (~30-90s for 10-30 POIs)
- Avoids complex JSON diffing logic (fragile, hard to maintain)
- Guarantees completeness (won't miss any POIs due to diff bugs)

---

## Implementation Steps

### Step 1: Modify plan.md - Add Step 14a (Image Fetching Gate)

**File**: `.claude/commands/plan.md`

**Location**: After line 853 (after "Option 1 - This day is perfect" processing)

**Changes Required**:

1. **Update state tracking variables** (lines 841-845):
   ```markdown
   **STATE TRACKING**:
   - `current_day_index`: Which day in sequence (1 to total_days)
   - `day_confirmed_perfect`: Boolean flag for INNER loop exit
   - `iteration_count_per_day`: Limit 5 iterations per day
   - `days_with_warnings`: Initial list of days requiring review
   - `retry_count_per_day`: Dict tracking fetch retry attempts {day_num: count}  ← NEW
   - `days_missing_images`: List of days confirmed without images  ← NEW
   ```

2. **Insert Step 14a after line 853**:
   ```markdown
   #### Step 14a: Fetch Images for Confirmed Day

   **TRIGGER**: Immediately after user confirms "This day is perfect"

   **Substep 1: Execute Batch Image Fetch**
   ```bash
   cd /root/travel-planner && \
   source venv/bin/activate && \
   python3 scripts/fetch-images-batch.py \
     {destination-slug} \
     0 \
     999 \
     --day {current_day_index} \
     --force
   ```

   **Parameters**:
   - `0`: Skip city covers (already fetched)
   - `999`: High POI limit (fetch all for this day)
   - `--day N`: Target only confirmed day
   - `--force`: Ignore cache (captures Step 15 modifications)

   **Substep 2: Verify Exit Code**
   ```bash
   fetch_exit_code=$?
   if [ "$fetch_exit_code" -ne 0 ]; then
     # BLOCK: Jump to Substep 3
   else
     # SUCCESS: Jump to Substep 4
   fi
   ```

   **Substep 3: Error Handling (BLOCKING)**
   ```
   ❌ IMAGE FETCHING FAILED - Day {N}

   **Last 20 Lines of Output**: {tail -20}

   **Common Causes**:
   - API rate limits (wait 5-10 min)
   - Invalid POI coordinates/names
   - Network issues
   - Missing API keys

   **OPTIONS**:
   1. 🔄 RETRY (Attempts: {retry_count}/3)
   2. 🔍 REVIEW AND FIX data
   3. ⚠️  CONTINUE WITHOUT IMAGES

   Enter choice:
   ```

   - Option 1: Increment retry_count, return to Substep 1 (max 3)
   - Option 2: Show fix instructions, wait for user, retry
   - Option 3: Log warning, proceed to Substep 4

   **Substep 4: Success Confirmation**
   ```
   ✅ Fetched images for Day {N} ({count} POIs updated)
   Proceeding to Day {N+1}...
   ```

   - Reset retry_count to 0
   - Set `day_confirmed_perfect = true`
   - Exit INNER loop (proceed to increment day_index)
   ```

**Integration with existing flow**:
- **BEFORE**: "This day is perfect" → Set flag → Exit INNER loop
- **AFTER**: "This day is perfect" → Execute Step 14a → Set flag → Exit INNER loop

---

### Step 2: Modify review.md - Add Step 4a (Same Pattern)

**File**: `.claude/commands/review.md`

**Location**: After line 520 (after "Option 1 - This day is perfect")

**Changes Required**:
- Copy exact Step 14a structure from plan.md
- Rename to "Step 4a: Fetch Images for Confirmed Day"
- Update state tracking variables (same as plan.md)

---

### Step 3: No Subagent Modifications

**Decision**: NO agent file modifications needed

**Rationale**:
- Step 14a/4a already captures new/modified POIs via force mode
- Agent save workflow (Step 15) → iterations → Day confirmation → Step 14a fetches ALL
- Force mode with --day N includes new + modified + existing POIs
- No need to distinguish "new" vs "existing" (would require complex JSON diffing)

**Workflow Example**:
```
1. User: "Add spa to Day 3"
2. Step 15: entertainment-agent modifies entertainment.json
3. Step 14 INNER loop: Re-present Day 3
4. User: "This day is perfect"
5. Step 14a: Fetch images for Day 3 (--day 3 --force)
   → Includes newly added spa + all existing POIs
6. Proceed to Day 4
```

## Critical Files to Modify

### Primary Modifications

1. **`.claude/commands/plan.md`** (lines 841-853)
   - Add state tracking variables: `retry_count_per_day`, `days_missing_images`
   - Insert complete Step 14a after line 853 (~100 lines)
   - References existing code at: plan.md:849-853

2. **`.claude/commands/review.md`** (lines 508-524)
   - Add same state tracking variables
   - Insert Step 4a (copy of Step 14a) after line 520 (~100 lines)
   - References existing code at: review.md:516-520

### Reference Files (No Changes)

3. **`scripts/fetch-images-batch.py`** (lines 1409-1474)
   - Script being integrated (no modifications needed)
   - Supports `--day N --force` already

4. **`.claude/agents/*.md`** (8 agent files)
   - NO changes needed (orchestrator handles image fetching)

**Total Code Changes**:
- **plan.md**: ~110 lines added
- **review.md**: ~110 lines added
- **Other files**: Zero modifications

## Verification Plan

### Test Case 1: Plan Command with Progressive Image Fetching

**Setup**:
1. Create new trip with `/plan` command
2. Progress through Phase 1-3 (requirements, agents, validation)
3. Enter Phase 4 (day-by-day review)

**Test Steps**:
1. Review Day 1, select "This day is perfect"
2. **Verify**: Step 14a executes, prints "✅ Fetched images for Day 1"
3. **Verify**: `data/{destination-slug}/images.json` updated
4. **Verify**: Day 1 POIs in meals.json, attractions.json have `image_url` fields
5. Review Day 2, select "Make changes" → add new restaurant
6. Confirm changes, select "This day is perfect"
7. **Verify**: Step 14a fetches images including new restaurant (--force mode)

**Expected Result**: All days have images fetched progressively, one at a time

---

### Test Case 2: Error Handling and Retry

**Setup**:
1. Temporarily break API access (invalid API key or network block)
2. Progress to day-by-day review

**Test Steps**:
1. Confirm Day 1 as perfect
2. **Verify**: Step 14a fails with exit code 1
3. **Verify**: Error options presented (Retry, Review, Continue)
4. Select "Retry"
5. **Verify**: Retry counter increments, re-executes fetch
6. After 3 retries, **Verify**: Forced to continue or review
7. Fix API access, select "Retry"
8. **Verify**: Fetch succeeds, proceeds to Day 2

**Expected Result**: Workflow blocks on image fetch failure, allows retry, eventually proceeds

---

### Test Case 3: Review Command with Existing Plan

**Setup**:
1. Use existing trip: `china-feb-15-mar-7-2026-20260202-195429`
2. Run `/review {plan-id} --day 1`

**Test Steps**:
1. Review Day 1 (already has data)
2. Select "Make changes" → modify existing attraction
3. Select "This day is perfect"
4. **Verify**: Step 4a executes with --force mode
5. **Verify**: Modified attraction gets new image_url

**Expected Result**: Force mode re-fetches images for modified POIs

---

### Test Case 4: Force Mode Effectiveness

**Setup**:
1. Manually edit `attractions.json` to remove `image_url` from a POI
2. Run review command

**Test Steps**:
1. Confirm day as perfect
2. **Verify**: Step 14a/4a detects missing image_url
3. **Verify**: Force mode re-fetches from API (not cache)
4. **Verify**: POI regains `image_url` field

**Expected Result**: Force mode ensures completeness even if cache exists

---

### Manual Verification Commands

```bash
# 1. Verify state tracking added to plan.md
grep -n "retry_count_per_day" .claude/commands/plan.md
grep -n "days_missing_images" .claude/commands/plan.md

# 2. Verify Step 14a exists
grep -n "Step 14a: Fetch Images" .claude/commands/plan.md

# 3. Verify review.md has Step 4a
grep -n "Step 4a: Fetch Images" .claude/commands/review.md

# 4. Test fetch-images-batch.py with day filter
cd /root/travel-planner
source venv/bin/activate
python3 scripts/fetch-images-batch.py \
  china-feb-15-mar-7-2026-20260202-195429 \
  0 999 --day 1 --force

# 5. Verify exit code
echo $?  # Should be 0 on success

# 6. Verify images.json updated
cat data/china-feb-15-mar-7-2026-20260202-195429/images.json | \
  jq '.pois | length'  # Should show POI count
```

---

## Trade-offs and Limitations

### Accepted Trade-offs

1. **Day-level force mode** (~30-90s redundant fetching) vs POI-level filtering (complex, fragile)
   - **Decision**: Accept redundancy for simplicity and reliability
   - **Impact**: ~30-90 seconds per day confirmation (acceptable)

2. **Orchestrator-side integration** (centralized) vs agent-side (distributed)
   - **Decision**: Centralized in commands for single point of control
   - **Impact**: No agent file modifications needed

3. **Soft blocking** (allow skip) vs hard blocking (force images)
   - **Decision**: Soft block with Option 3 "Continue without images"
   - **Impact**: User can proceed if images non-critical (graceful degradation)

### Known Limitations

1. **No POI-level filtering**: Must re-fetch entire day
   - Mitigated by: Day-level granularity already narrow (10-30 POIs max)

2. **No progress bar**: User waits without real-time feedback for large days
   - Mitigated by: fetch-images-batch.py prints per-POI "✓" or "✗" already

3. **Partial fetch failures**: Exit code 0 even if some POIs fail individually
   - Current behavior: Script completes with exit 0 even if 5/30 POIs fail
   - Future enhancement: Parse stdout to detect "✗" failures

4. **No image quality validation**: Broken URLs not detected until HTML render
   - Future enhancement: Add HEAD request validation for image URLs

### Future Enhancements (Out of Scope)

1. Add POI-level diff script if redundancy becomes performance issue
2. Add asyncio progress indicator with tqdm
3. Enhance exit codes for partial failures (0=full, 2=partial, 1=fail)
4. Add image URL validation (HTTP HEAD requests to verify 200 OK)
5. Add parallel fetching for multiple services (Gaode + Google simultaneously)

---

## Summary

**Implementation Complexity**: LOW
- Isolated changes to 2 command files
- No script modifications required
- No agent modifications required
- Reuses existing fetch-images-batch.py functionality

**Risk Assessment**: LOW
- Changes are workflow additions, not refactoring
- Existing functionality unaffected
- Error handling provides graceful degradation
- Easy to test incrementally (day-by-day)

**User Benefits**:
- Progressive image loading during review
- Immediate visual feedback after agent modifications
- Guaranteed image completeness before final deployment
- Better error visibility and retry options
