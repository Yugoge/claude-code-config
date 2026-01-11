# Test Framework

Comprehensive testing and validation framework for project standards and quality enforcement.

---

## Philosophy

Enforce documented standards through automated validation. Prevent edge cases through systematic testing.

---

## Directory Structure

```
test/
├── README.md              # This file
├── INDEX.md               # Auto-generated file catalog
├── scripts/               # Test and validation scripts
│   ├── validate-venv-usage.py
│   ├── validate-step-numbering.py
│   ├── validate-todowrite-requirement.py
│   ├── validate-chinese-content.py
│   ├── validate-claude-md-protection.py
│   ├── validate-file-naming.py
│   ├── validate-debug-file-age.py
│   ├── validate-workflow-json-cleanup.py
│   ├── validate-checklist-completeness.py
│   └── validate-optionality-language.py
├── instructions/          # AI-driven test instructions
│   ├── validation-guide.md
│   └── execution-guide.md
├── data/                  # Test data
│   ├── fixtures/          # Static test data
│   └── mocks/             # Mock data for testing
└── reports/               # Test execution reports
    ├── validation-report-<timestamp>.json
    └── execution-report-<timestamp>.json
```

---

## Test Types

### 1. Script-Based Tests

**Purpose**: Automated validation of standards and patterns

**Location**: `test/scripts/validate-*.py`

**Invocation**:
```bash
source ~/.claude/venv/bin/activate && python3 test/scripts/validate-venv-usage.py --project-root /path/to/project
```

**Output**: JSON report to stdout with exit code 0 (pass) or 1 (fail)

**Example**:
```json
{
  "validator": "validate-venv-usage",
  "status": "pass|fail",
  "violations": [],
  "summary": {
    "total_files_checked": 10,
    "violations_found": 0
  }
}
```

### 2. AI Instruction-Based Tests

**Purpose**: Complex validation requiring context understanding

**Location**: `test/instructions/*.md`

**Invocation**: Agent reads instruction, performs validation, writes report

**Example**: Validate that git commit messages follow conventional commit format

---

## Edge Case Prevention

This framework prevents 8 edge cases discovered in git history analysis:

- **EC001**: CLAUDE.md misidentified for relocation (validate-claude-md-protection.py)
- **EC002**: Venv usage violations (validate-venv-usage.py)
- **EC003**: TodoWrite requirement not enforced (validate-todowrite-requirement.py)
- **EC004**: Decimal step numbering (validate-step-numbering.py)
- **EC005**: Ambiguous optionality in workflows (validate-optionality-language.py)
- **EC006**: Chinese content in functional code (validate-chinese-content.py)
- **EC007**: Inconsistent file naming (validate-file-naming.py)
- **EC008**: Debug files accumulated without cleanup (validate-debug-file-age.py)

See `docs/test/edge-case-analysis.json` for detailed analysis.

---

## Usage

### Run All Validators

Use the `/test` command:

```bash
/test
```

The command will:
1. Initialize test folder if needed
2. Validate test syntax and dependencies
3. Execute all validators
4. Generate comprehensive report

### Run Individual Validator

```bash
source ~/.claude/venv/bin/activate && python3 test/scripts/validate-venv-usage.py --project-root /root/.claude
```

### Check Validation Status

```bash
# View latest validation report
cat test/reports/validation-report-latest.json

# View latest execution report
cat test/reports/execution-report-latest.json
```

---

## Creating New Validators

### Script-Based Validator Template

```python
#!/usr/bin/env python3
"""
Validator: {validator-name}
Edge Case: EC-XXX
Purpose: {single-line description}
"""

import argparse
import json
import sys
from pathlib import Path


def validate(project_root: Path) -> dict:
    """
    Validate {aspect} across project.

    Args:
        project_root: Root directory of project to validate

    Returns:
        dict: Validation result with status and violations
    """
    violations = []

    # Validation logic here
    # Add violations to list as: {"file": "path", "line": 10, "reason": "..."}

    return {
        "validator": "validate-{name}",
        "status": "pass" if not violations else "fail",
        "violations": violations,
        "summary": {
            "total_files_checked": 0,
            "violations_found": len(violations)
        },
        "recommendations": [] if not violations else ["Fix recommendation"]
    }


def main():
    parser = argparse.ArgumentParser(description="Validate {aspect}")
    parser.add_argument("--project-root", required=True, help="Project root directory")
    args = parser.parse_args()

    project_root = Path(args.project_root)
    if not project_root.exists():
        print(json.dumps({"error": "Project root does not exist"}), file=sys.stderr)
        sys.exit(1)

    result = validate(project_root)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    sys.exit(0 if result["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
```

### AI Instruction-Based Test Template

```markdown
# Test: {test-name}

## Purpose

{Single-line description of what this test validates}

## Instructions

1. Read {files} from project
2. Validate {aspect}
3. Check for {patterns}
4. Report violations

## Validation Criteria

- [ ] {criterion 1}
- [ ] {criterion 2}
- [ ] {criterion 3}

## Output Format

Write JSON report to `test/reports/{test-name}-report-<timestamp>.json`:

```json
{
  "test": "{test-name}",
  "status": "pass|fail",
  "findings": [],
  "summary": {...}
}
```

## Example Violations

{Example of what violations look like}
```

---

## Quality Standards

All validators must:

- Accept `--project-root` parameter
- Return exit code 0 (pass) or 1 (fail)
- Output JSON report to stdout
- Include fix recommendations for failures
- Be idempotent (same input → same output)
- Be fast (< 5 seconds for most projects)
- Use venv activation when called from bash

---

## Integration with /dev Workflow

When creating new standards in `/dev`:

1. Document standard in relevant file (CLAUDE.md, agents/dev.md, etc)
2. Create corresponding validator in `test/scripts/validate-{standard}.py`
3. Add validator to `/test` command execution list
4. Update edge case documentation if new pattern discovered

**Principle**: Every documented standard must have automated enforcement.

---

## Troubleshooting

### Validator Fails with Module Not Found

Ensure venv activated:
```bash
source ~/.claude/venv/bin/activate && python3 test/scripts/validate-xxx.py --project-root .
```

### False Positives

Check validator logic against edge cases in `docs/test/edge-case-analysis.json`. Update validator if needed.

### Validator Times Out

Optimize file scanning. Use glob patterns instead of recursive directory walks. Limit to relevant file types.

---

## Related Commands

- `/test` - Run test validation workflow
- `/clean` - Cleanup old test reports
- `/dev` - Create new validators during development

---

**Root Cause**: Missing enforcement layer. Standards documented but not validated automatically.

**Solution**: Systematic validation framework with script-based validators informed by git history edge case analysis.

**Prevention**: Every standard must have corresponding test.
