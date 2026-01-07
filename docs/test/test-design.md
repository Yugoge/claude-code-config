# Test Framework Design

Comprehensive testing and validation framework architecture and design documentation.

**Created**: 2026-01-07
**Version**: 1.0

---

## Overview

The test framework provides systematic validation of project standards through automated script-based and AI instruction-based tests. Designed to prevent 8 edge cases discovered in git history analysis over 70-day period.

---

## Architecture

### Components

```
/test Command (Orchestrator)
    ↓
┌───────────────┬────────────────┐
│               │                │
Test-Validator  Test-Executor   Git-Edge-Case-Analyst
│               │                │
│               ↓                ↓
│         Validators      Edge Case Analysis
│         (10 scripts)    (docs/test/)
│               │
└───────────────┴────────────────→ Reports
                                  (test/reports/)
```

### Workflow Phases

**Phase 1: Initialization**
- Load workflow checklist (scripts/todo/test.py)
- Check test folder exists
- Discover available validators

**Phase 2: Validation**
- Delegate to test-validator subagent
- Check syntax, dependencies, quality
- Verify edge case coverage
- Block execution if critical issues

**Phase 3: Execution**
- Create git safety checkpoint
- Delegate to test-executor subagent
- Run script-based validators
- Run AI instruction-based validators
- Aggregate results

**Phase 4: Reporting**
- Present failures to user
- Offer fix options
- Generate completion report

---

## Edge Case Prevention

### 8 Edge Cases from Git Analysis

**EC001: CLAUDE.md Protection** (Major)
- Issue: Official file misidentified for relocation
- Prevention: validate-claude-md-protection.py
- Checks: Explicit allow-lists in inspector logic

**EC002: Venv Usage** (Critical)
- Issue: 8 instances of direct python invocation without venv
- Prevention: validate-venv-usage.py
- Checks: Pattern matching for venv activation

**EC003: TodoWrite Requirement** (Critical)
- Issue: Multi-step workflows missing todo scripts
- Prevention: validate-todowrite-requirement.py
- Checks: Commands with 3+ steps have todo scripts

**EC004: Decimal Step Numbering** (Critical)
- Issue: Step 1.1, Step 1.2 format used despite prohibition
- Prevention: validate-step-numbering.py
- Checks: Regex for decimal step patterns

**EC005: Ambiguous Optionality** (Critical)
- Issue: "(Optional)" steps skipped despite being conditionally mandatory
- Prevention: validate-optionality-language.py
- Checks: Optional steps have clear execution conditions

**EC006: Chinese Content** (Major)
- Issue: 7 files with Chinese in functional code
- Prevention: validate-chinese-content.py
- Checks: Unicode range scan in .sh/.py/.json

**EC007: File Naming** (Minor)
- Issue: Inconsistent naming (UPPERCASE, snake_case)
- Prevention: validate-file-naming.py
- Checks: Kebab-case enforcement in docs/

**EC008: Debug File Accumulation** (Critical)
- Issue: 1923 files older than 30 days (103MB)
- Prevention: validate-debug-file-age.py
- Checks: File age threshold in debug/

### Additional Validators

**EC-General: Workflow JSON Cleanup**
- validate-workflow-json-cleanup.py
- Checks: Old JSONs archived in docs/dev/, docs/clean/

**EC-General: Checklist Completeness**
- validate-checklist-completeness.py
- Checks: Quality Checklist has all required items

---

## Validator Design Patterns

### Script-Based Validator Template

```python
#!/usr/bin/env python3
"""
Validator: {name}
Edge Case: EC-XXX
Purpose: {single-line description}
"""

import argparse, json, sys
from pathlib import Path

def validate(project_root: Path) -> dict:
    violations = []
    # Validation logic
    return {
        "validator": "{name}",
        "edge_case": "EC-XXX",
        "status": "pass|fail",
        "violations": violations,
        "summary": {...},
        "recommendations": [...]
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()

    result = validate(Path(args.project_root))
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "pass" else 1)

if __name__ == "__main__":
    main()
```

### AI Instruction-Based Template

```markdown
# Test: {name}

## Edge Case Reference
EC-XXX: {title}

## Purpose
{description}

## Context Files
- {file1}
- {file2}

## Validation Criteria
- [ ] {criterion1}
- [ ] {criterion2}

## Output Format
JSON schema with findings
```

---

## JSON Communication Protocol

### Context JSON

**Location**: `test/reports/{type}-context-{REQUEST_ID}.json`

**Schema**:
```json
{
  "request_id": "test-YYYYMMDD-HHMMSS",
  "timestamp": "ISO-8601",
  "orchestrator": {
    "command": "test",
    "phase": "validation|execution",
    "requirement": "..."
  },
  "context": {
    "project_root": "/absolute/path",
    "test_directory": "/absolute/path/test",
    "venv_path": "~/.claude/venv",
    "validators": [...]
  }
}
```

### Report JSON

**Location**: `test/reports/{type}-report-{REQUEST_ID}.json`

**Schema**:
```json
{
  "request_id": "test-YYYYMMDD-HHMMSS",
  "timestamp": "ISO-8601",
  "{subagent}": {
    "status": "pass|fail|completed|partial",
    "results": [...],
    "summary": {...},
    "recommendations": [...]
  }
}
```

---

## Integration Points

### /dev Command Integration

When creating new standards:

1. Document standard (CLAUDE.md, agents/dev.md, etc)
2. Create validator (test/scripts/validate-{standard}.py)
3. Add validator to test execution list
4. Update settings.json permissions

### /clean Command Integration

Cleanup old test artifacts:

- Archive test reports > 30 days: `test/reports/archive/YYYY-MM/`
- Remove reports > 90 days
- Preserve validator scripts

### CI/CD Integration

Pre-commit workflow:

```bash
# Run all validators
source ~/.claude/venv/bin/activate && python3 ~/.claude/scripts/todo/test.py

# Check exit code
if /test exits 1; then
  echo "Tests failed. Fix violations before committing."
  exit 1
fi
```

---

## Quality Metrics

### Test Coverage

**Edge Case Coverage**: 8/8 (100%)
- All documented edge cases have validators

**Priority Distribution**:
- Critical: 5 validators
- High: 2 validators
- Medium: 3 validators

### Validator Quality

**Standards compliance**:
- [ ] Accepts --project-root parameter
- [ ] Returns exit code 0 (pass) or 1 (fail)
- [ ] Outputs JSON to stdout
- [ ] Includes fix recommendations
- [ ] Execution time < 5 seconds
- [ ] Uses venv when called from bash

---

## Future Enhancements

### Phase 2 Features

**Automated fixes**:
- Create fix-*.py scripts for common violations
- Apply fixes with user approval
- Re-run tests automatically

**Parallel execution**:
- Run independent validators in parallel
- Reduce total execution time
- Maintain result aggregation

**Incremental testing**:
- Cache results for unchanged files
- Only re-run validators on modified files
- Speed up iteration cycles

**Test reporting**:
- HTML report generation
- Trend analysis (violations over time)
- Integration with monitoring tools

---

## Related Documentation

- Edge Case Analysis: `docs/test/edge-case-analysis.json`
- Test Framework README: `test/README.md`
- Test Command: `commands/test.md`
- Validator Subagent: `agents/test-validator.md`
- Executor Subagent: `agents/test-executor.md`
- Git Analyst Subagent: `agents/git-edge-case-analyst.md`

---

**Root Cause**: Missing enforcement layer. Standards documented but not validated.

**Solution**: Systematic validation framework with 10 validators informed by git history.

**Impact**: Zero violations accumulate silently. All standards automatically enforced.
