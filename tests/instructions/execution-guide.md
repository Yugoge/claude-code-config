# AI Test Execution Guide

Guide for test-executor subagent to execute both script-based and AI instruction-based tests.

---

## Purpose

Provides systematic execution workflow for test-executor subagent delegated by `/test` command orchestrator.

---

## Execution Context

You receive JSON context from orchestrator:

```json
{
  "request_id": "test-YYYYMMDD-HHMMSS",
  "timestamp": "ISO-8601",
  "orchestrator": {
    "command": "test",
    "mode": "validate|execute",
    "test_types": ["script", "instruction"]
  },
  "context": {
    "project_root": "/path/to/project",
    "test_directory": "/path/to/project/test",
    "validators": [
      {
        "type": "script",
        "path": "test/scripts/validate-venv-usage.py",
        "edge_case": "EC002",
        "priority": "critical"
      },
      {
        "type": "instruction",
        "path": "test/instructions/claude-md-protection.md",
        "edge_case": "EC001",
        "priority": "high"
      }
    ]
  },
  "parameters": {
    "fail_fast": false,
    "verbose": true,
    "report_path": "test/reports/execution-report-<timestamp>.json"
  }
}
```

---

## Execution Workflow

### Step 1: Initialize Execution

Read context JSON and validate:

```python
# Check project root exists
# Check test directory exists
# Check venv available (for script-based tests)
# Create reports directory if needed
```

### Step 2: Execute Script-Based Tests

For each validator with `type: "script"`:

```bash
# Activate venv
source ~/.claude/venv/bin/activate

# Execute validator
python3 test/scripts/validate-venv-usage.py --project-root /path/to/project > output.json

# Capture exit code
EXIT_CODE=$?

# Parse JSON output
# Record result with exit code
```

**Error handling**:
- If script fails to execute → Record as "error" (not "fail")
- If script returns non-JSON → Record error with output
- If script exits 0 → Record as "pass"
- If script exits 1 → Record as "fail" with violations

**Result format**:
```json
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
    "status": "pass|fail|error"
  },
  "result": {
    "status": "pass",
    "violations": [],
    "summary": {...}
  }
}
```

### Step 3: Execute AI Instruction-Based Tests

For each validator with `type: "instruction"`:

```markdown
1. Read instruction file: test/instructions/{test-name}.md
2. Follow validation guide: test/instructions/validation-guide.md
3. Gather context files specified in instruction
4. Apply validation criteria systematically
5. Identify violations with file, line, reason
6. Generate JSON report following instruction output format
7. Write report to test/reports/{test-name}-report-{timestamp}.json
8. Record execution result with status
```

**Error handling**:
- If instruction file not found → Record as "error"
- If context files missing → Record as "error"
- If validation completes → Record as "pass" or "fail" based on findings

**Result format**:
```json
{
  "validator": "claude-md-protection",
  "type": "instruction",
  "edge_case": "EC001",
  "priority": "high",
  "execution": {
    "started_at": "ISO-8601",
    "completed_at": "ISO-8601",
    "duration_seconds": 3.45,
    "status": "pass|fail|error"
  },
  "result": {
    "test": "claude-md-protection",
    "status": "pass",
    "findings": [],
    "summary": {...}
  }
}
```

### Step 4: Aggregate Results

Collect all execution results:

```python
total_tests = len(validators)
passed = sum(1 for r in results if r["execution"]["status"] == "pass")
failed = sum(1 for r in results if r["execution"]["status"] == "fail")
errors = sum(1 for r in results if r["execution"]["status"] == "error")

summary = {
  "total_tests": total_tests,
  "passed": passed,
  "failed": failed,
  "errors": errors,
  "pass_rate": passed / total_tests * 100,
  "edge_cases_prevented": count_unique_edge_cases(results)
}
```

### Step 5: Generate Execution Report

Write comprehensive report to `test/reports/execution-report-{timestamp}.json`:

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
        "execution": {...},
        "result": {...}
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
        "critical": {"passed": 3, "failed": 2, "errors": 0},
        "high": {"passed": 2, "failed": 0, "errors": 0},
        "medium": {"passed": 3, "failed": 0, "errors": 0}
      }
    },
    "failed_tests": [
      {
        "validator": "validate-venv-usage",
        "edge_case": "EC002",
        "violations_count": 3,
        "severity": "critical",
        "recommendation": "Fix venv usage in 3 files"
      }
    ]
  }
}
```

---

## Execution Modes

### Validate Mode

Execute tests without fixing violations:

```bash
/test --mode=validate
```

- Run all validators
- Report violations
- Do NOT make changes
- Exit with status code (0 if all pass, 1 if any fail)

### Execute Mode (Future)

Execute tests and optionally apply fixes:

```bash
/test --mode=execute --fix
```

- Run all validators
- Report violations
- Offer to apply automated fixes
- Generate fix commit if user approves

---

## Error Handling

### Script Execution Errors

**ModuleNotFoundError**:
- Check venv activated
- Check dependencies installed
- Record as "error" with fix recommendation

**FileNotFoundError**:
- Check project root correct
- Check file paths relative to project root
- Record as "error" with fix recommendation

**Timeout**:
- If script runs > 30 seconds → Kill and record as "error"
- Recommendation: Optimize validator performance

### AI Instruction Errors

**Instruction File Missing**:
- Check test/instructions/ directory
- Record as "error"
- Recommendation: Create instruction file

**Context Files Missing**:
- Check if files moved/deleted
- Update instruction if architecture changed
- Record as "error" with details

**Validation Logic Unclear**:
- Review criteria in instruction
- Ask orchestrator for clarification
- Record as "error" if cannot proceed

---

## Quality Standards

Before returning execution report:

- [ ] All validators attempted (unless fail_fast enabled)
- [ ] Exit codes captured correctly
- [ ] JSON output parsed and validated
- [ ] Execution times recorded
- [ ] Errors distinguished from failures
- [ ] Summary statistics accurate
- [ ] Failed tests have recommendations
- [ ] Report written to correct path

---

## Integration with Test Command

The `/test` command workflow:

```
Step 1: Initialize (orchestrator)
Step 2: Validate test folder exists (orchestrator)
Step 3: Discover validators (orchestrator)
Step 4: Build execution context JSON (orchestrator)
Step 5: Delegate to test-executor (YOU)
Step 6: Collect execution report (orchestrator)
Step 7: Present results to user (orchestrator)
```

You are responsible for Step 5 only.

---

## Troubleshooting

### All Scripts Fail with Venv Error

Check venv activation command:
```bash
source ~/.claude/venv/bin/activate && python3 -c "import sys; print(sys.prefix)"
```

### Inconsistent Results Across Runs

- Check if validators modify state (should be read-only)
- Verify validators are idempotent
- Check for time-dependent logic (use fixed timestamps in tests)

### Execution Takes Too Long

- Run critical priority validators first
- Enable fail_fast mode for quick feedback
- Optimize slow validators (profile with time command)

---

**Remember**: You execute tests systematically. You capture all results. You distinguish errors from failures. You provide actionable recommendations.
