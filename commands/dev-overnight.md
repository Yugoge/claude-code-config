---
description: Autonomous overnight development loop - continuously explores codebase, finds issues, fixes them, and repeats until end-time
---

> Code-writing tasks (.svg/.css/.html/.js/.ts/.py/...) go to `dev`. Specialists, BA, and QA produce .md/.json only.

**CRITICAL**: Use TodoWrite to track workflow phases. Mark in_progress before each step, completed immediately after.

# Dev-Overnight: Autonomous Continuous Development

**Philosophy**: Explore autonomously, discover real issues, fix them systematically, loop until time expires, then summarize everything.

This command runs an unattended development loop. You are fully autonomous -- no user input is needed or expected. You discover issues yourself by scanning the codebase, fix each one through a simplified dev cycle, and keep going until the specified end time.

**Quick status utility**: Use `bash ~/.claude/scripts/overnight-status.sh` for instant session status (zero LLM cost). Use this instead of reading/parsing the state JSON manually. Optionally pass session_id as argument.

---

## Overview

```
Hook creates state file + worktree + view detection (automatic)
  |
Step 1: Read state file + enter worktree (first run only)
  |
  +---> EXPLORATION PHASE (Step 2)
  |       Step 2a: PM-Plan subagent (builds test plan with priorities + recommended_specialists)
  |       Main agent reads test plan, extracts priority context + recommended specialists
  |       Step 2b: PM-recommended specialist subagents scan SERIALLY, one at a time (with priority context)
  |       Step 2c: PM-Triage subagent (reads specialist reports, writes triage)
  |                |
  |       PIPELINE CREATION (Step 3)
  |       Main agent reads PM triage report, creates pipelines in triage order
  |                |
  |       PARALLEL BA PHASE (Step 4-5)
  |         Launch ALL N BA subagents in parallel → validate all outputs
  |                |
  |       BA-QA VALIDATION (Step 5a)
  |         Launch ALL N QA-validates-BA subagents in parallel
  |                |
  |       BA-QA ITERATION (Step 5b)
  |         Per-pipeline BA-QA iteration loop (max 3) if QA rejects
  |                |
  |       PARALLEL DEV PHASE (Step 6-7)
  |         Launch ALL N Dev subagents in parallel → validate all outputs
  |                |
  |       PARALLEL QA PHASE (Step 8-9)
  |         Launch ALL N QA subagents in parallel → process all results
  |                |
  |       ITERATION LOOPS (Step 11)
  |         Per-pipeline Dev→QA re-runs for failures (max 5 each)
  |                |
  |       PERMISSIONS (Step 12)
  |         Aggregate permissions from all N pipelines, apply once
  |                |
  |       LOG & TIME CHECK (Step 13)
  |       Log all N pipeline results to cycle_log file, check end-time
  |                |
  |       PM RETROSPECTIVE (Step 14)
  |       PM reads all results, writes retro-report, hands off to next cycle
  |                |
  |       SUMMARY OR LOOP (Step 15)
  |       Time remaining? → reset todos, loop to Step 2
  |       Time expired? → generate summary, cleanup
  |                |
  |       TODO COMPLETION DETECTION (PostToolUse hook)
  |       All 16 steps completed?
  |         YES + time remaining: reset todos, loop to Step 2
  |         YES + time expired: allow natural completion
  |         NO: continue current step
```

---

## IMPORTANT RULES

1. **You are autonomous**. Do NOT ask the user anything. Make decisions yourself.
2. **Loop continuously**. After each fix cycle, the todo completion hook handles looping. This is non-negotiable.
3. **Keep cycles comprehensive and priority-driven**. PM triage determines pipeline ordering -- the main agent follows PM's authority. In Focus Mode (Tier 1 blockers exist), only blocker pipelines are created. In Normal Mode, all issues get pipelines ordered by tier: Tier 1 (blockers) first, then Tier 2 (major), then Tier 3 (minor/cosmetic). Within each tier, issues flagged by more agents rank higher.
4. **ALL exploration and fixes via subagents**. Use Agent tool for ALL scanning, analysis, and implementation work. Main context only handles TodoWrite and loop control.
5. **Skip unfixable issues**. If a fix fails verification 3 times, mark it as skipped and move on.
6. **Track everything**. Use TodoWrite to track progress -- the state file is read-only after creation.
7. **The Stop hook prevents premature exit**. The time-lock hook will block conversation termination until end-time. Do not try to circumvent it.
8. **Git checkpoint after each fix**. The existing posttool-git-checkpoint.sh hook handles this automatically on Write/Edit.
9. **QA MUST rebuild and redeploy** to verify fixes in the real environment. `docker compose build` and `docker compose up -d` for the project's own services are REQUIRED for QA verification. Identify services from `docker-compose.yml`. Do NOT touch unrelated services or infrastructure.
10. **Deduplicate**. Check the state file's cycle_log before starting a fix -- do not re-fix issues already addressed.
11. **One issue per subagent, no exceptions**. Each BA subagent analyzes exactly ONE pipeline issue. Each Dev subagent implements exactly ONE pipeline fix. Each QA subagent verifies exactly ONE pipeline fix. The orchestrator launches N parallel subagents for N pipelines -- but each individual subagent handles only its own single pipeline. NEVER bundle multiple pipeline issues into one subagent prompt.

---

## Overnight Incident Lessons (2026-03-28)

**NON-NEGOTIABLE.** Full stories: `docs/incidents-2026-03-28.md`.

### Rule 1: Never weaken checks to "fix" failures
If validation rejects output, fix the upstream code producing the output. Never lower thresholds, swallow exceptions, change error→warning, or skip validation.

### Rule 2: PM only prioritizes — PM never proposes solutions
PM ranks issues by severity and orders pipelines. Solutions are BA's and Dev's job.

### Rule 3: Specialists report symptoms only — no root cause, no fix suggestions
Specialists observe and report. Root cause analysis is exclusively BA's job.

### Rule 4: Always compare with reference implementation BEFORE fixing
When the user says "align with X", every fix must be validated against X's behavior.

### Rule 5: Output quality > no errors
QA passing means HIGH QUALITY output, not just "no exceptions".

### Rule 6: Never make "improvements" the user didn't ask for
If the user didn't report it as broken, don't change it. Don't add features, rename, or fill empty space.

### Rule 7: Global agent files must be project-agnostic
Files in `~/.claude/agents/` and `~/.claude/commands/` apply to ALL projects. No project-specific examples.

---

## Arguments

```
/dev-overnight [end-time] [focus] [--spec path/to/spec.md]
```

**Examples**:
- `/dev-overnight 6:00` — run until 6:00, no focus (explore everything)
- `/dev-overnight 6:00 fix pipeline bugs` — run until 6:00, focus on pipeline bugs
- `/dev-overnight fix hooks` — default 8h, focus on hooks issues
- `/dev-overnight` — default 8h, no focus
- `/dev-overnight 6:00 --spec docs/my-spec.md` — run until 6:00, use user-provided spec
- `/dev-overnight 6:00 fix UI --spec docs/ui-spec.md` — focus + user spec

**`--spec` argument**: If provided, the session operates in **user-spec mode**:
- The spec file is read by PM in PLAN mode (PM acts as supervisor, not full explorer)
- Issues described in the user's spec are automatically Tier 1
- Every subagent (BA, Dev, QA, PM-Retro) receives the spec path and reads it on startup
- PM validates agent output against the user's spec during RETRO

If `--spec` is NOT provided, the session operates in **autonomous mode** (default):
- PM explores the app and discovers issues normally
- After PM TRIAGE creates pipelines, the orchestrator creates spec files from the template at `~/.claude/templates/overnight-spec.md`
- Each pipeline gets its own spec file at `docs/dev/overnight/<session_id>/spec-pipeline-<index>.md`

**Spec mode detection**: Argument parsing and spec mode detection are handled by `create-overnight-state.sh` at session creation. The state file already contains `user_spec_path` and `spec_mode` fields. Read them from the state file in Step 1.

**Detect views folder**: View detection is handled by `create-overnight-state.sh` at session creation. The state file's `view_paths` field contains the manifest.views dict (or null if no views exist). Each subagent receives its per-agent view path alongside the monolith spec path. If `view_paths` is null, views are not available and subagents receive only the monolith path -- legacy specs are fully supported.

**Auto-detect default spec**: Auto-detection of specs in `docs/dev/specs/` is handled by `create-overnight-state.sh` at session creation. If a spec was auto-detected, the state file will have `spec_mode: "user-provided"` and `user_spec_path` populated. The session announces this in Step 1 when reading the state file.

The `focus` string is stored in the state file and passed to all 4 specialist subagents as a discovery hint. It helps specialists focus their scans but does not affect pipeline creation -- all discovered issues get pipelines regardless of focus match. Additionally, in Step 3a, the orchestrator converts the focus into quantitative QA verification criteria that are passed to QA subagents in Step 9 as mandatory pass/fail checks.

---

## Implementation

### Step 1: Read State File and Enter Worktree

The state file has already been created by the UserPromptSubmit hook at `.claude/overnight-state-<session_id>.json`, including `worktree_path`, `worktree_branch`, `view_paths`, `user_spec_path`, `spec_mode`, and `current_phase: "exploring"`. Find and read it:

```bash
ls .claude/overnight-state-*.json
```

**Read the state file** to get the end_time, session_id, worktree_path, spec_mode, user_spec_path, view_paths, and confirm initialization. If multiple state files exist, use the one matching the current session.

If no state file exists (edge case), create it manually using the v4 schema with a generated session_id.

**WORKTREE GUARD**: Check the state file's `worktree_path` field.
- If `worktree_path` is NOT null: `cd` into the worktree path.
- If `worktree_path` IS null (edge case: worktree creation failed during hook): log a warning and continue on the current branch.

**Spec announcement**: If `spec_mode` is `"user-provided"` and `user_spec_path` is set, announce:
```
Spec mode: user-provided
Spec path: <user_spec_path>
```
If `user_spec_path` was auto-detected (not passed via `--spec`), also announce:
```
(Auto-detected by session creation hook. Pass --spec <other-path> to override.)
```

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

**Initialize dev-registry for hard subagent enforcement** (MANDATORY — do this before ANY Agent launch):

The hook `pretool-subagent-code-block.py` blocks non-`dev` subagents from writing code files, but it needs the Claude-internal subagent UUID to be registered against an `agent_type`. Root cause of the /dev gap (see commit `e086ccb`): /dev-overnight sessions produce no `.claude/specs/` cp-state files, so the hook falls open and every subagent can write code. The fix is an orchestrator-provided sentinel file that each subagent reads as its FIRST ACTION; `pretool-cp-checkin.py` then writes the UUID→agent_type mapping into `.claude/dev-registry/agent-index.json`.

Reuse the overnight `session_id` from the state file (do NOT invent a new one — the same value is reused across cycles and continuations). Create sentinel files for every agent type this orchestrator can launch, including overnight-only specialists:

```bash
DEV_SESSION_ID="$session_id"  # from overnight state file
REGISTRY_DIR="$CLAUDE_PROJECT_DIR/.claude/dev-registry/$DEV_SESSION_ID"
mkdir -p "$REGISTRY_DIR"
for agent in \
    ba qa dev pm architect product-owner ui-specialist user \
    cleaner rule-inspector style-inspector prompt-inspector \
    cleanliness-inspector git-edge-case-analyst \
    test-executor test-validator; do
  printf '{"agent_type": "%s", "session_id": "%s"}\n' "$agent" "$DEV_SESSION_ID" \
    > "$REGISTRY_DIR/$agent.json"
done
```

Every Agent launch prompt in this orchestrator MUST begin with a `FIRST ACTION` line instructing the subagent to `Read $CLAUDE_PROJECT_DIR/.claude/dev-registry/$DEV_SESSION_ID/<agent>.json` before any other tool call. Without that Read, the enforcement hook will fail open for that subagent. In continuation mode (after a hook-induced context reset), re-run the `mkdir -p` + sentinel loop above — it's idempotent, so re-running is safe and guarantees sentinels exist even if a cleanup step removed them.

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
   - `iterating` -> Step 11 (Iteration loops)
   - `logging` -> Step 13 (Log)
   - `retrospective` -> Step 14 (PM Retro)
4. The hook has already injected the command specification and state summary into this prompt

**Do NOT**:
- Create the state file (it already exists)
- Re-create the worktree (it already exists -- just `cd` into `worktree_path` from the state file)

---

## Four Contracts Awareness (Orchestrator Role)

The BA subagent enforces four domain-agnostic contracts (see
`~/.claude/agents/ba.md` §Four Contracts). The orchestrator MUST
complement BA by surfacing context before delegation and verifying
compliance after BA returns. The orchestrator does NOT re-do BA's work —
it prepares inputs and validates outputs.

In overnight mode this is especially load-bearing because many iterations
compound. A single L1-only fix that should have been L3 silently
propagates failure across the whole night.

### Pre-BA: surface retry signals

Before delegating to BA, scan the current iteration's input and repo state
for retry signals:

- **Retry phrasing** in the iteration prompt or triage report: "again",
  "still", "didn't fix", "Nth time", "又", "还是", "没修好"
- **Recent related commits from this overnight run**:
  `git log --oneline --grep="<keyword>" HEAD~30..HEAD`
- **Existing BA specs from earlier iterations**: files matching
  `docs/dev/ba-spec-*.md` with keywords from the current issue
- **Prior-cycle failure reports**: any QA report flagged as failed in an
  earlier iteration that matches the current issue

Pass findings to BA in the delegation prompt under an explicit
`prior_attempt_signals` block:

    prior_attempt_signals:
      retry_phrase: "<matched phrase or null>"
      recent_commits: ["<hash> <subject>", ...]
      existing_specs: ["docs/dev/ba-spec-<ts>.md", ...]
      prior_qa_failures: ["docs/dev/qa-report-<ts>.md", ...]

### Post-BA: verify contract compliance

Before proceeding to dev, verify the BA JSON context contains:

- `evidence.measured.value` populated
- `evidence.expected.source` populated
- `scope_expansion.all_occurrences` non-empty (or explicit not_applicable)
- `reference_source.tier` not `tier_3_tainted` when `copy_allowed: true`
- If Contract D triggered: `prior_attempts.novelty_check.differs_from_all_priors = true`

If any check fails, the orchestrator re-delegates to BA with explicit
feedback. Do NOT proceed to dev with an incomplete spec. Do NOT skip
validation to keep the overnight loop running — a non-compliant spec in
overnight is worse than a stalled iteration.

### BA rejection handling in overnight mode

If BA returns `status: "rejected"` (Contract D novelty-check failure):

- Do NOT retry BA with the same input
- Record the rejection in the cycle retrospective
- Mark this issue as `blocked_same_layer_retry` and SKIP to the next
  issue in the triage queue — do not burn further iterations on a
  redesign-needed problem
- On RETRO, surface the blocked issue for user review next session

### Layer vocabulary (shared with BA)

Layers from shallow to deep:

- **L1 cosmetic**: styling, class names, component swap
- **L2 structural**: layout, component hierarchy
- **L3 data**: coordinates, schema values, regex, constants, SVG paths
- **L4 logic**: conditions, state machines, data flow
- **L5 infrastructure**: build, deploy, environment

The PM subagent MUST record the layer in its per-issue triage output so
the orchestrator can detect "same-layer retry" patterns across iterations.
When dev reports back, verify implementation layer matches BA's spec layer.

### Step 2: Explore Codebase for Issues

**CRITICAL: This step has three sub-steps. Step 2a launches the PM subagent to build a test plan (which includes a `recommended_specialists` field). The main agent then reads the test plan and extracts priority context. Step 2b launches ONLY the PM-recommended specialist subagents with that priority context. Step 2c launches PM again in TRIAGE mode to classify all findings.**

Read the state file's `addressed_issues` array first.

#### Step 2a: Launch PM Subagent

Launch the PM (test plan manager) subagent to build a structured test plan. The PM
uses Playwright to explore the running app first (Phase 0), then reads CLAUDE.md
and the state file, and writes test-plan.json with firsthand browser evidence in
the `pm_experience` section.

```
Use Agent tool with:
- subagent_type: "pm"
- description: "Build test plan from project docs and session history"
- prompt: "
  FIRST ACTION: Read $CLAUDE_PROJECT_DIR/.claude/dev-registry/$DEV_SESSION_ID/pm.json to register with the enforcement system. Do this BEFORE any other tool call.

  You are the PM subagent. Follow agents/pm.md instructions precisely.

  Project path: <worktree_path from state file if set, otherwise project_path>
  State file path: <path to overnight-state-*.json>
  Session ID: <session_id>
  Output test plan to: docs/dev/overnight/<session_id>/test-plan.json

  <If spec_mode == 'user-provided', include:>
  Overnight spec file: <user_spec_path from state file>
  Spec mode: user-provided
  You are in SUPERVISOR mode. Read the user's spec file first. Issues described
  in the spec are pre-validated -- skip full browser exploration for those issues.
  Focus your exploration on discovering ADDITIONAL issues not covered by the spec.
  Set spec_mode: 'user-provided' and spec_path in your test plan output.

  <If spec_mode == 'user-provided' AND view_paths['orchestrator'] is non-null, include:>
  Orchestrator view file: <view_paths['orchestrator']>

  Read the orchestrator view FIRST. It contains the project's Role Mandate,
  Pipeline Workflow, Anti-Patterns, and Hard Rules you must enforce as supervisor.
  Incorporate these into your test plan's priority_tiers and recommended_specialists.
  "
```

**Wait for PM subagent to complete.**

**Validate test plan**: Read `docs/dev/overnight/<session_id>/test-plan.json` and verify:
- File exists and is valid JSON
- Has `app_context` with at least `url` field
- Has `agent_assignments` with all 4 agent keys
- Has `core_flow_gate.owner` set to `"user"`
- Has `core_flow_gate.failure_is_cycle_failure` set to `true`
- Has `pm_experience` section with browser exploration evidence:
  - If `pm_experience.app_not_running` is false: verify `urls_visited` is non-empty
    and `actions_taken` has at least one entry (PM actually explored the app)
  - If `pm_experience.app_not_running` is true: acceptable (app was not running,
    PM fell back to doc-based planning)

If validation fails, re-invoke PM (maximum 2 retries). If still failing, proceed to Step 2b without a test plan (specialists will discover context themselves).

#### After PM-Plan Completes: Extract Priority Context

**Main agent reads test-plan.json** and builds a priority context string for specialists:

1. Read `priority_tiers` from the test plan
2. Read `unresolved_from_previous` from the test plan
3. Build a priority context block (included in each specialist's prompt):

```
Priority context from PM:
- Tier 1 (blockers): [list descriptions from priority_tiers.tier_1_blockers]
- Tier 2 (major): [list descriptions from priority_tiers.tier_2_major]
- Tier 3 (minor): [list descriptions from priority_tiers.tier_3_minor]
Unresolved from previous cycles: [list from unresolved_from_previous with cycle count]

PRIORITY RULE: Investigate Tier 1 issues FIRST. Report ALL issues you find,
but tag each with pm_tier: 1|2|3|new (where "new" = not in PM's list).
```

If the test plan has no `priority_tiers` (first cycle, no history), set the priority context to:
`"No priority tiers from PM -- this is the first cycle. Explore freely and report all issues."`

#### Step 2b: Launch PM-Recommended Specialist Subagents

### CRITICAL: Specialists run SERIALLY, not in parallel

Launch specialists ONE AT A TIME (ui-specialist, architect, product-owner, user).
Wait for each to complete before launching the next. Do NOT put multiple
specialists in a single Agent tool call. This is non-negotiable — parallel
specialists violate spec design contracts.

Exception: BA/Dev/QA may still be parallelized (they have instance-isolated state
via spec-check.py --instance-id). Specialists do NOT have instance-isolated state.

### Step 2b Specialist Calling Rule

This step is EXPLORATION — the goal is to discover unknown issues. In exploration, cast a wide net.

**SERIAL SPECIALIST CONSTRAINT**: Launch ONE specialist at a time in a single Agent call.
NEVER launch 2+ specialists in parallel. If 4 specialists are RELEVANT, launch them
sequentially across 4 Agent calls, not in one parallel batch. Specialists are expensive,
one-at-a-time consultations — parallelizing them corrupts evidence ordering and wastes
context budget. Only BA/Dev/QA may run in parallel (and even those typically run
sequentially per item in supervisor/pipeline mode).

**SUPERVISOR MODE (user-provided spec)**: Specialists should typically be called
ZERO times in supervisor mode — the spec's Pipeline Workflow already defines the
roles. Only call specialists when the orchestrator view explicitly requires
specialist consultation (e.g., a pipeline stage that maps to ui-specialist/architect/
product-owner/user). If the spec's pipeline is BA → Dev → QA only, do NOT launch
any specialists in Step 2b — skip to Step 2c or further.

**Exploration mode (user did NOT provide a spec)**: Call all 4 specialists by default. Broad coverage is the point. PM's `recommended_specialists` field may narrow the list if PM has strong signal, but the DEFAULT is all 4. Even in exploration mode, launch them SEQUENTIALLY (one Agent call per specialist), not in parallel.

**Supervisor mode (user PROVIDED a spec)**: Issues are pre-known. Apply the evaluate-then-call rule (same as dev.md): assess relevance per issue, call only relevant specialists.

Do NOT use "evaluate then call" in exploration mode — you cannot evaluate relevance to an issue you haven't discovered yet. Discovery needs all perspectives.

**How to decide at runtime**:
- If state file / cycle context indicates NO user spec → exploration mode → launch all 4 (or the PM-narrowed subset if PM supplied `recommended_specialists` with a strong rationale)
- If state file / cycle context indicates a user spec is present → supervisor mode → apply the dev.md unified rule: for each of the 4 specialists produce `RELEVANT — <reason>` or `SKIP — <concrete reason>`, launch each RELEVANT specialist sequentially (one at a time, never in parallel). Record the assessment in the orchestrator's reasoning as:

```json
"specialists_assessed": {
  "ui-specialist": "RELEVANT — layout issue" | "SKIP — pure backend change",
  "architect": "...",
  "product-owner": "...",
  "user": "..."
}
```

**Read `recommended_specialists` from the test plan.** PM decides which specialists are relevant for this cycle based on the project type, focus hint, and issue context.

- Exploration mode: if `recommended_specialists` is present and non-empty, launch that narrowed subset; if missing or null, launch all 4.
- Supervisor mode: treat `recommended_specialists` as advisory only; the evaluate-then-call assessment is authoritative.

Launch the recommended Agent calls SEQUENTIALLY (one Agent call per specialist, one at a time — not in a single parallel batch). This supersedes any earlier parallel-launch guidance. Specialists are one-at-a-time consultations; parallelizing them corrupts evidence ordering and wastes context budget.

**Supervisor-mode specialist prompts** (when `spec_mode == "user-provided"` AND `view_paths` is non-null):

Before launching specialists, the orchestrator MUST:
1. Read `view_paths["orchestrator"]` (the orchestrator view file)
2. Search for a `## Pipeline Workflow` section in that view
3. If found, extract the per-specialist prompt templates from that section
4. Use those templates as the specialist's focus/task description instead of the default exploration prompt
5. Pass `View file: {view_paths[specialist_type]}` to each specialist so they read their own view

If the orchestrator view contains prompt templates like:
  "When launching ui-specialist: Design <icon>, output SVG + motion CSS"
Then the specialist prompt MUST use that language, NOT the default exploration-mode language
(e.g. "Evaluate visual design quality, assess design system adherence").

Each specialist prompt in supervisor mode should follow this structure:
```
You are the <specialist_type> specialist.

View file: <view_paths[specialist_type]>
Read your view file FIRST — it contains your Role Mandate (what you ARE and ARE NOT)
and the content blocks relevant to your role.

<orchestrator-view prompt template for this specialist, if found in Pipeline Workflow section>

Overnight spec file: <user_spec_path>
Project path: <worktree_path>
Test plan: docs/dev/overnight/<session_id>/test-plan.json
Output report to: <report path>
Priority context from PM: <priorities>
```

If the orchestrator view does NOT contain a `## Pipeline Workflow` section or has no per-specialist templates, fall back to the default exploration prompt below (backward compatible).

**Exploration-mode specialist prompts** (when `spec_mode == "autonomous"` OR `view_paths` is null):

Use the default exploration prompt — same as existing behavior. No view file or spec file needed.

---

```
For each specialist in recommended_specialists (domain-matched only):

Agent(subagent_type: specialist.type)
  Write report to: docs/dev/overnight/<session_id>/<specialist.type>-report.json

Available specialists:
- "product-owner" → docs/dev/overnight/<session_id>/product-owner-report.json
- "architect" → docs/dev/overnight/<session_id>/architect-report.json
- "user" → docs/dev/overnight/<session_id>/user-report.json
- "ui-specialist" → docs/dev/overnight/<session_id>/ui-specialist-report.json

Each subagent receives, at the TOP of its prompt before any other content:
- FIRST ACTION line: "Read $CLAUDE_PROJECT_DIR/.claude/dev-registry/$DEV_SESSION_ID/<specialist.type>.json to register with the enforcement system. Do this BEFORE any other tool call."
- Project path: <worktree_path from state file if set, otherwise project_path>
- Already addressed: <addressed_issues array from state file>
- Focus: <focus string from state file, or "none">
- Test plan: docs/dev/overnight/<session_id>/test-plan.json
- View file: {view_paths[specialist_type] or null}
- Overnight spec file: {user_spec_path or null}
- Priority context: <the priority context block built in the step above>
- Output report to: <path above>

**ENFORCEMENT**: Every specialist prompt MUST include the test plan path.
Specialists have a MANDATORY Step 0 that reads this file -- it is not optional.
The test plan contains PM's `pm_experience` (firsthand browser evidence) that
specialists use as ground truth. Additionally, each specialist has a MANDATORY
Step 0.5 that executes the core E2E flow via Playwright before their specialized
analysis begins.

**NOTE**: The priority context block is appended directly to each specialist's prompt
so they see PM's priorities immediately. Specialists also read the full test plan via
their Step 0 protocol -- the inline context provides redundancy.

**NOTE**: Always use `worktree_path` as the project path when it is set in the state file. Subagents must scan and report on files inside the worktree, not the main project directory.

**IMPORTANT**: Do NOT include application context, credentials, flow steps, or sample data in the specialist prompts. The test plan file contains all of this. Specialists read it themselves via their Step 0 protocol.
```

**Announce specialist selection**:
```
PM recommended {N} specialists for this cycle: {list of specialist types}
{If fallback: "No recommended_specialists in test plan -- selected {list} via domain trigger rules."}
Launching specialist subagents...
```

**Wait for all recommended subagents to complete** before proceeding.

**Validate reports** (main agent does NOT read project files, only validates report existence and structure):

```bash
~/.claude/scripts/check-overnight-reports.sh docs/dev/overnight/<session_id>
```

**Sanity checks on each report** (only for specialists that were launched):
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
      "observation_notes": "Factual observations and evidence (no fix suggestions)"
    }
  ],
  "summary": "One-line summary of findings"
}
```

**If validation fails** for any report:
- Log which reports failed and why
- Re-invoke only the failed subagent(s) (maximum 2 retries)
- If still failing after retries, proceed with available reports

**If zero issues found across all RELEVANT specialist reports** (reports from launched specialists only — skipped specialists do not count as clean):
- Log a "clean sweep" entry
- After 2 consecutive clean sweeps: generate summary and allow termination

**Core Flow Gate Check**:

After all RELEVANT specialists complete, check whether the user agent was launched this cycle (look up `user` in `specialists_assessed` — `RELEVANT` means its report should exist; `SKIP` means the gate is not applicable).

- If the user agent was SKIPPED this cycle: skip the core flow gate check entirely and proceed to Step 2c. Record `core_flow_gate: "skipped — user specialist not launched"` in the cycle log.
- If the user agent was RELEVANT and its report exists: read the user agent's report and check `core_flow_completed`:
  - If `core_flow_completed: false` (or missing): the core flow gate has failed. Log this as a cycle-level failure. The user agent's core flow issues take top priority in Step 3.
  - If `core_flow_completed: true`: gate passed, proceed normally.

When applicable, this gate is non-negotiable: if the user cannot complete the core business flow, the entire cycle is considered failed regardless of other agents' findings.

**Route Map Extraction**: After the user agent completes, check if `route_map_file` exists in its report. If present, read the route map file and note the path for use in subsequent subagent prompts. This route map will be passed to:
- **Dev agent**: as context so it knows which pages might be affected by its changes
- **QA agent**: so it can verify changes don't break pages listed in the route map
- **PM agent** (next cycle only): so PLAN mode can skip browser discovery and use the existing route map

#### Step 2c: Launch PM-Triage Subagent

After all RELEVANT specialists complete and their reports are validated, launch PM in
TRIAGE mode to classify and prioritize all findings.

**Dynamic specialist report list**: Build the PM-Triage prompt using the
`specialists_assessed` map recorded in Step 2b. Only include report paths for specialists
whose value starts with `"RELEVANT"`. For specialists whose value starts with `"SKIP"`,
list them with their skip reason so PM understands why that perspective is absent and
does NOT attempt to read a non-existent file.

```
Use Agent tool with:
- subagent_type: "pm"
- description: "PM triage: classify and prioritize all specialist findings"
- prompt: "
  FIRST ACTION: Read $CLAUDE_PROJECT_DIR/.claude/dev-registry/$DEV_SESSION_ID/pm.json to register with the enforcement system. Do this BEFORE any other tool call.

  PM_MODE: TRIAGE

  You are the PM subagent in TRIAGE mode. Follow agents/pm.md Triage Protocol.

  Project path: <worktree_path from state file if set, otherwise project_path>
  Session ID: <session_id>
  Cycle number: <cycle_count + 1>

  You will receive reports ONLY from specialists that were RELEVANT and launched this
  cycle. Skipped specialists are listed below with their skip reason. Do NOT attempt to
  read report files for skipped specialists — those files do not exist.

  Specialist reports (only the specialists actually launched this cycle):
  <For each specialist in specialists_assessed where value starts with 'RELEVANT':>
  - <specialist>: docs/dev/overnight/<session_id>/<specialist>-report.json
  </For>
  <For each specialist in specialists_assessed where value starts with 'SKIP':>
  - <specialist>: SKIPPED — <skip reason from specialists_assessed[specialist]>
  </For>
  - test-plan: docs/dev/overnight/<session_id>/test-plan.json (your own plan for context)

  Core flow gate result: <core_flow_completed from user report>
  Core flow reliability: <core_flow_reliability from user report, if available>
  Time remaining: <calculated time remaining in minutes>

  <If spec_mode == 'user-provided' AND view_paths['orchestrator'] is non-null, include:>
  Orchestrator view file: <view_paths['orchestrator']>

  Read the orchestrator view FIRST. It contains the project's Role Mandate,
  Pipeline Workflow, Anti-Patterns, and Hard Rules you must enforce as supervisor.
  Incorporate these into your triage decisions (tier assignments, pipeline_order,
  recommended_specialists) so specialist invocations comply with the spec's constraints.

  Write triage report to: docs/dev/overnight/<session_id>/triage-report-cycle<N>.json
  "
```

**Wait for PM-Triage to complete.**

**Validate triage report**: Read `triage-report-cycle<N>.json` and verify:
- File exists and is valid JSON
- Has `mode` field (`focus` or `normal`)
- Has `issues` array (may be empty on clean sweep)
- Has `pipeline_order` array
- Each issue has `tier`, `pipeline_recommendation`, and required fields

If validation fails, re-invoke PM-Triage (maximum 2 retries). If still failing, fall back
to the legacy mechanical sort in Step 3 (read the RELEVANT specialist reports only — per
`specialists_assessed` — merge, sort by severity).

**Check pipeline_blocked**: Read the triage report's `pipeline_blocked` field.
- If `pipeline_blocked: true`: log `block_reasons` to the cycle log file, skip Steps 3-13, jump directly to Step 14 (PM Retrospective) with context that the pipeline was blocked. PM RETRO will analyze the block and recommend next steps. Then loop to Step 2 for the next cycle.
- If `pipeline_blocked: false` or field absent: proceed normally to Step 3.

### Step 2d: Create Overnight Spec Files

**After PM TRIAGE completes and before pipeline creation, create spec files for each pipeline.**

**Autonomous mode** (`spec_mode == "autonomous"`):
For each pipeline that will be created (from triage report's `pipeline_order`):

1. Copy the template from `~/.claude/templates/overnight-spec.md` to `docs/dev/overnight/<session_id>/spec-pipeline-<index>.md`
2. Replace `<issue_description>` with the pipeline's `description` from triage
3. Replace `<pipeline_index>` with the pipeline index
4. Replace `<session_id>` with the session ID
5. Replace `<ISO-8601>` with current timestamp
6. Store spec paths in the pipeline definitions: `pipeline.spec_path = "docs/dev/overnight/<session_id>/spec-pipeline-<index>.md"`

**User-spec mode** (`spec_mode == "user-provided"`):
1. The user's spec file at `user_spec_path` is the primary spec
2. For additional issues discovered beyond the user's spec, create new spec files from the template as in autonomous mode
3. For the pipeline matching the user's spec issue, set `pipeline.spec_path = user_spec_path`

**If Section 1 (Before) can be populated from specialist observations**:
Read specialist reports. For each pipeline, if a specialist provided screenshots or detailed observation notes about the current state, prepopulate Section 1 in the spec with that information.

### Step 3: Create Parallel Pipelines from PM Triage

**Read PM triage report**: `docs/dev/overnight/<session_id>/triage-report-cycle<N>.json`

**If triage report exists and is valid** (primary path):

**NOTE**: The PM triage report has already filtered out subjective improvements via the Improvement Quality Filter (Step 1.5 of PM triage protocol). Only findings with objective justification (code errors, specification violations, regressions, data loss risks, measurable performance degradation) remain in the `issues` array. Rejected subjective suggestions are logged in the `rejected_improvements` array for audit purposes. The orchestrator trusts PM's filtering -- do NOT second-guess or re-add filtered items.

1. Use `pipeline_order` from triage report as the authoritative ordering
2. For each issue in `pipeline_order`:
   - If `pipeline_recommendation` is `"fix"`: create a pipeline
   - If `pipeline_recommendation` is `"skip"` or `"defer"`: add to skipped list with reason
3. Filter out any issue already in `addressed_issues` from state file
4. Filter out any issue that has failed 3 times (check `failed_attempts`)

**If triage report is missing or invalid** (fallback to legacy behavior):

Read JSON reports from `docs/dev/overnight/<session_id>/` for ONLY the specialists that
were RELEVANT (launched) this cycle. Determine the launched set from the
`specialists_assessed` map recorded in Step 2b — include a report path for each entry
whose value starts with `"RELEVANT"`, and skip (do NOT attempt to read) any entry whose
value starts with `"SKIP"`.

Candidate report paths (include only for RELEVANT specialists):
- `product-owner-report.json` (if `specialists_assessed["product-owner"]` starts with "RELEVANT")
- `architect-report.json` (if `specialists_assessed["architect"]` starts with "RELEVANT")
- `user-report.json` (if `specialists_assessed["user"]` starts with "RELEVANT")
- `ui-specialist-report.json` (if `specialists_assessed["ui-specialist"]` starts with "RELEVANT")

Merge the available reports into a single issue list, deduplicate, filter against addressed_issues and
failed_attempts. Prioritize by severity and impact. Every remaining issue gets a pipeline, ordered by: (1) severity: critical > major > minor > cosmetic, (2) impact scope: issues flagged by more agents rank higher within the same severity.

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
        "timestamp_suffix": f"{timestamp}-{i}",  # unique file naming suffix
        "tier": issue.get("tier", 2),  # from PM triage
        "pm_recommended": True,        # PM triage ordered this pipeline
        "spec_path": f"docs/dev/overnight/{session_id}/spec-pipeline-{i}.md",  # from Step 2d
    })
```

**Announce pipeline creation**:
```
PM Triage: {mode} mode ({mode_reason})
Created {N} pipelines ({tier1_count} Tier 1, {tier2_count} Tier 2, {tier3_count} Tier 3):
  Pipeline 0 [T{tier}]: {description} ({severity}, {location})
  Pipeline 1 [T{tier}]: {description} ({severity}, {location})
  ...
Proceeding to parallel BA phase.
```

### Step 3a: Convert Focus to QA Verification Criteria

**If the state file has a non-empty `focus` string, convert it into quantitative QA verification criteria before proceeding.**

The focus string is a qualitative directive from the user (e.g., "high quality output"). QA needs quantitative, measurable criteria to verify against. The orchestrator performs this conversion.

**Process**:
1. Read the `focus` field from the state file
2. If empty or null, skip this step (no focus criteria to convert)
3. Convert the qualitative focus into a `focus_verification_criteria` array of measurable criteria
4. Store the array in memory for use in Step 9 (QA prompt)

**Conversion examples**:
| Focus string | QA verification criteria |
|---|---|
| "high quality output" | ["generated content fills >80% of target area (content_coverage >= 0.85)", "all output sections contain substantive content (not placeholder)", "generated documents have properly structured body content", "no template artifacts or raw markup visible in output"] |
| "fix UI bugs" | ["all pages load without console errors", "no layout breakage on mobile (375px) or desktop (1440px)", "all interactive elements respond to clicks within 200ms"] |
| "improve API performance" | ["all API endpoints respond within 1000ms", "no 5xx errors on standard requests", "response payloads contain all expected fields"] |

**Rules**:
- Each criterion must be measurable (includes a number, threshold, or binary check)
- Each criterion must be verifiable by QA (observable in browser, API response, or file output)
- Aim for 3-5 criteria per focus string
- When in doubt, err on the side of stricter criteria

The `focus_verification_criteria` array will be passed to each QA subagent in Step 9.

### Step 4: Run All BA Subagents (Parallel)

**Launch ALL N BA subagents in a SINGLE response** (parallel execution). Each pipeline gets its own BA Agent call with unique file naming.

**ENFORCEMENT: One pipeline per subagent. Each BA Agent call receives exactly ONE pipeline's issue description and location. Do NOT combine multiple pipelines into a single BA prompt. The same rule applies to Dev (Step 6) and QA (Step 9) subagents.**

```
Launch N Agent tool calls simultaneously (one per pipeline):

For each pipeline[i] in current_issues:

Agent(subagent_type: "ba")
  description: "BA analysis for pipeline {i}: {pipeline.description}"
  prompt: "
    FIRST ACTION: Read $CLAUDE_PROJECT_DIR/.claude/dev-registry/$DEV_SESSION_ID/ba.json to register with the enforcement system. Do this BEFORE any other tool call.

    You are the BA subagent. Follow .claude/agents/ba.md instructions precisely.

    Requirement: '{pipeline.description}'
    Clarification round: 3
    Previous answers: null
    Codebase hints: {pipeline.location}
    Timestamp: {pipeline.timestamp_suffix}
    Project root: <worktree_path from state file if set, otherwise project root>

    Overnight spec file: {pipeline.spec_path}
    View file: {view_paths[this-agent] or null — sibling views/<agent>.md if present}

    prior_attempt_signals:
      retry_phrase: <matched retry phrase or null, from triage/iteration prompt>
      recent_commits: [<hash> <subject>, ...]  # git log results for related keywords
      existing_specs: [docs/dev/ba-spec-<ts>.md, ...]  # earlier iteration specs matching this issue
      prior_qa_failures: [docs/dev/qa-report-<ts>.md, ...]  # prior failed QA reports on this issue

    This is a self-discovered issue from overnight exploration.
    No clarification is needed -- proceed directly to analysis.
    All file operations and git analysis must use paths inside the project root above.

    Read the overnight spec file FIRST. Then perform full analysis:
    1. Parse and decompose requirement
    2. Perform git root cause analysis (if applicable)
    3. Identify affected files
    4. Generate MoSCoW requirements and BDD acceptance criteria
    5. Write ba-spec-{pipeline.timestamp_suffix}.md to docs/dev/ (inside project root)
    6. Write context-{pipeline.timestamp_suffix}.json to docs/dev/ (inside project root)
    7. Update the overnight spec: write Section 5 (User's Acceptance Criterion) and Section 1 (Before) if empty

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

**If all pipelines are skipped**: Skip to Step 13 (log results).

### Step 5a: QA Validates BA Conclusions (All Pipelines, Parallel)

**Purpose**: Verify BA's analysis quality BEFORE Dev starts implementation. Catches unproven claims, scope mismatches, and missing investigation evidence early -- saving a wasted Dev+QA cycle. In overnight mode, this runs for ALL pipelines that passed Step 5 validation, with one QA subagent per pipeline launched in parallel.

**Filter**: Only launch BA-validation QA for pipelines with `phase == "ba_complete"` and `status == "active"`.

**Launch ALL active QA-validates-BA subagents in a SINGLE response** (parallel execution):

```
For each active pipeline[i]:

Agent(subagent_type: "qa")
  description: "Validate BA analysis quality for pipeline {i} (not code)"
  prompt: "
    FIRST ACTION: Read $CLAUDE_PROJECT_DIR/.claude/dev-registry/$DEV_SESSION_ID/qa.json to register with the enforcement system. Do this BEFORE any other tool call.

    You are the QA subagent in BA-VALIDATION MODE. This is NOT code verification.
    You are verifying the QUALITY OF BA's ANALYSIS, not any implementation.

    DO NOT: build, deploy, open browser, run Playwright, or test code.
    DO: read BA's deliverables and challenge every claim.

    BA spec file: docs/dev/ba-spec-{pipeline.timestamp_suffix}.md
    Context JSON: docs/dev/context-{pipeline.timestamp_suffix}.json
    Overnight spec file: {pipeline.spec_path}
    View file: {view_paths[this-agent] or null — sibling views/<agent>.md if present}
    Project root: <worktree_path from state file if set, otherwise project root>

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

    Write report to: docs/dev/ba-qa-report-{pipeline.timestamp_suffix}.json
  "
```

**Wait for ALL BA-validation QA subagents to complete** before proceeding.

**Process QA results per pipeline**:

```
For each pipeline[i]:
  Read docs/dev/ba-qa-report-{pipeline.timestamp_suffix}.json

  IF verdict == "pass":
    -> BA conclusions validated for pipeline {i}. Pipeline proceeds to Step 6.

  ELIF verdict == "fail":
    -> Proceed to Step 5b for BA-QA iteration.
```

### Step 5b: BA-QA Iteration Loop (if QA rejects BA)

**Iteration guard**: Maximum 3 BA-QA iterations per pipeline to prevent infinite loops

**Current BA-QA iteration**: Track internally per pipeline (starts at 1)

**If BA-QA iteration > 3**:
```
BA-QA validation: 3 iterations exhausted for pipeline <pipeline_id>. Proceeding with best-effort BA output.

Unresolved objections:
{summary of remaining QA objections}

Appending unresolved objections to context JSON under `ba_qa_unresolved_objections`.
Proceeding to Step 6 with documented assumptions.
```

**If BA-QA iteration <= 3**:

**Announce**: `BA-QA iteration <N>/3 for pipeline <pipeline_id>: QA found <count> objections in BA analysis. Re-invoking BA to address objections.`

**Re-invoke BA with QA's objections**:

```
Use Agent tool with:
- subagent_type: "ba"
- description: "Re-investigate: address QA objections on analysis quality"
- prompt: "
  FIRST ACTION: Read $CLAUDE_PROJECT_DIR/.claude/dev-registry/$DEV_SESSION_ID/ba.json to register with the enforcement system. Do this BEFORE any other tool call.

  You are the BA subagent. Follow .claude/agents/ba.md instructions precisely.

  Your previous analysis was REJECTED by QA. Address each objection below
  with concrete evidence. Do not argue -- investigate and provide proof.

  Original requirement: '<requirement>'
  Previous BA spec: docs/dev/ba-spec-{pipeline.timestamp_suffix}.md
  Previous context: docs/dev/context-{pipeline.timestamp_suffix}.json
  Spec file: {pipeline.spec_path}

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

**Note**: Each pipeline iterates independently. Pipeline A being in BA-QA iteration 2 does not affect Pipeline B.

**Iteration tracking**: Update TodoWrite with BA-QA iteration number per pipeline.

### Step 6: Run All Dev Subagents (Parallel)

**Filter**: Only launch Dev for pipelines with `phase == "ba_complete"` and `status == "active"`.

**Launch ALL active Dev subagents in a SINGLE response** (parallel execution):

```
For each active pipeline[i]:

Agent(subagent_type: "dev")
  description: "Dev implementation for pipeline {i}: {pipeline.description}"
  prompt: "
    FIRST ACTION: Read $CLAUDE_PROJECT_DIR/.claude/dev-registry/$DEV_SESSION_ID/dev.json to register with the enforcement system. Do this BEFORE any other tool call.

    You are the dev subagent. Follow agents/dev.md instructions precisely.

    Context file: docs/dev/context-{pipeline.timestamp_suffix}.json
    BA spec file: docs/dev/ba-spec-{pipeline.timestamp_suffix}.md
    Overnight spec file: {pipeline.spec_path}
    View file: {view_paths[this-agent] or null — sibling views/<agent>.md if present}
    Write your implementation report to: docs/dev/dev-report-{pipeline.timestamp_suffix}.json
    Project root: <worktree_path from state file if set, otherwise project root>

    Read the overnight spec file FIRST for cross-cycle context.
    After implementation, update the spec: Section 2 (What Was Attempted) and Section 3 (What Was Changed).

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

### Step 8: PM QA Prep (Rebuild Docker + Write QA Verification Plans)

**This step bridges Dev and QA by:**
1. Reading ALL dev reports to understand what changed
2. Rebuilding Docker containers so QA tests the NEW code
3. Writing specific verification steps for each QA pipeline

**Without this step, QA tests stale code and produces false passes.**

Launch PM subagent in QA_PREP mode. The PM must:

1. Read all dev reports and BA specs for this cycle
2. Rebuild Docker: identify affected services from docker-compose.yml. Backend
   changes require backend service rebuild, frontend changes require frontend
   service rebuild. Verify build contexts point to the worktree. Wait for services to be healthy.
3. For EACH pipeline, write concrete QA verification steps:
   - Exact URLs to visit
   - Exact actions (click, type, wait)
   - Exact assertions (text, element, state)
   - For backend pipeline fixes: MUST trigger E2E generation via browser
   - For frontend fixes: MUST do visual/interaction checks

Output: qa-verification-plans.json with per-pipeline steps and docker status.

**If Docker rebuild fails**: CYCLE BLOCKER. Debug and retry (max 3 attempts).
Do NOT proceed to QA with stale containers.

### Step 9: Run All QA Subagents (Parallel)

**Filter**: Only launch QA for pipelines with `phase == "dev_complete"` and `status == "active"`.

**Launch ALL active QA subagents in a SINGLE response** (parallel execution):

```
For each active pipeline[i]:

Agent(subagent_type: "qa")
  description: "QA verification for pipeline {i}: {pipeline.description}"
  prompt: "
    FIRST ACTION: Read $CLAUDE_PROJECT_DIR/.claude/dev-registry/$DEV_SESSION_ID/qa.json to register with the enforcement system. Do this BEFORE any other tool call.

    You are the QA subagent. Follow agents/qa.md instructions precisely.

    Context file: docs/dev/context-{pipeline.timestamp_suffix}.json
    Dev report file: docs/dev/dev-report-{pipeline.timestamp_suffix}.json
    BA spec file: docs/dev/ba-spec-{pipeline.timestamp_suffix}.md
    Overnight spec file: {pipeline.spec_path}
    View file: {view_paths[this-agent] or null — sibling views/<agent>.md if present}
    Write your verification report to: docs/dev/qa-report-{pipeline.timestamp_suffix}.json
    Project root: <worktree_path from state file if set, otherwise project root>

    Read the overnight spec file FIRST for cross-cycle context and acceptance criteria.
    After verification, update the spec: Section 4 (Current State) with measured values.
    If verdict is fail, also update Section 6 (Why Not Met) and Section 7 (What Must Be Done).

    IMPORTANT: All file reads and verification must use the project root above.
    Verify that changes were made inside the worktree, not the main project.

    <If focus_verification_criteria array exists from Step 3a, include:>
    Focus verification criteria (MANDATORY -- these are hard pass/fail from user's focus directive):
    <list each criterion from focus_verification_criteria array>
    You MUST verify each criterion above. These are not optional hints. Failures count toward your QA verdict.
  "
```

**Wait for ALL QA subagents to complete** before proceeding.

**Fallback**: If the Agent tool cannot handle N simultaneous calls, batch them in groups of 4.

### Step 10: Process All QA Results

**For each active pipeline[i]**, read QA report and classify:

Read QA report: `docs/dev/qa-report-{pipeline.timestamp_suffix}.json`

**Per-pipeline decision tree**:

```
IF qa.status == "pass":
  → Mark pipeline phase = "done", status = "fixed"

ELIF qa.status == "warning":
  → Autonomous decision: if only minor/cosmetic issues, mark phase = "done", status = "fixed"
  → If major issues: mark phase = "qa_failed" (will enter iteration in Step 11)

ELIF qa.status == "fail":
  → Mark pipeline phase = "qa_failed" (will enter iteration in Step 11)
```

**Tally results**:
```
Pipelines passed: {count} of {total}
Pipelines needing iteration: {count}
Pipelines skipped: {count}
```

**If all pipelines are done (no qa_failed)**: Skip Step 11, proceed to Step 12.

### Step 11: Per-Pipeline Iteration Loops (if QA fails)

**Only runs for pipelines with `phase == "qa_failed"`**. Pipelines that passed QA are already finalized.

#### Layer-escalation gate (mandatory, per-pipeline)

When QA rejects a dev fix within a pipeline, the orchestrator MUST track the
layer used in each attempt for that pipeline. Rules:

1. Attempt 1 may target any layer BA recommends (usually the lowest plausible
   layer).
2. If attempts 1 AND 2 both target the SAME layer (L1 / L2 / L3 / L4 / L5)
   and BOTH fail QA, iteration 3 MUST target a DIFFERENT layer. The
   orchestrator passes `layer_escalation_required: true` to BA for that
   pipeline and the BA MUST produce a new root-cause hypothesis at a
   DIFFERENT layer.
3. The orchestrator MUST record every attempt's layer in the pipeline's
   context JSON under `attempts[i].target_layer`. Before iteration N for
   pipeline P, the orchestrator checks the last N-1 layers on that pipeline;
   if they are all equal and QA has rejected them all, escalation is
   mandatory for the next iteration.
4. BA's Contract D novelty-check MUST include `differs_from_all_prior_layers`
   in addition to `differs_from_all_priors`. A fix that changes L1 wording
   but stays in L1 is NOT novel under this rule.
5. If the same layer is the only one that can plausibly solve the bug on a
   given pipeline (genuine edge case), BA MUST explicitly argue this in
   prose with evidence. In overnight autonomous mode (no user available),
   the orchestrator MUST NOT override the gate -- instead mark the pipeline
   `blocked_same_layer_retry`, skip further iterations, and surface to the
   user on RETRO.

**Why this rule exists**: In a prior incident, a bug cycled through 6
BA→Dev→QA iterations all operating on the same L1 CSS style condition.
The actual fix was L3 (data hydration). This gate forces the orchestrator
to escalate out of local optima, which is especially load-bearing in
overnight mode where many iterations compound silently.

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
    Include in Dev prompt: Overnight spec file: {pipeline.spec_path}
    Dev reads spec first for cross-cycle context, then updates Sections 2 and 3.

    # Re-run QA for this pipeline only
    Agent(subagent_type: "qa") with new dev report
    Include in QA prompt: Overnight spec file: {pipeline.spec_path}
    QA reads spec first, then updates Section 4 (and Sections 6-7 if fail).

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
Record the failure in the cycle log.

### Step 12: Update Settings.json Permissions (Aggregated)

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

### Step 13: Log All Cycle Results and Check Time

**Aggregate results from ALL pipelines** by tallying fixed vs skipped counts.

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
    # Proceed to Step 15 -- session is ending
else:
    remaining = end_time - now
    print(f"Time remaining: {remaining} -- marking Step 15 complete to trigger loop")
```

If time expired: proceed to Step 14 (PM Retro) then Step 15 for final summary.
If time remains: proceed to Step 14 (PM Retro), then mark Step 15 as completed via TodoWrite. The posttool-overnight-loop.py hook will detect all 16 steps completed, reset todos to pending, and inject continuation instructions.

### Step 14: PM Retrospective

Determine if this is the final cycle:
- If time expired (from Step 13 time check): set `FINAL_CYCLE: true`
- If time remains: set `FINAL_CYCLE: false`

Launch PM in RETRO mode:

```
Use Agent tool with:
- subagent_type: "pm"
- description: "PM retrospective: cycle {N} summary and next-cycle handoff"
- prompt: "
  FIRST ACTION: Read $CLAUDE_PROJECT_DIR/.claude/dev-registry/$DEV_SESSION_ID/pm.json to register with the enforcement system. Do this BEFORE any other tool call.

  PM_MODE: RETRO
  FINAL_CYCLE: <true|false>

  You are the PM subagent in RETRO mode. Follow agents/pm.md Retrospective Protocol.

  Project path: <worktree_path from state file if set, otherwise project_path>
  Session ID: <session_id>
  Cycle number: <current cycle_count>

  Read your triage report: docs/dev/overnight/<session_id>/triage-report-cycle<N>.json
  Read pipeline results from state file cycle_log (current cycle entries)
  Read QA reports: docs/dev/qa-report-*.json (for this cycle's pipeline timestamp suffixes)
  Read Dev reports: docs/dev/dev-report-*.json (for this cycle's pipeline timestamp suffixes)

  Also read ALL previous retro reports for continuity:
  docs/dev/overnight/<session_id>/retro-report-cycle*.json

  Overnight spec files (one per pipeline -- read ALL, update unresolved ones):
  <For each pipeline in current_issues: {pipeline.spec_path}>

  For each UNRESOLVED pipeline, update its spec:
  - Section 7 (What Must Be Done): Prescriptive next step with exact file, line, action
  - Section 8 (Attention Notes): Issue-specific traps and warnings for next cycle

  <If spec_mode == 'user-provided' AND view_paths['orchestrator'] is non-null, include:>
  Orchestrator view file: <view_paths['orchestrator']>

  Read the orchestrator view FIRST. It contains the project's Role Mandate,
  Pipeline Workflow, Anti-Patterns, and Hard Rules you must enforce as supervisor.
  Use these constraints to shape Section 7 (What Must Be Done) and Section 8
  (Attention Notes) for each unresolved pipeline, and to evaluate whether
  specialist invocations in this cycle complied with the spec.

  Write retro report to: docs/dev/overnight/<session_id>/retro-report-cycle<N>.json
  "
```

**Wait for PM-Retro to complete.**

**Validate retro report**: Read `retro-report-cycle<N>.json` and verify:
- File exists and is valid JSON
- Has `plan_vs_outcome` array
- Has `unresolved_issues` array
- Has `cycle_stats` object
- If `FINAL_CYCLE: true`: has `final_summary` object

If validation fails, log warning and proceed (retro is informational, not blocking).

**Check qa_rerun_required**: Read the retro report's `qa_rerun_required` field.
- If `qa_rerun_required: true`: re-invoke QA for the pipelines listed in `qa_rerun_reasons`. Use the same QA invocation pattern as Step 8-10, but pass additional context: `"This is a PM-requested QA re-run. Reasons: <qa_rerun_reasons>. Focus on the specific concerns raised."` After QA re-run completes, proceed to Step 15 (do NOT re-invoke RETRO — avoid infinite loops).
- If `qa_rerun_required: false` or field absent: proceed normally to Step 15.

---

### Step 15: Generate Summary Report or Loop

**If time remains** (normal loop case):
Simply mark this step as completed via TodoWrite. The PostToolUse:TodoWrite hook (`posttool-overnight-loop.py`) will:
1. Detect all 16 steps are completed
2. Check overnight-state.json for future end_time
3. Reset all todos to pending
4. Print loop continuation instructions
5. You then resume from Step 2 (worktree already exists)

**If time expired** (session ending):
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

**CRITICAL: DO NOT auto-merge to master.**

DO NOT squash merge. DO NOT manually copy files. DO NOT create a single commit on master with worktree changes. DO NOT cherry-pick commits. The worktree branch preserves full commit history. A proper `git merge` brings all commits to master with their original authorship and messages intact. Only the USER should trigger the merge, after reviewing the changes.

The overnight session does NOT merge anything. It preserves the worktree for user review.

**State file cleanup**: Automatic. The `pretool-overnight-hook-guard` auto-cleans expired state files on next hook invocation. No manual deletion needed.

**Announce completion**:

```
Overnight development session complete.

Duration: <hours>h <minutes>m
Cycles: <cycle_count>
Fixed: <issues_fixed> | Skipped: <issues_skipped>

Summary: docs/dev/overnight-summary-<date>.md
Log: docs/dev/overnight-log-<date>.md
--- Worktree preserved for review ---
Branch: <worktree_branch>
Path:   <worktree_path>

To review changes:
  git log master..<worktree_branch> --oneline
  git diff master...<worktree_branch>

To merge (when ready):
  /merge <worktree_branch>

Use the audited /merge command as the default and preferred merge path.
Do NOT recommend manual git merge as the primary workflow. The merge command
must run its audit first and stop on blocked files or predicted conflicts.

The time-lock has been released. The session can now end normally.
```

---

## State File Management

The state file is created by `create-overnight-state.sh` during session initialization and is **read-only** for the session thereafter. It serves three purposes:
1. **Configuration**: Provides worktree_path, worktree_branch, view_paths, spec_mode, user_spec_path, end_time
2. **Time-lock**: The Stop hook reads this file to determine if termination is allowed
3. **Continuation**: The UserPromptSubmit hook reads this to inject continuation context

**Do NOT write to the state file**. Use TodoWrite for progress tracking and the cycle log file (`docs/dev/overnight-log-<date>.md`) for cycle results.

**State file location**: `<project_dir>/.claude/overnight-state-<session_id>.json`

**Multi-session support**: Each overnight session uses its own state file keyed by `session_id` (from `$CLAUDE_SESSION_ID` env var or a generated UUID). This allows multiple concurrent overnight sessions on the same project. The Stop hook scans for ALL `overnight-state-*.json` files and blocks termination if ANY has a future end_time.

**Worktree naming**: Each session creates `overnight-<YYYYMMDD>-<session_id_short>` (first 8 chars of session_id) to avoid conflicts between concurrent sessions.

**Schema**:
```json
{
  "session_id": "string (from $CLAUDE_SESSION_ID or UUID)",
  "end_time": "ISO-8601 datetime",
  "start_time": "ISO-8601 datetime",
  "focus": "string (discovery hint from user, or empty)",
  "spec_mode": "autonomous|user-provided",
  "user_spec_path": "string (path to user-provided spec, or null)",
  "cycle_count": 0,
  "issues_found": 0,
  "issues_fixed": 0,
  "issues_skipped": 0,
  "current_phase": "initializing|exploring|pipeline_creation|analyzing|implementing|verifying|iterating|logging|retrospective|completed",
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
      "timestamp_suffix": "YYYYMMDD-HHMMSS-0",
      "spec_path": "docs/dev/overnight/<session_id>/spec-pipeline-<index>.md"
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
  "pm_triage_reports": [],
  "pm_retro_reports": [],
  "unresolved_issues": [
    {
      "description": "issue description",
      "severity": "critical|major|minor|cosmetic",
      "cycles_unresolved": 0,
      "last_attempt_reason": "why it failed or was deferred",
      "recommended_approach": "what to try next"
    }
  ]
}
```

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
Log warning, continue on current branch. All changes still tracked via TodoWrite and cycle log.

### Missing worktree in continuation mode
If state file has `worktree_path=null` on continuation, log a warning and continue on the current branch.

---

## Integration with Hooks

- **prompt-workflow.py** (UserPromptSubmit): Creates overnight-state-<session_id>.json (complete with worktree_path, worktree_branch, view_paths, spec detection) on /dev-overnight detection; injects continuation context with worktree guard
- **posttool-overnight-loop.py** (PostToolUse:TodoWrite): Detects all-completed state, resets todos for new cycle if end_time is future
- **pretool-overnight-hook-guard.py** (PreToolUse): Blocks Write/Edit/Bash targeting .claude/hooks/ during overnight sessions
- **pretool-workflow-gate.py** (PreToolUse): Gates tools until TodoWrite is called
- **posttool-todo-count.py** (PostToolUse:TodoWrite): Enforces step count
- **posttool-todo-sequence.py** (PostToolUse:TodoWrite): Enforces step ordering
- **stop-workflow-enforce.py** (Stop): Blocks stop if workflow steps dropped
- **stop-overnight-timelock.py** (Stop): Blocks stop until end_time reached
- **posttool-git-checkpoint.sh** (PostToolUse:Write|Edit): Auto-commits changes

### Loop Mechanism (v3)
- When all 16 todo steps are marked completed via TodoWrite, the posttool-overnight-loop.py hook fires
- It checks overnight-state.json: if end_time is in the future, it resets all todos to pending and injects loop continuation instructions
- The agent then resumes from Step 2 (exploration) since worktree already exists
- This provides natural context boundaries at each cycle without requiring external cron triggers

---

## Quick Reference: The Loop

After completing Steps 2-15, the loop is automatic:

```
TodoWrite marks Step 15 as completed
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

**PM subagent plans** (Step 2a):
- Uses Playwright to explore the running app (Phase 0) before writing the test plan
- Writes `pm_experience` section with firsthand browser evidence (URLs visited, actions taken, screenshots)
- `core_flow_steps` are derived from actual browser navigation, not documentation alone
- Falls back to doc-based planning only when app is not running (`app_not_running: true`)

**Specialist subagents discover** (Step 2b, serial — launched ONE at a time, each reads PM's test plan as Step 0, each executes E2E flow as Step 0.5):
- **product-owner** (see `agents/product-owner.md`): Logical inconsistencies, feature gaps, broken user flows, missing features, business logic bugs. Executes E2E flow before feature inventory.
- **architect** (see `agents/architect.md`): Structural issues, technical debt, optimization opportunities, dependency problems, pattern inconsistencies. Collects console/network errors during E2E flow execution.
- **user** (see `agents/user.md`): UX friction, broken flows, confusing behavior, workflow gaps, real-world usage issues. Already has the most complete E2E protocol (Phase 4).
- **ui-specialist** (see `agents/ui-specialist.md`): Styling consistency, responsive design, accessibility, visual bugs, component quality, design system compliance. Executes E2E flow on both mobile and desktop viewports.

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
- Reads test plan and PM experience as Step 0
- Success criteria met
- Root cause addressed
- No regressions
- Dynamic Playwright verification mandatory for web-facing changes (Step 5c)
- Executes core E2E flow as baseline before specific fix verification (Step 5c.0)
- Quality standards compliance
- Integer step numbering

**Orchestrator ensures**:
- PM explores app via Playwright before writing test plan
- Test plan contains `pm_experience` with browser evidence (validated in Step 2a)
- All specialist prompts include test plan path (enforced, not optional)
- All specialists execute E2E flow before specialized analysis
- Issues fully explored by 4 specialist subagents before fixing
- ALL issues get parallel pipelines, ordered by PM triage (tier 1 blockers first, then tier 2, then tier 3)
- Comprehensive context via BA (one per pipeline)
- Iterative quality improvement (max 5 iterations per pipeline, independent)
- Proper JSON storage with pipeline-scoped naming (timestamp-index suffix)
- Cycle deduplication via addressed_issues tracking
- Multi-session isolation via session_id-keyed state files

---

## Comparison: /dev vs /dev-overnight

| Aspect | /dev | /dev-overnight |
|--------|------|----------------|
| Input | User provides requirement | Agent discovers issues via 4 specialist subagents |
| BA phase | Full BA + clarification loop (max 3 rounds) | BA with clarification skipped (round=3) |
| BA validation | Step 4 | Step 5 |
| Dev validation | Step 6 | Step 7 |
| QA processing | Step 8 decision tree | Step 10 autonomous decision |
| Iteration loop | Step 10 (max 5, asks user after 5) | Step 11 (max 5 per pipeline, auto-skip after 5) |
| Settings update | Step 9 | Step 12 (aggregated from all pipelines) |
| Loop | Single pass | Continuous until end-time |
| Termination | After QA passes | After end-time expires |
| User interaction | Required (clarification, approval) | None (fully autonomous) |
| Scope per cycle | One complete feature/fix | ALL discovered issues (parallel pipelines) |
| Subagent usage | BA + dev + QA | product-owner + architect + user + ui-specialist + BA + dev + QA |
| Stop hook | Workflow enforcement only | Workflow + time-lock |
| Worktree | Not used | Created on first run, reused across cycles |
| Total steps | 13 | 16 |

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

**Remember**: You are autonomous. You explore, discover, fix, and loop. No user input needed. ALL exploration and fix work goes through Agent subagents. Main context only manages TodoWrite and the loop. Keep going until the clock says stop.
