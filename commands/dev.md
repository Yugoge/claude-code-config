---
description: Orchestrated development workflow with BA subagent delegation, parallel agent execution, and iterative QA verification
---

**CRITICAL**: Use TodoWrite to track workflow phases. Mark in_progress before each step, completed immediately after.

# Development Orchestrator

**Philosophy**: Understand requirement fully → Find root cause → Delegate implementation → Verify quality → Iterate until perfect

This command uses multi-round inquiry to fully understand requirements, then orchestrates development through specialized subagents with continuous QA verification.

---

## Core Workflow

**BA-Delegated Orchestration Pattern**:
```
User Requirement (may be vague)
  ↓
Quick parse of $ARGUMENTS
  ↓
Delegate to BA subagent (analysis + context building)
  ↓
BA clarification loop (if BA needs user input, max 3 rounds)
  ↓
Validate BA output (ba-spec + context JSON)
  ↓
Delegate to dev subagent (implementation)
  ↓
Delegate to QA subagent (verification)
  ↓
IF QA fails → Refine context → Iterate
  ↓
IF QA passes → Generate completion report
```

**Key Principles**:
- Orchestrator does NO analysis or context building (BA handles it)
- Orchestrator does NO implementation work (dev handles it)
- All requirement clarification routed through BA subagent
- BA returns dual output: Markdown spec + JSON context
- Orchestrator only relays BA's clarification questions to user
- Rich JSON context stored in `docs/dev/`
- QA verification after each dev cycle
- Iterate until all quality standards met

---

## Implementation

### Step 1: Parse Development Requirement

Extract requirement from `$ARGUMENTS`:

```
Requirement: "$ARGUMENTS"
```

**Edge cases**:
- Empty `$ARGUMENTS` → Prompt user for requirement
- Otherwise → Pass raw text to BA subagent in Step 2

**Keep this step lightweight** - BA subagent handles all analysis.

### Step 2: Delegate to BA Subagent

**Use Task tool to invoke BA subagent for requirements analysis and context building**:

```
Use Task tool with:
- description: "Analyze requirement and build development context"
- prompt: "
  You are the BA subagent. Follow .claude/agents/ba.md instructions precisely.

  Requirement: '<requirement from Step 1>'
  Clarification round: 0
  Previous answers: null
  Codebase hints: <any file paths mentioned by user, or null>
  Timestamp: <YYYYMMDD-HHMMSS>

  Perform full analysis:
  1. Parse and decompose requirement
  2. Perform git root cause analysis (if applicable)
  3. Identify affected files
  4. Generate MoSCoW requirements and BDD acceptance criteria
  5. Write ba-spec-<timestamp>.md to docs/dev/
  6. Write context-<timestamp>.json to docs/dev/

  Return JSON with status, file paths, and summary.
  "
```

**Wait for BA subagent completion** before proceeding.

### Step 3: BA Clarification Loop

**If BA returns `status: "needs_clarification"`**:

1. Present BA's questions to user (relay verbatim)
2. Collect user answers
3. Re-invoke BA with answers:

```
Use Task tool with:
- description: "Continue BA analysis with clarification answers"
- prompt: "
  You are the BA subagent. Follow .claude/agents/ba.md instructions precisely.

  Requirement: '<original requirement>'
  Clarification round: <N>
  Previous answers: <JSON array of {question, answer} pairs>
  Codebase hints: <accumulated hints>
  Timestamp: <same timestamp>

  Continue analysis with user's answers. Generate output if clarity sufficient.
  "
```

**Loop rules**:
- Maximum 3 clarification rounds
- After round 3, BA returns best-effort with explicit assumptions
- If BA returns `status: "ready"`, proceed to Step 4

**If BA returns `status: "ready"` on first invocation**: Skip to Step 4.

### Step 4: Validate BA Output

**Check BA deliverables exist and are well-formed**:

Read BA output files:
- `docs/dev/ba-spec-<timestamp>.md` - Markdown specification
- `docs/dev/context-<timestamp>.json` - JSON context for dev subagent

**Sanity checks**:
- [ ] Both files exist
- [ ] Markdown spec has required sections (Goal, Requirements, Acceptance Criteria)
- [ ] JSON context has required fields (requirement, root_cause_analysis, development_approach)
- [ ] Success criteria are measurable
- [ ] Affected files identified

**If validation fails**:
- Re-invoke BA with specific feedback about what's missing
- Maximum 2 re-invocations for validation fixes

**If validation passes**: Proceed to Step 5

### Step 5: Delegate to Dev Subagent

**Use Task tool to invoke dev subagent with file paths only**:

```
Use Task tool with:
- description: "Implement development changes based on BA context"
- prompt: "
  You are the dev subagent. Follow agents/dev.md instructions precisely.

  Context file: docs/dev/context-<timestamp>.json
  BA spec file: docs/dev/ba-spec-<timestamp>.md
  Write your implementation report to: docs/dev/dev-report-<timestamp>.json
  "
```

**Wait for dev subagent completion** before proceeding.

### Step 6: Validate Dev Implementation

**Quick validation before QA**:

Read dev implementation report: `docs/dev/dev-report-<timestamp>.json`

**Sanity checks**:
- [ ] Status is "completed" (not "blocked")
- [ ] All tasks documented
- [ ] Scripts created have usage examples
- [ ] Git rationale references root cause
- [ ] Files exist that were reported as created/modified

**If dev blocked**:
- Read blocking issues from report
- Resolve blockers (e.g., missing information, technical constraints)
- Refine context JSON with additional information
- Re-invoke dev subagent (maximum 3 attempts)

**If dev completed**: Proceed to Step 7

### Step 7: Delegate to QA Subagent

**Use Task tool to invoke QA subagent with file paths only**:

```
Use Task tool with:
- description: "Verify implementation quality against standards"
- prompt: "
  You are the QA subagent. Follow agents/qa.md instructions precisely.

  Context file: docs/dev/context-<timestamp>.json
  Dev report file: docs/dev/dev-report-<timestamp>.json
  BA spec file: docs/dev/ba-spec-<timestamp>.md
  Write your verification report to: docs/dev/qa-report-<timestamp>.json
  "
```

**Wait for QA subagent completion** before proceeding.

### Step 8: Process QA Results

Read QA report: `docs/dev/qa-report-<timestamp>.json`

**Decision tree**:

```
IF qa.status == "pass":
  → Proceed to Step 9 (Update Permissions)

ELIF qa.status == "warning":
  → Check if minor issues acceptable
  → If yes: Proceed to Step 9 (Update Permissions)
  → If no: Proceed to Step 10 (Iteration)

ELIF qa.status == "fail":
  → Proceed to Step 10 (Iteration)
```

### Step 9: Update Settings.json Permissions

**CRITICAL**: Auto-update permissions for new functionality.

**Extract validated permissions from QA report**:

```bash
jq '.qa.permissions_verification.validated_permissions' docs/dev/qa-report-<timestamp>.json
```

**Update settings.json**:

Read current settings:
```bash
cat .claude/settings.json
```

For each validated permission:

```json
{
  "pattern": "Bash(scripts/new-script.sh:*)",
  "section": "allow",
  "reason": "Allow execution of..."
}
```

**Add to appropriate section in settings.json**:

```bash
# Use jq to add permission
jq '.permissions.allow += ["Bash(scripts/new-script.sh:*)"]' .claude/settings.json > .claude/settings.json.tmp
mv .claude/settings.json.tmp .claude/settings.json
```

**Permission update rules**:

1. **Scripts created** → Add to "allow":
   - `"Bash(scripts/<script-name>.sh:*)"`
   - `"Bash(~/.claude/scripts/<script-name>.sh:*)"`

2. **Python scripts** → Add to "allow":
   - `"Bash(source ~/.claude/venv/bin/activate && python3 ~/.claude/scripts/todo/<script>.py:*)"`

3. **Hooks created** → Add to "allow":
   - `"Bash(~/.claude/hooks/<hook-name>.sh:*)"`

4. **Commands created** → Already allowed via "SlashCommand"

**Notify user**:

```
Updated settings.json permissions:

Added to "allow" section:
- Bash(scripts/validate-timeout.sh:*) - Allow timeout validation script
- Bash(scripts/measure-api-latency.sh:*) - Allow latency measurement script

Total permissions added: 2

You can now use these scripts without permission prompts.
```

**Validation**:
- Check JSON syntax after modification
- Verify no duplicate permissions
- Confirm permissions follow patterns

**Error handling**:
- If settings.json has syntax error → Ask user to fix manually
- If permission already exists → Skip, don't duplicate
- If user denies update → Log to completion report

### Step 10: Iteration Loop (if QA fails)

**Iteration guard**: Maximum 5 iterations to prevent infinite loops

**Current iteration**: Track internally (starts at 1)

**If iteration > 5**:
```
Quality verification failed after 5 iterations.

Issues remaining:
{summary of critical/major issues}

Recommendation:
- Manual review needed, OR
- Requirements need to be broken down into smaller tasks, OR
- Technical constraints prevent automated solution

Would you like to:
1. Review current state manually
2. Break down into smaller tasks
3. Accept current implementation with known issues
```

**If iteration <= 5**:

**Refine context for next iteration**:

```bash
# Extract refined context from QA report
jq '.qa.refined_context' docs/dev/qa-report-<timestamp>.json \
  > docs/dev/refined-context-<timestamp>.json

# Merge with original context
jq -s '.[0] * {
  iteration: (.[0].iteration // 0) + 1,
  previous_attempts: [.[0].previous_attempts // [], {
    iteration: (.[0].iteration // 0),
    dev: .[1].dev,
    qa: .[1].qa,
    timestamp: now | strftime("%Y-%m-%dT%H:%M:%SZ")
  }] | flatten,
  refined_requirements: .[2]
}' \
  docs/dev/context-<timestamp>.json \
  docs/dev/qa-input-<timestamp>.json \
  docs/dev/refined-context-<timestamp>.json \
  > docs/dev/context-iter<N>-<timestamp>.json
```

**Return to Step 5** with new context JSON

**Iteration tracking**: Update TodoWrite with iteration number

### Step 11: Generate Completion Report

**QA passed! Generate final report.**

**Completion report structure**:

```markdown
# Development Completion Report

**Request ID**: dev-<timestamp>
**Completed**: <ISO-8601>
**Iterations**: <N>

## Requirement

**Original**: {original user request}

**Clarified**: {final clarified requirement}

**Success Criteria**:
- {criterion 1}
- {criterion 2}

## Root Cause Analysis

**Symptom**: {what user reported}

**Root Cause**: {underlying issue}

**Root Cause Commit**: `<hash> - <message>`

**Timeline**: {when problem introduced}

## Implementation

**Approach**: {how root cause was addressed}

**Scripts Created**:
- `script-name.sh` - {purpose}
  - Parameters: {param1}, {param2}
  - Usage: `script-name.sh <param1> <param2>`

**Files Modified**:
- `path/to/file` - {what changed}

**Git Rationale**: {why this fixes root cause}

## Quality Verification

**Status**: PASSED

**Success Criteria**: ✅ All met

**Quality Standards**:
- ✅ No hardcoded values
- ✅ Source venv used
- ✅ Integer step numbering
- ✅ Meaningful naming
- ✅ Root cause referenced

**Issues Found**: {N critical, N major, N minor}

**Iterations**: {N}

## Files Generated

- Context: `docs/dev/context-<timestamp>.json`
- Dev Report: `docs/dev/dev-report-<timestamp>.json`
- QA Report: `docs/dev/qa-report-<timestamp>.json`

## Next Steps

{Any follow-up tasks or recommendations}

---

Development completed successfully!
```

**Save report to**: `docs/dev/completion-<timestamp>.md`

**Present to user**: Show summary with key changes and next steps

**Offer git commit** (if requested):
```
Would you like me to create a git commit for these changes?

I'll include:
- Clear commit message with root cause reference
- All modified files
- Link to completion report
```

---

## JSON Storage Policy

**All JSON files stored in**: `docs/dev/`

**File naming convention**:
- Context: `context-<timestamp>.json` or `context-iter<N>-<timestamp>.json`
- Dev report: `dev-report-<timestamp>.json`
- QA report: `qa-report-<timestamp>.json`
- QA input: `qa-input-<timestamp>.json`
- Completion: `completion-<timestamp>.md`

**Timestamp format**: `YYYYMMDD-HHMMSS`

**Retention**:
- Keep all files for current session
- Archive to `docs/dev/archive/YYYY-MM/` after 30 days (via /clean)

---

## Integration with /clean

The `/clean` command supports `docs/dev/`:
- Preserves active development contexts (< 7 days old)
- Archives completed contexts to `docs/dev/archive/YYYY-MM/`
- Removes contexts > 90 days old

See `/clean` command documentation for details.

---

## Quality Standards Enforcement

**Dev subagent enforces** (see `agents/dev.md`):
- Parameterized scripts (no hardcoded values)
- `source venv` (not `python3`)
- Meaningful naming (no `enhance`, `fast`)
- Git root cause analysis

**QA subagent verifies** (see `agents/qa.md`):
- Success criteria met
- Root cause addressed
- No regressions
- Quality standards compliance
- Integer step numbering

**Orchestrator ensures**:
- Requirements fully clarified
- Comprehensive context
- Iterative quality improvement
- Proper JSON storage

---

## Agent Development Use Cases

**This command supports ALL development tasks, not just scripts:**

### Supported Development Types

1. **Scripts** (`scripts/`)
   - Bash automation scripts
   - Python utility scripts
   - Build/deployment scripts

2. **Slash Commands** (`.claude/commands/`)
   - New slash commands
   - Command modifications
   - Command documentation

3. **Subagents** (`.claude/agents/`)
   - Specialist subagent definitions
   - Agent behavior specifications
   - Agent integration patterns

4. **Hooks** (`.claude/hooks/`)
   - Pre/post tool use hooks
   - Session lifecycle hooks
   - Safety and validation hooks

5. **Configuration** (`.claude/`)
   - `CLAUDE.md` global instructions
   - `settings.json` permissions/hooks
   - Project-specific configs

6. **Todo Scripts** (`.claude/scripts/todo/`)
   - Workflow checklist generators
   - Step tracking automation

### Agent-Flexible Implementation

**IMPORTANT**: Avoid over-engineering when Agent intelligence can handle it.

**When to use scripts**:
- ✅ Repeated operations (run 5+ times)
- ✅ Complex multi-step workflows
- ✅ Integration with existing tools
- ✅ Performance-critical operations

**When to use Agent intelligence**:
- ✅ One-time operations
- ✅ Context-dependent decisions
- ✅ Natural language processing
- ✅ Creative problem-solving
- ✅ Adaptive workflows

**Example - Avoid Over-Engineering**:

```
BAD (over-engineered):
  User: "Check if file has correct header"
  Dev: Creates scripts/validate-file-header.sh with 50 lines

GOOD (agent-flexible):
  User: "Check if file has correct header"
  Dev: Agent reads file, checks header, reports result
  (No script needed for one-time check)

WHEN TO SCRIPT:
  User: "Add header validation to CI/CD pipeline"
  Dev: Creates scripts/validate-headers.sh
  (Repeated operation, needs automation)
```

### Settings.json Permissions

**All development operations require user confirmation via `ask` permission**:

```json
"ask": [
  "Write(.claude/commands/**)",
  "Edit(.claude/commands/**)",
  "Write(.claude/agents/**)",
  "Edit(.claude/agents/**)",
  "Write(.claude/hooks/**)",
  "Edit(.claude/hooks/**)",
  "Write(.claude/scripts/**)",
  "Edit(.claude/scripts/**)",
  "Edit(.claude/settings.json)",
  "Edit(.claude/CLAUDE.md)"
]
```

**Why `ask` permission?**
- Commands and agents change system behavior
- Hooks can block operations
- Settings control security
- CLAUDE.md affects all sessions

**User must explicitly approve each file change**

### Todo Script Integration

**Learn from knowledge-system pattern**:

When creating commands with multi-step workflows:

1. **Create todo script** in `.claude/scripts/todo/<command>.py`
2. **Return workflow steps** as JSON
3. **Force todo refresh** via hook injection (like knowledge-system)

**Example todo script** (`.claude/scripts/todo/mycommand.py`):

```python
#!/usr/bin/env python3
"""Preloaded TodoList for /mycommand workflow."""

def get_todos():
    return [
        {"content": "Step 1: Parse input", "activeForm": "Step 1: Parsing input", "status": "pending"},
        {"content": "Step 2: Process data", "activeForm": "Step 2: Processing data", "status": "pending"},
        {"content": "Step 3: Generate output", "activeForm": "Step 3: Generating output", "status": "pending"}
    ]

if __name__ == "__main__":
    import json
    print(json.dumps(get_todos(), indent=2, ensure_ascii=False))
```

**Why todo scripts?**
- Agent can see progress
- User can track progress
- Steps never forgotten
- Consistent workflow enforcement

---

## Example End-to-End Workflow

**User**: `/dev "Fix timeout in API"`

**Step 1**: Parse requirement
- Requirement: "Fix timeout in API"

**Step 2**: Delegate to BA subagent
- BA returns `needs_clarification` with questions

**Step 3**: BA clarification loop
- Round 1: Which API? → POST /api/data, timeout 5s, need 95% completion
- Round 2: BA has enough clarity → returns `ready`
- BA creates: `ba-spec-20251226-114500.md` + `context-20251226-114500.json`

**Step 4**: Validate BA output
- Both files exist with required sections

**Step 5**: Dev subagent
- Created: `scripts/measure-api-latency.sh`
- Created: `scripts/validate-api-timeout.sh`
- Modified: `config/api.json`
- Saved report: `docs/dev/dev-report-20251226-114500.json`

**Step 6-7**: QA subagent
- Verified all scripts work
- Confirmed root cause addressed
- Status: PASS
- Saved report: `docs/dev/qa-report-20251226-114500.json`

**Step 8**: Process results
- QA passed → proceed to completion

**Step 11**: Completion report
- Generated: `docs/dev/completion-20251226-114500.md`
- Presented summary to user

---

## Success Metrics

- ✅ 100% requirement clarity before development
- ✅ Root cause identified and addressed
- ✅ Zero hardcoded values in scripts
- ✅ QA passes within 3 iterations
- ✅ All standards enforced
- ✅ Complete audit trail in JSON files

---

**Remember**: You are an orchestrator. You clarify, analyze, delegate, coordinate, and verify. You do NOT implement. Let the subagents do the work.
