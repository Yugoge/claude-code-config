# Fix save.py Overlapping Detection

## Context

**User's core issue**: "我一直给你说了是overlapping的问题检测不到，彻底修复" (I've been telling you overlapping detection doesn't work, fix it completely)

The user has repeatedly reported that `plan-validate.py` **fails to detect time overlaps** between activities:
- "为什么这么多重合时间线？我的save脚本不是会报错吗！" (Why so many overlapping timelines? Shouldn't my save script report errors?)
- "仍然有时间冲突，脚本不够完善" (Still has time conflicts, the script is not comprehensive enough)
- "简单的时间冲突save检查不出来？" (Simple time conflicts can't be detected by save?)

## Root Cause Analysis

From codebase exploration (`scripts/plan-validate.py`):

**Current overlapping detection has 3 CRITICAL GAPS**:

### Gap 1: Timeline Data Excluded from Cross-Agent Checks
**Lines 975-1094**: POI conflict detection collects data from:
- ✅ meals.json
- ✅ attractions.json
- ✅ entertainment.json
- ✅ shopping.json
- ❌ **timeline.json NOT included**

**Result**: Timeline activities never checked against other agents. If `meals.json` has dinner at 18:00-19:30 AND `entertainment.json` has a show at 18:30-20:00, this overlap is detected. But if `timeline.json` has an activity overlapping with either, it's **NOT detected**.

### Gap 2: Different Data Structures Not Unified
**POI agents** use: `time: {start: "18:00", end: "19:30"}`
**Timeline agent** uses: `start_time: "18:00", end_time: "19:30"`

**Lines 1039-1055**: Overlap comparison only works for POI format:
```python
start1 = poi1.get("time", {}).get("start", "")
end1 = poi1.get("time", {}).get("end", "")
```

Timeline's `start_time`/`end_time` format is **never converted** to POI format, so even if timeline data were included, comparisons would fail.

### Gap 3: Timeline Internal Check Only Covers Adjacent Activities
**Lines 698-724**: Timeline overlap detection sorts activities by `start_time` and checks only **adjacent pairs**:
```python
for i in range(len(sorted_timeline) - 1):
    curr = sorted_timeline[i]
    next = sorted_timeline[i + 1]
    # Only checks if curr overlaps with next
```

**Problem**: If activities A, B, C exist where:
- A: 10:00-12:00
- B: 11:00-11:30 ← overlaps A (detected ✅)
- C: 10:30-11:00 ← overlaps A (NOT detected ❌, because not adjacent after sorting)

Only checks B vs A and C vs B, missing A vs C overlap.

## Complete Fix Strategy

**Goal**: Detect ALL time overlaps across ALL agents (meals, attractions, entertainment, shopping, timeline) on the same day.

**Approach**: Unify all activity data into a single format, then perform comprehensive pairwise overlap detection.

### Implementation Changes

**File**: `/root/travel-planner/scripts/plan-validate.py`

### 1. Replace Broken POI Conflict Detection (Lines 975-1094)

**Current code** (lines 975-1094):
```python
def check_cross_agent(all_data: dict, trip: str) -> list:
    # Collects POIs from 4 agents only
    for agent in ["meals", "attractions", "entertainment", "shopping"]:
        # ... missing timeline data
```

**New unified overlap detection**:
```python
def check_all_activity_overlaps(all_data: dict, trip: str) -> list:
    """Detect ALL time overlaps across ALL agents including timeline.

    Unifies data from 5 agents (meals, attractions, entertainment, shopping, timeline)
    into common format, then performs comprehensive pairwise overlap detection.
    """
    issues = []

    # Collect ALL activities from ALL agents per day
    for day_num in range(1, 22):  # Iterate through all possible days
        activities = _collect_all_activities_for_day(all_data, day_num)

        # Pairwise overlap detection
        for i in range(len(activities)):
            for j in range(i + 1, len(activities)):
                act1, act2 = activities[i], activities[j]

                overlap = _check_time_overlap(act1["start"], act1["end"],
                                               act2["start"], act2["end"])

                if overlap:
                    # At least one optional → INFO severity (alternatives don't conflict)
                    if act1["optional"] or act2["optional"]:
                        severity = Severity.INFO
                    # Both non-optional, identical time → HIGH severity
                    elif act1["start"] == act2["start"] and act1["end"] == act2["end"]:
                        severity = Severity.HIGH
                    # Both non-optional, partial overlap → MEDIUM severity
                    else:
                        severity = Severity.MEDIUM

                    issues.append(Issue(
                        severity, Category.CROSS_AGENT,
                        f"{act1['agent']}+{act2['agent']}", trip, day_num,
                        f"Day {day_num}", "time",
                        f"TIME OVERLAP: '{act1['name']}' ({act1['agent']}, "
                        f"{act1['start']}-{act1['end']}) overlaps with "
                        f"'{act2['name']}' ({act2['agent']}, {act2['start']}-{act2['end']})"
                    ))

    return issues
```

### 2. Helper Function: Collect All Activities (Unified Format)

```python
def _collect_all_activities_for_day(all_data: dict, day_num: int) -> list:
    """Collect ALL activities from ALL agents for a specific day.

    Returns unified format: [{
        "agent": "meals",
        "name": "Dinner at Restaurant",
        "start": "18:00",
        "end": "19:30",
        "optional": false
    }, ...]
    """
    activities = []

    # 1. Meals (breakfast, lunch, dinner)
    meals_data = all_data.get("meals", {})
    if meals_data:
        for day in meals_data.get("data", {}).get("days", []):
            if day.get("day") == day_num:
                for meal_type in ["breakfast", "lunch", "dinner"]:
                    meal = day.get(meal_type, {})
                    if isinstance(meal, dict) and meal:
                        time_obj = meal.get("time", {})
                        if isinstance(time_obj, dict) and time_obj.get("start"):
                            activities.append({
                                "agent": "meals",
                                "name": meal.get("name_base", f"{meal_type}"),
                                "start": time_obj["start"],
                                "end": time_obj["end"],
                                "optional": meal.get("optional", False)
                            })

    # 2. POI agents (attractions, entertainment, shopping)
    for agent in ["attractions", "entertainment", "shopping"]:
        agent_data = all_data.get(agent, {})
        if agent_data:
            for day in agent_data.get("data", {}).get("days", []):
                if day.get("day") == day_num:
                    for poi in day.get(agent, []):
                        if isinstance(poi, dict):
                            time_obj = poi.get("time", {})
                            if isinstance(time_obj, dict) and time_obj.get("start"):
                                activities.append({
                                    "agent": agent,
                                    "name": poi.get("name_base", "Unknown"),
                                    "start": time_obj["start"],
                                    "end": time_obj["end"],
                                    "optional": poi.get("optional", False)
                                })

    # 3. Timeline (CRITICAL: this is the missing piece!)
    timeline_data = all_data.get("timeline", {})
    if timeline_data:
        for day in timeline_data.get("data", {}).get("days", []):
            if day.get("day") == day_num:
                timeline_dict = day.get("timeline", {})
                for activity_name, sched in timeline_dict.items():
                    if isinstance(sched, dict) and sched.get("start_time"):
                        activities.append({
                            "agent": "timeline",
                            "name": activity_name,
                            "start": sched["start_time"],  # Note: timeline uses start_time
                            "end": sched["end_time"],      # not time.start
                            "optional": False  # Timeline activities assumed required
                        })

    return activities
```

### 3. Helper Function: Time Overlap Detection

```python
def _check_time_overlap(start1: str, end1: str, start2: str, end2: str) -> bool:
    """Check if two time ranges overlap.

    Args:
        start1, end1: First time range (HH:MM format)
        start2, end2: Second time range (HH:MM format)

    Returns:
        True if ranges overlap, False otherwise

    Examples:
        _check_time_overlap("10:00", "12:00", "11:00", "13:00") → True (overlap 11:00-12:00)
        _check_time_overlap("10:00", "11:00", "11:00", "12:00") → False (adjacent, not overlapping)
        _check_time_overlap("10:00", "12:00", "09:00", "10:00") → False (no overlap)
    """
    # Normalize times (handle both "8:00" and "08:00")
    def normalize_time(t):
        if not t or ":" not in t:
            return "00:00"
        parts = t.split(":")
        return f"{int(parts[0]):02d}:{parts[1]}"

    start1 = normalize_time(start1)
    end1 = normalize_time(end1)
    start2 = normalize_time(start2)
    end2 = normalize_time(end2)

    # Overlap condition: start1 < end2 AND start2 < end1
    # Note: Using < not <= to treat adjacent times (11:00-12:00 vs 12:00-13:00) as non-overlapping
    return start1 < end2 and start2 < end1


### 4. Remove Broken Timeline Internal Check (Lines 698-724)

**Current code** only checks adjacent activities - misses many overlaps.

**Action**: Delete lines 698-724 or comment out. The new `check_all_activity_overlaps()` replaces this with comprehensive pairwise checking.

### 5. Integration in `check_semantics()` Function

**Location**: Line ~655-755 (`check_semantics` function)

**Current call** (line ~716):
```python
# Timeline chronological ordering
if agent == "timeline":
    # ... lines 698-724 ...
```

**Replace with**: (Keep existing checks, just remove broken timeline overlap logic)
```python
# Timeline chronological ordering
if agent == "timeline":
    pass  # Timeline overlaps now handled in check_all_activity_overlaps()
```

### 6. Integration in `run_pipeline()` Function

**Location**: Line ~1188-1190 (cross-agent validation section)

**Current code**:
```python
# Cross-agent (once per trip)
if not agent_filter:
    all_issues.extend(check_cross_agent(all_data, trip))
```

**Replace with**:
```python
# Cross-agent (once per trip)
if not agent_filter:
    # OLD: check_cross_agent() - broken, missing timeline data
    # NEW: Comprehensive overlap detection across ALL agents
    all_issues.extend(check_all_activity_overlaps(all_data, trip))
```

### 7. Optional: Keep Legacy POI Conflict Detection

If you want to keep the old `check_cross_agent()` for non-time-based checks (like duplicate POI names), rename it:

```python
# Keep legacy checks (if any remain after removing overlap logic)
all_issues.extend(check_cross_agent_non_temporal(all_data, trip))
# New comprehensive overlap detection
all_issues.extend(check_all_activity_overlaps(all_data, trip))
```

But if `check_cross_agent()` ONLY did overlap detection, simply replace it entirely.

### Critical Files to Modify

**File**: `/root/travel-planner/scripts/plan-validate.py`

**Changes**:
1. **Add 2 new functions** (~100 lines):
   - `check_all_activity_overlaps(all_data, trip)` - main overlap detector
   - `_collect_all_activities_for_day(all_data, day_num)` - data collector
   - `_check_time_overlap(start1, end1, start2, end2)` - overlap logic

2. **Modify `check_semantics()`** (line ~716):
   - Remove or comment out lines 698-724 (broken timeline internal check)

3. **Modify `run_pipeline()`** (line ~1188):
   - Replace `check_cross_agent()` with `check_all_activity_overlaps()`

**Total changes**: ~100 lines added, ~30 lines removed/modified

### Verification & Testing

**Goal**: Ensure the fix detects ALL time overlaps that were previously missed.

### Test Scenarios

| Scenario | Setup | Expected Result |
|----------|-------|-----------------|
| **Clean data** | Current Day 13-14 data (no overlaps) | PASS - 0 overlap issues |
| **Timeline ↔ Meals overlap** | Timeline activity 18:00-19:00<br>Meals dinner 18:30-20:00 | **MEDIUM severity** overlap detected ✅ |
| **Timeline ↔ Entertainment overlap** | Timeline activity 19:30-21:00<br>Entertainment show 20:00-22:00 | **MEDIUM severity** overlap detected ✅ |
| **Identical time slots** | Two activities 12:00-13:30 same time | **HIGH severity** (exact duplicate) ✅ |
| **Both optional overlap** | Two optional activities overlap | **INFO severity** (downgraded) ✅ |
| **Adjacent times (no overlap)** | Activity A 11:00-12:00<br>Activity B 12:00-13:00 | PASS - no overlap (12:00 boundary) ✅ |
| **Non-adjacent overlap** | Activities A, B, C where A overlaps C<br>but not adjacent in sorted order | **Detected** ✅ (pairwise check catches all) |

### Verification Steps

**Step 1: Verify current clean data passes**
```bash
source /root/.claude/venv/bin/activate
python scripts/plan-validate.py china-feb-15-mar-7-2026-20260202-195429
```

**Expected**: No HIGH severity overlap issues (data is already clean after manual fixes)

---

**Step 2: Create artificial overlap to verify detection works**

Temporarily modify Day 13 timeline to create overlap:
```bash
# Backup
cp data/china-feb-15-mar-7-2026-20260202-195429/timeline.json timeline.json.bak

# Add test overlap: duplicate dinner time in timeline
# Timeline already has "Dinner at Yanzhimian (18:00-19:20)"
# Meals also has dinner at 18:00-19:20
# These should be detected as OVERLAPPING (same activity in 2 agents)
```

Run validation:
```bash
python scripts/plan-validate.py china-feb-15-mar-7-2026-20260202-195429
```

**Expected**: Overlap detected between timeline and meals for Day 13 dinner

---

**Step 3: Test save.py integration**
```bash
# Try to save meals.json with overlapping data
python scripts/save.py --trip china-feb-15-mar-7-2026-20260202-195429 \
  --agent meals --input timeline.json.bak
```

**Expected**: Validation blocks save if HIGH severity overlaps exist

---

**Step 4: Restore clean data**
```bash
mv timeline.json.bak data/china-feb-15-mar-7-2026-20260202-195429/timeline.json
```

### Success Criteria

✅ **Fix is complete when**:
1. Current clean data passes validation (0 overlap errors)
2. Artificial overlaps between timeline ↔ POI agents are detected
3. Non-adjacent overlaps are caught (pairwise logic works)
4. save.py correctly blocks overlapping data from being saved
5. User confirms: "overlapping问题检测到了" (overlapping problems are detected)

---

## Summary of Fix

**Problem**: save.py validation failed to detect time overlaps because:
1. Timeline data excluded from cross-agent overlap checks
2. Different data structures (timeline uses `start_time`, POI uses `time.start`)
3. Timeline internal check only compared adjacent activities (missed gaps)

**Solution**: Unified overlap detection
1. **Collect ALL activities** from ALL 5 agents (meals, attractions, entertainment, shopping, timeline) per day
2. **Unify format** - convert timeline's `start_time`/`end_time` to common format
3. **Pairwise comparison** - check EVERY activity against EVERY other activity (comprehensive)
4. **Proper severity**:
   - INFO: At least one activity is optional (alternatives don't conflict)
   - HIGH: Both non-optional AND identical time slots
   - MEDIUM: Both non-optional AND partial overlap

**Code changes**: ~100 lines added, ~30 lines modified in `scripts/plan-validate.py`

**No configuration changes needed** - pure logic fix

**Backward compatible** - all existing validations still work, just adds missing overlap detection
