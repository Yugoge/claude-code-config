---
description: Orchestrated development workflow with multi-round requirement clarification, parallel agent execution, and iterative QA verification
allowed-tools: Task, Read, Write, Edit, Bash, Glob, Grep, TodoWrite
argument-hint: "<development-requirement>"
---

**CRITICAL**: Use TodoWrite to track workflow phases. Mark in_progress before each step, completed immediately after.

# Development Orchestrator

**Philosophy**: Understand requirement fully → Find root cause → Delegate implementation → Verify quality → Iterate until perfect

This command uses multi-round inquiry to fully understand requirements, then orchestrates development through specialized subagents with continuous QA verification.

---

## Step 0: Initialize Workflow Checklist

**Load todos from**: `~/.claude/scripts/todo/dev.py`

Execute:
```bash
source ~/.claude/venv/bin/activate && python3 ~/.claude/scripts/todo/dev.py
```

Use output to create TodoWrite with all workflow steps.

**Rules**: Mark `in_progress` before each step, `completed` after. NEVER skip steps.

---

## Core Workflow

**Multi-Round Orchestration Pattern**:
```
User Requirement (may be vague)
  ↓
Multi-round inquiry until requirement is CRYSTAL CLEAR
  ↓
Git deep-dive for root cause analysis
  ↓
Build comprehensive JSON context (stored in docs/dev/)
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
- NEVER start development with unclear requirements
- Multi-round questioning until you fully understand user intent
- Orchestrator does NO implementation work
- All execution delegated to subagents
- Rich JSON context (1M tokens) stored in `docs/dev/`
- QA verification after each dev cycle
- Git deep-dive for root cause analysis
- Scripts for reusable logic, not inline code
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
- Vague requirement → Proceed to Step 2 (Clarification)
- Clear and specific → Skip to Step 3

**Vague requirement signals**:
- Too broad ("make better", "optimize everything")
- Missing context ("fix the bug", "add feature")
- Unclear scope ("improve performance")
- Multiple unrelated requests
- Missing success criteria

### Step 2: Multi-Round Requirement Clarification

**DO NOT start development with unclear requirements**

**Clarification approach** (iterative until clear):

```
I want to make sure I fully understand your requirement before starting.

Current understanding: {your interpretation}

Clarification questions:
1. {Specific aspect 1}?
2. {Specific aspect 2}?
3. {Success criteria}?

Please answer these so I can develop exactly what you need.
```

**Required information to gather**:
- **What**: Specific feature/fix/change requested
- **Why**: Business reason or problem being solved
- **Where**: Affected components/files/systems
- **Scope**: What's included vs excluded
- **Success**: How to measure completion
- **Constraints**: Technical limitations, backward compatibility

**Multi-round dialog loop**:
1. Ask targeted questions
2. User responds
3. Assess clarity: < 80% clear → Ask more questions
4. Repeat until >= 80% clear
5. Summarize understanding for user confirmation
6. Wait for explicit confirmation ("yes", "correct", "proceed")

**Clarity gate** (must pass before proceeding):
- [ ] Specific components/files identified
- [ ] Root problem understood (not just symptom)
- [ ] Success criteria defined and measurable
- [ ] Scope boundaries clear
- [ ] Technical constraints known
- [ ] User explicitly confirmed understanding

**Example Multi-Round Dialog**:

```
User: "Fix the timeout"

Round 1:
You: "I need clarification on the timeout issue:
1. Which component has the timeout (API client, server, database)?
2. What error message or symptom are you seeing?
3. When did this start happening?
Please provide details so I can properly analyze the root cause."

User: "API calls are timing out"

Round 2:
You: "Thanks. More specifics needed:
1. Which API endpoints are timing out?
2. All calls or only certain conditions?
3. What's the current timeout value?
4. What should be the success criteria (e.g., '99% of calls complete within X seconds')?
Please clarify so we fix the right thing."

User: "POST /api/data times out after 5s, needs to be 15s, should handle 95% of calls"

Round 3:
You: "Perfect! Let me confirm my understanding:
- Issue: POST /api/data endpoint timing out at 5s
- Root cause to investigate: Why 5s insufficient, when did it change
- Solution: Adjust timeout to appropriate value (likely 15s) based on actual latency analysis
- Success: 95% of POST /api/data calls complete without timeout
Is this correct?"

User: "Yes, correct"

→ Proceed to Step 3
```

**Maximum clarification rounds**: 5 (if still unclear after 5, inform user requirement needs restructuring)

### Step 3: Git Root Cause Analysis

**CRITICAL**: Before any fix, understand WHY the problem exists.

**Git investigation steps**:

**1. Identify affected files**:
```bash
# Find files related to requirement
git log --oneline --all --grep="<keyword-from-requirement>"

# Check recent changes to suspected components
git log --oneline -10 -- path/to/component
```

**2. Trace the symptom**:
```bash
# When was this file last changed?
git log --follow --oneline -- path/to/file

# What changed in that commit?
git show <commit-hash>

# Who else was affected by related changes?
git log --all --since="1 month ago" --grep="<related-keyword>"
```

**3. Find root cause**:
```bash
# What was the file before the change?
git show <commit>^:<file>

# What is it now?
git show <commit>:<file>

# Diff to see exact changes
git diff <commit>^ <commit> -- <file>

# Check commit message for intent
git log -1 --format="%B" <commit>
```

**4. Build timeline**:
```bash
# Chronological changes
git log --oneline --reverse --all -- <affected-files>

# Find when problem likely introduced
git log --since="<estimated-date>" --oneline -- <files>
```

**Root cause determination**:
- **NOT**: "Timeout value is too low" (symptom)
- **YES**: "Performance optimization in commit abc123 reduced timeout from 30s to 5s without measuring actual latency" (root cause)

**Document findings**:
- Root cause commit: `<hash> - <message>`
- Why change was made: `<original intent>`
- Why it caused problem: `<unintended consequence>`
- Proper fix approach: `<address root cause, not symptom>`

### Step 4: Build Comprehensive Context JSON

**JSON context file location**: `docs/dev/context-<timestamp>.json`

**Structure**:
```json
{
  "request_id": "dev-<timestamp>",
  "timestamp": "ISO-8601",
  "requirement": {
    "original": "user's original request verbatim",
    "clarified": "final clarified requirement after multi-round inquiry",
    "what": "specific feature/fix/change",
    "why": "business reason or problem",
    "where": ["affected components"],
    "scope": {
      "included": ["what's in scope"],
      "excluded": ["what's out of scope"]
    },
    "success_criteria": [
      "measurable outcome 1",
      "measurable outcome 2"
    ],
    "constraints": ["technical limitations"]
  },
  "root_cause_analysis": {
    "symptom": "what user sees",
    "root_cause": "underlying issue from git analysis",
    "root_cause_commit": "abc123 - commit message",
    "why_introduced": "original intent of problematic change",
    "why_problematic": "unintended consequence",
    "timeline": "when problem started",
    "affected_files": ["list from git log"]
  },
  "context": {
    "codebase_state": "git status output",
    "recent_commits": "git log output",
    "file_contents": {
      "path/to/file1": "relevant file content",
      "path/to/file2": "relevant file content"
    },
    "dependencies": {
      "runtime": "Python 3.11, Node 20, etc",
      "packages": "key dependency versions"
    },
    "environment": {
      "venv_path": "path to venv if Python project",
      "config_files": ["relevant configuration files"]
    }
  },
  "development_approach": {
    "strategy": "how to fix root cause",
    "scripts_to_create": ["parameterized scripts needed"],
    "files_to_modify": ["files to change"],
    "validation_approach": "how QA will verify"
  },
  "standards_to_enforce": {
    "no_hardcoded_values": true,
    "use_source_venv": true,
    "integer_step_numbering": true,
    "meaningful_naming": true,
    "git_root_cause_reference": true
  }
}
```

**Save to**: `docs/dev/context-<timestamp>.json`

### Step 5: Delegate to Dev Subagent

**Use Task tool to invoke dev subagent**:

```
Use Task tool with:
- subagent_type: "general-purpose"
- description: "Implement development changes based on context"
- prompt: "
  You are the dev subagent. Follow agents/dev.md instructions precisely.

  Read context from: docs/dev/context-<timestamp>.json

  Your tasks:
  1. Read and internalize the complete context JSON
  2. Implement changes following the development approach
  3. Create parameterized scripts (no hardcoded values)
  4. Use source venv for Python (NOT python3)
  5. Reference root cause in all changes
  6. Write implementation report to: docs/dev/dev-report-<timestamp>.json

  Implementation report structure:
  {
    \"request_id\": \"same as context\",
    \"dev\": {
      \"status\": \"completed|blocked\",
      \"tasks_completed\": [...],
      \"scripts_created\": [...],
      \"files_modified\": [...],
      \"git_rationale\": {
        \"root_cause_commit\": \"...\",
        \"why_issue_occurred\": \"...\",
        \"how_fix_addresses_root\": \"...\"
      },
      \"qa_ready\": true|false
    }
  }

  Follow all quality standards from agents/dev.md.
  "
```

**Dev subagent workflow** (see `agents/dev.md`):
1. Reads context JSON
2. Implements changes
3. Creates scripts with parameters
4. Writes implementation report JSON

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

**Merge context + dev report for QA**:

```bash
# Combine JSONs
jq -s '.[0] * {dev: .[1].dev}' \
  docs/dev/context-<timestamp>.json \
  docs/dev/dev-report-<timestamp>.json \
  > docs/dev/qa-input-<timestamp>.json
```

**Use Task tool to invoke QA subagent**:

```
Use Task tool with:
- subagent_type: "general-purpose"
- description: "Verify implementation quality against standards"
- prompt: "
  You are the QA subagent. Follow agents/qa.md instructions precisely.

  Read combined context from: docs/dev/qa-input-<timestamp>.json

  Your tasks:
  1. Validate all success criteria met
  2. Verify root cause addressed (not just symptom)
  3. Test created scripts
  4. Check for regressions
  5. Verify quality standards:
     - No hardcoded values in scripts
     - Used source venv (not python3)
     - Integer step numbering only
     - Meaningful naming (no 'enhance', 'fast', etc)
     - Git root cause referenced
  6. Write verification report to: docs/dev/qa-report-<timestamp>.json

  QA report structure:
  {
    \"request_id\": \"same as context\",
    \"qa\": {
      \"status\": \"pass|fail|warning\",
      \"success_criteria_results\": [...],
      \"root_cause_verification\": {...},
      \"quality_findings\": [...],
      \"summary\": {
        \"critical_issues\": 0,
        \"major_issues\": 0,
        \"minor_issues\": 0
      },
      \"iteration_needed\": false|true,
      \"refined_context\": {...}
    }
  }

  Follow all verification procedures from agents/qa.md.
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

**Load in command**:
```markdown
## Step 0: Initialize Workflow Checklist

Execute:
\`\`\`bash
source ~/.claude/venv/bin/activate && python3 ~/.claude/scripts/todo/mycommand.py
\`\`\`

Use output to create TodoWrite with all workflow steps.
```

**Why todo scripts?**
- Agent can see progress
- User can track progress
- Steps never forgotten
- Consistent workflow enforcement

---

## Example End-to-End Workflow

**User**: `/dev "Fix timeout in API"`

**Step 1-2**: Multi-round clarification
- Which API? → POST /api/data
- Current timeout? → 5s
- Success criteria? → 95% calls complete

**Step 3**: Git analysis
- Found: commit abc123 reduced timeout
- Root cause: Performance optimization without measurement

**Step 4**: Build context JSON
- Saved to: `docs/dev/context-20251226-114500.json`

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

**Step 10**: Completion report
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
