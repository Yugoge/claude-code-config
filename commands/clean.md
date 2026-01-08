---
description: Aggressive project cleanup - normalize docs structure, archive everything, delete one-time scripts/tests
---

# Clean Command Orchestrator

Aggressive project cleanup and normalization with orchestrated multi-agent workflow.

---

## Philosophy

Enforce strict organization standards through systematic inspection and selective cleanup.

---

## Workflow Overview

This command orchestrates three specialized subagents:

1. **cleanliness-inspector**: Detects file organization issues
2. **style-inspector**: Audits development standards compliance
3. **cleaner**: Executes approved cleanup actions

All agents communicate via JSON in `docs/clean/`.

---

## Execution Steps

### Step 1: Initialize Workflow

Load TodoList checklist:

```bash
source ~/.claude/venv/bin/activate && python3 ~/.claude/scripts/todo/clean.py
```

Set up working directory:

```bash
mkdir -p docs/clean/
REQUEST_ID="clean-$(date +%Y%m%d-%H%M%S)"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
```

**Documentation Structure Rules**:

Root directory .md files:
- **ALLOWED**: README.md, ARCHITECTURE.md, CLAUDE.md (official Claude Code files, do not move)
- **MOVE TO docs/**: All other .md files in project root

docs/ subdirectory structure:
- `docs/guides/` - User guides, tutorials, how-to documents
- `docs/reference/` - Technical docs, API reference, registries
- `docs/planning/` - Planning docs, roadmaps, design proposals
- `docs/reports/` - Completion reports, summaries, QA reports
- `docs/archive/YYYY-MM/` - Historical docs (by last modified month)
- `docs/dev/` - Development workflow JSONs only (no .md files)
- `docs/clean/` - Clean workflow JSONs only (no .md files)
- `docs/INDEX.md` - Auto-generated index (created by cleaner agent)

### Step 2: Scan Project Structure

Detect project type and gather baseline info:

```bash
PROJECT_ROOT=$(pwd)
SCAN_RESULT=$(~/.claude/scripts/scan-project.sh "$PROJECT_ROOT")
PROJECT_TYPE=$(echo "$SCAN_RESULT" | jq -r '.project_type')
TOTAL_FILES=$(echo "$SCAN_RESULT" | jq -r '.file_counts.total')
DOC_FILES=$(echo "$SCAN_RESULT" | jq -r '.file_counts.docs')
SCRIPT_FILES=$(echo "$SCAN_RESULT" | jq -r '.file_counts.scripts')
TEST_FILES=$(echo "$SCAN_RESULT" | jq -r '.file_counts.tests')
```

### Step 3: Build Inspection Context

Create comprehensive JSON context for inspectors:

```json
{
  "request_id": "clean-YYYYMMDD-HHMMSS",
  "timestamp": "ISO-8601",
  "orchestrator": {
    "requirement": "Inspect project for file organization issues and development standards violations",
    "analysis": {
      "project_root": "/absolute/path/to/project",
      "project_type": "Python|Node.js|Go|Generic",
      "constraints": [
        "preserve functional files",
        "safety first - never delete without confirmation",
        "archive docs rather than delete"
      ]
    }
  },
  "full_context": {
    "codebase_state": {
      "git_status": "output of git status",
      "current_branch": "branch name",
      "recent_commits": ["commit log"]
    },
    "directory_structure": "tree output or ls -R",
    "file_counts": {
      "total": 0,
      "docs": 0,
      "scripts": 0,
      "tests": 0
    }
  },
  "parameters": {
    "docs_directory": "docs/",
    "scripts_directory": "scripts/",
    "tests_directory": "tests/"
  }
}
```

Save to: `docs/clean/context-{REQUEST_ID}.json`

### Step 4: Rule Inspection and README Updates

**CRITICAL**: This step MUST execute BEFORE Step 5 on EVERY /clean run.

Run rule-inspector to update folder documentation with recent changes:

```bash
# Discover all folders dynamically
FOLDERS=$(~/.claude/scripts/discover-folders.sh "$PROJECT_ROOT")

echo "Running rule inspection with freshness check..." >&2

# Create context for rule-inspector
RULE_CONTEXT="docs/clean/rule-context-${REQUEST_ID}.json"

jq -n \
  --arg request_id "$REQUEST_ID" \
  --arg timestamp "$TIMESTAMP" \
  --arg project_root "$PROJECT_ROOT" \
  --argjson folders "$(echo "$FOLDERS" | jq -R . | jq -s .)" \
  '{
    request_id: $request_id,
    timestamp: $timestamp,
    orchestrator: {
      requirement: "Discover and document folder organization rules with freshness check",
      analysis: {
        project_root: $project_root,
        folders_to_analyze: $folders,
        freshness_check: true
      }
    },
    full_context: {
      codebase_state: {
        git_status: "output of git status",
        current_branch: "branch name"
      },
      discovered_folders: $folders
    },
    parameters: {
      freshness_check: true,
      update_stale_readmes: true
    }
  }' > "$RULE_CONTEXT"

# Invoke rule-inspector subagent with freshness check
~/.claude/scripts/orchestrator.sh rule-inspect "$RULE_CONTEXT"

echo "✅ Rule inspection completed - READMEs updated with recent changes" >&2

# VERIFICATION CHECKPOINT: Ensure rule inspection completed
if [[ ! -f "docs/clean/rule-context-${REQUEST_ID}.json" ]]; then
  echo "❌ ERROR: Rule inspection failed! Cannot proceed to cleanliness inspection." >&2
  exit 1
fi
```

**What this step does**:
- Analyzes Git history for ALL folders (including root directory)
- Checks README freshness (compares README mtime vs folder content mtime)
- Updates stale READMEs (> 7 days old: full update, 3-7 days: incremental)
- **Special handling for root documentation files (README.md and ARCHITECTURE.md)**: Checks against structural changes, updates project-level overview (not folder rules)
- Creates README for folders that lack one
- Regenerates INDEX.md with current file inventory
- Applies recency weighting (recent commits weighted 3x higher)

**Root documentation special processing** (ref: commit 590881d5 fix):
- Root `README.md` and `ARCHITECTURE.md` describe entire project structure, not folder-specific rules
- Freshness check compares against last structural change (new folders, archived folders, major commits)
- Update triggers when structural changes > 7 days old compared to documentation files
- README preserves user-written sections (Installation, Quick Start, Features), only regenerates Structure and Git Analysis
- ARCHITECTURE preserves user-written sections (Design Principles), only regenerates Directory Structure, Data Flow, and Git Analysis
- Different templates from subfolder READMEs (project overview, not organization rules)

**Verification**: Before proceeding to Step 5, you MUST confirm:
- ✅ Rule inspection completed (rule-context JSON exists)
- ✅ READMEs updated or confirmed fresh

**Root cause reference**: This fixes the issue from commands/clean.md lines 151-188 where rule-inspector only ran conditionally (NEEDS_INIT check), causing READMEs to become stale as repository evolved. Now runs on EVERY execution with freshness detection.

---

### Step 5: Invoke Cleanliness Inspector

Delegate to cleanliness-inspector subagent:

```bash
~/.claude/scripts/orchestrator.sh clean-inspect docs/clean/context-{REQUEST_ID}.json
```

Cleanliness inspector reads context, performs inspection, writes:
- `docs/clean/cleanliness-report-{REQUEST_ID}.json`

Expected output structure:

```json
{
  "request_id": "clean-YYYYMMDD-HHMMSS",
  "timestamp": "ISO-8601",
  "inspector": "cleanliness-inspector",
  "findings": {
    "misplaced_docs": [],
    "naming_violations": [],
    "archive_candidates": [],
    "dev_context_files": [],
    "temp_files": [],
    "duplicate_scripts": [],
    "duplicate_tests": [],
    "non_functional_files": []
  },
  "summary": {
    "total_issues": 0,
    "critical": 0,
    "major": 0,
    "minor": 0,
    "estimated_space_saved": "XX MB"
  }
}
```

### Step 6: Invoke Style Inspector

Delegate to style-inspector subagent:

```bash
~/.claude/scripts/orchestrator.sh clean-inspect docs/clean/context-{REQUEST_ID}.json
```

Style inspector reads context, audits standards, writes:
- `docs/clean/style-report-{REQUEST_ID}.json`

Expected output structure:

```json
{
  "request_id": "clean-YYYYMMDD-HHMMSS",
  "timestamp": "ISO-8601",
  "inspector": "style-inspector",
  "violations": [
    {
      "standard": "no-hardcoded-domains",
      "severity": "critical|major|minor",
      "location": "file:line",
      "finding": "description",
      "recommendation": "how to fix"
    }
  ],
  "summary": {
    "standards_checked": 10,
    "violations_found": 0,
    "critical": 0,
    "major": 0,
    "minor": 0
  }
}
```

### Step 7: Merge Inspection Reports

Combine both reports using orchestrator:

```bash
~/.claude/scripts/orchestrator.sh clean-merge-reports \
  docs/clean/context-with-reports-{REQUEST_ID}.json
```

Orchestrator merges and writes:
- `docs/clean/combined-report-{REQUEST_ID}.json`

### Step 8: Present Combined Report to User

Format and display findings:

```markdown
# Cleanup Analysis Report

**Project**: <project_name>
**Type**: <project_type>
**Generated**: <timestamp>

## File Organization Issues (Cleanliness Inspector)

### Critical Issues: X
- <critical findings>

### Major Issues: Y
- <major findings>

### Minor Issues: Z
- <minor findings>

## Development Standards Violations (Style Inspector)

### Critical Violations: X
- <critical violations>

### Major Violations: Y
- <major violations>

### Minor Violations: Z
- <minor violations>

## Summary

- Total issues: X
- Estimated space to free: XX MB
- Files to move: Y
- Files to archive: Z
- Files to delete: W
- Style fixes: V

## Cleanup Options

1. Execute all recommended actions (aggressive)
2. Execute only file organization (conservative)
3. Execute only critical/major issues
4. Review and approve individually (interactive)
5. Cancel and generate report only
```

### Step 9: Collect User Approval

Based on user selection, build approval context:

**Option 1: Execute all** (auto-approve everything)

**Option 2: File organization only** (approve cleanliness findings, skip style)

**Option 3: Critical/major only** (filter by severity)

**Option 4: Interactive** (ask for each action)

**Option 5: Report only** (skip to completion report)

Generate approval JSON:

```json
{
  "request_id": "clean-YYYYMMDD-HHMMSS",
  "timestamp": "ISO-8601",
  "user_approvals": {
    "approved_actions": [
      {
        "action_id": "misplace_doc_1",
        "action": "move",
        "source": "./SETUP.md",
        "destination": "docs/setup.md",
        "approved": true
      }
    ],
    "rejected_actions": [
      {
        "action_id": "delete_script_1",
        "action": "delete",
        "file": "scripts/test-important.sh",
        "approved": false,
        "reason": "Still needed for testing"
      }
    ]
  }
}
```

Save to: `docs/clean/user-approvals-{REQUEST_ID}.json`

### Step 10: Create Safety Checkpoint

Before execution, create git checkpoint:

```bash
git add -A
git commit -m "checkpoint: Before aggressive cleanup on $(date +%Y-%m-%d)"

# Record checkpoint in context
CHECKPOINT_COMMIT=$(git rev-parse HEAD)
~/.claude/scripts/orchestrator.sh record-checkpoint \
  docs/clean/context-with-reports-{REQUEST_ID}.json \
  "$CHECKPOINT_COMMIT"
```

### Step 11: Invoke Cleaner with Approvals

Merge approvals into context:

```bash
jq -s '.[0] * {user_approvals: .[1].user_approvals}' \
  docs/clean/context-with-reports-{REQUEST_ID}.json \
  docs/clean/user-approvals-{REQUEST_ID}.json \
  > docs/clean/context-with-approvals-{REQUEST_ID}.json
```

Delegate to cleaner subagent:

```bash
~/.claude/scripts/orchestrator.sh clean-execute \
  docs/clean/context-with-approvals-{REQUEST_ID}.json
```

Cleaner reads approvals, executes actions, writes:
- `docs/clean/cleanup-execution-{REQUEST_ID}.json`

Expected output structure:

```json
{
  "request_id": "clean-YYYYMMDD-HHMMSS",
  "timestamp": "ISO-8601",
  "cleaner": {
    "status": "completed|partial|blocked",
    "actions_completed": [],
    "actions_failed": [],
    "actions_skipped": [],
    "summary": {
      "total_actions": 10,
      "successful": 8,
      "failed": 0,
      "skipped": 2,
      "files_moved": 3,
      "files_archived": 2,
      "files_deleted": 3,
      "space_freed": "15 MB"
    },
    "git_status": {
      "checkpoint_commit": "abc123",
      "cleanup_commit": "def456",
      "files_staged": 8,
      "ready_for_review": true
    }
  }
}
```

### Step 12: Verify Cleanup Results

Review git changes:

```bash
git status
git diff --stat HEAD~1
```

Present verification summary:

```markdown
# Cleanup Execution Results

**Status**: <completed|partial|blocked>
**Actions**: X successful, Y failed, Z skipped

## Changes Made

- Moved X files to correct locations
- Archived Y old documents
- Deleted Z temp files
- Fixed W style violations
- Updated .gitignore

## Git Status

- Checkpoint commit: <hash>
- Cleanup commit: <hash>
- Files changed: X
- Ready for review: Yes

## Next Steps

1. Review changes: `git diff HEAD~1`
2. If satisfied: Changes already committed
3. If not satisfied: `git reset --hard <checkpoint_commit>`
4. See detailed report: docs/clean/completion-{REQUEST_ID}.md
```

### Step 13: Generate Completion Report

Create comprehensive completion report:

Save to: `docs/clean/completion-{REQUEST_ID}.md`

```markdown
# Cleanup Completion Report

**Request ID**: clean-YYYYMMDD-HHMMSS
**Project**: <project_path>
**Type**: <project_type>
**Executed**: <timestamp>
**Status**: <completed|partial|blocked>

---

## Inspection Summary

### Cleanliness Issues Found
- Total: X
- Critical: Y
- Major: Z
- Minor: W

### Style Violations Found
- Total: X
- Critical: Y
- Major: Z
- Minor: W

---

## Actions Executed

### File Organization (X actions)
- Moved Y misplaced docs to docs/
- Archived Z old documents to docs/archive/
- Deleted W temp files
- Renamed V files to kebab-case

### Style Fixes (X actions)
- Fixed Y hardcoded URLs
- Fixed Z python3 calls to use venv
- Fixed W naming violations

---

## Results

### Successful (X actions)
<list of successful actions>

### Failed (Y actions)
<list of failed actions with reasons>

### Skipped (Z actions)
<list of skipped actions with reasons>

---

## Summary Statistics

- Space freed: XX MB
- Files moved: Y
- Files archived: Z
- Files deleted: W
- Style fixes: V
- Git commits: 2 (checkpoint + cleanup)

---

## Git Information

- Checkpoint commit: <hash>
- Cleanup commit: <hash>
- Branch: <branch>
- Files changed: X
- Rollback command: `git reset --hard <checkpoint_commit>`

---

## Related Files

- Context: docs/clean/context-{REQUEST_ID}.json
- Cleanliness report: docs/clean/cleanliness-report-{REQUEST_ID}.json
- Style report: docs/clean/style-report-{REQUEST_ID}.json
- Combined report: docs/clean/combined-report-{REQUEST_ID}.json
- User approvals: docs/clean/user-approvals-{REQUEST_ID}.json
- Execution report: docs/clean/cleanup-execution-{REQUEST_ID}.json

---

**Root Cause**: Project files evolved organically without consistent organization standards. Manual cleanup was error-prone and time-consuming.

**Solution**: Implemented orchestrated multi-agent cleanup workflow with automated detection, user approval, and safe execution.

**Next Steps**: Run /clean periodically to maintain organization standards.
```

---

## Safety Features

### Git Checkpoint
- Automatic commit before cleanup
- Easy rollback with `git reset --hard <checkpoint>`

### User Approval
- No automatic deletion without confirmation
- Interactive approval for all actions
- Clear categorization by severity

### Reference Detection
- Uses `check-file-references.sh` for safety
- Preserves files with functional references
- Archives instead of deleting when uncertain

### Incremental Execution
- Commits after each category
- Continues on failure
- Reports all results

---

## Quality Standards

### Agent Communication
- All via JSON in docs/clean/
- Structured schemas enforced
- Clear request_id tracking

### Documentation
- Comprehensive reports generated
- Git rationale included
- Easy to audit and review

### Orchestration Pattern
- Follows /dev workflow model
- Specialized subagents
- Clear separation of concerns

---

## Helper Scripts Used

- `~/.claude/scripts/check-file-references.sh` - Reference detection
- `~/.claude/scripts/normalize-doc-names.sh` - Naming validation
- `~/.claude/scripts/update-gitignore.sh` - Gitignore updates
- `~/.claude/scripts/orchestrator.sh` - Agent coordination
- `~/.claude/scripts/todo/clean.py` - Workflow checklist

---

## Usage

Execute in any project directory:

```bash
cd /path/to/project
# In Claude Code, invoke: /clean
```

The orchestrator will guide you through all steps interactively.

---

**Remember**: This is an aggressive cleanup command with safety features. First-time users should select "Report only" mode to review findings before executing cleanup actions.
