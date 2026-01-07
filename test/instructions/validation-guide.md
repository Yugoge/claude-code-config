# AI-Driven Validation Guide

Guide for executing AI instruction-based tests that require context understanding.

---

## Purpose

Some validations require semantic understanding that regex patterns cannot capture. This guide provides instructions for AI agents to perform such validations.

---

## When to Use AI Instructions

Use AI instruction-based tests when:

- Validation requires understanding code semantics
- Pattern matching is insufficient
- Context across multiple files needed
- Natural language processing required

**Examples**:
- Validate commit message follows conventional commit format AND accurately describes changes
- Verify function documentation matches actual implementation
- Check if error handling is appropriate for failure mode
- Validate architectural consistency across modules

---

## Validation Process

### Step 1: Read Instruction File

AI agent reads test instruction from `test/instructions/{test-name}.md`

### Step 2: Gather Context

Agent reads relevant files specified in instruction:
```markdown
## Context Files

- commands/clean.md
- agents/cleanliness-inspector.md
- Recent git commits
```

### Step 3: Apply Validation Criteria

Agent checks each criterion in instruction:
```markdown
## Validation Criteria

- [ ] Official files (CLAUDE.md, README.md) never flagged for relocation
- [ ] Inspector allow-list includes all framework files
- [ ] Documentation mentions framework file preservation
```

### Step 4: Identify Violations

Agent finds patterns that violate criteria:
```json
{
  "file": "agents/cleanliness-inspector.md",
  "line": 1050,
  "criterion": "Framework file preservation",
  "violation": "ARCHITECTURE.md not mentioned in allow-list",
  "severity": "major"
}
```

### Step 5: Generate Report

Agent writes JSON report to `test/reports/{test-name}-report-{timestamp}.json`:
```json
{
  "test": "claude-md-protection",
  "timestamp": "2026-01-07T10:00:00Z",
  "status": "fail",
  "findings": [
    {
      "file": "agents/cleanliness-inspector.md",
      "line": 1050,
      "criterion": "Framework file preservation",
      "violation": "ARCHITECTURE.md not mentioned in allow-list",
      "severity": "major",
      "recommendation": "Add ARCHITECTURE.md to official file allow-list"
    }
  ],
  "summary": {
    "criteria_checked": 3,
    "criteria_passed": 2,
    "criteria_failed": 1,
    "violations_found": 1
  }
}
```

---

## Test Instruction Template

```markdown
# Test: {test-name}

## Edge Case Reference

**EC-XXX**: {edge case title from analysis}

## Purpose

{Single-line description}

## Context Files

- {file1}
- {file2}
- {git commits if relevant}

## Validation Criteria

- [ ] {criterion 1}
- [ ] {criterion 2}
- [ ] {criterion 3}

## Validation Steps

1. Read {files}
2. Check for {pattern}
3. Verify {aspect}
4. Report violations

## Example Violations

{Code snippet or description of what violation looks like}

## False Positives to Avoid

- {Scenario that looks like violation but isn't}
- {Another edge case}

## Output Format

Write JSON report to `test/reports/{test-name}-report-<timestamp>.json`

## Success Exit Code

- 0 if all criteria pass
- 1 if any criterion fails
```

---

## Example: CLAUDE.md Protection Test

### Instruction File

```markdown
# Test: claude-md-protection

## Edge Case Reference

**EC001**: CLAUDE.md incorrectly flagged for relocation

## Purpose

Verify CLAUDE.md never appears in relocation recommendations from any inspector.

## Context Files

- agents/cleanliness-inspector.md
- commands/clean.md
- docs/clean/* (recent inspection reports)

## Validation Criteria

- [ ] CLAUDE.md explicitly listed in official files allow-list
- [ ] README.md explicitly listed in official files allow-list
- [ ] ARCHITECTURE.md explicitly listed in official files allow-list
- [ ] Cleanliness inspector logic preserves these files
- [ ] No recent reports recommend moving these files

## Validation Steps

1. Read agents/cleanliness-inspector.md
2. Find official files allow-list (typically in "Root Directory Organization" section)
3. Verify CLAUDE.md, README.md, ARCHITECTURE.md all present
4. Read commands/clean.md Step 1 documentation rules
5. Verify same three files mentioned as ALLOWED in root
6. Check recent reports in docs/clean/ for any relocation recommendations
7. Report violations if any file missing from allow-lists or found in reports

## Example Violations

**Violation in cleanliness-inspector.md**:
```markdown
Root directory .md files:
- **ALLOWED**: README.md (project overview)
- **MOVE TO docs/**: All other .md files
```
Missing: CLAUDE.md, ARCHITECTURE.md

**Violation in inspection report**:
```json
{
  "findings": {
    "misplaced_docs": [
      {
        "file": "CLAUDE.md",
        "recommendation": "Move to docs/reference/claude.md"
      }
    ]
  }
}
```

## False Positives to Avoid

- Don't flag if CLAUDE.md mentioned in examples (check context)
- Don't flag archived cleanup reports in docs/clean/archive/

## Output Format

Write JSON report to `test/reports/claude-md-protection-report-<timestamp>.json`:

```json
{
  "test": "claude-md-protection",
  "edge_case": "EC001",
  "timestamp": "ISO-8601",
  "status": "pass|fail",
  "findings": [
    {
      "file": "agents/cleanliness-inspector.md",
      "location": "line 1050",
      "criterion": "CLAUDE.md in allow-list",
      "violation": "CLAUDE.md not mentioned in official files",
      "severity": "critical",
      "recommendation": "Add CLAUDE.md to official file allow-list alongside README.md"
    }
  ],
  "summary": {
    "criteria_checked": 5,
    "criteria_passed": 3,
    "criteria_failed": 2,
    "violations_found": 2,
    "severity_breakdown": {
      "critical": 2,
      "major": 0,
      "minor": 0
    }
  }
}
```

## Success Exit Code

- 0 if all criteria pass
- 1 if any criterion fails
```

---

## Best Practices

### For AI Agents Executing Tests

1. **Read instruction completely** before starting validation
2. **Gather all context** specified in instruction
3. **Check each criterion** systematically
4. **Document rationale** for each violation found
5. **Provide fix recommendations** that are actionable
6. **Write structured report** following template exactly
7. **Exit with correct code** (0 or 1)

### For Test Instruction Writers

1. **Single responsibility** - One test validates one aspect
2. **Clear criteria** - Checklist format, unambiguous
3. **Context complete** - List all files needed
4. **Examples provided** - Show what violations look like
5. **False positives** - Document edge cases to avoid
6. **Output structured** - JSON schema defined
7. **Exit codes** - 0 for pass, 1 for fail

---

## Integration with Test Command

The `/test` command automatically:

1. Discovers all instruction files in `test/instructions/`
2. Delegates each to test-executor subagent
3. Collects reports from `test/reports/`
4. Aggregates results in final report

---

## Troubleshooting

### Agent Misinterprets Instruction

- Make criteria more explicit
- Add concrete examples
- Document false positive scenarios

### Test Takes Too Long

- Limit context files to essential only
- Use glob patterns to reduce file scanning
- Consider converting to script-based test if possible

### Inconsistent Results

- Check if criteria are subjective (needs objectivity)
- Verify context files specified are stable
- Add more example violations to guide agent

---

**Remember**: AI instruction-based tests are for semantic validation. Use script-based tests for pattern matching.
