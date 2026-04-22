---
description: Enhanced development workflow with BA subagent delegation, command development best practices, Three-Party Architecture, and comprehensive automation patterns
---

**CRITICAL**: Use TodoWrite to track workflow phases. Mark in_progress before each step, completed immediately after.

# Development Orchestrator for Command Development

**Philosophy**: Understand requirement fully → Find root cause → Delegate implementation → Verify quality → Iterate until perfect

This command uses multi-round inquiry to fully understand requirements, then orchestrates development through specialized subagents with continuous QA verification. Enhanced with proven command development patterns from successful implementations.

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

## Command Development Best Practices

**This section documents proven patterns for developing slash commands, subagents, and todo workflows.**

### Overview

Developing effective slash commands requires understanding several key architectural patterns:

1. **Three-Party Architecture** - Orchestrator → Specialist → Orchestrator pattern
2. **Specialist Subagent Design** - Domain-specific consultant agents
3. **Todo Workflow Scripts** - Automated progress tracking
4. **Three-Hook Checklist Enforcement** - Hook-based mandatory workflow compliance
5. **YAML Frontmatter** - Command metadata and configuration
6. **Complete Automation** - Zero user-in-the-loop design
7. **Script Parameterization** - Flexible, reusable scripts

These patterns have been validated through successful implementations like the `/update` command.

---

### Pattern 1: Three-Party Architecture

**What**: Separation of orchestration, analysis, and execution into three distinct phases.

**Architecture**:
```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Main Agent (Orchestrator)                         │
│ - Receives user request                                     │
│ - Clarifies requirements                                    │
│ - Gathers context                                           │
│ - Prepares structured input                                 │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: Specialist Subagent (Consultant)                  │
│ - Receives structured context                               │
│ - Performs domain-specific analysis                         │
│ - Returns structured recommendations (JSON)                 │
│ - NO direct file modifications                              │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: Main Agent (Executor)                             │
│ - Receives specialist recommendations                       │
│ - Implements changes based on recommendations               │
│ - Validates results                                         │
│ - Presents to user                                          │
└─────────────────────────────────────────────────────────────┘
```

**When to Use**:
- Commands requiring domain expertise (analysis, classification, optimization)
- Complex decision-making that benefits from specialized knowledge
- Operations where separation of concerns improves quality
- Reusable analysis logic across multiple commands

**Benefits**:
1. **Separation of Concerns** - Orchestration separate from domain logic
2. **Reusable Specialists** - Same subagent can serve multiple commands
3. **Clear Responsibilities** - Each phase has specific duties
4. **Quality Consistency** - Specialist expertise applied uniformly

**Implementation**:

```markdown
## Step N: Invoke Specialist for Analysis

Use Task tool:
- subagent_type: "general-purpose"
- subagent_name: "<specialist-name>" (from .claude/agents/)
- prompt: "
  You are the <specialist-name>. Follow .claude/agents/<specialist-name>.md.

  Context: <structured input>

  Your task: <specific analysis request>

  Output: Return JSON with recommendations:
  {
    \"analysis\": {...},
    \"recommendations\": [...],
    \"rationale\": \"...\"
  }

  DO NOT modify files. Return recommendations only.
  "
```

**Real-World Example**: `/update` command
- Main agent: Reads resume, prepares job posting context
- Specialist (resume-refiner-update): Analyzes fit, recommends additions/changes
- Main agent: Implements recommendations, saves updated resume

**Anti-Patterns to Avoid**:
- ❌ Orchestrator performing domain analysis directly
- ❌ Specialist modifying files directly (breaks separation)
- ❌ Skipping specialist when domain expertise needed
- ❌ Using specialist for simple CRUD operations

---

### Pattern 2: Specialist Subagent Design

**What**: Domain-specific consultant agents that provide expertise without direct file manipulation.

**Subagent Structure** (`.claude/agents/<specialist-name>.md`):

```markdown
# <Specialist Name> Subagent

**Role**: <Domain expertise description>

**Responsibilities**:
- <Analysis task 1>
- <Analysis task 2>
- <Recommendation generation>

**NOT Responsible For**:
- File modifications (orchestrator handles)
- User interaction (orchestrator handles)
- Workflow coordination (orchestrator handles)

## Input Format

Expects structured context:
\`\`\`json
{
  "context_field_1": "...",
  "context_field_2": {...},
  "requirements": {...}
}
\`\`\`

## Analysis Process

1. **Read Context**: Internalize all provided context
2. **Apply Domain Expertise**: <domain-specific analysis>
3. **Generate Recommendations**: <structured output>
4. **Rationale**: Explain reasoning

## Output Format

Return JSON only:
\`\`\`json
{
  "analysis": {
    "findings": [...],
    "assessment": "..."
  },
  "recommendations": [
    {
      "type": "add|modify|remove",
      "target": "...",
      "content": "...",
      "rationale": "..."
    }
  ],
  "confidence": "high|medium|low",
  "notes": "..."
}
\`\`\`

## Quality Standards

- Recommendations must be specific and actionable
- Rationale required for each recommendation
- Consider edge cases and constraints
- Output must be valid JSON
```

**When to Use**:
- LLM-based analysis (classification, sentiment, quality assessment)
- Domain-specific optimization (resume tailoring, code review)
- Complex decision-making requiring expertise
- Reusable logic across multiple workflows

**Benefits**:
1. **Domain Expertise Encapsulation** - Knowledge centralized
2. **Reusability** - Multiple commands can use same specialist
3. **Consistent Quality** - Expertise applied uniformly
4. **Clear Interface** - Structured input/output contract

**Output Characteristics**:
- **Structured JSON** (not direct file modifications)
- **Recommendations** (not commands)
- **Rationale** (explains reasoning)
- **Confidence levels** (indicates certainty)

**Real-World Example**: `resume-refiner-update.md`
```markdown
# Resume Refiner Update Subagent

**Role**: Analyze job postings and recommend resume enhancements

**Input**: Job posting text + current resume JSON
**Output**: Recommendations for additions/modifications
**Does NOT**: Modify resume files directly
```

**Anti-Patterns to Avoid**:
- ❌ Specialist using Write/Edit tools directly
- ❌ Specialist handling user interaction
- ❌ Returning unstructured text instead of JSON
- ❌ Making decisions outside domain expertise

---

### Pattern 3: Todo Workflow Script

**What**: Python scripts that generate workflow checklists for consistent progress tracking.

**Purpose**:
- Agent sees current step in workflow
- User tracks progress visually
- Steps never forgotten or skipped
- Workflow enforcement through TodoWrite

**Script Location**: `.claude/scripts/todo/<command>.py`

**Script Structure**:

```python
#!/usr/bin/env python3
"""Preloaded TodoList for /<command> workflow."""

def get_todos():
    """Return workflow steps as TodoWrite-compatible list."""
    return [
        {
            "content": "Step 1: <Imperative description>",
            "activeForm": "Step 1: <Present continuous description>",
            "status": "pending"
        },
        {
            "content": "Step 2: <Imperative description>",
            "activeForm": "Step 2: <Present continuous description>",
            "status": "pending"
        },
        # ... more steps
    ]

if __name__ == "__main__":
    import json
    print(json.dumps(get_todos(), indent=2, ensure_ascii=False))
```

**When to Use**:
- Multi-step commands (3+ steps)
- Commands requiring progress tracking
- Complex workflows where steps might be forgotten
- Commands with conditional branches

**Benefits**:
1. **Agent Visibility** - Agent always knows current step
2. **User Tracking** - User sees progress in real-time
3. **Workflow Enforcement** - Steps cannot be skipped
4. **Consistency** - Same workflow every execution

**Todo Item Format**:
- `content`: Imperative form ("Parse input", "Run tests")
- `activeForm`: Present continuous ("Parsing input", "Running tests")
- `status`: "pending" (all start as pending)

**Real-World Example**: `~/.claude/scripts/todo/update.py`
```python
def get_todos():
    return [
        {"content": "Step 1: Parse arguments", "activeForm": "...", "status": "pending"},
        {"content": "Step 2: Validate job posting", "activeForm": "...", "status": "pending"},
        {"content": "Step 3: Invoke resume-refiner-update specialist", "activeForm": "...", "status": "pending"},
        # ... 7 steps total
    ]
```

**Anti-Patterns to Avoid**:
- ❌ Hardcoding todos in command markdown
- ❌ Not updating todos as steps complete
- ❌ Using todos for trivial single-step commands

---

### Pattern 4: Three-Hook Checklist Enforcement

**What**: A system of three coordinated hooks that enforce mandatory, ordered, step-by-step workflow compliance. Prevents agents from ignoring the checklist, abbreviating steps, or skipping ahead.

**Why**: Todo scripts alone are passive — agents can ignore them or write fewer steps. The three-hook system makes the checklist mechanically enforced, not just advisory.

**Architecture**:

```
User runs /command
       ↓
hook-checklist-userprompt.py creates workflow bookmark
  (todo_acknowledged = false)
       ↓
Agent tries any tool
       ↓
[GATE 1] hook-precheck-workflow.py (PreToolUse)
  - Blocks ALL tools until TodoWrite is called first
  - Passes TodoWrite and ToolSearch through freely
       ↓
Agent calls TodoWrite
       ↓
[GATE 2] hook-enforce-todo-count.py (PostToolUse/TodoWrite)
  - Checks count against canonical todo script output
  - Blocks + resets lock if count < required
  - Shows canonical step list on violation
       ↓
Count is correct → todo_acknowledged = true → gates open
       ↓
[GATE 3] hook-enforce-step-sequence.py (PostToolUse/TodoWrite)
  - Tracks previous todo state in bookmark
  - Blocks if: multiple steps completed at once,
    pending→completed without in_progress,
    multiple in_progress simultaneously,
    starting step N while earlier step pending
```

**The Three Hooks**:

**Hook 1: `~/.claude/hooks/hook-precheck-workflow.py`** (PreToolUse)
- Fires before every tool use
- Reads `workflow-{session_id}.json` bookmark
- If `todo_acknowledged == false`: blocks all tools with descriptive error
- Different error messages per `lock_reason`: `not_started`, `count_mismatch`, `sequence_violation`
- Passes through: `TodoWrite` (to allow fix), `ToolSearch` (to allow schema loading)

**Hook 2: `~/.claude/hooks/hook-enforce-todo-count.py`** (PostToolUse, matcher: TodoWrite)
- Fires after every TodoWrite call
- Runs the canonical todo script (`.claude/scripts/todo/<cmd>.py`) to get `blocking_count`
- If `len(submitted_todos) < blocking_count`: sets `todo_acknowledged = false`, `lock_reason = 'count_mismatch'`, exits 2
- Shows full canonical step list so agent knows exactly what to submit
- Exit 0 if count matches or exceeds required

**Hook 3: `~/.claude/hooks/hook-enforce-step-sequence.py`** (PostToolUse, matcher: TodoWrite)
- Fires after every TodoWrite call (after hook 2)
- Stores previous state as `last_todos` in bookmark; skips validation on first call
- Enforces four rules per call:
  1. Max 1 step newly completed per call
  2. No `pending → completed` without passing through `in_progress`
  3. Max 1 step in `in_progress` at a time
  4. Cannot start step N if any earlier step is not yet `completed`
- On violation: sets `todo_acknowledged = false`, `lock_reason = 'sequence_violation'`, exits 2
- On valid transition: updates `last_todos` in bookmark

**Workflow Bookmark**: `.claude/workflow-{session_id}.json`

```json
{
  "command": "dev",
  "todo_acknowledged": false,
  "lock_reason": "not_started",
  "last_todos": [...]
}
```

**Settings.json Wiring**:

```json
"PreToolUse": [
  {
    "hooks": [{
      "type": "command",
      "command": "python3 ~/.claude/hooks/hook-precheck-workflow.py",
      "stdin_json": true,
      "on_error": "ignore"
    }]
  }
],
"PostToolUse": [
  {
    "matcher": "TodoWrite",
    "hooks": [
      {
        "type": "command",
        "command": "python3 ~/.claude/hooks/hook-todo-state-tracker.py",
        "stdin_json": true,
        "on_error": "ignore"
      },
      {
        "type": "command",
        "stdin_json": true,
        "command": "python3 ~/.claude/hooks/hook-enforce-todo-count.py"
      },
      {
        "type": "command",
        "stdin_json": true,
        "command": "python3 ~/.claude/hooks/hook-enforce-step-sequence.py"
      }
    ]
  }
]
```

**Complete Enforcement Chain**:

| Violation | Hook | Action |
|-----------|------|--------|
| Agent ignores checklist entirely | hook-precheck-workflow | Block all tools, force TodoWrite |
| TodoWrite with too few steps | hook-enforce-todo-count | Block, reset lock, show canonical list |
| Multiple steps completed at once | hook-enforce-step-sequence | Block, reset lock, show next required action |
| Step skips in_progress | hook-enforce-step-sequence | Block, reset lock |
| Multiple in_progress simultaneously | hook-enforce-step-sequence | Block, reset lock |
| Steps completed out of order | hook-enforce-step-sequence | Block, reset lock |

**Required Files for Full Enforcement**:
1. `~/.claude/scripts/todo/<command>.py` - Canonical step list (drives count enforcement)
2. `~/.claude/hooks/hook-checklist-userprompt.py` - Creates workflow bookmark on command invocation
3. `~/.claude/hooks/hook-precheck-workflow.py` - Gate 1 (pre-tool)
4. `~/.claude/hooks/hook-enforce-todo-count.py` - Gate 2 (post-TodoWrite)
5. `~/.claude/hooks/hook-enforce-step-sequence.py` - Gate 3 (post-TodoWrite)

**Expected Agent Behavior** (compliant):
```
TodoWrite([11 canonical steps, all pending, step 1 in_progress])
  → Gate 2: count OK (11 == 11) → todo_acknowledged = true
  → Gate 3: first call, no validation, saves last_todos
  → All gates open

[... does work for step 1 ...]

TodoWrite([step 1 completed, step 2 in_progress, rest pending])
  → Gate 2: count OK → pass
  → Gate 3: 1 newly completed ✓, pending→in_progress→completed ✓, 1 in_progress ✓ → pass
```

**Anti-Patterns to Avoid**:
- ❌ Creating commands without a matching `.claude/scripts/todo/<cmd>.py` (count enforcement silently skips)
- ❌ Submitting abbreviated or custom step lists (count hook blocks)
- ❌ Marking multiple steps complete in one TodoWrite call (sequence hook blocks)
- ❌ Going from `pending` directly to `completed` (sequence hook blocks)

---

### Pattern 5: YAML Frontmatter

**What**: Structured metadata at the top of command files for configuration and discoverability.

**CRITICAL RULE**: **ONLY use `description` field. Do NOT add other fields.**

**Correct Frontmatter Format**:

```yaml
---
description: <One-line description of command purpose>
---
```

**Why This Format**:
1. **System Compatibility**: Claude Code only recognizes `description` field
2. **Command Execution**: Other fields (allowed-tools, argument-hint, model) cause command to fail silently
3. **Proven Pattern**: All working system commands use only `description`

**Field Description**:

**description**:
- One-line summary of command purpose
- Shows in help text and command listings
- Should be clear and actionable
- Enclosed in quotes if contains special characters

**Real-World Example**: `/update` command frontmatter
```yaml
---
description: "Update resume with new work experience and automatically archive conversation"
---
```

**More Examples from System Commands**:
```yaml
# /clean command
---
description: Aggressive project cleanup - normalize docs structure, archive everything, delete one-time scripts/tests
---

# /dev command
---
description: Orchestrated development workflow with multi-round requirement clarification, parallel agent execution, and iterative QA verification
---
```

**Critical Anti-Patterns to Avoid**:
- ❌ **Adding `model` field** - Causes command execution to fail
- ❌ **Adding `allowed-tools` field** - Not recognized by system
- ❌ **Adding `argument-hint` field** - Not recognized by system
- ❌ Omitting frontmatter entirely (acceptable but not recommended)
- ❌ Overly verbose descriptions (keep to one line)

**Root Cause Analysis**:
When `/update` command failed silently during testing:
- **Problem**: Frontmatter had `model: claude-sonnet-4.5` (with dot)
- **First Fix Attempt**: Changed to `model: claude-sonnet-4-5` (with hyphen) - still failed
- **Root Cause**: System doesn't recognize `model` field at all
- **Correct Fix**: Remove all fields except `description`
- **Result**: Command works perfectly

**Lesson Learned**: Don't assume frontmatter fields from other systems work in Claude Code. Test commands after creation and verify execution, not just file existence.

---

### Pattern 6: Complete Automation

**What**: Design workflows that require zero user interaction during execution.

**Principles**:

1. **Automatic Backup**:
   ```bash
   # Create timestamped backup before modifications
   cp data/resume.json data/resume.json.bak.$(date +%Y%m%d-%H%M%S)
   ```

2. **Automatic Validation**:
   ```python
   # Validate before and after
   def validate_structure(data):
       required = ["personal_info", "work_experience"]
       return all(k in data for k in required)
   ```

3. **Automatic Archival**:
   ```bash
   # Archive old versions
   mv data/resume.json.bak.* archive/$(date +%Y%m)/
   ```

4. **Error Resilience**:
   ```python
   # Handle failures gracefully
   try:
       result = process_data()
   except Exception as e:
       restore_backup()
       log_error(e)
       notify_user()
   ```

**When to Use**:
- Production commands used frequently
- Commands modifying critical data
- Operations requiring consistency
- Workflows where user interruption breaks state

**Benefits**:
1. **Efficiency** - No waiting for user confirmations
2. **Consistency** - Same behavior every time
3. **User Experience** - Simple, fast, reliable
4. **Reduced Errors** - Fewer manual intervention points

**Techniques**:

**Backup Pattern**:
```bash
# Before modification
BACKUP_FILE="${ORIGINAL_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
cp "$ORIGINAL_FILE" "$BACKUP_FILE"
echo "Backup created: $BACKUP_FILE"
```

**Validation Pattern**:
```python
# Validate structure
def validate_json_structure(data, schema):
    errors = []
    for field in schema["required"]:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    return len(errors) == 0, errors
```

**Rollback Pattern**:
```bash
# On error, restore backup
if [ $? -ne 0 ]; then
    echo "Error detected, restoring backup..."
    cp "$BACKUP_FILE" "$ORIGINAL_FILE"
    exit 1
fi
```

**Real-World Example**: `/update` command
- Automatically backs up resume before changes
- Automatically validates JSON structure
- Automatically archives old backups
- No user confirmation needed during workflow

**Anti-Patterns to Avoid**:
- ❌ Requesting confirmation for every step
- ❌ Failing without cleanup
- ❌ Leaving partial modifications
- ❌ Not backing up before destructive changes

---

### Pattern 7: Script Parameterization

**What**: All scripts use CLI arguments instead of hardcoded values for maximum flexibility.

**Principles**:

1. **No Hardcoded Paths**:
   ```bash
   # BAD
   INPUT_FILE="/home/user/data.json"

   # GOOD
   INPUT_FILE="$1"
   if [ -z "$INPUT_FILE" ]; then
       echo "Usage: $0 <input-file>"
       exit 1
   fi
   ```

2. **Use argparse for Python**:
   ```python
   import argparse

   parser = argparse.ArgumentParser(description="Process data")
   parser.add_argument("input_file", help="Input JSON file")
   parser.add_argument("--output", help="Output file", default="output.json")
   parser.add_argument("--verbose", action="store_true", help="Verbose output")
   args = parser.parse_args()
   ```

3. **Environment Variables When Appropriate**:
   ```bash
   # For configuration that rarely changes
   VENV_PATH="${CLAUDE_VENV:-$HOME/.claude/venv}"
   DATA_DIR="${CLAUDE_DATA_DIR:-./data}"
   ```

4. **Clear Usage Messages**:
   ```bash
   if [ $# -lt 2 ]; then
       echo "Usage: $0 <input-file> <output-file> [options]"
       echo "  input-file: Path to input JSON"
       echo "  output-file: Path to output JSON"
       echo "  options: --verbose, --dry-run"
       exit 1
   fi
   ```

**When to Use**:
- **ALWAYS** - Every script should be parameterized
- Especially important for paths, filenames, and configuration
- Critical for scripts used in multiple contexts

**Benefits**:
1. **Reusability** - Same script, different contexts
2. **Testability** - Easy to test with different inputs
3. **Flexibility** - Users can customize behavior
4. **Maintainability** - Changes in one place, not throughout code

**Parameter Types**:

**Positional Arguments** (bash):
```bash
#!/bin/bash
INPUT_FILE="$1"
OUTPUT_FILE="$2"
OPTION="${3:-default_value}"
```

**Named Arguments** (Python):
```python
parser.add_argument("--input", required=True, help="Input file")
parser.add_argument("--output", required=True, help="Output file")
parser.add_argument("--mode", choices=["fast", "accurate"], default="fast")
```

**Optional Arguments**:
```bash
# With defaults
VERBOSE="${VERBOSE:-false}"
DRY_RUN="${DRY_RUN:-false}"

# Parse flags
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose) VERBOSE=true; shift ;;
        -n|--dry-run) DRY_RUN=true; shift ;;
        *) break ;;
    esac
done
```

**Real-World Example**: Parameterized resume update script
```bash
#!/bin/bash
# scripts/update-resume.sh

RESUME_FILE="$1"
JOB_POSTING="$2"
OUTPUT_FILE="${3:-$RESUME_FILE}"

if [ $# -lt 2 ]; then
    echo "Usage: $0 <resume-file> <job-posting-file> [output-file]"
    exit 1
fi

# Process with parameters
process_resume "$RESUME_FILE" "$JOB_POSTING" "$OUTPUT_FILE"
```

**Anti-Patterns to Avoid**:
- ❌ Hardcoding file paths in scripts
- ❌ Hardcoding configuration values
- ❌ No usage messages
- ❌ Assuming specific directory structure

---

### Pattern 8: Subagent Call Enforcement

**What**: A fourth behavioral gate added to the three structural gates (Pattern 4) that mechanically prevents agents from marking subagent delegation steps as completed without actually calling the Agent tool.

**Why**: The three-hook enforcement chain validates structural compliance (correct steps, correct order) but not behavioral compliance. Without this gate, an agent can mark "Delegate to BA subagent" as completed without ever spawning a subagent.

**Schema**: Todo scripts add an optional `subagent_call` field to step dicts:

```python
# Single subagent (dev.py, dev-command.py)
{"content": "Step 2: Delegate to BA subagent", ..., "subagent_call": {"agent": "ba", "subagent_type": "ba"}}

# Multiple subagents (dev-overnight.py parallel steps)
{"content": "Step 2: Explore codebase", ..., "subagent_call": [
    {"agent": "pm", "subagent_type": "pm"},
    {"agent": "specialist", "subagent_type": "architect"}
]}
```

The `subagent_call` field lives in the todo script output only. It is NOT included in TodoWrite payloads (content/activeForm/status remain unchanged). Hooks read it via `run_todo_script()`.

**How the hooks work together**:

```
Agent starts Step N (in_progress)
       |
[pretool-subagent-enforce.py] reads canonical todos
  - Step N has subagent_call? → Initialize tracking in bookmark
  - subagent_calls[N] == false? → BLOCK all tools except Agent/TodoWrite
  - Step N-1 in_progress, Step N has subagent_call? → Advisory hint
       |
Agent calls Agent tool (subagent)
       |
[posttool-subagent-track.py] fires after Agent completes
  - Sets subagent_calls[N] = true in bookmark
  - Other tools now unblocked
       |
Agent tries TodoWrite to mark Step N completed
       |
[pretool-todo-validate.py] completion guard
  - Step N has subagent_call AND subagent_calls[N] == false? → BLOCK
  - subagent_calls[N] == true? → ALLOW completion
```

**Bookmark extension**: `subagent_calls` dict keyed by step index string:

```json
{
  "command": "dev",
  "todo_acknowledged": true,
  "subagent_calls": {"1": true, "4": false, "6": false}
}
```

**How to add subagent_call to new todo scripts**:

1. Identify steps that require Agent tool invocation
2. Add `subagent_call` field to those step dicts in `get_todos()`
3. Use `{"agent": "<name>", "subagent_type": "<type>"}` for single calls
4. Use a list of dicts for parallel/multi-call steps
5. Steps without `subagent_call` are completely unaffected

**Anti-Patterns to Avoid**:
- Putting `subagent_call` in TodoWrite content/activeForm/status (canonical validation rejects it)
- Adding `subagent_call` to non-delegation steps (only steps requiring Agent tool)
- Manually editing the bookmark's `subagent_calls` field
- Skipping the Agent call and expecting the gate to open

---

### Real-World Case Study: /update Command

**Context**: Need command to analyze job postings and update resumes with tailored content.

**Patterns Applied**:

1. **Three-Party Architecture**:
   - Main agent: Parses job posting, prepares context
   - Specialist (resume-refiner-update): Analyzes fit, recommends changes
   - Main agent: Implements recommendations, saves result

2. **Specialist Subagent**:
   - Created `.claude/agents/resume-refiner-update.md`
   - Analyzes job requirements vs current resume
   - Returns JSON recommendations (not direct edits)

3. **Todo Workflow Script**:
   - Created `.claude/scripts/todo/update.py`
   - 7 workflow steps tracked
   - Progress visible to agent and user

4. **YAML Frontmatter**:
   ```yaml
   description: Analyze job posting and intelligently update resume
   allowed-tools: Task, Read, Write, Edit, Bash, Glob, Grep, TodoWrite
   argument-hint: "<job-posting-url-or-text>"
   model: claude-sonnet-4-5
   ```

5. **Complete Automation**:
   - Automatic backup before changes
   - Automatic validation of JSON structure
   - Automatic archival of old backups
   - No user confirmation needed

6. **Script Parameterization**:
   - All paths passed as arguments
   - No hardcoded values
   - Reusable across different resume files

**Results**:
- ✅ Clear separation of concerns
- ✅ Reusable specialist for future resume commands
- ✅ Consistent workflow enforcement
- ✅ Zero user interaction required
- ✅ Fully automated backup/restore

**Command Structure**:
```
Step 1: Parse job posting (URL or text)
Step 2: Read current resume
Step 3: Invoke resume-refiner-update specialist
Step 4: Receive recommendations (JSON)
Step 5: Apply recommendations to resume
Step 6: Validate updated resume
Step 7: Archive old versions, save new resume
```

**Key Takeaways**:
1. Specialist subagent enables reuse across commands
2. Todo script ensures workflow never deviates
3. Automatic backup/restore provides safety
4. Clear architecture makes debugging easy
5. Zero user interaction improves experience

**Files Created**:
- `.claude/commands/update.md` (11KB, 7 steps)
- `.claude/agents/resume-refiner-update.md` (specialist)
- `.claude/scripts/todo/update.py` (workflow tracker)

**Success Metrics**:
- 100% workflow compliance (todos enforce)
- Zero data loss (automatic backups)
- Reusable specialist (can serve other commands)
- Excellent user experience (fully automated)

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

**Detect views folder (sibling to spec)**:

If `spec_path` is not null, check `<dirname>/<spec-id>/views/manifest.json`.
If the manifest exists AND is valid JSON AND `schema_version == 1`, set:
- `views_available = true`
- `view_paths` = manifest.views (dict of agent → path)

Otherwise `views_available = false` — legacy specs without views are supported, the monolith path alone is passed to subagents with no checkpoint enforcement.

Pass per-agent view paths alongside (not in place of) `spec_path` to subagents so each receives only its slice of the 8-section monolith.

**Edge cases**:
- Empty `$ARGUMENTS` → Prompt user for requirement
- Otherwise → Pass raw text (minus --spec flag) to BA subagent in Step 2

**Keep this step lightweight** - BA subagent handles all analysis.

### Step 2: Specialist Consultation (always evaluate, never silently skip)

Before touching any specialist, you MUST evaluate each one's relevance to the issue and document the decision. Silently skipping is forbidden — skipping without assessment is itself a workflow violation.

#### Procedure (mandatory, applies to every issue)

1. For each of the 4 specialists (`ui-specialist`, `architect`, `product-owner`, `user`), produce one line:
   - `<specialist>: RELEVANT — <reason>` OR
   - `<specialist>: SKIP — <concrete reason>`
2. Call every specialist marked RELEVANT. Parallelize in a single Agent call.
3. If you cannot articulate a concrete SKIP reason, default to CALL.

#### Relevance triggers (treat as RELEVANT unless clearly unrelated)

- **ui-specialist**: any visual/UI/UX/layout/CSS/responsive/styling/icon/component-appearance issue, any "looks wrong" report, any viewport-specific bug
- **architect**: any architectural/performance/dependency/pattern-consistency/structural concern, any cross-module change
- **product-owner**: any business-logic/feature-completeness/user-flow/missing-feature question, any "should this exist" question
- **user**: any end-to-end scenario, UX friction, broken flow, or unclear-behavior report

#### Forbidden shortcuts

- "No specialists needed" without per-specialist assessment — INVALID
- Skipping all 4 by default — INVALID
- Calling all 4 when 2 clearly don't apply — wasteful (document why each skipped)

#### Record the assessment

In the orchestrator's reasoning (and in BA's context JSON when BA is invoked next), include:
```json
"specialists_assessed": {
  "ui-specialist": "RELEVANT — layout issue" | "SKIP — pure backend change",
  "architect": "...",
  "product-owner": "...",
  "user": "..."
}
```

**How to invoke** (for each RELEVANT specialist, parallelize in a single response):

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

Pass all specialist findings (and the full `specialists_assessed` block) to the BA subagent in Step 3 as additional context.

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

> If a subagent's report contains `error: blocked_code_write`, the orchestrator constructed an invalid prompt that asked the subagent to write code. Reassign the code-writing portion to a `dev` subagent.

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
  View file: <view_paths[this-agent] or null — sibling views/<agent>.md if present>
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
  View file: <view_paths[this-agent] or null — sibling views/<agent>.md if present>

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
  View file: <view_paths[this-agent] or null — sibling views/<agent>.md if present>

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
  View file: <view_paths[this-agent] or null — sibling views/<agent>.md if present>
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
  View file: <view_paths[this-agent] or null — sibling views/<agent>.md if present>
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

#### Layer-escalation gate (mandatory)

When QA rejects the dev fix, the orchestrator MUST track the layer used in
each attempt. Rules:

1. Attempt 1 may target any layer BA recommends (usually the lowest plausible
   layer).
2. If attempts 1 AND 2 both target the SAME layer (L1 / L2 / L3 / L4 / L5)
   and BOTH fail QA, iteration 3 MUST target a DIFFERENT layer. The
   orchestrator passes `layer_escalation_required: true` to BA and the BA
   MUST produce a new root-cause hypothesis at a DIFFERENT layer.
3. The orchestrator MUST record every attempt's layer in the context JSON
   under `attempts[i].target_layer`. Before iteration N, the orchestrator
   checks the last N-1 layers; if they are all equal and QA has rejected
   them all, escalation is mandatory.
4. BA's Contract D novelty-check MUST include `differs_from_all_prior_layers`
   in addition to `differs_from_all_priors`. A fix that changes L1 wording
   but stays in L1 is NOT novel under this rule.
5. If the same layer is the only one that can plausibly solve the bug
   (genuine edge case), BA MUST explicitly argue this in prose with
   evidence; the orchestrator may override the gate only after user
   confirmation.

**Why this rule exists**: In a prior incident, a bug cycled through 6
BA→Dev→QA iterations all operating on the same L1 CSS style condition.
The actual fix was L3 (data hydration). This gate forces the orchestrator
to escalate out of local optima.

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
- ✅ Command development patterns applied

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
- Command development patterns

**QA subagent verifies** (see `agents/qa.md`):
- Success criteria met
- Root cause addressed
- No regressions
- Quality standards compliance
- Integer step numbering
- Command patterns applied correctly

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

---

## Example End-to-End Workflow

**User**: `/dev-command "Create /analyze command that uses specialist subagent"`

**Step 1**: Parse requirement
- Requirement: "Create /analyze command that uses specialist subagent"

**Step 2**: Consult specialists (optional)
- No specialists needed → skip

**Step 3**: Delegate to BA subagent
- BA returns `needs_clarification` with questions about metrics and output format

**Step 4**: BA clarification loop
- Round 1: What metrics? → Complexity, maintainability, test coverage
- BA has enough clarity → returns `ready`
- BA creates: `ba-spec-20260206-120000.md` + `context-20260206-120000.json`

**Step 5**: Validate BA output
- Both files exist with required sections

**Step 6**: Dev subagent
- Created: `.claude/commands/analyze.md` (with YAML frontmatter)
- Created: `.claude/agents/code-analyzer.md` (specialist)
- Created: `.claude/scripts/todo/analyze.py` (workflow tracker)
- Applied: Three-Party Architecture pattern
- Applied: Complete Automation pattern
- Saved report: `docs/dev/dev-report-20260206-120000.json`

**Step 7-8**: QA subagent
- Verified YAML frontmatter complete
- Verified specialist returns JSON only
- Verified todo script works
- Verified all patterns applied correctly
- Status: PASS
- Saved report: `docs/dev/qa-report-20260206-120000.json`

**Step 9**: Process results
- QA passed → proceed to completion

**Step 10**: Update permissions
- Added: `SlashCommand(.claude/commands/analyze.md:*)`
- Added: `Bash(source ~/.claude/venv/bin/activate && python3 ~/.claude/scripts/todo/analyze.py:*)`

**Step 12**: Completion report
- Generated: `docs/dev/completion-20260206-120000.md`
- Presented summary to user

---

## Success Metrics

- ✅ 100% requirement clarity before development
- ✅ Root cause identified and addressed (when applicable)
- ✅ Zero hardcoded values in scripts
- ✅ QA passes within 3 iterations
- ✅ All command development patterns applied
- ✅ All standards enforced
- ✅ Complete audit trail in JSON files

---

**Remember**: You are an orchestrator. You clarify, analyze, delegate, coordinate, and verify. You do NOT implement. Let the subagents do the work.
