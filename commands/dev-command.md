---
description: Enhanced development workflow with command development best practices, Three-Party Architecture, specialist subagents, and comprehensive automation patterns
---

**CRITICAL**: Use TodoWrite to track workflow phases. Mark in_progress before each step, completed immediately after.

# Development Orchestrator for Command Development

**Philosophy**: Understand requirement fully → Find root cause → Delegate implementation → Verify quality → Iterate until perfect

This command uses multi-round inquiry to fully understand requirements, then orchestrates development through specialized subagents with continuous QA verification. Enhanced with proven command development patterns from successful implementations.

---

## Step 0: Initialize Workflow Checklist

**Load todos from**: `~/.claude/scripts/todo/dev-command.py`

Execute:
```bash
source ~/.claude/venv/bin/activate && python3 ~/.claude/scripts/todo/dev-command.py
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

## Command Development Best Practices

**This section documents proven patterns for developing slash commands, subagents, and todo workflows.**

### Overview

Developing effective slash commands requires understanding several key architectural patterns:

1. **Three-Party Architecture** - Orchestrator → Specialist → Orchestrator pattern
2. **Specialist Subagent Design** - Domain-specific consultant agents
3. **Todo Workflow Scripts** - Automated progress tracking
4. **YAML Frontmatter** - Command metadata and configuration
5. **Complete Automation** - Zero user-in-the-loop design
6. **Script Parameterization** - Flexible, reusable scripts

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

**Integration in Command**:

```markdown
## Step 0: Initialize Workflow Checklist

**Load todos from**: `~/.claude/scripts/todo/<command>.py`

Execute:
\`\`\`bash
source ~/.claude/venv/bin/activate && python3 ~/.claude/scripts/todo/<command>.py
\`\`\`

Use output to create TodoWrite with all workflow steps.

**Rules**: Mark `in_progress` before each step, `completed` after. NEVER skip steps.
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
- ❌ Skipping todo initialization (Step 0)
- ❌ Not updating todos as steps complete
- ❌ Using todos for trivial single-step commands

---

### Pattern 4: YAML Frontmatter

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

### Pattern 5: Complete Automation

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

### Pattern 6: Script Parameterization

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
Step 0: Initialize todos (via todo script)
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
  You are the dev subagent. Follow development standards precisely.

  Read context from: docs/dev/context-<timestamp>.json

  Your tasks:
  1. Read and internalize the complete context JSON
  2. Implement changes following the development approach
  3. Create parameterized scripts (no hardcoded values)
  4. Use source venv for Python (NOT python3)
  5. Reference root cause in all changes
  6. Apply Command Development Best Practices when creating commands
  7. Write implementation report to: docs/dev/dev-report-<timestamp>.json

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

  Follow all quality standards.
  "
```

**Dev subagent workflow**:
1. Reads context JSON
2. Implements changes
3. Creates scripts with parameters
4. Applies command development patterns
5. Writes implementation report JSON

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
     - Command development patterns applied correctly
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

**Step 1-2**: Multi-round clarification
- What should /analyze do? → Analyze code quality
- What metrics? → Complexity, maintainability, test coverage
- Success criteria? → Generate structured report with recommendations

**Step 3**: Git analysis
- No root cause (new feature)
- Review similar commands for patterns

**Step 4**: Build context JSON
- Saved to: `docs/dev/context-20260206-120000.json`

**Step 5**: Dev subagent
- Created: `.claude/commands/analyze.md` (with YAML frontmatter)
- Created: `.claude/agents/code-analyzer.md` (specialist)
- Created: `.claude/scripts/todo/analyze.py` (workflow tracker)
- Applied: Three-Party Architecture pattern
- Applied: Complete Automation pattern
- Saved report: `docs/dev/dev-report-20260206-120000.json`

**Step 6-7**: QA subagent
- Verified YAML frontmatter complete
- Verified specialist returns JSON only
- Verified todo script works
- Verified all patterns applied correctly
- Status: PASS
- Saved report: `docs/dev/qa-report-20260206-120000.json`

**Step 8**: Process results
- QA passed → proceed to completion

**Step 9**: Update permissions
- Added: `SlashCommand(.claude/commands/analyze.md:*)`
- Added: `Bash(source ~/.claude/venv/bin/activate && python3 ~/.claude/scripts/todo/analyze.py:*)`

**Step 11**: Completion report
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
