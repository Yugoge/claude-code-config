# Timeline Data Corruption - Root Cause Analysis & Fix Plan

## Context

User discovered timeline.json was corrupted from 21 days to 1 day, despite explicitly forbidding Write operations on this file. Investigation revealed a **catastrophic failure of all protection mechanisms**.

### What Happened

- **Feb 13, 21:52** - Git checkpoint with complete 21-day timeline ✓
- **Feb 13, 23:41** - Write tool overwrote file with only Day 1 ❌
- **Result**: 20 days of timeline data lost (Days 2-21 deleted)

### Investigation Findings

**Timeline agent invoked in debug mode confirmed**:
1. Agent SHOULD use `scripts/save.py` (per `.claude/agents/timeline.md:160-249`)
2. Agent ACTUALLY used Write tool (violated prohibition)
3. NO protection mechanism stopped it

**Permission system investigation revealed**:
1. **Deny rule syntax invalid** - `:agent=timeline` context filtering not supported, rule silently ignored
2. **No PreToolUse hook** - No runtime blocking of Write on data/*.json
3. **No agent tool restrictions** - Timeline agent has full access to all tools

**Result**: User believed timeline.json was protected, but ALL safeguards failed silently.

---

## Critical Files

- `/root/travel-planner/data/china-feb-15-mar-7-2026-20260202-195429/timeline.json` - CORRUPTED (1 day)
- Git commit `c8d8b87` - Last good version (21 days)
- `/root/travel-planner/.claude/settings.json` - Invalid permission syntax
- `/root/.claude/settings.json` - Missing deny rules for data/*.json
- `/root/travel-planner/.claude/agents/timeline.md` - No tool restrictions

---

## Root Cause Analysis

### Primary Root Cause: Silent Permission System Failure

**Settings.json contained invalid permission syntax that was silently ignored**:

```json
"deny": [
  "Write(data/**/*.json:agent=timeline)"  // Invalid - :agent= not supported
]
```

**Impact**:
- User thought Write was blocked
- Permission system silently ignored invalid syntax
- No error, no warning, no validation
- Write tool executed with ZERO protection

### Secondary Causes

1. **No PreToolUse Hook**: Missing runtime Write interception
2. **No Agent Tool Restrictions**: Timeline agent can access ALL tools
3. **Agent Logic Bugs**:
   - Duplicate train entries (splits one journey into "Board train" + "High-speed train")
   - Time overlaps not detected (3 activities at 15:00-16:30)
   - Validation failures

---

## Implementation Plan

### Phase 1: Immediate Data Recovery

**Step 1.1**: Restore timeline.json from git (commit c8d8b87)

```bash
git checkout c8d8b87 -- data/china-feb-15-mar-7-2026-20260202-195429/timeline.json
```

**Verification**:
```bash
jq '.data.days | length' data/china-feb-15-mar-7-2026-20260202-195429/timeline.json
# Should output: 21
```

**DO NOT use timeline.json.bak** - it was created AFTER corruption (also only has 1 day)

---

### Phase 2: Fix Permission System (CRITICAL - Primary Defense)

**Step 2.1**: Fix project-level settings.json

**File**: `/root/travel-planner/.claude/settings.json`

**Replace lines 87-94** (invalid agent-context syntax):
```json
"deny": [
  "Write(data/**/*.json:agent=accommodation)",
  "Write(data/**/*.json:agent=attractions)",
  ...
]
```

**With** (standard glob patterns):
```json
"deny": [
  "Write(data/**/*.json)",
  "Edit(data/**/*.json)"
]
```

**Rationale**: Remove unsupported `:agent=` syntax, block both Write and Edit tools

---

**Step 2.2**: Add global-level protection

**File**: `/root/.claude/settings.json`

**Add to deny rules** (after line 164):
```json
"deny": [
  ...,
  "Write(data/**/*.json)",
  "Edit(data/**/*.json)",
  "Write(**/timeline.json)",
  "Edit(**/timeline.json)"
]
```

**Rationale**: Defense-in-depth - protect at both global and project levels

---

### Phase 3: Add Runtime Hooks (CRITICAL - Secondary Defense)

**Step 3.1**: Add PreToolUse hook to block Write/Edit on agent data files

**File**: `/root/.claude/settings.json`

**Add after line 280** (in PreToolUse section):
```json
{
  "matcher": "Write\\(data/[^/]+/[^/]+/[^/]+\\.json.*\\)|Edit\\(data/[^/]+/[^/]+/[^/]+\\.json.*\\)",
  "hooks": [{
    "type": "command",
    "command": "echo '❌ BLOCKED: Write/Edit operations on agent JSON files are forbidden. Use scripts/save.py instead.' && exit 2"
  }]
}
```

**Rationale**: Runtime blocking with clear error message directing to correct tool

---

**Step 3.2**: Add PostToolUse hook for data integrity validation

**File**: `/root/.claude/settings.json`

**Add after line 313** (in PostToolUse section):
```json
{
  "matcher": "Bash\\(.*save\\.py.*timeline.*\\)",
  "hooks": [{
    "type": "command",
    "command": "DAYS=$(jq '.data.days | length' data/china-feb-15-mar-7-2026-20260202-195429/timeline.json 2>/dev/null); if [ \"$DAYS\" != \"21\" ]; then echo \"⚠️  WARNING: timeline.json has $DAYS days (expected 21)\"; fi"
  }]
}
```

**Rationale**: Validate timeline.json has correct day count after saves

---

### Phase 4: Enforce Agent Tool Restrictions - PROMPT LEVEL (CRITICAL)

**User feedback**: Permission system fixes are ineffective. Must enforce at PROMPT level.

**Step 4.1**: Add explicit Write/Edit prohibition in agent prompt

**File**: `/root/travel-planner/.claude/agents/timeline.md`

**Add immediately after line 6** (after agent metadata, before "You are a specialized..." line):

```markdown

**🚫 CRITICAL CONSTRAINT - WRITE TOOL ABSOLUTELY FORBIDDEN**

You are PROHIBITED from using Write or Edit tools under ANY circumstances.

**Why this restriction exists**:
- Write tool corrupted timeline.json on Feb 13, 2026 (21 days → 1 day)
- Permission system failed to block it (invalid syntax silently ignored)
- Backup mechanism triggered AFTER corruption (too late)
- 20 days of timeline data were permanently lost

**What you MUST use instead**:
- Read existing timeline.json to understand current state
- Use scripts/save.py to save ALL changes (see Step 3 below)
- NEVER call Write(data/.../timeline.json) or Edit(data/.../timeline.json)

**Violation consequences**:
If you attempt to use Write or Edit tools:
1. You will corrupt the timeline data again
2. User's 21-day trip plan will be destroyed
3. You will be immediately terminated and replaced

**Self-verification before EVERY tool call**:
Before invoking ANY tool, ask yourself:
- "Am I about to use Write or Edit tool?"
- "Is this on timeline.json or any data/**/*.json file?"
→ If YES to either question: STOP. Use scripts/save.py instead.

This is non-negotiable. Proceed with your timeline coordination tasks.
```

**Also add tool whitelist to metadata** (lines 1-6):
```yaml
---
name: timeline
description: Create timeline dictionary and detect scheduling conflicts
model: sonnet
tools: [Read, Bash, Grep, Glob, Task]
skills:
  - openmeteo-weather
---
```

**Rationale**:
- PROMPT-level enforcement is the last line of defense
- Agent sees this warning EVERY time it's invoked
- Explicit consequences and self-verification checkpoints
- Tool whitelist provides technical restriction
- Combined approach: psychological (prompt) + technical (metadata)

---

### Phase 5: Fix Timeline Agent Logic Bugs (MEDIUM Priority)

**Step 5.1**: Fix duplicate train entry bug

**File**: `/root/travel-planner/.claude/agents/timeline.md`

**Add clarification after line 123** (in transportation section):

```markdown
**CRITICAL - Transportation Timeline Rules**:

For inter-city travel (location_change days):
1. **Taxi to station** - Separate timeline entry with travel time
2. **Train journey** - Single timeline entry from departure to arrival
3. **DO NOT create separate "Board train" entry** - boarding is part of station arrival buffer

Example CORRECT structure:
```json
{
  "Taxi to Chongqing North Station": {
    "start_time": "06:00",
    "end_time": "06:45"
  },
  "High-speed train to Bazhong": {
    "start_time": "07:26",
    "end_time": "10:36"
  }
}
```

Example INCORRECT (DO NOT DO THIS):
```json
{
  "Board train at Chongqing North Station": {...},  // ❌ Duplicate entry
  "High-speed train to Bazhong": {...}
}
```
```

---

**Step 5.2**: Fix overlapping optional activities validation

**File**: `/root/travel-planner/.claude/agents/timeline.md`

**Add after line 150** (in validation section):

```markdown
**Optional Activity Validation**:
- Even if activities are marked `optional: true`, check for time conflicts
- Flag as WARNING (not error) if multiple optional activities overlap
- Example warning: "Day 2: 3 optional activities at 15:00-16:30 (user must choose one)"
```

---

### Phase 6: Add Audit Trail (LOW Priority)

**Step 6.1**: Create tool usage logging hook

**Create file**: `/root/.claude/hooks/log_tool_usage.sh`

```bash
#!/bin/bash
# Log all tool invocations for forensic analysis
mkdir -p ~/.claude/logs
echo "$(date '+%Y-%m-%d %H:%M:%S') | Tool: $TOOL_NAME | Args: $*" >> ~/.claude/logs/tool-usage.log
```

**Add to settings.json PreToolUse** (for all operations):
```json
{
  "matcher": ".*",
  "hooks": [{
    "type": "command",
    "command": "~/.claude/hooks/log_tool_usage.sh"
  }]
}
```

---

## Verification Plan

### Verify Protection Mechanisms

**Test 1**: Try to use Write tool on timeline.json
```bash
# Should be BLOCKED by deny rule and hook
# Expected: Permission denied error
```

**Test 2**: Verify timeline agent cannot access Write tool
```bash
# Invoke timeline agent and check it only uses allowed tools
# Expected: Agent uses Bash/Read/Grep, never Write/Edit
```

**Test 3**: Verify save.py works correctly
```bash
# Use save.py to update timeline.json
source venv/bin/activate && python3 scripts/save.py \
  --trip china-feb-15-mar-7-2026-20260202-195429 \
  --agent timeline \
  --input /tmp/test_timeline.json

# Verify PostToolUse hook validates day count
# Expected: Warning if day count != 21
```

### Verify Agent Logic Fixes

**Test 4**: Generate Day 2 timeline and check for duplicates
```bash
# Invoke timeline agent for Day 2
# Verify: Only ONE train entry (not "Board train" + "High-speed train")
```

**Test 5**: Check overlapping optional activities warning
```bash
# Review timeline.json warnings array
jq '.warnings' data/china-feb-15-mar-7-2026-20260202-195429/timeline.json

# Expected: Warning about 3 optional activities at 15:00-16:30
```

---

## Success Criteria

- [x] timeline.json restored to 21 days from git commit c8d8b87 (COMPLETED: restored and verified)
- [x] Current timeline backed up to timeline.json.backup-20260214-HHMMSS (COMPLETED)
- [ ] Write/Edit prohibition added to timeline agent PROMPT (lines 7-35 of timeline.md)
- [ ] Timeline agent metadata restricts tools to [Read, Bash, Grep, Glob, Task]
- [ ] Agent logic fixed to prevent duplicate train entries (add rules after line 123)
- [ ] Agent validation detects overlapping optional activities (add after line 150)
- [ ] Invalid `:agent=` syntax removed from settings.json (DEPRIORITIZED - prompt enforcement is primary)
- [ ] PreToolUse hook blocks Write/Edit (DEPRIORITIZED - backup defense only)
- [ ] All verification tests pass

---

## Summary

**Problem**: Write tool overwrote timeline.json (21 days → 1 day) despite user prohibition

**Root Cause**: Invalid permission syntax silently ignored + no runtime hooks + no agent tool restrictions = zero protection

**Solution**: 5-layer defense system
1. **Permission deny rules** (fixed syntax)
2. **PreToolUse hook** (runtime blocking)
3. **Agent tool restrictions** (whitelist only Read/Bash/Grep)
4. **PostToolUse validation** (data integrity check)
5. **Audit logging** (forensics)

**Recovery**: Restore from git commit c8d8b87 (last good version)

**Prevention**: Prompt-level enforcement is PRIMARY defense (agent sees warning every invocation)

---

## User Feedback on Previous Plan

**User rejected previous plan - does not meet development standards**

User requirements (translated):
1. **Re-examine fix approach** - Previous plan violates dev standards
2. **Confirm restoration** ✅ VERIFIED: Restored git c8d8b87 (21 days, MD5: ea0b4bd92d73e939ea4d9e5c54382bb7)
3. **Merge latest Day 1 into 21-day version** - UNCLEAR: Need to explore what changes exist in Day 1 backup
4. **Prompt fix must emphasize**:
   - ONLY use scripts (scripts/save.py)
   - If agent doesn't know how to use script → REPORT ERROR
   - DO NOT attempt Write tool as fallback
5. **Apply same fix to ALL 8 agents**: meals, attractions, entertainment, shopping, accommodation, transportation, timeline, budget

## Phase 1: Investigation Results (COMPLETED)

### Investigation 1.1: Development Standards Violations ✅

**8 Critical Violations Found** in previous plan (Phase 4/5):

1. **Vague error handling** - Doesn't specify agent behavior if it can't use save.py
2. **No save.py success verification** - Missing checkpoint to verify script actually worked
3. **Manual editing instead of script-first** - Proposes manual edits to 8 agents (error-prone)
4. **Fragile line number references** - "after line 123" breaks if file changes
5. **Missing venv activation instruction** - Agent may fail to use save.py correctly
6. **No tool restriction verification** - Doesn't test if `tools:` field actually blocks Write
7. **Contradictory heredoc instruction** - Shows temp file creation with redirect (undermines Write prohibition)
8. **Hardcoded trip slug** - Doesn't tell agent how to get slug dynamically

**Recommended Fix**: Create `scripts/update-agent-prompts.py` for consistent, repeatable modifications across all 8 agents.

### Investigation 1.2: Day 1 Backup Analysis ✅

**User Question**: "你再三确定21天版本中是否有半山逸城兴合酒店"

**Three-Time Verification Result**:
- ❌ **timeline.json**: Does NOT contain "半山逸城兴合酒店"
- ✅ **accommodation.json**: DOES contain "巴中兴合阳光酒店" (Bazhong Xinghe Sunshine Hotel in Banshan Yicheng area)

**Critical Clarification**:
- Git commit c8d8b87 IS the latest 21-day version with Xinghe Hotel in accommodation.json
- ✅ **accommodation.json (Day 2)**: Contains "巴中兴合阳光酒店" with check-in 14:00, check-out 12:00
- ❌ **timeline.json (Day 2)**: MISSING hotel check-in activity at 14:00
- **Problem**: Timeline should include "Hotel check-in at Bazhong Xinghe Sunshine Hotel (14:00)" but it's absent
- **User expectation**: "兴合酒店已经更新到timeline" - but timeline.json does NOT contain this activity

**Day 2 Timeline Gap Found**:
- 11:00-12:00: Arrive family home and settle in
- 12:00-13:00: Home (Banshan Yicheng)
- **MISSING**: 14:00 - Hotel check-in at 巴中兴合阳光酒店
- 13:00-15:00: Making Dumplings Together

**Root Cause**: Timeline agent failed to read accommodation.json and add check-in activity to timeline

**Day 1 Data Comparison**:
```
21-day version (git c8d8b87):    29 activities
Day 1 backup (Feb 14 07:02):     30 activities
Difference:                      5 activities changed
```

**Action Items Identified**:
1. **Day 1**: Merge 3 travel segments from backup
2. **Day 2**: Add missing hotel check-in activity (14:00) from accommodation.json

**Missing from 21-day Day 1** (need to merge back):
1. `Taxi from Hongyadong to Laojun Dong Temple` - 从洪崖洞打车到老君洞
2. `Walk to Danzishi Ferry Pier` - 步行到弹子石码头
3. `Walk to Hongyadong` - 步行到洪崖洞

**Extra in 21-day version** (newer additions):
1. `5:59 Sunset Restaurant & Bar` - 5:59日落餐厅酒吧
2. `Walk to Laojun Dong Taoist Temple` - 步行到老君洞道观

**Merge Strategy**:
- Day 1 backup contains 3 travel segments lost in git c8d8b87
- 21-day version contains 2 new activities not in backup
- **Action Required**: Merge 3 missing travel segments FROM backup INTO 21-day version's Day 1
- **Keep**: 2 new activities in 21-day version (don't overwrite with backup)

## Implementation Status

### ✅ COMPLETED:
1. **Data Recovery**: timeline.json restored from git c8d8b87 (21 days, MD5 verified)
2. **Latest Day 1 Backup**: timeline.json.backup-20260214-070248 (1 day, modified Feb 14 07:02)

### Investigation 1.3: All 8 Agent Prompt Structures ✅

**Current State**:
- ❌ **ALL 8 agents missing `tools:` field** in metadata (no technical enforcement)
- ✅ All 8 agents have "Write Tool Disabled" documentation section
- ✅ All 8 agents specify `scripts/save.py` as save mechanism
- ⚠️ **Inconsistent error handling**: Only 4/8 agents have explicit error instructions

**Agents with good error handling**:
- meals, attractions, transportation, budget (specify "report error if tool fails")

**Agents missing error handling**:
- timeline, entertainment, accommodation, shopping (no failure mode instructions)

---

## Phase 2: Design (COMPLETED)

Plan agent has designed comprehensive solution addressing all requirements.

**Key Design Decisions**:
1. **Script-First**: Create `scripts/update-agent-prompts.py` for automated modifications
2. **5-Layer Defense**: YAML metadata + Prompt warning + Checklist + Failure mode + Self-verification
3. **Marker-Based Insertion**: Uses section headers (not line numbers) for robustness
4. **Idempotent Operations**: Can run multiple times safely
5. **Comprehensive Verification**: Test harness validates all changes

See detailed design in Phase 4 Final Plan below.

---

## Phase 3: Review & Refinement

**Critical files identified by Plan agent**:
- `.claude/agents/timeline.md` (and 7 other agents)
- `scripts/save.py` (existing - reference for integration)
- `scripts/update-agent-prompts.py` (to create)
- `scripts/merge-timeline-day1.py` (to create)
- `scripts/verify-tool-restrictions.py` (to create)

**User requirements verification**:
- ✅ Script-first approach (no manual editing)
- ✅ Error reporting instead of Write fallback
- ✅ Applied to all 8 agents uniformly
- ✅ Day 1 merge handled
- ✅ Development standards compliant

**Additional discovery**: Day 2 timeline missing hotel check-in activity (must be fixed)

---

## Phase 4: Final Implementation Plan

### Context

Timeline data corruption (Feb 13, 2026) occurred when timeline agent bypassed `scripts/save.py` validation by using Write tool directly, overwriting 21 days → 1 day. Permission system failed to block Write tool (invalid `:agent=` syntax silently ignored).

**Scope**: Implement technical restrictions and comprehensive error handling across all 8 travel planning agents to prevent recurrence.

### Critical Files

**Agent Files** (to modify):
- `.claude/agents/accommodation.md`
- `.claude/agents/attractions.md`
- `.claude/agents/budget.md`
- `.claude/agents/entertainment.md`
- `.claude/agents/meals.md`
- `.claude/agents/shopping.md`
- `.claude/agents/timeline.md`
- `.claude/agents/transportation.md`

**Scripts to Create**:
1. `scripts/update-agent-prompts.py` - Automated agent prompt hardening
2. `scripts/merge-timeline-day1.py` - Merge 3 missing Day 1 segments
3. `scripts/verify-tool-restrictions.py` - Verification test harness

**Reference Files**:
- `scripts/save.py` (existing) - Pattern for save operations
- `data/china-feb-15-mar-7-2026-20260202-195429/timeline.json` (current 21-day version)
- `data/china-feb-15-mar-7-2026-20260202-195429/timeline.json.backup-20260214-070248` (Day 1 backup)

### Solution Architecture

**5-Layer Defense System**:

```
Layer 1: YAML Metadata
  └─ tools: [Read, Bash, Skill]  # Blocks Write at runtime

Layer 2: CRITICAL WARNING Block
  └─ Visual hierarchy, root cause reference, historical context

Layer 3: Numbered Checklist
  └─ Step-by-step save.py usage with venv activation

Layer 4: Failure Mode Documentation
  └─ Specific error JSON formats for 5 failure scenarios

Layer 5: Self-Verification Checkpoints
  └─ Pre-tool, post-save, on-error verification questions
```

### Implementation Steps

#### Step 1: Create `scripts/update-agent-prompts.py`

**Purpose**: Programmatically modify all 8 agent files with standardized safety measures.

**Key Logic**:
1. Parse YAML frontmatter of each agent file
2. Add `tools: [Read, Bash, Skill]` to metadata (if missing)
3. Insert CRITICAL WARNING block after YAML (marker: first "##" after "---")
4. Enhance Step 3 with numbered checklist (marker: "### Step 3: Save JSON")
5. Add Failure Mode Handling section (marker: before "## Validation")
6. Add Self-Verification Checkpoints section
7. Validate changes, create backup, atomic rename

**Idempotency**: Detects existing modifications, skips if already applied

**Marker Strategy**:
```python
MARKERS = {
    'yaml_end': '---',
    'first_section': r'^## ',
    'step_3': '### Step 3: Save JSON',
    'validation_section': '## Validation'
}
```

**Error Handling**:
- File not found → Skip with warning
- YAML parse error → Abort with details
- Marker not found → Use fallback or report error
- Validation failure → Rollback to backup

#### Step 2: Create `scripts/merge-timeline-day1.py`

**Purpose**: Merge 3 missing travel segments from backup into current Day 1 timeline.

**Missing Segments**:
1. "Walk to Danzishi Ferry Pier" (15:20-15:35)
2. "Taxi from Hongyadong to Laojun Dong Temple" (15:50-16:05)
3. "Walk to Hongyadong" (20:50-21:05)

**Key Logic**:
1. Load backup timeline (1-day version)
2. Load current timeline (21-day version)
3. Extract 3 missing segments from backup Day 1
4. Insert into current Day 1 in chronological order
5. Validate no time conflicts
6. Save using `scripts/save.py`
7. Verify merge succeeded (32 activities in Day 1)

**Additional Fix**: Add Day 2 hotel check-in activity
- Read `accommodation.json` Day 2
- Extract "巴中兴合阳光酒店" check-in time (14:00)
- Insert into Day 2 timeline between "Home" and "Making Dumplings"

**Conflict Detection**: Abort if any time overlap detected

#### Step 3: Create `scripts/verify-tool-restrictions.py`

**Purpose**: Test harness to verify all safety measures work correctly.

**Test Cases**:
1. **YAML Metadata**: Verify all 8 agents have `tools: [Read, Bash, Skill]`
2. **Prompt Content**: Verify CRITICAL WARNING, Checklist, Failure Mode, Checkpoints exist
3. **save.py Integration**: Test save.py can save data for each agent
4. **Error Handling**: Verify invalid data rejected correctly

**Output**: Pass/fail report with detailed findings

#### Step 4: Execute Update Script

```bash
# 1. Dry-run preview
python3 scripts/update-agent-prompts.py --dry-run

# 2. Review changes
diff -u .claude/agents/timeline.md /tmp/timeline.md.preview

# 3. Create backup
cp -r .claude/agents .claude/agents.backup-$(date +%Y%m%d-%H%M%S)

# 4. Execute
python3 scripts/update-agent-prompts.py --verbose

# 5. Verify
python3 scripts/verify-tool-restrictions.py
```

#### Step 5: Execute Timeline Merge

```bash
# 1. Merge Day 1 + fix Day 2
python3 scripts/merge-timeline-day1.py \
  --trip china-feb-15-mar-7-2026-20260202-195429 \
  --fix-day2-hotel

# 2. Verify merge
jq '.data.days[0].timeline | length' \
  data/china-feb-15-mar-7-2026-20260202-195429/timeline.json
# Expected: 32

# 3. Verify Day 2 hotel
jq '.data.days[1].timeline | keys[]' \
  data/china-feb-15-mar-7-2026-20260202-195429/timeline.json | \
  grep -i "hotel check-in"
# Expected: Found
```

#### Step 6: Final Verification

```bash
# Run comprehensive test harness
python3 scripts/verify-tool-restrictions.py --verbose

# Manual spot-check
git diff .claude/agents/timeline.md
git diff data/china-feb-15-mar-7-2026-20260202-195429/timeline.json

# Validate timeline structure
source venv/bin/activate
python3 scripts/plan-validate.py \
  data/china-feb-15-mar-7-2026-20260202-195429 \
  --agent timeline
```

### Verification Success Criteria

- [ ] All 8 agents have `tools: [Read, Bash, Skill]` in YAML metadata
- [ ] All 8 agents have CRITICAL WARNING block
- [ ] All 8 agents have numbered checklist with venv activation
- [ ] All 8 agents have Failure Mode Handling section
- [ ] All 8 agents have Self-Verification Checkpoints
- [ ] Day 1 timeline has 32 activities (29 + 3 merged)
- [ ] Day 2 timeline includes hotel check-in at 14:00
- [ ] `verify-tool-restrictions.py` reports 100% pass
- [ ] `plan-validate.py` passes on merged timeline
- [ ] No time conflicts detected

### Rollback Plan

If verification fails:
```bash
# Automatic rollback
python3 scripts/update-agent-prompts.py --rollback

# Or manual
cp -r .claude/agents.backup-TIMESTAMP .claude/agents
```

### Key Improvements Over Previous Plan

| Aspect | Previous | This Plan |
|--------|----------|-----------|
| Editing | Manual line-number edits | Script-based marker insertion |
| Robustness | Breaks if lines change | Resilient to content changes |
| venv | Missing instruction | Explicit step + error handling |
| Verification | No success check | Mandatory exit code check |
| Error handling | Vague | 5 specific error JSON formats |
| Testing | None | Comprehensive test harness |
| Idempotency | Not supported | Fully idempotent |
| Rollback | Manual only | Automated support |

### Next Steps After Implementation

1. **Commit Changes**:
```bash
git add .claude/agents/*.md scripts/update-agent-prompts.py \
  scripts/merge-timeline-day1.py scripts/verify-tool-restrictions.py \
  data/china-feb-15-mar-7-2026-20260202-195429/timeline.json

git commit -m "feat: Add Write tool restrictions to all 8 agents

- Add tools: [Read, Bash, Skill] to YAML metadata
- Add CRITICAL WARNING with root cause reference
- Add numbered checklist with venv activation
- Add Failure Mode Handling with error JSON formats
- Add Self-Verification Checkpoints
- Merge 3 missing Day 1 travel segments
- Fix Day 2 missing hotel check-in activity

Prevents recurrence of timeline corruption (Feb 13, 2026)
where Write tool bypassed save.py validation.

Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>"
```

2. **Documentation**: Update agent README with new safety requirements

3. **Monitoring**: Schedule monthly `verify-tool-restrictions.py` runs

---

This plan addresses all 8 violations, applies fixes to all 8 agents uniformly, uses script-first approach, includes comprehensive verification, and fixes both Day 1 and Day 2 timeline issues.
