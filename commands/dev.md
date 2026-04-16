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
QA validates BA conclusions (analysis quality check)
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

**No-Multitasking Rule (MANDATORY)**:
- Each subagent invocation handles exactly ONE issue/task
- BA analyzes ONE requirement, Dev implements ONE fix, QA verifies ONE fix
- The orchestrator may launch multiple subagents in parallel for different issues
- NEVER bundle multiple issues into a single subagent prompt
- If QA fails and iteration is needed, re-invoke Dev with the SAME single issue, not a batch

---

## Implementation

### Step 1: Parse Development Requirement

Extract requirement from `$ARGUMENTS`:

```
Requirement: "$ARGUMENTS"
```

**Parse `--spec`**: If `$ARGUMENTS` contains `--spec <path>`, extract the path and remove the flag from the requirement text. Store as `spec_path`.

**Auto-detect spec**: If `--spec` is NOT provided, scan `docs/dev/specs/*.md` sorted by modification time (newest first). If a file exists, set `spec_path` to that path and announce:
```
Auto-detected spec: <path>
(Created by /spec — pass --spec <other-path> to override.)
```

If no spec found, set `spec_path = null`. All downstream behavior is unchanged when `spec_path` is null.

**Edge cases**:
- Empty `$ARGUMENTS` → Prompt user for requirement
- Otherwise → Pass raw text (minus --spec flag) to BA subagent in Step 2

**Keep this step lightweight** - BA subagent handles all analysis.

### Step 2: Specialist Consultation (MANDATORY for matching domains)

When the requirement matches a specialist's domain, you MUST call that specialist. This is not optional.

**Mandatory triggers:**
- ANY visual/UI/UX/layout/styling/responsive issue → MUST call `ui-specialist`
- ANY architectural/structural/performance/dependency concern → MUST call `architect`
- ANY business-logic/feature-completeness/user-flow question → MUST call `product-owner`
- ANY end-to-end user scenario or UX-friction issue → MUST call `user`

**How to decide:**
- Read the requirement text
- If it contains words like: "UI", "layout", "CSS", "gap", "margin", "padding", "mobile", "desktop", "responsive", "style", "color", "icon", "component looks", "render", "visible", "hidden", "overflow", "scroll" → ui-specialist is REQUIRED
- If it contains words like: "performance", "architecture", "slow", "memory", "dependency", "integration", "pattern", "structure" → architect is REQUIRED
- Multiple specialists can and should be called in parallel when multiple domains are touched.

**How to invoke**:

```
Use Agent tool with:
- description: "<Specialist role> consultation for: <requirement summary>"
- prompt: "
  You are the <specialist-name> specialist. Follow .claude/agents/<specialist-name>.md.

  Requirement: '<requirement from Step 1>'

  Provide your observations and analysis relevant to this requirement.
  Return structured findings that will inform the BA analysis.
  DO NOT modify files. Return observations only.
  "
```

**Rationale:** Skipping the UI specialist on a UI bug means BA analyzes from a code perspective only, missing visual cause patterns (global CSS overrides, computed style inspection, viewport-specific bugs). This has caused 6 consecutive fix failures.

Pass all specialist findings to the BA subagent in Step 3 as additional context.

## Four Contracts Awareness (Orchestrator Role)

The BA subagent enforces four domain-agnostic contracts (see
`~/.claude/agents/ba.md` §Four Contracts). The orchestrator MUST
complement BA by surfacing context before delegation and verifying
compliance after BA returns. The orchestrator does NOT re-do BA's work —
it prepares inputs and validates outputs.

### Pre-BA: surface retry signals

Before delegating to BA, scan the user's request and repo state for retry
signals. BA will independently check these, but the orchestrator must
provide them explicitly so BA starts with ground truth:

- **Retry phrasing** in user text: "again", "still", "didn't fix",
  "Nth time", "又", "还是", "没修好", "第 N 次"
- **Recent related commits**: `git log --oneline --grep="<keyword>" -20`
- **Existing BA specs**: files matching `docs/dev/ba-spec-*.md` with
  keywords from the current request

Pass findings to BA in the delegation prompt under an explicit
`prior_attempt_signals` block:

    prior_attempt_signals:
      retry_phrase: "<matched phrase or null>"
      recent_commits: ["<hash> <subject>", ...]
      existing_specs: ["docs/dev/ba-spec-<ts>.md", ...]

### Post-BA: verify contract compliance

Before proceeding to dev, verify the BA JSON context contains:

- `evidence.measured.value` populated (not null, not empty string)
- `evidence.expected.source` populated
- `scope_expansion.all_occurrences` non-empty (or scope_expansion explicitly
  marked `not_applicable` with reason)
- `reference_source.tier` not `tier_3_tainted` when `copy_allowed: true`
- If Contract D triggered: `prior_attempts.novelty_check.differs_from_all_priors = true`

If any check fails, the orchestrator re-delegates to BA with explicit
feedback naming the missing field. Do NOT proceed to dev with an
incomplete spec.

### BA rejection handling

If BA returns `status: "rejected"` (Contract D novelty-check failure):

- Do NOT retry BA with the same input (it will reject again)
- Surface the rejection reason and prior-attempt layer to the user
- Propose a different-layer approach (use the L1–L5 layer vocabulary)
- Only after user selects a different layer, re-delegate to BA

### Layer vocabulary (shared with BA)

Layers from shallow to deep:

- **L1 cosmetic**: styling, class names, component swap
- **L2 structural**: layout, component hierarchy
- **L3 data**: coordinates, schema values, regex, constants, SVG paths
- **L4 logic**: conditions, state machines, data flow
- **L5 infrastructure**: build, deploy, environment

When dev reports back, verify implementation layer matches BA's spec layer.
If dev changed L1 when spec called for L3, treat as failed implementation.

### Step 3: Delegate to BA Subagent

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
  Spec file: <spec_path or null>
  Prior attempt signals:
    retry_phrase: <matched phrase or null>
    recent_commits: [<hash> <subject>, ...]
    existing_specs: [docs/dev/ba-spec-<ts>.md, ...]

  If Spec file is not null: Read the spec file FIRST. Use Section 5 (User's Acceptance Criterion) as the primary requirement source. Use Sections 1-4 as baseline context. If Section 7 (What Must Be Done) is populated, treat it as prescriptive guidance.

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

### Step 4: BA Clarification Loop

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
- If BA returns `status: "ready"`, proceed to Step 5

**If BA returns `status: "ready"` on first invocation**: Skip to Step 5.

### Step 5: Validate BA Output

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

**If validation passes**: Proceed to Step 5a

### Step 5a: QA Validates BA Conclusions

**Purpose**: Verify BA's analysis quality BEFORE Dev starts implementation. Catches unproven claims, scope mismatches, and missing investigation evidence early -- saving a wasted Dev+QA cycle.

**Invoke QA in BA-validation mode**:

```
Use Agent tool with:
- subagent_type: "qa"
- description: "Validate BA analysis quality (not code)"
- prompt: "
  You are the QA subagent in BA-VALIDATION MODE. This is NOT code verification.
  You are verifying the QUALITY OF BA's ANALYSIS, not any implementation.

  DO NOT: build, deploy, open browser, run Playwright, or test code.
  DO: read BA's deliverables and challenge every claim.

  BA spec file: docs/dev/ba-spec-<timestamp>.md
  Context JSON: docs/dev/context-<timestamp>.json
  Spec file: <spec_path or null>

  Verify these 4 dimensions:

  1. EVIDENCE QUALITY: For every factual claim BA makes (root cause, affected files,
     component identification), is there evidence? 'BA says so' is not evidence.
     Look for: git blame output, file path verification, code grep results,
     import chain tracing. Flag claims stated as fact without investigation proof.

  2. SCOPE ALIGNMENT: Compare BA's bug title and acceptance criteria against
     the original requirement (and spec Section 5 if available). Did BA narrow,
     rename, or redefine the bug? Is anything from the original requirement
     missing from BA's analysis?

  3. INVESTIGATION COMPLETENESS: If the requirement says 'audit X', 'investigate Y',
     or 'trace Z' -- did BA actually do it, or did BA skip the investigation and
     jump to a conclusion? Check for investigation deliverables the requirement
     explicitly asked for.

  4. AFFECTED-FILE ACCURACY: Are the files BA identified actually the right files?
     Quick-verify: do the file paths exist? Do they contain the code BA claims?
     Does the import chain support BA's component identification?

  Return JSON:
  {
    'verdict': 'pass' or 'fail',
    'objections': [
      {
        'dimension': 'evidence_quality|scope_alignment|investigation_completeness|affected_file_accuracy',
        'claim': 'what BA claimed',
        'problem': 'what is wrong with the claim',
        'required_evidence': 'what BA must provide to satisfy this objection'
      }
    ],
    'summary': 'one-line overall assessment'
  }

  Write report to: docs/dev/ba-qa-report-<timestamp>.json
  "
```

**Process QA result**:

```
IF verdict == "pass":
  -> BA conclusions validated. Proceed to Step 6.

ELIF verdict == "fail":
  -> Proceed to Step 5b for BA-QA iteration.
```

### Step 5b: BA-QA Iteration Loop (if QA rejects BA)

**Iteration guard**: Maximum 3 BA-QA iterations to prevent infinite loops

**Current BA-QA iteration**: Track internally (starts at 1)

**If BA-QA iteration > 3**:
```
BA-QA validation: 3 iterations exhausted. Proceeding with best-effort BA output.

Unresolved objections:
{summary of remaining QA objections}

Appending unresolved objections to context JSON under `ba_qa_unresolved_objections`.
Proceeding to Step 6 with documented assumptions.
```

**If BA-QA iteration <= 3**:

**Announce**: `BA-QA iteration <N>/3: QA found <count> objections in BA analysis. Re-invoking BA to address objections.`

**Re-invoke BA with QA's objections**:

```
Use Agent tool with:
- subagent_type: "ba"
- description: "Re-investigate: address QA objections on analysis quality"
- prompt: "
  You are the BA subagent. Follow .claude/agents/ba.md instructions precisely.

  Your previous analysis was REJECTED by QA. Address each objection below
  with concrete evidence. Do not argue -- investigate and provide proof.

  Original requirement: '<requirement>'
  Previous BA spec: docs/dev/ba-spec-<timestamp>.md
  Previous context: docs/dev/context-<timestamp>.json
  Spec file: <spec_path or null>

  QA objections:
  <JSON array of objections from ba-qa-report>

  For each objection:
  - Perform the investigation QA requested
  - Provide the specific evidence QA asked for
  - If your original claim was wrong, CORRECT it
  - If your original claim was right, PROVE it with evidence

  Update ba-spec and context JSON with corrected/proven analysis.
  Return JSON with status and updated file paths.
  "
```

**After BA re-delivers**: Return to Step 5 (validate BA output), then Step 5a (QA re-validates).

**Rule**: Every BA invocation MUST be followed by QA validation. No exceptions.

**Iteration tracking**: Update TodoWrite with BA-QA iteration number.

### Step 6: Delegate to Dev Subagent

**Use Task tool to invoke dev subagent with file paths only**:

```
Use Task tool with:
- description: "Implement development changes based on BA context"
- prompt: "
  You are the dev subagent. Follow agents/dev.md instructions precisely.

  Context file: docs/dev/context-<timestamp>.json
  BA spec file: docs/dev/ba-spec-<timestamp>.md
  Spec file: <spec_path or null>
  Write your implementation report to: docs/dev/dev-report-<timestamp>.json

  If Spec file is not null: Read the spec file FIRST for context. After implementation, update the spec: Section 2 (What Was Attempted) with your approach and rationale. Section 3 (What Was Changed) with exact file:line edits.
  "
```

**Wait for dev subagent completion** before proceeding.

### Step 7: Validate Dev Implementation

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

**If dev completed**: Proceed to Step 8

### Step 8: Delegate to QA Subagent

**Use Task tool to invoke QA subagent with file paths only**:

```
Use Task tool with:
- description: "Verify implementation quality against standards"
- prompt: "
  You are the QA subagent. Follow agents/qa.md instructions precisely.

  Context file: docs/dev/context-<timestamp>.json
  Dev report file: docs/dev/dev-report-<timestamp>.json
  BA spec file: docs/dev/ba-spec-<timestamp>.md
  Spec file: <spec_path or null>
  Write your verification report to: docs/dev/qa-report-<timestamp>.json

  If Spec file is not null: Read the spec file FIRST. After verification, update the spec: Section 4 (Current State) with measured values. If verdict is fail, also update Section 6 (Why Not Met) and Section 7 (What Must Be Done) with prescriptive next steps.
  "
```

**Wait for QA subagent completion** before proceeding.

### Step 9: Process QA Results

Read QA report: `docs/dev/qa-report-<timestamp>.json`

**Decision tree**:

```
IF qa.status == "pass":
  → Proceed to Step 10 (Update Permissions)

ELIF qa.status == "warning":
  → Check if minor issues acceptable
  → If yes: Proceed to Step 10 (Update Permissions)
  → If no: Proceed to Step 11 (Iteration)

ELIF qa.status == "fail":
  → Proceed to Step 11 (Iteration)
```

### Step 10: Update Settings.json Permissions

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

### Step 11: Iteration Loop (if QA fails)

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

**Return to Step 6** with new context JSON

**Iteration tracking**: Update TodoWrite with iteration number

### Step 12: Generate Completion Report

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

**Step 2**: Consult specialists (optional)
- No specialists needed for this requirement → skip

**Step 3**: Delegate to BA subagent
- BA returns `needs_clarification` with questions

**Step 4**: BA clarification loop
- Round 1: Which API? → POST /api/data, timeout 5s, need 95% completion
- Round 2: BA has enough clarity → returns `ready`
- BA creates: `ba-spec-20251226-114500.md` + `context-20251226-114500.json`

**Step 5**: Validate BA output
- Both files exist with required sections

**Step 6**: Dev subagent
- Created: `scripts/measure-api-latency.sh`
- Created: `scripts/validate-api-timeout.sh`
- Modified: `config/api.json`
- Saved report: `docs/dev/dev-report-20251226-114500.json`

**Step 7-8**: QA subagent
- Verified all scripts work
- Confirmed root cause addressed
- Status: PASS
- Saved report: `docs/dev/qa-report-20251226-114500.json`

**Step 9**: Process results
- QA passed → proceed to completion

**Step 12**: Completion report
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
