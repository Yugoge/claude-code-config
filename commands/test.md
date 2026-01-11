---
description: Test validation workflow with edge case detection, systematic validation, and quality enforcement
---

# Test Command Orchestrator

Comprehensive testing and validation framework with orchestrated multi-agent workflow.

---

## Philosophy

Enforce documented standards through automated validation. Prevent recurring edge cases discovered in git history analysis.

---

## Workflow Overview

This command orchestrates two specialized subagents:

1. **test-validator**: Validates test syntax, dependencies, and quality
2. **test-executor**: Executes script-based and AI instruction-based tests

All agents communicate via JSON in `tests/reports/`.

---

## Execution Steps

### Step 1: Initialize Workflow and Load TodoList

Load TodoList checklist:

```bash
source ~/.claude/venv/bin/activate && python3 ~/.claude/scripts/todo/test.py
```

Set up working directory:

```bash
mkdir -p tests/reports/
REQUEST_ID="test-$(date +%Y%m%d-%H%M%S)"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
```

**Test folder structure**:

If `tests/` directory doesn't exist, initialize it:

```bash
if [[ ! -d "tests" ]]; then
  echo "Test directory not found. Initializing tests folder structure..."
  mkdir -p tests/{scripts,instructions,data/fixtures,data/mocks,reports}

  # Copy template README
  cp ~/.claude/tests/README.md tests/README.md
  cp ~/.claude/tests/INDEX.md tests/INDEX.md
  cp ~/.claude/tests/instructions/*.md tests/instructions/

  echo "✅ Test folder initialized. Add validators to tests/scripts/"
fi
```

### Step 2: Analyze Git History for Edge Cases

Analyze git history to identify real edge cases from bug fix commits:

```bash
# Run git edge case analyzer
~/.claude/scripts/analyze-git-edge-cases.sh \
  --project-root "$(pwd)" \
  --since-date "90.days.ago" \
  --output "docs/test/edge-case-analysis.json"

# Check if analysis succeeded
if [[ $? -eq 0 ]]; then
  EDGE_CASES_FOUND=$(jq -r '.summary.total_edge_cases' docs/test/edge-case-analysis.json)
  echo "✅ Found $EDGE_CASES_FOUND edge cases from git history"
else
  echo "⚠️  Git edge case analysis failed - proceeding without cleanup"
fi
```

This analyzer:
- Searches git history for commits with keywords: fix, bug, error, issue, problem
- Extracts edge case identifiers (EC001, EC002, etc.)
- Groups by edge case and counts occurrences
- Generates JSON analysis for validator cleanup

### Step 3: Migrate test/ to tests/ if Needed

Check if old `test/` folder exists and migrate to `tests/`:

```bash
if [[ -d "test" ]] && [[ ! -d "tests" || "test" -nt "tests" ]]; then
  echo "Found test/ folder - migrating to tests/ (Python standard naming)"

  ~/.claude/scripts/migrate-test-to-tests.sh --project-root "$(pwd)"

  if [[ $? -eq 0 ]]; then
    echo "✅ Migration complete - review tests/ folder"
    echo "   Remove test/ folder when ready: rm -rf test/"
  fi
elif [[ -d "test" ]] && [[ -d "tests" ]]; then
  echo "⚠️  Both test/ and tests/ exist - manual review recommended"
  echo "   Run: ~/.claude/scripts/migrate-test-to-tests.sh --project-root $(pwd)"
fi
```

This migration:
- Merges all content from test/ into tests/
- Preserves files, avoids overwriting different content
- Creates backups for conflicts
- Idempotent (safe to run multiple times)

### Step 4: Cleanup tests/ Based on Git History

Remove validators that don't correspond to edge cases found in git history:

```bash
if [[ -f "docs/test/edge-case-analysis.json" ]] && [[ -d "tests" ]]; then
  echo "Cleaning tests/ folder based on git history analysis..."

  ~/.claude/scripts/cleanup-tests-folder.sh \
    --project-root "$(pwd)" \
    --edge-case-analysis "docs/test/edge-case-analysis.json"

  if [[ $? -eq 0 ]]; then
    echo "✅ Tests folder cleanup complete"
  fi
else
  echo "⚠️  Skipping cleanup - missing edge case analysis or tests/ folder"
fi
```

This cleanup:
- Preserves validators matching edge cases from git history
- Removes validators for hypothetical edge cases not in git
- Always preserves reports/ and data/ folders
- Maintains documentation files (README.md, INDEX.md)

### Step 5: Check Test Folder Exists

Verify tests infrastructure in place:

```bash
# Check required directories
if [[ ! -d "tests/scripts" ]] || [[ ! -d "tests/reports" ]]; then
  echo "❌ ERROR: Test folder structure incomplete" >&2
  echo "Run Step 1 initialization or manually create tests/ directory" >&2
  exit 1
fi

# Count available validators
SCRIPT_VALIDATORS=$(find tests/scripts -name "validate-*.py" 2>/dev/null | wc -l)
INSTRUCTION_VALIDATORS=$(find tests/instructions -name "*.md" -not -name "*guide.md" 2>/dev/null | wc -l)
TOTAL_VALIDATORS=$((SCRIPT_VALIDATORS + INSTRUCTION_VALIDATORS))

echo "Found $TOTAL_VALIDATORS validators ($SCRIPT_VALIDATORS scripts, $INSTRUCTION_VALIDATORS instructions)"

if [[ $TOTAL_VALIDATORS -eq 0 ]]; then
  echo "⚠️  WARNING: No validators found in tests/scripts/ or tests/instructions/" >&2
  echo "Create validators based on edge case analysis in docs/test/edge-case-analysis.json" >&2
  exit 1
fi
```

### Step 6: Discover Validators

Scan tests directory for available validators:

```bash
# Discover script-based validators
SCRIPT_VALIDATORS=$(find tests/scripts -name "validate-*.py" -type f 2>/dev/null)

# Discover AI instruction-based validators
INSTRUCTION_VALIDATORS=$(find tests/instructions -name "*.md" -type f -not -name "*guide.md" 2>/dev/null)

# Parse validator metadata (edge case, priority)
# Extract from file headers using head/grep
# Build validator registry
```

Example validator registry:

```json
{
  "validators": [
    {
      "type": "script",
      "path": "tests/scripts/validate-venv-usage.py",
      "name": "validate-venv-usage",
      "edge_case": "EC002",
      "priority": "critical",
      "description": "Venv usage violations (8 instances)"
    },
    {
      "type": "instruction",
      "path": "tests/instructions/claude-md-protection.md",
      "name": "claude-md-protection",
      "edge_case": "EC001",
      "priority": "high",
      "description": "CLAUDE.md protection validation"
    }
  ]
}
```

Save to: `tests/reports/validator-registry-{REQUEST_ID}.json`

### Step 7: Build Validation Context

Create comprehensive JSON context for validator subagent:

```json
{
  "request_id": "test-YYYYMMDD-HHMMSS",
  "timestamp": "ISO-8601",
  "orchestrator": {
    "command": "test",
    "phase": "validation",
    "requirement": "Validate test syntax, dependencies, and quality before execution"
  },
  "context": {
    "project_root": "/absolute/path/to/project",
    "test_directory": "/absolute/path/to/project/tests",
    "venv_path": "~/.claude/venv",
    "validators": [
      {
        "type": "script",
        "path": "tests/scripts/validate-venv-usage.py",
        "edge_case": "EC002",
        "priority": "critical"
      }
    ]
  },
  "validation_criteria": {
    "syntax": ["Python syntax valid", "No import errors", "Argparse defined"],
    "dependencies": ["All imports available in venv", "No circular dependencies"],
    "quality": ["Exit codes documented", "JSON output format", "Error handling present"],
    "edge_cases": ["Prevents documented edge case", "Covers patterns from git analysis"]
  }
}
```

Save to: `tests/reports/validation-context-{REQUEST_ID}.json`

### Step 8: Invoke Test Validator

Delegate to test-validator subagent:

```bash
# Validator reads context, checks all validators, writes validation report
# This is conceptual - in practice, the agent performs validation inline
```

Test validator performs:

1. **Syntax validation**: Python scripts parse correctly, no syntax errors
2. **Dependency check**: All imports available in venv
3. **Quality check**: Exit codes documented, JSON output format, error handling
4. **Edge case verification**: Validator prevents documented edge case from analysis

Expected output: `tests/reports/validation-report-{REQUEST_ID}.json`

```json
{
  "request_id": "test-YYYYMMDD-HHMMSS",
  "timestamp": "ISO-8601",
  "validator": {
    "status": "pass|fail",
    "validators_checked": 10,
    "syntax_errors": [],
    "dependency_errors": [],
    "quality_issues": [],
    "edge_case_coverage": {
      "total_edge_cases": 8,
      "covered_by_validators": 8,
      "uncovered": []
    },
    "summary": {
      "valid": 10,
      "invalid": 0,
      "warnings": 0
    }
  }
}
```

### Step 9: Process Validation Results

Check validation report status:

```bash
VALIDATION_STATUS=$(jq -r '.validator.status' tests/reports/validation-report-${REQUEST_ID}.json)

if [[ "$VALIDATION_STATUS" == "fail" ]]; then
  echo "❌ Validation failed. Fix issues before execution:" >&2
  jq -r '.validator.syntax_errors[]' tests/reports/validation-report-${REQUEST_ID}.json
  jq -r '.validator.dependency_errors[]' tests/reports/validation-report-${REQUEST_ID}.json
  jq -r '.validator.quality_issues[]' tests/reports/validation-report-${REQUEST_ID}.json
  exit 1
fi

echo "✅ Validation passed. Proceeding to execution..."
```

**Decision tree**:

```
IF validation.status == "pass":
  → Proceed to Step 10 (Build Execution Context)

ELIF validation.status == "fail":
  → Present errors to user
  → Offer to fix automatically OR exit
  → If fix: Apply fixes → Re-validate (max 3 attempts)
  → If exit: Stop workflow

```

### Step 10: Build Execution Context

Create comprehensive JSON context for executor subagent:

```json
{
  "request_id": "test-YYYYMMDD-HHMMSS",
  "timestamp": "ISO-8601",
  "orchestrator": {
    "command": "test",
    "phase": "execution",
    "requirement": "Execute all validated tests and generate comprehensive report"
  },
  "context": {
    "project_root": "/absolute/path/to/project",
    "test_directory": "/absolute/path/to/project/tests",
    "venv_path": "~/.claude/venv",
    "validators": [
      {
        "type": "script",
        "path": "tests/scripts/validate-venv-usage.py",
        "edge_case": "EC002",
        "priority": "critical"
      }
    ]
  },
  "parameters": {
    "fail_fast": false,
    "verbose": true,
    "report_path": "tests/reports/execution-report-{REQUEST_ID}.json"
  },
  "validation_report": {
    "status": "pass",
    "validators_checked": 10,
    "all_valid": true
  }
}
```

Save to: `tests/reports/execution-context-{REQUEST_ID}.json`

### Step 11: Create Safety Checkpoint

Before execution, create git checkpoint:

```bash
# Check if there are uncommitted changes
if [[ -n $(git status --porcelain) ]]; then
  echo "Creating safety checkpoint before test execution..."
  git add -A
  git commit -m "checkpoint: Before test execution on $(date +%Y-%m-%d)"

  CHECKPOINT_COMMIT=$(git rev-parse HEAD)
  echo "✅ Checkpoint created: $CHECKPOINT_COMMIT"
  echo "   Rollback command: git reset --hard $CHECKPOINT_COMMIT"
else
  echo "✅ No uncommitted changes, skipping checkpoint"
  CHECKPOINT_COMMIT=$(git rev-parse HEAD)
fi

# Record checkpoint in context
jq --arg commit "$CHECKPOINT_COMMIT" \
  '.context.checkpoint_commit = $commit' \
  tests/reports/execution-context-${REQUEST_ID}.json \
  > tests/reports/execution-context-${REQUEST_ID}.json.tmp
mv tests/reports/execution-context-${REQUEST_ID}.json.tmp tests/reports/execution-context-${REQUEST_ID}.json
```

### Step 12: Invoke Test Executor

Delegate to test-executor subagent using Task tool:

```
Use Task tool with:
- subagent_type: "test-executor"
- description: "Execute validated tests"
- prompt: "
  You are the test-executor subagent. Follow agents/test-executor.md instructions precisely.

  Read execution context from: tests/reports/execution-context-${REQUEST_ID}.json

  Your tasks:
  1. Read and validate execution context JSON
  2. Execute all script-based validators (tests/scripts/validate-*.py)
  3. Execute all AI instruction-based validators (tests/instructions/*.md)
  4. Capture results, exit codes, timing for each validator
  5. Aggregate summary statistics (total/passed/failed/errors)
  6. Analyze failed tests and generate recommendations
  7. Write execution report to: tests/reports/execution-report-${REQUEST_ID}.json

  Execution requirements:
  - Activate venv: source ~/.claude/venv/bin/activate
  - Pass --project-root parameter to all script validators
  - Capture stdout (JSON), stderr (errors), exit codes
  - Timeout: 30 seconds per validator
  - Continue execution even if individual tests fail (unless fail_fast=true)
  - Generate comprehensive execution report with all results

  Follow all execution procedures from agents/test-executor.md.
  "
```

Test executor performs:

1. **Script-based tests**: Execute each `tests/scripts/validate-*.py` with `--project-root`
2. **AI instruction-based tests**: Read instruction, gather context, perform validation
3. **Capture results**: Exit codes, JSON output, execution time
4. **Aggregate summary**: Total/passed/failed/errors, edge cases prevented

Expected output: `tests/reports/execution-report-{REQUEST_ID}.json`

```json
{
  "request_id": "test-YYYYMMDD-HHMMSS",
  "timestamp": "ISO-8601",
  "executor": {
    "status": "completed|partial|blocked",
    "execution_started": "ISO-8601",
    "execution_completed": "ISO-8601",
    "total_duration_seconds": 10.5,
    "results": [
      {
        "validator": "validate-venv-usage",
        "type": "script",
        "edge_case": "EC002",
        "priority": "critical",
        "execution": {
          "started_at": "ISO-8601",
          "completed_at": "ISO-8601",
          "duration_seconds": 1.23,
          "exit_code": 0,
          "status": "pass"
        },
        "result": {
          "status": "pass",
          "violations": [],
          "summary": {
            "total_files_checked": 10,
            "violations_found": 0
          }
        }
      }
    ],
    "summary": {
      "total_tests": 10,
      "passed": 8,
      "failed": 2,
      "errors": 0,
      "pass_rate": 80.0,
      "edge_cases_prevented": 8,
      "priority_breakdown": {
        "critical": {"passed": 3, "failed": 2},
        "high": {"passed": 2, "failed": 0},
        "medium": {"passed": 3, "failed": 0}
      }
    },
    "failed_tests": [
      {
        "validator": "validate-venv-usage",
        "edge_case": "EC002",
        "violations_count": 3,
        "severity": "critical",
        "files_affected": ["settings.json", "commands/clean.md"],
        "recommendation": "Fix venv usage: use 'source ~/.claude/venv/bin/activate && python3' pattern"
      }
    ]
  }
}
```

### Step 13: Process Execution Results

Read execution report and determine next action:

```bash
EXEC_STATUS=$(jq -r '.executor.status' tests/reports/execution-report-${REQUEST_ID}.json)
TOTAL_TESTS=$(jq -r '.executor.summary.total_tests' tests/reports/execution-report-${REQUEST_ID}.json)
PASSED=$(jq -r '.executor.summary.passed' tests/reports/execution-report-${REQUEST_ID}.json)
FAILED=$(jq -r '.executor.summary.failed' tests/reports/execution-report-${REQUEST_ID}.json)
ERRORS=$(jq -r '.executor.summary.errors' tests/reports/execution-report-${REQUEST_ID}.json)

echo "Test execution completed: $PASSED/$TOTAL_TESTS passed"

if [[ $FAILED -gt 0 ]]; then
  echo "⚠️  $FAILED tests failed"
fi

if [[ $ERRORS -gt 0 ]]; then
  echo "❌ $ERRORS tests had errors"
fi
```

**Decision tree**:

```
IF executor.status == "completed" AND failed == 0 AND errors == 0:
  → All tests passed → Skip to Step 16 (Generate Success Report)

ELIF executor.status == "completed" AND failed > 0:
  → Tests failed → Proceed to Step 14 (Present Failures)

ELIF executor.status == "partial":
  → Some tests couldn't run → Proceed to Step 14 (Present Failures)

ELIF executor.status == "blocked":
  → Execution blocked → Present error → Exit
```

### Step 14: Present Test Failures to User

Format and display failures:

```markdown
# Test Execution Report

**Project**: <project_name>
**Tests Run**: <total_tests>
**Status**: <passed>/<total> passed (<pass_rate>%)

## ❌ Failed Tests (<failed> tests)

### Critical Priority (<count> failures)

#### EC002: Venv Usage Violations
**Validator**: validate-venv-usage.py
**Violations**: 3 files
**Affected Files**:
- settings.json:42
- commands/clean.md:36
- commands/dev.md:23

**Recommendation**: Use `source ~/.claude/venv/bin/activate && python3` pattern for all Python invocations

**Fix Command**:
```bash
# Option 1: Manual fix
# Edit each file and update venv usage

# Option 2: Automated fix (if available)
./tests/scripts/fix-venv-usage.sh --project-root .
```

---

### High Priority (<count> failures)

#### EC001: CLAUDE.md Protection
**Validator**: claude-md-protection
**Violations**: 1 file
**Affected Files**:
- agents/cleanliness-inspector.md:1050

**Recommendation**: Add CLAUDE.md to official file allow-list

---

## ✅ Passed Tests (<passed> tests)

- validate-step-numbering (EC004) - No decimal steps found
- validate-chinese-content (EC006) - No Chinese in functional code
- validate-file-naming (EC007) - All files use kebab-case
- validate-debug-file-age (EC008) - No old debug files
- validate-optionality-language (EC005) - No ambiguous optionality

---

## 📊 Summary

- **Total Tests**: <total>
- **Pass Rate**: <pass_rate>%
- **Edge Cases Prevented**: <covered> / 8
- **Execution Time**: <duration> seconds

## 🎯 Next Steps

1. Review failed tests above
2. Apply recommended fixes
3. Re-run tests: `/test`
4. When all pass, proceed with confidence

## 📁 Detailed Reports

- Validation: tests/reports/validation-report-{REQUEST_ID}.json
- Execution: tests/reports/execution-report-{REQUEST_ID}.json
- Registry: tests/reports/validator-registry-{REQUEST_ID}.json
```

### Step 15: Collect User Decision

Based on failures, offer options:

```markdown
## Test Execution Options

**Current Status**: {failed} tests failed

1. **Fix failures manually** - Review recommendations and update files
2. **Apply automated fixes** (if available) - Run fix scripts
3. **View detailed report** - Inspect JSON reports for full context
4. **Ignore failures** - Generate report and exit (NOT recommended)
5. **Cancel** - Exit without report

Select option [1-5]:
```

**Option 1: Fix manually**
- User makes changes
- Offer to re-run tests
- If re-run → Return to Step 10 (Execution)

**Option 2: Apply automated fixes**
- Check if fix scripts exist for failed validators
- Run fix scripts with user approval
- Re-run tests automatically
- If still fail → Show remaining failures

**Option 3: View detailed report**
- Display JSON report paths
- User inspects manually
- Return to option selection

**Option 4: Ignore failures**
- Proceed to Step 16 with failures noted
- NOT recommended for critical failures

**Option 5: Cancel**
- Exit workflow
- Preserve reports for manual review

### Step 16: Generate Completion Report

Create comprehensive completion report:

Save to: `tests/reports/completion-{REQUEST_ID}.md`

```markdown
# Test Execution Completion Report

**Request ID**: test-YYYYMMDD-HHMMSS
**Project**: <project_path>
**Executed**: <timestamp>
**Status**: <pass|fail>

---

## Execution Summary

### Validation Phase
- **Status**: PASS
- **Validators Checked**: 10
- **Syntax Errors**: 0
- **Dependency Errors**: 0
- **Quality Issues**: 0

### Execution Phase
- **Status**: <completed|partial>
- **Total Tests**: 10
- **Passed**: 8
- **Failed**: 2
- **Errors**: 0
- **Pass Rate**: 80%
- **Execution Time**: 10.5 seconds

---

## Edge Case Prevention

**Total Edge Cases**: 8 (from git history analysis)
**Covered by Validators**: 8
**Prevented Today**: 6

### Prevented Edge Cases

- ✅ EC002: Venv usage violations (FAIL - 3 violations found)
- ✅ EC003: TodoWrite requirement (PASS)
- ✅ EC004: Decimal step numbering (PASS)
- ✅ EC005: Ambiguous optionality (PASS)
- ✅ EC006: Chinese content (PASS)
- ✅ EC007: File naming (PASS)
- ✅ EC008: Debug file accumulation (PASS)
- ❌ EC001: CLAUDE.md protection (FAIL - 1 violation found)

---

## Failed Tests (2)

### Critical: EC002 - Venv Usage Violations
**Files Affected**: 3
- settings.json:42
- commands/clean.md:36
- commands/dev.md:23

**Recommendation**: Update to use `source ~/.claude/venv/bin/activate && python3` pattern

**Fix Applied**: <Yes|No|Partial>

---

### High: EC001 - CLAUDE.md Protection
**Files Affected**: 1
- agents/cleanliness-inspector.md:1050

**Recommendation**: Add CLAUDE.md to official file allow-list

**Fix Applied**: <Yes|No>

---

## Passed Tests (8)

All validators passed for edge cases:
- EC003: TodoWrite requirement enforced
- EC004: No decimal step numbering
- EC005: No ambiguous optionality
- EC006: No Chinese content in functional code
- EC007: Consistent file naming (kebab-case)
- EC008: No old debug files (< 30 days)

---

## Git Information

- **Checkpoint Commit**: <hash>
- **Branch**: <branch>
- **Rollback Command**: `git reset --hard <checkpoint_commit>`

---

## Related Files

- Validation Context: tests/reports/validation-context-{REQUEST_ID}.json
- Validation Report: tests/reports/validation-report-{REQUEST_ID}.json
- Execution Context: tests/reports/execution-context-{REQUEST_ID}.json
- Execution Report: tests/reports/execution-report-{REQUEST_ID}.json
- Validator Registry: tests/reports/validator-registry-{REQUEST_ID}.json

---

## Root Cause

**Problem**: Missing enforcement layer. Standards documented in CLAUDE.md and agents/* but no automated validation. 8 edge cases accumulated over 70 days (Oct 25, 2025 - Jan 3, 2026).

**Solution**: Systematic validation framework with 10 validators informed by git history analysis. Each documented standard now has corresponding enforcement mechanism.

**Prevention**: Every new standard must have corresponding validator created in same commit. Use `/test` command regularly to catch violations early.

---

## Next Steps

1. ✅ Fix failed tests (2 remaining)
2. ✅ Re-run `/test` until all pass
3. ✅ Integrate into CI/CD pipeline
4. ✅ Run `/test` before every commit
5. ✅ Create validators for new standards immediately

---

**Test execution completed!**
```

---

## Test Folder Initialization

If project has no `tests/` directory, initialize it:

```bash
mkdir -p tests/{scripts,instructions,data/fixtures,data/mocks,reports}

# Copy templates from ~/.claude/tests/
cp ~/.claude/tests/README.md tests/
cp ~/.claude/tests/INDEX.md tests/
cp ~/.claude/tests/instructions/*.md tests/instructions/

# Create initial validator set based on edge cases
# (User must implement validators based on docs/test/edge-case-analysis.json)
```

**Initial validators to create** (based on 8 edge cases):

1. `tests/scripts/validate-venv-usage.py` - EC002
2. `tests/scripts/validate-todowrite-requirement.py` - EC003
3. `tests/scripts/validate-step-numbering.py` - EC004
4. `tests/scripts/validate-chinese-content.py` - EC006
5. `tests/scripts/validate-claude-md-protection.py` - EC001
6. `tests/scripts/validate-file-naming.py` - EC007
7. `tests/scripts/validate-debug-file-age.py` - EC008
8. `tests/scripts/validate-optionality-language.py` - EC005
9. `tests/scripts/validate-workflow-json-cleanup.py` - General
10. `tests/scripts/validate-checklist-completeness.py` - General

---

## Safety Features

### Git Checkpoint
- Automatic commit before test execution
- Easy rollback with `git reset --hard <checkpoint>`
- No data loss risk

### Fail-Safe Validation
- Syntax validation before execution
- Dependency check before running scripts
- Quality verification of validators themselves

### Incremental Execution
- Tests run independently
- Failure in one test doesn't block others
- Detailed per-test results

---

## Quality Standards

### Agent Communication
- All via JSON in tests/reports/
- Structured schemas enforced
- Clear request_id tracking

### Documentation
- Comprehensive reports generated
- Git rationale included
- Easy to audit and review

### Orchestration Pattern
- Follows /dev and /clean workflow model
- Specialized subagents (validator, executor)
- Clear separation of concerns

---

## Helper Scripts Used

- `~/.claude/scripts/todo/test.py` - Workflow checklist
- `~/.claude/scripts/analyze-git-edge-cases.sh` - Git history edge case analyzer
- `~/.claude/scripts/cleanup-tests-folder.sh` - Remove non-git validators
- `~/.claude/scripts/migrate-test-to-tests.sh` - Migrate test/ to tests/
- Test validators in `tests/scripts/validate-*.py`
- AI instructions in `tests/instructions/*.md`

---

## Integration with Other Commands

### /clean
- Archives old test reports to `tests/reports/archive/YYYY-MM/`
- Removes reports > 90 days old
- Preserves validator scripts

### /dev
- Create new validators during development
- Update validators when standards change
- Add validators to `/test` execution list

### CI/CD
- Run `/test` in pre-commit hook
- Block commits if critical tests fail
- Generate test reports for pull requests

---

## Usage

Execute in project directory:

```bash
cd /path/to/project
# In Claude Code, invoke: /test
```

The orchestrator will guide you through all steps interactively.

---

**Remember**: Tests enforce standards automatically. Standards without tests will be violated. Create validators immediately when documenting new standards.
