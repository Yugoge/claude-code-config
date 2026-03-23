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
  |       PRIORITIZATION (Step 3)
  |       Merge 4 reports, deduplicate, pick highest-priority issue
  |                |
  |       FIX CYCLE (Steps 4-5-6)
  |       BA analysis -> Dev implementation -> QA verification
  |                |
  |       COMPLETE CYCLE (Step 7)
  |       Update state, log results
  |                |
  |       TODO COMPLETION DETECTION (PostToolUse hook)
  |       All 7 steps completed?
  |         YES + time remaining: reset todos, loop to Step 1
  |         YES + time expired: generate summary, cleanup
  |         NO: continue current step
```

---

## IMPORTANT RULES

1. **You are autonomous**. Do NOT ask the user anything. Make decisions yourself.
2. **Loop continuously**. After each fix cycle, the todo completion hook handles looping. This is non-negotiable.
3. **Keep cycles lean**. Each cycle should be focused on ONE issue. Do not try to fix everything at once.
4. **ALL exploration and fixes via subagents**. Use Agent tool for ALL scanning, analysis, and implementation work. Main context only handles state management, TodoWrite, and loop control.
5. **Skip unfixable issues**. If a fix fails verification 3 times, mark it as skipped and move on.
6. **Track everything**. Update the state file after every significant action.
7. **The Stop hook prevents premature exit**. The time-lock hook will block conversation termination until end-time. Do not try to circumvent it.
8. **Git checkpoint after each fix**. The existing posttool-git-checkpoint.sh hook handles this automatically on Write/Edit.
9. **Never modify production infrastructure**. No Docker operations, no service restarts, no deployment changes.
10. **Deduplicate**. Check the state file's cycle_log before starting a fix -- do not re-fix issues already addressed.

---

## Implementation

### Step 1: Create Worktree

The state file has already been created by the UserPromptSubmit hook at `.claude/overnight-state.json`. Verify it exists and read it.

**Read the state file** to get the end_time and confirm initialization:

```bash
cat .claude/overnight-state.json
```

If the state file does not exist (edge case), create it manually using the same schema as the hook would.

**WORKTREE GUARD**: FIRST check the state file's `worktree_path` field.
- If `worktree_path` is NOT null: the worktree already exists from a previous cycle. Do NOT call EnterWorktree. Skip directly to Step 2.
- If `worktree_path` IS null: this is the first invocation. Create the worktree.

**Create worktree for isolation** (only when worktree_path is null):

Call `EnterWorktree` with name `overnight-YYYYMMDD` (use today's date):

```
Call EnterWorktree with name: "overnight-<YYYYMMDD>"
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
   - `selecting` -> Step 3 (Select)
   - `fixing` -> Step 4 (Fix)
   - `verifying` -> Step 5 (Verify)
   - `logging` -> Step 6 (Log)
4. The hook has already injected the command specification and state summary into this prompt

**Do NOT**:
- Create the state file (it already exists)
- Call EnterWorktree (the worktree already exists -- the continuation context explicitly tells you this)

---

### Step 2: Explore Codebase for Issues

**Update state**: Set `current_phase` to `"exploring"`.

**CRITICAL: Launch 4 specialist subagents in parallel using Agent tool.** Do not scan the codebase directly from the main context. Do NOT read project files yourself.

Read the state file's `addressed_issues` array first, then launch all 4 Agent calls in a SINGLE response (parallel execution):

```
Launch 4 Agent tool calls simultaneously:

1. Agent(agent: "product-owner", prompt: "
   Project path: <project_path>
   Already addressed: <addressed_issues from state>
   Output report to: docs/dev/overnight/product-owner-report.json
   Explore this project for product-level issues: logical inconsistencies,
   feature gaps, broken user flows, missing features, business logic bugs.")

2. Agent(agent: "architect", prompt: "
   Project path: <project_path>
   Already addressed: <addressed_issues from state>
   Output report to: docs/dev/overnight/architect-report.json
   Review architecture for: structural issues, technical debt, optimization
   opportunities, dependency problems, pattern inconsistencies.")

3. Agent(agent: "user", prompt: "
   Project path: <project_path>
   Already addressed: <addressed_issues from state>
   Output report to: docs/dev/overnight/user-report.json
   Simulate end-user usage: test real scenarios, find broken flows,
   identify UX friction, confusing behavior, workflow gaps.")

4. Agent(agent: "ui-specialist", prompt: "
   Project path: <project_path>
   Already addressed: <addressed_issues from state>
   Output report to: docs/dev/overnight/ui-specialist-report.json
   Review UI/UX: styling consistency, responsive design, accessibility,
   visual bugs, component quality, design system compliance.")
```

**After all 4 return**, validate reports:

```bash
~/.claude/scripts/check-overnight-reports.sh docs/dev/overnight
```

**If zero issues found across all 4 reports**:
- Log a "clean sweep" entry
- After 2 consecutive clean sweeps: generate summary and allow termination

### Step 3: Select and Prioritize Next Issue

**Update state**: Set `current_phase` to `"selecting"`.

**Read all 4 JSON reports** from `docs/dev/overnight/`:
- `product-owner-report.json`
- `architect-report.json`
- `user-report.json`
- `ui-specialist-report.json`

**Merge into single issue list**:
1. Combine all issues from all 4 reports
2. Deduplicate: same file+description from multiple agents counts as one (but note which agents flagged it)
3. Filter out any issue already in `addressed_issues` from state file

**Prioritization rules** (in order):
1. Critical severity first
2. Then major severity
3. Among same severity, prefer small effort (quick wins)
4. Among same severity and effort, prefer issues flagged by multiple agents
5. Skip any issue that has failed 3 times (check `failed_attempts`)

**Select ONE issue**. Update state file:
- Set `current_issue` to the issue description
- Increment `issues_found` counter

### Step 4: Analyze Issue (BA)

**Update state**: Set `current_phase` to `"fixing"`.

**Delegate to BA subagent** for lightweight analysis (no clarification needed since issue is self-discovered):

```
Agent(agent: "ba", prompt: "
  Requirement: '<issue description>'
  Clarification round: 3
  Previous answers: null
  Codebase hints: <file paths from the issue>
  Timestamp: <current timestamp>

  This is a self-discovered issue from overnight exploration.
  No clarification is needed -- proceed directly to analysis.
  Generate context JSON and BA spec for the dev subagent.")
```

### Step 5: Implement Fix (Dev)

**Update state**: Set `current_phase` to `"implementing"`.

**Delegate to Dev subagent**:

```
Agent(agent: "dev", prompt: "
  Context file: <path to context JSON from BA>
  BA spec file: <path to BA spec from BA>
  Write your implementation report to: docs/dev/dev-report-overnight-<cycle>.json")
```

**Retry logic**:
- If fix fails, retry up to 3 times
- Track attempts in state file's `failed_attempts` dict
- After 3 failures, mark as skipped

### Step 6: Verify Fix (QA) and Log Results

**Update state**: Set `current_phase` to `"verifying"`.

**Delegate to QA subagent**:

```
Agent(agent: "qa", prompt: "
  Context file: <path to context JSON from BA>
  Dev report: <path to dev report>
  BA spec: <path to BA spec>")
```

**Log cycle results** -- update the state file:

```python
state['cycle_count'] += 1
state['issues_fixed' if succeeded else 'issues_skipped'] += 1
state['addressed_issues'].append(issue_description)
state['cycle_log'].append({
    'cycle': state['cycle_count'],
    'issue': issue_description,
    'location': file_path,
    'severity': severity,
    'status': 'fixed' if succeeded else 'skipped',
    'changes': list_of_changes,
    'timestamp': now_iso
})
state['current_issue'] = None
```

Write atomically (tmp + rename).

**Append to running log** at `docs/dev/overnight-log-<date>.md`.

**TIME CHECK**:

```python
now = datetime.now()
end_time = datetime.fromisoformat(state['end_time'])
if now >= end_time:
    # Proceed to Step 7 -- session is ending
else:
    remaining = end_time - now
    print(f"Time remaining: {remaining} -- marking Step 7 complete to trigger loop")
```

If time expired: proceed to Step 7 for final summary.
If time remains: mark Step 7 as completed via TodoWrite. The posttool-overnight-loop.py hook will detect all 7 steps completed, reset todos to pending, and inject continuation instructions.

### Step 7: Generate Summary Report (or trigger loop)

**If time remains** (normal loop case):
Simply mark this step as completed via TodoWrite. The PostToolUse:TodoWrite hook (`posttool-overnight-loop.py`) will:
1. Detect all 7 steps are completed
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

## Skipped Issues (need manual attention)

<List of issues that failed 3 times with error context>

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

**Delete state file** to release time-lock:

```bash
rm -f .claude/overnight-state.json
```

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

The state file `.claude/overnight-state.json` serves three purposes:
1. **Persistence**: Track progress across cycles and loop resets
2. **Time-lock**: The Stop hook reads this file to determine if termination is allowed
3. **Continuation**: The UserPromptSubmit hook reads this to inject continuation context

**Always write atomically**: Write to `.tmp` file first, then `os.rename()`.

**State file location**: `<project_dir>/.claude/overnight-state.json`.

**Schema (v3)**:
```json
{
  "session_id": "string",
  "end_time": "ISO-8601 datetime",
  "start_time": "ISO-8601 datetime",
  "cycle_count": 0,
  "issues_found": 0,
  "issues_fixed": 0,
  "issues_skipped": 0,
  "current_phase": "initializing|exploring|selecting|fixing|implementing|verifying|logging|completed",
  "current_issue": "string or null",
  "failed_attempts": {"issue_desc": 2},
  "addressed_issues": ["issue_desc_1", "issue_desc_2"],
  "cycle_log": [
    {
      "cycle": 1,
      "issue": "description",
      "location": "file:line",
      "severity": "critical|major|minor|cosmetic",
      "status": "fixed|skipped",
      "changes": ["change 1", "change 2"],
      "timestamp": "ISO-8601"
    }
  ],
  "worktree_path": "/path/to/worktree or null",
  "worktree_branch": "overnight-YYYYMMDD or null",
  "schema_version": 3
}
```

---

## Edge Cases

### No issues found
After 2 consecutive clean sweeps: treat as "codebase is clean", generate summary and delete state file.

### Unfixable issue (3 failed attempts)
Mark as skipped, add to addressed_issues, continue to next issue.

### Very short time remaining (< 5 minutes)
Skip medium/large effort issues, only attempt small fixes or go to summary.

### State file corruption
Create a fresh state file preserving end_time from $ARGUMENTS. Continue operation.

### Worktree creation failure
Log warning, continue on current branch. All changes still tracked in state file.

### Missing worktree in continuation mode
If state file has `worktree_path=null` on continuation, attempt to create worktree.

---

## Integration with Hooks

- **prompt-workflow.py** (UserPromptSubmit): Creates overnight-state.json on /dev-overnight detection; injects continuation context with worktree guard
- **posttool-overnight-loop.py** (PostToolUse:TodoWrite): Detects all-completed state, resets todos for new cycle if end_time is future
- **pretool-overnight-hook-guard.py** (PreToolUse): Blocks Write/Edit/Bash targeting .claude/hooks/ during overnight sessions
- **pretool-workflow-gate.py** (PreToolUse): Gates tools until TodoWrite is called
- **posttool-todo-count.py** (PostToolUse:TodoWrite): Enforces step count
- **posttool-todo-sequence.py** (PostToolUse:TodoWrite): Enforces step ordering
- **stop-workflow-enforce.py** (Stop): Blocks stop if workflow steps dropped
- **stop-overnight-timelock.py** (Stop): Blocks stop until end_time reached
- **posttool-git-checkpoint.sh** (PostToolUse:Write|Edit): Auto-commits changes

### Loop Mechanism (v3)
- When all 7 todo steps are marked completed via TodoWrite, the posttool-overnight-loop.py hook fires
- It checks overnight-state.json: if end_time is in the future, it resets all todos to pending and injects loop continuation instructions
- The agent then resumes from Step 2 (exploration) since worktree already exists
- This provides natural context boundaries at each cycle without requiring external cron triggers

---

## Quick Reference: The Loop

After completing Steps 2-7, the loop is automatic:

```
TodoWrite marks Step 7 as completed
  |
posttool-overnight-loop.py fires
  |
IF end_time > now:
    Reset all todos to pending
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

**Remember**: You are autonomous. You explore, discover, fix, and loop. No user input needed. ALL exploration and fix work goes through Agent subagents. Main context only manages state and the loop. Keep going until the clock says stop.
