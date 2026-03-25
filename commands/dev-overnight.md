---
description: Autonomous overnight development loop - continuously explores codebase, finds issues, fixes them, and repeats until end-time
---

**CRITICAL**: Use TodoWrite to track workflow phases. Mark in_progress before each step, completed immediately after.

# Dev-Overnight: Autonomous Continuous Development

**Philosophy**: Explore autonomously, discover real issues, fix them systematically, loop until time expires, then summarize everything.

This command runs an unattended development loop. You are fully autonomous -- no user input is needed or expected. You discover issues yourself by scanning the codebase, fix each one through a simplified dev cycle, and keep going until the specified end time.

---

## Overview

```
Hook creates state file + parses end-time (automatic)
  |
Step 1: Create worktree (first run only)
  |
  +---> EXPLORATION PHASE (Step 2)
  |       4 specialist subagents scan in parallel:
  |         product-owner | architect | user | ui-specialist
  |                |
  |       PIPELINE CREATION (Step 3)
  |       Merge 4 reports, deduplicate, create N pipelines (one per issue)
  |                |
  |       PARALLEL BA PHASE (Step 4-5)
  |         Launch ALL N BA subagents in parallel → validate all outputs
  |                |
  |       PARALLEL DEV PHASE (Step 6-7)
  |         Launch ALL N Dev subagents in parallel → validate all outputs
  |                |
  |       PARALLEL QA PHASE (Step 8-9)
  |         Launch ALL N QA subagents in parallel → process all results
  |                |
  |       ITERATION LOOPS (Step 10)
  |         Per-pipeline Dev→QA re-runs for failures (max 5 each)
  |                |
  |       PERMISSIONS (Step 11)
  |         Aggregate permissions from all N pipelines, apply once
  |                |
  |       LOG & TIME CHECK (Step 12)
  |       Update state with all N pipeline results, check end-time
  |                |
  |       SUMMARY OR LOOP (Step 13)
  |       Time remaining? → reset todos, loop to Step 2
  |       Time expired? → generate summary, cleanup
  |                |
  |       TODO COMPLETION DETECTION (PostToolUse hook)
  |       All 13 steps completed?
  |         YES + time remaining: reset todos, loop to Step 2
  |         YES + time expired: allow natural completion
  |         NO: continue current step
```

---

## IMPORTANT RULES

1. **You are autonomous**. Do NOT ask the user anything. Make decisions yourself.
2. **Loop continuously**. After each fix cycle, the todo completion hook handles looping. This is non-negotiable.
3. **Keep cycles comprehensive**. Each cycle settles ALL discovered issues via parallel pipelines. Every issue gets its own BA/Dev/QA pipeline. Pipelines are ordered by severity (critical > major > minor > cosmetic) and impact scope (agents_flagged count) to ensure high-severity issues are processed first.
4. **ALL exploration and fixes via subagents**. Use Agent tool for ALL scanning, analysis, and implementation work. Main context only handles state management, TodoWrite, and loop control.
5. **Skip unfixable issues**. If a fix fails verification 3 times, mark it as skipped and move on.
6. **Track everything**. Update the state file after every significant action.
7. **The Stop hook prevents premature exit**. The time-lock hook will block conversation termination until end-time. Do not try to circumvent it.
8. **Git checkpoint after each fix**. The existing posttool-git-checkpoint.sh hook handles this automatically on Write/Edit.
9. **Never modify production infrastructure**. No Docker operations, no service restarts, no deployment changes.
10. **Deduplicate**. Check the state file's cycle_log before starting a fix -- do not re-fix issues already addressed.

---

## Arguments

```
/dev-overnight [end-time] [focus]
```

**Examples**:
- `/dev-overnight 6:00` — run until 6:00, no focus (explore everything)
- `/dev-overnight 6:00 applio UI bugs` — run until 6:00, focus on applio UI bugs
- `/dev-overnight fix hooks` — default 8h, focus on hooks issues
- `/dev-overnight` — default 8h, no focus

The `focus` string is stored in the state file and passed to all 4 specialist subagents as a discovery hint. It helps specialists focus their scans but does not affect pipeline creation -- all discovered issues get pipelines regardless of focus match.

---

## Implementation

### Step 1: Create Worktree

The state file has already been created by the UserPromptSubmit hook at `.claude/overnight-state-<session_id>.json`. Find and read it:

```bash
ls .claude/overnight-state-*.json
```

**Read the state file** to get the end_time, session_id, and confirm initialization. If multiple state files exist, use the one matching the current session.

If no state file exists (edge case), create it manually using the v4 schema with a generated session_id.

**WORKTREE GUARD**: FIRST check the state file's `worktree_path` field.
- If `worktree_path` is NOT null: the worktree already exists from a previous cycle. Do NOT call EnterWorktree. Skip directly to Step 2.
- If `worktree_path` IS null: this is the first invocation. Create the worktree.

**Create worktree for isolation** (only when worktree_path is null):

Call `EnterWorktree` with name `overnight-YYYYMMDD-<session_id_short>` (first 8 chars of session_id):

```
Call EnterWorktree with name: "overnight-<YYYYMMDD>-<session_id_short>"
```

After EnterWorktree succeeds, update the state file:
- Set `worktree_path` to the worktree directory path
- Set `worktree_branch` to the branch name

If EnterWorktree fails (disk space, git lock, etc):
- Log a warning
- Continue on the current branch
- Leave `worktree_path` as null in the state file

**Announce initialization**:

```
Overnight development session initialized.
Start time: <start_time>
End time: <end_time>
Worktree: <worktree_path or "none (using current branch)">
Loop: todo-completion-driven (automatic reset on cycle complete)
Time-lock hook is active -- session will not terminate until end-time.
Beginning autonomous exploration...
```

---

### Continuation Mode

When you see "OVERNIGHT CONTINUATION" injected by the prompt hook, you are in continuation mode with fresh context.

**In continuation mode**:
1. Read the state file to determine `current_phase`
2. Skip Step 1 entirely (worktree already exists)
3. Resume from the appropriate step based on current_phase:
   - `initializing` or `exploring` -> Step 2 (Explore)
   - `pipeline_creation` -> Step 3 (Create pipelines)
   - `analyzing` -> Step 4 (Parallel BA)
   - `implementing` -> Step 6 (Parallel Dev)
   - `verifying` -> Step 8 (Parallel QA)
   - `iterating` -> Step 10 (Iteration loops)
   - `logging` -> Step 12 (Log)
4. The hook has already injected the command specification and state summary into this prompt

**Do NOT**:
- Create the state file (it already exists)
- Call EnterWorktree (the worktree already exists -- the continuation context explicitly tells you this)

---

### Step 2: Explore Codebase for Issues

**Update state**: Set `current_phase` to `"exploring"`.

**CRITICAL: This step has two sub-steps. Step 2a launches the PM subagent to build a test plan. Step 2b launches 4 specialist subagents that read the test plan themselves.**

Read the state file's `addressed_issues` array first.

#### Step 2a: Launch PM Subagent

Launch the PM (test plan manager) subagent to build a structured test plan. The PM reads CLAUDE.md and the state file, then writes test-plan.json.

```
Use Agent tool with:
- subagent_type: "pm"
- description: "Build test plan from project docs and session history"
- prompt: "
  You are the PM subagent. Follow agents/pm.md instructions precisely.

  Project path: <worktree_path from state file if set, otherwise project_path>
  State file path: <path to overnight-state-*.json>
  Session ID: <session_id>
  Output test plan to: docs/dev/overnight/<session_id>/test-plan.json
  "
```

**Wait for PM subagent to complete.**

**Validate test plan**: Read `docs/dev/overnight/<session_id>/test-plan.json` and verify:
- File exists and is valid JSON
- Has `app_context` with at least `url` field
- Has `agent_assignments` with all 4 agent keys
- Has `core_flow_gate.owner` set to `"user"`
- Has `core_flow_gate.failure_is_cycle_failure` set to `true`

If validation fails, re-invoke PM (maximum 2 retries). If still failing, proceed to Step 2b without a test plan (specialists will discover context themselves).

#### Step 2b: Launch 4 Specialist Subagents

Launch all 4 Agent calls in a SINGLE response (parallel execution):

```
Launch 4 Agent tool calls simultaneously:

1. Agent(subagent_type: "product-owner")
   Write report to: docs/dev/overnight/<session_id>/product-owner-report.json

2. Agent(subagent_type: "architect")
   Write report to: docs/dev/overnight/<session_id>/architect-report.json

3. Agent(subagent_type: "user")
   Write report to: docs/dev/overnight/<session_id>/user-report.json

4. Agent(subagent_type: "ui-specialist")
   Write report to: docs/dev/overnight/<session_id>/ui-specialist-report.json

Each subagent receives ONLY:
- Project path: <worktree_path from state file if set, otherwise project_path>
- Already addressed: <addressed_issues array from state file>
- Focus: <focus string from state file, or "none">
- Test plan: docs/dev/overnight/<session_id>/test-plan.json
- Output report to: <path above>

**NOTE**: Always use `worktree_path` as the project path when it is set in the state file. Subagents must scan and report on files inside the worktree, not the main project directory.

**IMPORTANT**: Do NOT include application context, credentials, flow steps, or sample data in the specialist prompts. The test plan file contains all of this. Specialists read it themselves via their Step 0 protocol.
```

**Wait for all 4 subagents to complete** before proceeding.

**Validate reports** (main agent does NOT read project files, only validates report existence and structure):

```bash
~/.claude/scripts/check-overnight-reports.sh docs/dev/overnight/<session_id>
```

**Sanity checks on each report**:
- [ ] File exists and is valid JSON
- [ ] Has `issues` array (may be empty)
- [ ] Each issue has required fields: `description`, `location`, `severity`, `category`, `estimated_effort`
- [ ] No duplicate issues within the same report
- [ ] Issues do not overlap with `addressed_issues` from state file

**Report JSON schema** (all 4 subagents output the same schema):
```json
{
  "agent": "product-owner|architect|user|ui-specialist",
  "timestamp": "ISO-8601",
  "project_path": "/path/to/project",
  "scan_duration_seconds": 42,
  "issues": [
    {
      "description": "Brief description of the issue",
      "location": "file/path:line or file/path or 'project-wide'",
      "severity": "critical|major|minor|cosmetic",
      "category": "agent-specific category string",
      "estimated_effort": "small|medium|large",
      "details": "Extended explanation with evidence",
      "suggested_fix": "How to fix (optional)"
    }
  ],
  "summary": "One-line summary of findings"
}
```

**If validation fails** for any report:
- Log which reports failed and why
- Re-invoke only the failed subagent(s) (maximum 2 retries)
- If still failing after retries, proceed with available reports

**If zero issues found across all 4 reports**:
- Log a "clean sweep" entry
- After 2 consecutive clean sweeps: generate summary and allow termination

**Core Flow Gate Check**:

After all 4 specialists complete, read the user agent's report. Check `core_flow_completed`:
- If `core_flow_completed: false` (or missing): the core flow gate has failed. Log this as a cycle-level failure. The user agent's core flow issues take top priority in Step 3.
- If `core_flow_completed: true`: gate passed, proceed normally.

This gate is non-negotiable: if the user cannot complete the core business flow, the entire cycle is considered failed regardless of other agents' findings.

### Step 3: Create Parallel Pipelines for All Issues

**Update state**: Set `current_phase` to `"pipeline_creation"`.

**Read all 4 JSON reports** from `docs/dev/overnight/`:
- `product-owner-report.json`
- `architect-report.json`
- `user-report.json`
- `ui-specialist-report.json`

**Merge into single issue list**:
1. Combine all issues from all 4 reports
2. Deduplicate: same file+description from multiple agents counts as one (but note which agents flagged it)
3. Filter out any issue already in `addressed_issues` from state file
4. Filter out any issue that has failed 3 times (check `failed_attempts`)

**Prioritize by severity and impact**. Every remaining issue gets a pipeline, ordered by: (1) severity: critical > major > minor > cosmetic, (2) impact scope: issues flagged by more agents rank higher within the same severity.

**Time guard** (severity-aware): If time remaining < 5 minutes, filter issues by severity+effort: (a) Drop cosmetic issues regardless of effort, (b) Drop minor issues with medium/large effort, (c) Keep major issues with small effort only, (d) Keep critical issues with small effort only. This ensures remaining time is spent on the highest-severity fixable issues.

**Create pipeline definitions** -- one per deduplicated issue, with zero-indexed suffix:

```python
# Sort by severity (critical first), then by impact scope (more agents = higher priority)
severity_order = {"critical": 0, "major": 1, "minor": 2, "cosmetic": 3}
sorted_issues = sorted(
    deduplicated_issues,
    key=lambda x: (severity_order.get(x["severity"], 3), -len(x["agents_flagged"]))
)

pipelines = []
for i, issue in enumerate(sorted_issues):
    pipelines.append({
        "index": i,
        "description": issue["description"],
        "location": issue["location"],
        "severity": issue["severity"],
        "category": issue["category"],
        "agents_flagged": issue["agents_flagged"],  # which specialists found it
        "phase": "pending",      # pending -> ba -> dev -> qa -> done/skipped
        "iteration": 0,
        "status": "active",      # active -> fixed/skipped
        "timestamp_suffix": f"{timestamp}-{i}"  # unique file naming suffix
    })
```

**Update state file**:
- Set `current_issues` to the pipeline array
- Set `issues_found` += len(pipelines)

**Announce pipeline creation**:
```
Created {N} parallel pipelines for this cycle:
  Pipeline 0: {description} ({severity}, {location})
  Pipeline 1: {description} ({severity}, {location})
  ...
Proceeding to parallel BA phase.
```

### Step 4: Run All BA Subagents (Parallel)

**Update state**: Set `current_phase` to `"analyzing"`.

**Launch ALL N BA subagents in a SINGLE response** (parallel execution). Each pipeline gets its own BA Agent call with unique file naming.

```
Launch N Agent tool calls simultaneously (one per pipeline):

For each pipeline[i] in current_issues:

Agent(subagent_type: "ba")
  description: "BA analysis for pipeline {i}: {pipeline.description}"
  prompt: "
    You are the BA subagent. Follow .claude/agents/ba.md instructions precisely.

    Requirement: '{pipeline.description}'
    Clarification round: 3
    Previous answers: null
    Codebase hints: {pipeline.location}
    Timestamp: {pipeline.timestamp_suffix}
    Project root: <worktree_path from state file if set, otherwise project root>

    This is a self-discovered issue from overnight exploration.
    No clarification is needed -- proceed directly to analysis.
    All file operations and git analysis must use paths inside the project root above.

    Perform full analysis:
    1. Parse and decompose requirement
    2. Perform git root cause analysis (if applicable)
    3. Identify affected files
    4. Generate MoSCoW requirements and BDD acceptance criteria
    5. Write ba-spec-{pipeline.timestamp_suffix}.md to docs/dev/ (inside project root)
    6. Write context-{pipeline.timestamp_suffix}.json to docs/dev/ (inside project root)

    Return JSON with status, file paths, and summary.
  "
```

**Wait for ALL N BA subagents to complete** before proceeding.

**NOTE**: Since this is autonomous mode, there is NO BA clarification loop. If any BA returns `needs_clarification`, treat it as `ready` and use best-effort output with explicit assumptions. Do NOT ask the user.

**Fallback**: If the Agent tool cannot handle N simultaneous calls, batch them in groups of 4 and wait for each batch to complete before starting the next.

### Step 5: Validate All BA Outputs

**For each pipeline[i]**, check BA deliverables exist and are well-formed:

Read BA output files:
- `docs/dev/ba-spec-{pipeline.timestamp_suffix}.md` - Markdown specification
- `docs/dev/context-{pipeline.timestamp_suffix}.json` - JSON context for dev subagent

**Sanity checks per pipeline**:
- [ ] Both files exist
- [ ] Markdown spec has required sections (Goal, Requirements, Acceptance Criteria)
- [ ] JSON context has required fields (requirement, root_cause_analysis, development_approach)
- [ ] Success criteria are measurable
- [ ] Affected files identified

**If validation fails for pipeline[i]**:
- Re-invoke only the failed BA with specific feedback about what's missing
- Maximum 2 re-invocations per pipeline
- If still failing after retries: mark pipeline status as `"skipped"` with reason `"BA validation failed"`

**Update state**: Set each pipeline's `phase` to `"ba_complete"`.

**If all pipelines are skipped**: Skip to Step 12 (log results).

### Step 6: Run All Dev Subagents (Parallel)

**Update state**: Set `current_phase` to `"implementing"`.

**Filter**: Only launch Dev for pipelines with `phase == "ba_complete"` and `status == "active"`.

**Launch ALL active Dev subagents in a SINGLE response** (parallel execution):

```
For each active pipeline[i]:

Agent(subagent_type: "dev")
  description: "Dev implementation for pipeline {i}: {pipeline.description}"
  prompt: "
    You are the dev subagent. Follow agents/dev.md instructions precisely.

    Context file: docs/dev/context-{pipeline.timestamp_suffix}.json
    BA spec file: docs/dev/ba-spec-{pipeline.timestamp_suffix}.md
    Write your implementation report to: docs/dev/dev-report-{pipeline.timestamp_suffix}.json
    Project root: <worktree_path from state file if set, otherwise project root>

    IMPORTANT: All file reads, writes, and git operations must use absolute paths
    inside the project root above. Do not modify files in the main project directory.
  "
```

**Wait for ALL Dev subagents to complete** before proceeding.

**Fallback**: If the Agent tool cannot handle N simultaneous calls, batch them in groups of 4.

### Step 7: Validate All Dev Implementations

**For each active pipeline[i]**, validate dev output:

Read dev report: `docs/dev/dev-report-{pipeline.timestamp_suffix}.json`

**Sanity checks per pipeline**:
- [ ] Status is "completed" (not "blocked")
- [ ] All tasks documented
- [ ] Scripts created have usage examples
- [ ] Git rationale references root cause
- [ ] Files exist that were reported as created/modified

**If dev blocked for pipeline[i]**:
- Read blocking issues from report
- Resolve blockers (e.g., missing information, technical constraints)
- Refine context JSON with additional information
- Re-invoke only that pipeline's dev subagent (maximum 3 attempts)
- If still blocked: mark pipeline status as `"skipped"` with reason `"Dev blocked"`

**Update state**: Set each successful pipeline's `phase` to `"dev_complete"`.

### Step 8: Run All QA Subagents (Parallel)

**Update state**: Set `current_phase` to `"verifying"`.

**Filter**: Only launch QA for pipelines with `phase == "dev_complete"` and `status == "active"`.

**Launch ALL active QA subagents in a SINGLE response** (parallel execution):

```
For each active pipeline[i]:

Agent(subagent_type: "qa")
  description: "QA verification for pipeline {i}: {pipeline.description}"
  prompt: "
    You are the QA subagent. Follow agents/qa.md instructions precisely.

    Context file: docs/dev/context-{pipeline.timestamp_suffix}.json
    Dev report file: docs/dev/dev-report-{pipeline.timestamp_suffix}.json
    BA spec file: docs/dev/ba-spec-{pipeline.timestamp_suffix}.md
    Write your verification report to: docs/dev/qa-report-{pipeline.timestamp_suffix}.json
    Project root: <worktree_path from state file if set, otherwise project root>

    IMPORTANT: All file reads and verification must use the project root above.
    Verify that changes were made inside the worktree, not the main project.
  "
```

**Wait for ALL QA subagents to complete** before proceeding.

**Fallback**: If the Agent tool cannot handle N simultaneous calls, batch them in groups of 4.

### Step 9: Process All QA Results

**For each active pipeline[i]**, read QA report and classify:

Read QA report: `docs/dev/qa-report-{pipeline.timestamp_suffix}.json`

**Per-pipeline decision tree**:

```
IF qa.status == "pass":
  → Mark pipeline phase = "done", status = "fixed"

ELIF qa.status == "warning":
  → Autonomous decision: if only minor/cosmetic issues, mark phase = "done", status = "fixed"
  → If major issues: mark phase = "qa_failed" (will enter iteration in Step 10)

ELIF qa.status == "fail":
  → Mark pipeline phase = "qa_failed" (will enter iteration in Step 10)
```

**Tally results**:
```
Pipelines passed: {count} of {total}
Pipelines needing iteration: {count}
Pipelines skipped: {count}
```

**If all pipelines are done (no qa_failed)**: Skip Step 10, proceed to Step 11.

### Step 10: Per-Pipeline Iteration Loops (if QA fails)

**Only runs for pipelines with `phase == "qa_failed"`**. Pipelines that passed QA are already finalized.

**Per-pipeline iteration guard**: Maximum 5 iterations per pipeline to prevent infinite loops.

**Sort failed pipelines by severity before iterating** (critical first, cosmetic last):

```
# Sort qa_failed pipelines by severity to prioritize critical fixes
severity_order = {"critical": 0, "major": 1, "minor": 2, "cosmetic": 3}
qa_failed_pipelines = sorted(
    [p for p in pipelines if p["phase"] == "qa_failed"],
    key=lambda p: (severity_order.get(p["severity"], 3), -len(p.get("agents_flagged", [])))
)

For each failed pipeline[i] in qa_failed_pipelines:

WHILE pipeline[i].iteration < 5 AND pipeline[i].phase == "qa_failed":
    pipeline[i].iteration += 1

    # Refine context
    Extract refined context from QA report:
    jq '.qa.refined_context' docs/dev/qa-report-{pipeline.timestamp_suffix}.json \
      > docs/dev/refined-context-{pipeline.timestamp_suffix}.json

    Merge with original context:
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
      docs/dev/context-{pipeline.timestamp_suffix}.json \
      docs/dev/qa-report-{pipeline.timestamp_suffix}.json \
      docs/dev/refined-context-{pipeline.timestamp_suffix}.json \
      > docs/dev/context-iter{pipeline.iteration}-{pipeline.timestamp_suffix}.json

    # Re-run Dev for this pipeline only
    Agent(subagent_type: "dev") with iteration context

    # Re-run QA for this pipeline only
    Agent(subagent_type: "qa") with new dev report

    IF qa.status == "pass" or (qa.status == "warning" and minor only):
        pipeline[i].phase = "done"
        pipeline[i].status = "fixed"
        BREAK
```

**If iteration reaches 5 without passing**:
```
Quality verification failed after 5 iterations for pipeline {i}: {description}.
Marking as skipped.
```
Mark pipeline: `phase = "done"`, `status = "skipped"`.
Add to `failed_attempts` in state file.

### Step 11: Update Settings.json Permissions (Aggregated)

**CRITICAL**: Aggregate permissions from ALL pipelines before updating.

**Collect permissions from all pipeline QA reports**:

```python
all_permissions = []
for pipeline in current_issues:
    if pipeline['status'] == 'fixed':
        qa_report = load(f"docs/dev/qa-report-{pipeline['timestamp_suffix']}.json")
        perms = qa_report.get('qa', {}).get('permissions_verification', {}).get('validated_permissions', [])
        all_permissions.extend(perms)

# Deduplicate by pattern
unique_permissions = deduplicate(all_permissions, key='pattern')
```

**Update settings.json** with deduplicated permissions:

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
# Use jq to add permission (for each unique permission)
jq '.permissions.allow += ["Bash(scripts/new-script.sh:*)"]' .claude/settings.json > .claude/settings.json.tmp
mv .claude/settings.json.tmp .claude/settings.json
```

**Permission update rules**:

1. **Scripts created** -> Add to "allow":
   - `"Bash(scripts/<script-name>.sh:*)"`
   - `"Bash(~/.claude/scripts/<script-name>.sh:*)"`

2. **Python scripts** -> Add to "allow":
   - `"Bash(source ~/.claude/venv/bin/activate && python3 ~/.claude/scripts/todo/<script>.py:*)"`

3. **Hooks created** -> Add to "allow":
   - `"Bash(~/.claude/hooks/<hook-name>.sh:*)"`

4. **Commands created** -> Already allowed via "SlashCommand"

**Validation**:
- Check JSON syntax after modification
- Verify no duplicate permissions
- Confirm permissions follow patterns

**Error handling**:
- If settings.json has syntax error -> Log and skip (do not ask user -- autonomous mode)
- If permission already exists -> Skip, don't duplicate

### Step 12: Log All Cycle Results and Check Time

**Update state**: Set `current_phase` to `"logging"`.

**Aggregate results from ALL pipelines and update the state file**:

```python
state['cycle_count'] += 1
fixed_count = 0
skipped_count = 0

for pipeline in state['current_issues']:
    if pipeline['status'] == 'fixed':
        fixed_count += 1
    elif pipeline['status'] == 'skipped':
        skipped_count += 1

    state['addressed_issues'].append(pipeline['description'])
    state['cycle_log'].append({
        'cycle': state['cycle_count'],
        'pipeline_index': pipeline['index'],
        'issue': pipeline['description'],
        'location': pipeline['location'],
        'severity': pipeline['severity'],
        'status': pipeline['status'],
        'iterations': pipeline['iteration'],
        'timestamp': now_iso
    })

state['issues_fixed'] += fixed_count
state['issues_skipped'] += skipped_count
state['current_issues'] = []  # Clear pipeline array for next cycle
```

Write atomically (tmp + rename).

**Append to running log** at `docs/dev/overnight-log-<date>.md`:

```markdown
### Cycle <N>: {total_pipelines} pipelines ({fixed_count} fixed, {skipped_count} skipped)

| Pipeline | Issue | Status | Iterations |
|----------|-------|--------|------------|
| 0 | {description} | Fixed | 1 |
| 1 | {description} | Skipped | 5 |
| ... | ... | ... | ... |

**Time**: <timestamp>
```

**TIME CHECK**:

```python
now = datetime.now()
end_time = datetime.fromisoformat(state['end_time'])
if now >= end_time:
    # Proceed to Step 13 -- session is ending
else:
    remaining = end_time - now
    print(f"Time remaining: {remaining} -- marking Step 13 complete to trigger loop")
```

If time expired: proceed to Step 13 for final summary.
If time remains: mark Step 13 as completed via TodoWrite. The posttool-overnight-loop.py hook will detect all 13 steps completed, reset todos to pending, and inject continuation instructions.

### Step 13: Generate Summary Report or Loop

**If time remains** (normal loop case):
Simply mark this step as completed via TodoWrite. The PostToolUse:TodoWrite hook (`posttool-overnight-loop.py`) will:
1. Detect all 13 steps are completed
2. Check overnight-state.json for future end_time
3. Reset all todos to pending
4. Print loop continuation instructions
5. You then resume from Step 2 (worktree already exists)

**If time expired** (session ending):
**Update state**: Set `current_phase` to `"completed"`.

**Read the full state file** to get all cycle data.

**Generate summary report** at `docs/dev/overnight-summary-<date>.md`:

```markdown
# Overnight Development Summary

**Session**: <session_id>
**Start time**: <start_time>
**End time**: <end_time> (planned) / <actual_end> (actual)
**Duration**: <hours>h <minutes>m
**Cycles completed**: <cycle_count>
**Worktree**: <worktree_branch>

## Statistics

| Metric | Count |
|--------|-------|
| Issues found | <issues_found> |
| Issues fixed | <issues_fixed> |
| Issues skipped | <issues_skipped> |
| Fix rate | <percentage>% |

## Cycle Details

### Cycle 1: <issue>
- **Status**: Fixed / Skipped
- **Location**: <file>
- **Changes**: <summary>
- **Iterations**: <N>

## Skipped Issues (need manual attention)

<List of issues that failed 3+ times with error context>

## Files Generated

- Context files: `docs/dev/context-*.json`
- Dev reports: `docs/dev/dev-report-overnight-*.json`
- QA reports: `docs/dev/qa-report-overnight-*.json`
- Running log: `docs/dev/overnight-log-<date>.md`

## Recommendations

<Patterns noticed during exploration that need human decision-making>
```

**Worktree**: Keep the worktree for user to review. Mention:
```
The worktree at <worktree_path> contains all changes.
Review with: git diff master...<worktree_branch>
To merge: git merge <worktree_branch>
To discard: call ExitWorktree with action "remove"
```

**State file cleanup**: Automatic. The `pretool-overnight-hook-guard` auto-cleans expired state files on next hook invocation. No manual deletion needed.

**Announce completion**:

```
Overnight development session complete.

Duration: <hours>h <minutes>m
Cycles: <cycle_count>
Fixed: <issues_fixed> | Skipped: <issues_skipped>

Summary: docs/dev/overnight-summary-<date>.md
Log: docs/dev/overnight-log-<date>.md
Worktree: <worktree_branch> (preserved for review)

The time-lock has been released. The session can now end normally.
```

---

## State File Management

The state file serves three purposes:
1. **Persistence**: Track progress across cycles and loop resets
2. **Time-lock**: The Stop hook reads this file to determine if termination is allowed
3. **Continuation**: The UserPromptSubmit hook reads this to inject continuation context

**Always write atomically**: Write to `.tmp` file first, then `os.rename()`.

**State file location**: `<project_dir>/.claude/overnight-state-<session_id>.json`

**Multi-session support**: Each overnight session uses its own state file keyed by `session_id` (from `$CLAUDE_SESSION_ID` env var or a generated UUID). This allows multiple concurrent overnight sessions on the same project. The Stop hook scans for ALL `overnight-state-*.json` files and blocks termination if ANY has a future end_time.

**Worktree naming**: Each session creates `overnight-<YYYYMMDD>-<session_id_short>` (first 8 chars of session_id) to avoid conflicts between concurrent sessions.

**Schema (v6)**:
```json
{
  "session_id": "string (from $CLAUDE_SESSION_ID or UUID)",
  "end_time": "ISO-8601 datetime",
  "start_time": "ISO-8601 datetime",
  "focus": "string (discovery hint from user, or empty)",
  "cycle_count": 0,
  "issues_found": 0,
  "issues_fixed": 0,
  "issues_skipped": 0,
  "current_phase": "initializing|exploring|pipeline_creation|analyzing|implementing|verifying|iterating|logging|completed",
  "current_issues": [
    {
      "index": 0,
      "description": "issue description",
      "location": "file:line",
      "severity": "critical|major|minor|cosmetic",
      "category": "category string",
      "agents_flagged": ["product-owner", "architect"],
      "phase": "pending|ba_complete|dev_complete|qa_failed|done",
      "iteration": 0,
      "status": "active|fixed|skipped",
      "timestamp_suffix": "YYYYMMDD-HHMMSS-0"
    }
  ],
  "failed_attempts": {"issue_desc": 2},
  "addressed_issues": ["issue_desc_1", "issue_desc_2"],
  "cycle_log": [
    {
      "cycle": 1,
      "pipeline_index": 0,
      "issue": "description",
      "location": "file:line",
      "severity": "critical|major|minor|cosmetic",
      "status": "fixed|skipped",
      "iterations": 1,
      "timestamp": "ISO-8601"
    }
  ],
  "consecutive_clean_sweeps": 0,
  "worktree_path": "/path/to/worktree or null",
  "worktree_branch": "overnight-YYYYMMDD-<session_id_short> or null",
  "schema_version": 6
}
```

**Migration from v5**: If reading a v5 state file, convert `current_issue` (string) to `current_issues` (array with single entry if non-null, empty array if null). Remove `current_issue` and `current_issue_iteration` fields.

---

## Edge Cases

### No issues found
After 2 consecutive clean sweeps: treat as "codebase is clean", generate summary and delete state file.

### Unfixable issue (5 failed iterations per pipeline)
Mark pipeline as skipped, add to addressed_issues. Other pipelines in the same cycle are unaffected.

### Very short time remaining (< 5 minutes)
In Step 3 pipeline creation, skip issues with medium/large effort. If zero small-effort issues remain, go directly to summary.

### State file corruption
Create a fresh state file preserving end_time from $ARGUMENTS. Continue operation.

### Worktree creation failure
Log warning, continue on current branch. All changes still tracked in state file.

### Missing worktree in continuation mode
If state file has `worktree_path=null` on continuation, attempt to create worktree.

---

## Integration with Hooks

- **prompt-workflow.py** (UserPromptSubmit): Creates overnight-state-<session_id>.json on /dev-overnight detection; injects continuation context with worktree guard
- **posttool-overnight-loop.py** (PostToolUse:TodoWrite): Detects all-completed state, resets todos for new cycle if end_time is future
- **pretool-overnight-hook-guard.py** (PreToolUse): Blocks Write/Edit/Bash targeting .claude/hooks/ during overnight sessions
- **pretool-workflow-gate.py** (PreToolUse): Gates tools until TodoWrite is called
- **posttool-todo-count.py** (PostToolUse:TodoWrite): Enforces step count
- **posttool-todo-sequence.py** (PostToolUse:TodoWrite): Enforces step ordering
- **stop-workflow-enforce.py** (Stop): Blocks stop if workflow steps dropped
- **stop-overnight-timelock.py** (Stop): Blocks stop until end_time reached
- **posttool-git-checkpoint.sh** (PostToolUse:Write|Edit): Auto-commits changes

### Loop Mechanism (v3)
- When all 13 todo steps are marked completed via TodoWrite, the posttool-overnight-loop.py hook fires
- It checks overnight-state.json: if end_time is in the future, it resets all todos to pending and injects loop continuation instructions
- The agent then resumes from Step 2 (exploration) since worktree already exists
- This provides natural context boundaries at each cycle without requiring external cron triggers

---

## Quick Reference: The Loop

After completing Steps 2-13, the loop is automatic:

```
TodoWrite marks Step 13 as completed
  |
posttool-overnight-loop.py fires
  |
IF end_time > now:
    Reset all todos to pending (except Step 1 which stays completed)
    Increment cycle_count
    Print "OVERNIGHT LOOP: Starting cycle N+1"
    Agent resumes from Step 2
  |
IF end_time <= now:
    No reset (allow natural completion)
    Agent proceeds with summary generation
```

The loop MUST continue until end-time. Only break for:
1. End-time reached
2. Two consecutive clean sweeps
3. Unrecoverable error

---

## JSON Storage Policy

**All JSON files stored in**: `docs/dev/`

**File naming convention**:
- Context: `context-<timestamp>-<pipeline_index>.json` or `context-iter<N>-<timestamp>-<pipeline_index>.json`
- BA spec: `ba-spec-<timestamp>-<pipeline_index>.md`
- Dev report: `dev-report-<timestamp>-<pipeline_index>.json`
- QA report: `qa-report-<timestamp>-<pipeline_index>.json`
- Refined context: `refined-context-<timestamp>-<pipeline_index>.json`
- Overnight reports: `docs/dev/overnight/<session_id>/product-owner-report.json`, etc.
- Running log: `overnight-log-<session_id>.md`
- Summary: `overnight-summary-<session_id>.md`

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

**Specialist subagents discover** (Step 2, parallel):
- **product-owner** (see `agents/product-owner.md`): Logical inconsistencies, feature gaps, broken user flows, missing features, business logic bugs
- **architect** (see `agents/architect.md`): Structural issues, technical debt, optimization opportunities, dependency problems, pattern inconsistencies
- **user** (see `agents/user.md`): UX friction, broken flows, confusing behavior, workflow gaps, real-world usage issues
- **ui-specialist** (see `agents/ui-specialist.md`): Styling consistency, responsive design, accessibility, visual bugs, component quality, design system compliance

**BA subagent analyzes** (see `agents/ba.md`):
- Requirement decomposition from self-discovered issues
- Git root cause analysis
- MoSCoW requirements and BDD acceptance criteria
- Context JSON generation for dev subagent

**Dev subagent implements** (see `agents/dev.md`):
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
- Issues fully explored by 4 specialist subagents before fixing
- ALL issues get parallel pipelines, ordered by severity (critical first) and impact scope
- Comprehensive context via BA (one per pipeline)
- Iterative quality improvement (max 5 iterations per pipeline, independent)
- Proper JSON storage with pipeline-scoped naming (timestamp-index suffix)
- Cycle deduplication via state file
- Multi-session isolation via session_id-keyed state files

---

## Comparison: /dev vs /dev-overnight

| Aspect | /dev | /dev-overnight |
|--------|------|----------------|
| Input | User provides requirement | Agent discovers issues via 4 specialist subagents |
| BA phase | Full BA + clarification loop (max 3 rounds) | BA with clarification skipped (round=3) |
| BA validation | Step 4 | Step 5 |
| Dev validation | Step 6 | Step 7 |
| QA processing | Step 8 decision tree | Step 9 autonomous decision |
| Iteration loop | Step 10 (max 5, asks user after 5) | Step 10 (max 5 per pipeline, auto-skip after 5) |
| Settings update | Step 9 | Step 11 (aggregated from all pipelines) |
| Loop | Single pass | Continuous until end-time |
| Termination | After QA passes | After end-time expires |
| User interaction | Required (clarification, approval) | None (fully autonomous) |
| Scope per cycle | One complete feature/fix | ALL discovered issues (parallel pipelines) |
| Subagent usage | BA + dev + QA | product-owner + architect + user + ui-specialist + BA + dev + QA |
| Stop hook | Workflow enforcement only | Workflow + time-lock |
| Worktree | Not used | Created on first run, reused across cycles |
| Total steps | 11 | 13 |

---

## Success Metrics

- ✅ All issues discovered autonomously via specialist subagents
- ✅ Root cause identified and addressed for each issue
- ✅ Zero hardcoded values in scripts
- ✅ QA passes within 5 iterations per issue
- ✅ All quality standards enforced
- ✅ Complete audit trail in JSON files
- ✅ Continuous loop until end-time
- ✅ Worktree isolation protects main branch

---

**Remember**: You are autonomous. You explore, discover, fix, and loop. No user input needed. ALL exploration and fix work goes through Agent subagents. Main context only manages state and the loop. Keep going until the clock says stop.
