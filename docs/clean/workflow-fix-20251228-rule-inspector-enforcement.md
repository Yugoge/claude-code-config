# Workflow Fix: Enforce rule-inspector Step 3.5

**Date**: 2025-12-28
**Request ID**: clean-20251228-150046
**Issue**: Rule-inspector step (Step 3.5) was being skipped, causing incomplete workflow execution
**Status**: ✅ FIXED

---

## Problem Analysis

### Root Cause

The `/clean` command workflow had a **critical design flaw** in Step 3.5:

1. **Misleading title**: "Step 3.5: Rule Initialization (Optional)"
   - The word "Optional" signaled that this step could be skipped
   - In reality, this step is **mandatory** for first-time clean execution

2. **Execution ambiguity**:
   - Documentation contained bash code blocks meant for reference
   - Claude agent interpreted these as "user should run this manually"
   - No clear directive to execute the step autonomously

3. **No enforcement mechanism**:
   - Step 4 (clean-inspect) could execute without Step 3.5 completing
   - No validation that rule-context existed before proceeding
   - Silent failures led to incomplete cleanup

### Impact

- Rule-inspector was never invoked during first /clean execution
- Folders lacked INDEX.md and README.md documentation
- Cleanup proceeded without baseline folder organization rules
- Inconsistent results across multiple /clean runs

---

## Fix Implementation

### 1. Updated /clean Command Documentation

**File**: `/root/.claude/commands/clean.md`

#### Changes to Step 3.5 Header (line 121):

**Before**:
```markdown
### Step 3.5: Rule Initialization (Optional)

Initialize folder rules if not already present:

**Skip if**:
- All folders already have INDEX.md and README.md
- This is a repeat /clean execution
```

**After**:
```markdown
### Step 3.5: Rule Initialization ⚠️ MANDATORY PRE-INSPECTION

**CRITICAL**: This step MUST execute BEFORE Step 4. DO NOT SKIP unless explicitly verified.

Initialize folder rules to establish baseline documentation:

**You MUST execute this step if ANY of the following are true**:
- First time running /clean on this project
- Any folder lacks INDEX.md or README.md
- New folders detected since last /clean run
- You are unsure whether rules are initialized

**Only skip if ALL conditions are met**:
- All key folders have INDEX.md AND README.md
- You have verified this in the current session
- This is a repeat /clean execution within same session
```

**Rationale**:
- Removed misleading "(Optional)" label
- Added ⚠️ emoji for visual prominence
- Changed from negative conditions (Skip if) to positive conditions (MUST execute if)
- Made skip conditions exhaustive (ALL must be true)
- Added "when unsure" clause to bias toward execution

#### Added Verification Checkpoint (line 190-201):

**After the rule-inspector bash block**:
```bash
# VERIFICATION CHECKPOINT: Ensure rule initialization completed or was not needed
if [[ ! -f "docs/clean/rule-context-$REQUEST_ID.json" ]] && [[ "$NEEDS_INIT" == "true" ]]; then
  echo "❌ ERROR: Rule initialization failed! Cannot proceed to inspection." >&2
  exit 1
fi
```

**Verification section**:
```markdown
**Verification**: Before proceeding to Step 4, you MUST confirm one of:
- ✅ Rule initialization completed (rule-context JSON exists)
- ✅ Rule initialization was not needed (all folders documented)

**If uncertain, STOP and verify manually.**
```

**Rationale**:
- Explicit verification checkpoint with bash validation
- Exit on failure prevents proceeding to Step 4
- Markdown checklist for agent to follow
- "STOP" directive for uncertain cases

---

### 2. Enhanced orchestrator.sh Validation

**File**: `/root/.claude/scripts/orchestrator.sh`

#### Added Prerequisite Check in `clean_inspect()` (line 193-228):

**Before** (line 183-198):
```bash
clean_inspect() {
  echo "=== Clean Inspection Orchestration ===" >&2
  echo "Context: $CONTEXT_FILE" >&2

  # Extract project root
  PROJECT_ROOT=$(jq -r '.orchestrator.analysis.project_root // "."' "$CONTEXT_FILE")
  echo "Project: $PROJECT_ROOT" >&2

  # Validate required fields
  if ! jq -e '.orchestrator.requirement' "$CONTEXT_FILE" >/dev/null 2>&1; then
    echo "Error: Missing requirement in context" >&2
    exit 1
  fi

  # ... rest of function
```

**After** (line 183-234):
```bash
clean_inspect() {
  echo "=== Clean Inspection Orchestration ===" >&2
  echo "Context: $CONTEXT_FILE" >&2

  # Extract project root
  PROJECT_ROOT=$(jq -r '.orchestrator.analysis.project_root // "."' "$CONTEXT_FILE")
  echo "Project: $PROJECT_ROOT" >&2

  # Extract request ID for rule-context verification
  REQUEST_ID=$(jq -r '.request_id // ""' "$CONTEXT_FILE")
  RULE_CONTEXT_FILE="docs/clean/rule-context-${REQUEST_ID}.json"

  # CRITICAL PREREQUISITE CHECK: Verify rule-inspector was executed
  # Step 3.5 MUST complete before clean-inspect (Step 4)
  echo "🔍 Checking prerequisite: rule-inspector completion..." >&2

  # Check if key folders need documentation
  KEY_FOLDERS=("agents" "scripts" "docs" "hooks" "commands")
  NEEDS_RULES=false

  for folder in "${KEY_FOLDERS[@]}"; do
    if [[ ! -f "$PROJECT_ROOT/$folder/INDEX.md" ]] || [[ ! -f "$PROJECT_ROOT/$folder/README.md" ]]; then
      NEEDS_RULES=true
      echo "⚠️  Missing documentation in $folder/" >&2
      break
    fi
  done

  # If rules are needed but rule-context doesn't exist, BLOCK execution
  if [[ "$NEEDS_RULES" == "true" ]] && [[ ! -f "$RULE_CONTEXT_FILE" ]]; then
    echo "❌ ERROR: Rule initialization required but not completed!" >&2
    echo "   Step 3.5 (rule-inspector) MUST execute before Step 4 (clean-inspect)" >&2
    echo "   Missing: $RULE_CONTEXT_FILE" >&2
    echo "" >&2
    echo "   Action required: Execute Step 3.5 first:" >&2
    echo "   ~/.claude/scripts/orchestrator.sh rule-inspect <rule-context-json>" >&2
    exit 1
  fi

  if [[ "$NEEDS_RULES" == "false" ]]; then
    echo "✅ Rule initialization not needed (all folders documented)" >&2
  else
    echo "✅ Rule initialization completed: $RULE_CONTEXT_FILE" >&2
  fi

  # Validate required fields
  if ! jq -e '.orchestrator.requirement' "$CONTEXT_FILE" >/dev/null 2>&1; then
    echo "Error: Missing requirement in context" >&2
    exit 1
  fi

  # ... rest of function
```

**Rationale**:
- **Defense in depth**: Even if Step 3.5 is skipped in /clean, orchestrator will catch it
- **Automated detection**: Checks key folders for missing INDEX.md/README.md
- **Explicit blocking**: `exit 1` prevents proceeding with incomplete workflow
- **Clear error messages**: Tells user exactly what's wrong and how to fix it
- **Visual indicators**: Uses emojis (🔍, ⚠️, ❌, ✅) for quick scanning

---

## Testing Results

### Test 1: With rule-context present (Success Path)

```bash
$ ~/.claude/scripts/orchestrator.sh clean-inspect /root/.claude/docs/clean/context-clean-20251228-150046.json

=== Clean Inspection Orchestration ===
Context: /root/.claude/docs/clean/context-clean-20251228-150046.json
Project: /root/.claude
🔍 Checking prerequisite: rule-inspector completion...
⚠️  Missing documentation in agents/
✅ Rule initialization completed: docs/clean/rule-context-clean-20251228-150046.json
Cleanliness inspector can now read context from: ...
```

**Result**: ✅ Validation passed, workflow continues

---

### Test 2: Without rule-context (Failure Path - Enforcement)

```bash
# Simulate missing rule-context
$ mv docs/clean/rule-context-clean-20251228-150046.json docs/clean/rule-context-clean-20251228-150046.json.backup

$ ~/.claude/scripts/orchestrator.sh clean-inspect /root/.claude/docs/clean/context-clean-20251228-150046.json

=== Clean Inspection Orchestration ===
Context: /root/.claude/docs/clean/context-clean-20251228-150046.json
Project: /root/.claude
🔍 Checking prerequisite: rule-inspector completion...
⚠️  Missing documentation in agents/
❌ ERROR: Rule initialization required but not completed!
   Step 3.5 (rule-inspector) MUST execute before Step 4 (clean-inspect)
   Missing: docs/clean/rule-context-clean-20251228-150046.json

   Action required: Execute Step 3.5 first:
   ~/.claude/scripts/orchestrator.sh rule-inspect <rule-context-json>

$ echo $?
1
```

**Result**: ❌ Validation correctly blocked execution with exit code 1

---

## Key Improvements

### 1. Language Clarity
- Removed ambiguous "Optional" labeling
- Used imperative language ("MUST", "DO NOT SKIP")
- Added visual warnings (⚠️ MANDATORY)

### 2. Conditional Logic
- Changed from negative (skip if) to positive (execute if)
- Made conditions exhaustive and explicit
- Added "when unsure" bias toward execution

### 3. Enforcement Layers

#### Layer 1: Documentation
- Clear instructions in /clean command
- Explicit verification checkpoints
- Bash validation examples

#### Layer 2: Orchestrator
- Automated prerequisite checking
- File existence validation
- Folder documentation verification

#### Layer 3: Error Handling
- Descriptive error messages
- Actionable remediation steps
- Non-zero exit codes for failures

---

## Workflow Impact

### Before Fix
```
Step 1: Initialize ✅
Step 2: Scan ✅
Step 3: Build Context ✅
Step 3.5: Rule Init (Optional) ⏭️ SKIPPED
Step 4: Cleanliness Inspect ✅ (incomplete, no baseline rules)
Step 5: Style Inspect ✅
...
```

### After Fix
```
Step 1: Initialize ✅
Step 2: Scan ✅
Step 3: Build Context ✅
Step 3.5: Rule Init ⚠️ MANDATORY
  → Check: Is rule-context needed? YES (agents/ lacks INDEX.md)
  → Execute: rule-inspector subagent ✅
  → Verify: rule-context-{REQUEST_ID}.json exists ✅
Step 4: Cleanliness Inspect
  → Prerequisite check: rule-context exists? ✅
  → Execute: cleanliness-inspector ✅
Step 5: Style Inspect ✅
...
```

---

## Lessons Learned

### Design Principles

1. **No ambiguous optionality**: If a step is conditionally required, make the conditions explicit and exhaustive

2. **Defense in depth**: Multiple validation layers prevent workflow failures:
   - Documentation-level (instructions)
   - Script-level (bash validation)
   - Orchestrator-level (automated checks)

3. **Fail fast with clear messages**: Block execution immediately with actionable error messages

4. **Visual prominence**: Use formatting (⚠️, ❌, ✅) to draw attention to critical sections

5. **Bias toward safety**: When uncertain, execute the step rather than skip it

---

## Related Files

- `/root/.claude/commands/clean.md` - Updated Step 3.5 documentation
- `/root/.claude/scripts/orchestrator.sh` - Added prerequisite validation to clean_inspect()
- `/root/.claude/docs/clean/rule-context-clean-20251228-150046.json` - Rule context created by fix

---

## Root Cause Summary

**Technical**: Misleading "Optional" label + lack of enforcement mechanism

**Systemic**: Ambiguous workflow documentation designed for human execution, not agent automation

**Solution**: Multi-layered enforcement (documentation + orchestrator validation) with explicit conditions and visual warnings

---

## Next Steps

1. ✅ Fix deployed and tested
2. Monitor next /clean execution for compliance
3. Consider adding similar prerequisite checks to other multi-step workflows (/dev, /refactor)
4. Update workflow design guidelines to prevent similar issues

---

**Status**: ✅ Fixed, tested, and documented
**Severity**: Critical (P0) - Workflow incompleteness
**Verification**: Manual testing passed (both success and failure paths)
