# Dev Subagent Quality Standard Violations - Fixed

**Date**: 2025-12-28
**Severity**: Critical (P0) - Quality standard violations
**Status**: ✅ FIXED

---

## Problem Summary

Dev subagent documentation (`/root/.claude/agents/dev.md`) had **critical gaps** in quality enforcement that violated explicit user requirements.

### Violation 1: Missing TodoWrite Requirement

**User Requirement**: "我明确要求过... 不要这样做" (I explicitly required not to do this)

**Evidence**:
- `/clean` workflow Step 1 (line 33-37) mandates: `python ~/.claude/scripts/todo/clean.py`
- Dev subagent Quality Checklist (line 395-409) **completely missing** TodoWrite check
- During /clean execution, todo script was **never called**
- Workflow progress invisible to user

### Violation 2: Decimal Step Numbering Not Enforced

**User Requirement**: "不... 采用小数点step" (Don't use decimal step numbering)

**Evidence**:
- `/clean` command used "Step 3.5" decimal numbering
- Dev.md anti-patterns (line 456-469) mentioned prohibition
- **But Quality Checklist didn't enforce it**
- Result: `/clean` created with violating numbering scheme

---

## Root Cause Analysis

### Technical Root Cause

**Quality Checklist incomplete** - Missing mandatory verification items:
1. Todo script creation/update for multi-step workflows
2. Decimal step numbering prohibition enforcement

### Systemic Root Cause

**Documentation-only guidance insufficient** - Anti-patterns section exists but:
- Not referenced in Quality Checklist
- No automated enforcement
- Easy to overlook during implementation

### Design Flaw

**Separation of concerns broken**:
- Anti-patterns documented (line 456-469)
- Implementation guidelines documented (line 70-236)
- **But checklist didn't consolidate requirements**

---

## Fix Implementation

### Fix 1: Added TodoWrite to Quality Checklist

**File**: `/root/.claude/agents/dev.md`

**Location**: Line 409-410 (new)

**Before**:
```markdown
- [ ] Usage examples provided

---
```

**After**:
```markdown
- [ ] Usage examples provided
- [ ] **CRITICAL: Todo script created/updated** (if workflow has multiple steps, create `~/.claude/scripts/todo/{workflow-name}.py`)
- [ ] **CRITICAL: No decimal step numbering** (use sequential integers: Step 1, Step 2, Step 3, NOT Step 1.1, Step 1.2)

---
```

---

### Fix 2: Added TodoWrite Integration Section

**File**: `/root/.claude/agents/dev.md`

**Location**: Line 240-285 (new section 7)

**Added comprehensive TodoWrite integration guide**:

```markdown
### 7. TodoWrite Integration for Multi-Step Workflows

**CRITICAL**: For workflows with multiple steps, create a todo checklist script.

**When to create todo script**:
- Workflow has 3+ sequential steps
- User needs visibility into progress
- Steps have dependencies or blocking conditions
- Workflow is complex (e.g., /clean, /dev, multi-agent orchestration)

**Todo script requirements**:
```python
#!/usr/bin/env python3
# ~/.claude/scripts/todo/{workflow-name}.py

import json

def get_todos():
    return [
        {"content": "Step description", "status": "pending", "activeForm": "Present continuous form"},
        {"content": "Next step", "status": "pending", "activeForm": "Doing next step"},
        # ... more steps
    ]

if __name__ == "__main__":
    print(json.dumps(get_todos(), indent=2))
```

**Integration**:
- Workflow command should call: `python ~/.claude/scripts/todo/{workflow-name}.py`
- Agent executing workflow uses TodoWrite tool to update status
- Each step transitions: pending → in_progress → completed
```

**Rationale**:
- Clear "when to create" criteria (3+ steps)
- Complete example code (copy-paste ready)
- Integration instructions (how workflow calls it)
- Status transition model (pending → in_progress → completed)

---

### Fix 3: Strengthened Decimal Step Numbering Prohibition

**File**: `/root/.claude/agents/dev.md`

**Location**: Line 506-534 (updated anti-pattern)

**Before**:
```bash
# BAD
# Step 1: Do thing
# Step 1.1: Sub-thing
# Step 1.2: Another sub-thing
# Step 2: Next thing

# GOOD (resequence to integers)
# Step 1: Do thing
# Step 2: Sub-thing
# Step 3: Another sub-thing
# Step 4: Next thing
```

**After**:
```bash
# BAD (creates confusion, hard to track progress)
# Step 1: Do thing
# Step 1.1: Sub-thing
# Step 1.2: Another sub-thing
# Step 2: Next thing
# Step 2.1: Sub-step
# Step 2.1.1: Nested sub-step (WTF?)

# GOOD (resequence to integers - clear, trackable)
# Step 1: Do thing
# Step 2: Sub-thing
# Step 3: Another sub-thing
# Step 4: Next thing
# Step 5: Sub-step
# Step 6: Nested operation
```

**Added explicit rationale**:
```markdown
**Why decimal numbering is prohibited**:
1. **TodoWrite incompatible**: TodoWrite tracks linear progress, not nested hierarchies
2. **Ambiguous priority**: Is Step 1.1 more important than Step 2? Unclear.
3. **Hard to reference**: "Step 1.2.3" is harder to communicate than "Step 5"
4. **Git commit confusion**: "Completed Step 1.1" is less clear than "Completed Step 2"

**How to handle sub-tasks**:
- If workflow has sub-tasks, create separate todo items for each
- Use descriptive names instead of nesting: "Validate config" not "Sub-step 1.1: validation"
- If grouping needed, use markdown sections (## Section) not decimal steps
```

**Rationale**:
- Clear technical reasons (TodoWrite incompatibility)
- Usability reasons (referencing, priority)
- Practical alternatives (how to handle sub-tasks without nesting)

---

### Fix 4: Renumbered /clean Steps to Integers

**File**: `/root/.claude/commands/clean.md`

**Changes**:
- Step 3.5 → Step 4 (Rule Initialization)
- Step 4 → Step 5 (Cleanliness Inspector)
- Step 5 → Step 6 (Style Inspector)
- ... through Step 12 → Step 13 (Completion Report)

**Updated references**:
- Step 4 text: "BEFORE Step 4" → "BEFORE Step 5"
- Verification text: "Before proceeding to Step 4" → "Before proceeding to Step 5"
- orchestrator.sh error: "Step 3.5... Step 4" → "Step 4... Step 5"

---

### Fix 5: Updated clean.py Todo Script

**File**: `/root/.claude/scripts/todo/clean.py`

**Before** (incomplete, mismatched):
```python
return [
    {"content": "Step 1: Scan Project Structure", ...},
    {"content": "Step 2: Invoke Cleanliness Inspector", ...},
    # ... missing Step 1, Step 3, Step 4
    {"content": "Step 10: Generate Completion Report", ...}
]
```

**After** (complete, correct):
```python
return [
    {"content": "Step 1: Initialize Workflow", ...},
    {"content": "Step 2: Scan Project Structure", ...},
    {"content": "Step 3: Build Inspection Context", ...},
    {"content": "Step 4: Rule Initialization (MANDATORY PRE-INSPECTION)", ...},
    {"content": "Step 5: Invoke Cleanliness Inspector", ...},
    # ... all steps through 13
    {"content": "Step 13: Generate Completion Report", ...}
]
```

**Changes**:
- Added missing steps (1, 3, 4)
- Renumbered all steps to match /clean.md
- Step 4 marked as "MANDATORY PRE-INSPECTION"
- Total steps: 10 → 13 (complete)

**Test Result**:
```bash
$ python3 /root/.claude/scripts/todo/clean.py | jq '.[3]'
{
  "content": "Step 4: Rule Initialization (MANDATORY PRE-INSPECTION)",
  "activeForm": "Step 4: Initializing Folder Rules",
  "status": "pending"
}
```

✅ Correct output, Step 4 present with MANDATORY marker

---

## Testing

### Test 1: Quality Checklist Completeness

**Verification**: Read agents/dev.md Quality Checklist (line 395-410)

**Result**:
```markdown
- [ ] Usage examples provided
- [ ] **CRITICAL: Todo script created/updated** (if workflow has multiple steps, create `~/.claude/scripts/todo/{workflow-name}.py`)
- [ ] **CRITICAL: No decimal step numbering** (use sequential integers: Step 1, Step 2, Step 3, NOT Step 1.1, Step 1.2)
```

✅ Both requirements present and marked CRITICAL

---

### Test 2: TodoWrite Documentation Complete

**Verification**: Read agents/dev.md section 7 (line 240-285)

**Result**:
- ✅ When to create criteria defined (3+ steps)
- ✅ Code example provided (complete, runnable)
- ✅ Integration instructions clear
- ✅ Status transition model explained

---

### Test 3: Decimal Numbering Rationale Clear

**Verification**: Read agents/dev.md anti-patterns (line 506-534)

**Result**:
- ✅ 4 technical/usability reasons listed
- ✅ Examples show bad (nested) vs good (flat)
- ✅ Alternative approaches provided (markdown sections)

---

### Test 4: /clean Steps Renumbered

**Verification**: Check step numbering in clean.md

**Result**:
```
Step 1: Initialize Workflow ✅
Step 2: Scan Project Structure ✅
Step 3: Build Inspection Context ✅
Step 4: Rule Initialization ✅ (was 3.5)
Step 5: Invoke Cleanliness Inspector ✅ (was 4)
...
Step 13: Generate Completion Report ✅ (was 12)
```

✅ All steps use integers, no decimals

---

### Test 5: clean.py Matches clean.md

**Verification**: Compare steps in both files

**Result**:
| clean.md | clean.py | Match |
|----------|----------|-------|
| Step 1: Initialize Workflow | Step 1: Initialize Workflow | ✅ |
| Step 2: Scan Project Structure | Step 2: Scan Project Structure | ✅ |
| Step 3: Build Inspection Context | Step 3: Build Inspection Context | ✅ |
| Step 4: Rule Initialization | Step 4: Rule Initialization (MANDATORY PRE-INSPECTION) | ✅ |
| ... | ... | ✅ |
| Step 13: Generate Completion Report | Step 13: Generate Completion Report | ✅ |

✅ All 13 steps match

---

## Impact

### Immediate Impact

1. **TodoWrite now mandatory** for multi-step workflows
   - Dev agent will create todo scripts for complex workflows
   - User gets progress visibility
   - /clean and similar commands now trackable

2. **Decimal numbering prohibited**
   - All future workflows use integer steps
   - TodoWrite compatible by default
   - Clear, unambiguous progress tracking

3. **/clean workflow corrected**
   - Steps renumbered 1-13 (no decimals)
   - clean.py updated to match
   - Step 4 marked as MANDATORY

### Long-term Impact

**Quality standard enforcement**:
- Checklist now comprehensive (todos + numbering)
- Anti-patterns include rationale (why prohibited)
- Implementation guidelines complete (section 7)

**Workflow consistency**:
- All multi-step workflows will have todo scripts
- All workflows use integer step numbering
- User experience consistent across /clean, /dev, /refactor

---

## Files Changed

1. `/root/.claude/agents/dev.md`
   - Quality Checklist: Added 2 CRITICAL items (line 409-410)
   - Section 7: Added TodoWrite Integration guide (line 240-285)
   - Anti-patterns: Strengthened decimal numbering prohibition (line 506-534)

2. `/root/.claude/commands/clean.md`
   - Renumbered Step 3.5 → Step 4 through Step 12 → Step 13
   - Updated all step references in text
   - Fixed verification checkpoints

3. `/root/.claude/scripts/orchestrator.sh`
   - Updated error messages: "Step 3.5/4" → "Step 4/5"

4. `/root/.claude/scripts/todo/clean.py`
   - Added missing steps (1, 3, 4)
   - Renumbered all steps to match clean.md
   - Marked Step 4 as MANDATORY PRE-INSPECTION

---

## Root Cause

**Insufficient quality enforcement** in dev subagent documentation:
- Anti-patterns documented but not checked
- TodoWrite requirement implied but not mandated
- Decimal numbering prohibited but not enforced

**Solution**: Multi-layered enforcement:
1. **Checklist**: Mandatory verification before execution
2. **Documentation**: Complete implementation guidelines
3. **Rationale**: Explicit reasons for each requirement

---

## Lessons Learned

### Design Principles

1. **Checklist is source of truth**: If it's not in the checklist, it won't be checked
2. **Anti-patterns need rationale**: "Don't do X" is weak; "Don't do X because Y" is strong
3. **Examples must be complete**: Partial examples lead to partial implementations
4. **Consistency across artifacts**: Command docs must match todo scripts must match actual execution

### Enforcement Strategy

**Three-layer approach**:
1. **Guidelines**: Explain how to implement (section 7)
2. **Anti-patterns**: Explain what NOT to do (section on decimal numbering)
3. **Checklist**: Verify compliance before completion

Without all three layers, requirements slip through.

---

## Next Steps

1. ✅ Fixes committed and tested
2. Apply same quality review to other subagents (cleanliness-inspector, style-inspector, cleaner)
3. Create automated checklist validator (script that checks dev.md Quality Checklist against actual implementations)
4. Add pre-commit hook to validate step numbering (reject decimal steps in .md files)

---

**Status**: ✅ Fixed and verified
**Severity**: Critical (P0) - Quality standard violations
**Verification**: All tests passed (5/5)
