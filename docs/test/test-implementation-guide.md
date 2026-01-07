# Test Implementation Guide - Quick Reference

**Purpose**: Practical guide for implementing /test command based on edge case analysis
**Audience**: Developers implementing the /test command
**Related**: edge-case-analysis.json, edge-case-analysis-summary.md

---

## Quick Stats

- **Edge Cases Found**: 8 (all preventable with proper testing)
- **Critical Validators Needed**: 5
- **High Priority Validators**: 2
- **Architectural Validators**: 3
- **Total Prevention Coverage**: 100%

---

## Implementation Priority Matrix

### Phase 1: Critical Preventers (Week 1)

These prevent the most severe edge cases found:

```yaml
Priority: CRITICAL
Implementation Time: 2-3 days
Prevention Coverage: 5/8 edge cases (EC002, EC003, EC004, EC005, EC001)
```

**Validators**:

1. **venv_usage_checker** (Prevents EC002)
   ```python
   import re

   def check_venv_usage(file_path, content):
       """Detect python calls without venv activation"""
       pattern = r'python[3]?\s+(?!.*venv).*\.py'
       matches = re.findall(pattern, content)
       if matches:
           return {
               'severity': 'critical',
               'message': f'Found {len(matches)} venv violations',
               'violations': matches,
               'fix': 'Change to: source venv/bin/activate && python3 ...'
           }
       return None
   ```

2. **step_numbering_validator** (Prevents EC004)
   ```python
   def check_step_numbering(file_path, content):
       """Detect decimal step numbering"""
       pattern = r'Step\s+\d+\.\d+'
       matches = re.findall(pattern, content)
       if matches:
           return {
               'severity': 'critical',
               'message': f'Found {len(matches)} decimal step numbers',
               'violations': matches,
               'fix': 'Renumber to sequential integers: Step 1, Step 2, Step 3'
           }
       return None
   ```

3. **todowrite_requirement_checker** (Prevents EC003)
   ```python
   def check_todowrite_requirement(command_file):
       """Verify todo script exists for multi-step commands"""
       steps = count_steps(command_file)
       if steps >= 3:
           command_name = Path(command_file).stem
           todo_script = f'scripts/todo/{command_name}.py'
           if not Path(todo_script).exists():
               return {
                   'severity': 'critical',
                   'message': f'Missing todo script for {command_name} ({steps} steps)',
                   'fix': f'Create {todo_script} with {steps} todo items'
               }
       return None

   def count_steps(file_path):
       """Count steps in command markdown file"""
       content = Path(file_path).read_text()
       matches = re.findall(r'^###?\s+Step\s+\d+:', content, re.MULTILINE)
       return len(matches)
   ```

4. **chinese_character_detector** (Prevents EC006)
   ```python
   def check_chinese_characters(file_path, content):
       """Detect Chinese characters in functional files"""
       # Only check functional files, not documentation
       if file_path.endswith(('.sh', '.py', '.json')):
           if 'docs/' in file_path:
               return None  # Skip docs

           pattern = r'[\u4e00-\u9fff]'
           matches = re.findall(pattern, content)
           if matches:
               return {
                   'severity': 'critical',
                   'message': f'Found {len(matches)} Chinese characters in functional file',
                   'violations': matches[:5],  # Show first 5
                   'fix': 'Translate to English or move to docs/archive/legacy-chinese/'
               }
       return None
   ```

5. **claude_md_protection_test** (Prevents EC001)
   ```python
   def test_claude_md_protection():
       """Verify CLAUDE.md never flagged for relocation"""
       # Run cleanliness inspector on test fixture
       context = create_test_context()
       report = run_cleanliness_inspector(context)

       # Check if CLAUDE.md appears in misplaced_docs
       for issue in report.get('findings', {}).get('misplaced_docs', []):
           if 'CLAUDE.md' in issue.get('file', ''):
               return {
                   'severity': 'critical',
                   'message': 'CLAUDE.md incorrectly flagged for relocation',
                   'fix': 'Update cleanliness-inspector.md and clean.md allow-lists'
               }
       return None
   ```

---

### Phase 2: High Priority Validators (Week 2)

```yaml
Priority: HIGH
Implementation Time: 1-2 days
Prevention Coverage: 2/8 edge cases (EC007, EC008)
```

6. **file_naming_validator** (Prevents EC007)
   ```python
   def check_file_naming(file_path):
       """Verify docs/ uses kebab-case naming"""
       if file_path.startswith('docs/'):
           filename = Path(file_path).name

           # Allow special files
           if filename in ['README.md', 'INDEX.md', 'CLAUDE.md']:
               return None

           # Check for non-kebab-case
           if re.search(r'[A-Z_]', filename.replace('.md', '')):
               return {
                   'severity': 'high',
                   'message': f'File not in kebab-case: {filename}',
                   'fix': f'Rename to: {to_kebab_case(filename)}'
               }
       return None

   def to_kebab_case(s):
       """Convert string to kebab-case"""
       s = re.sub(r'[A-Z]', lambda m: '-' + m.group(0).lower(), s)
       s = s.replace('_', '-').replace(' ', '-')
       return s.lstrip('-')
   ```

7. **debug_file_age_checker** (Prevents EC008)
   ```python
   import time
   from pathlib import Path

   def check_debug_file_age(threshold_days=30):
       """Verify no debug files older than threshold"""
       violations = []
       debug_dir = Path('debug/')

       if not debug_dir.exists():
           return None

       cutoff_time = time.time() - (threshold_days * 86400)

       for file in debug_dir.rglob('*'):
           if file.is_file():
               if file.stat().st_mtime < cutoff_time:
                   age_days = (time.time() - file.stat().st_mtime) / 86400
                   violations.append({
                       'file': str(file),
                       'age_days': int(age_days)
                   })

       if violations:
           return {
               'severity': 'high',
               'message': f'Found {len(violations)} debug files older than {threshold_days} days',
               'violations': violations[:10],  # Show first 10
               'fix': f'Archive to debug/archive-YYYY-MM/ or delete'
           }
       return None
   ```

---

### Phase 3: Architectural Validators (Week 3)

```yaml
Priority: MEDIUM
Implementation Time: 2-3 days
Prevention Coverage: Systemic (prevents future edge cases)
```

8. **enforcement_layer_mapper**
   ```python
   def check_enforcement_coverage():
       """Verify each documented standard has enforcement"""
       standards = extract_standards_from_docs()
       enforcement_map = build_enforcement_map()

       gaps = []
       for standard in standards:
           if standard.id not in enforcement_map:
               gaps.append({
                   'standard': standard.name,
                   'documented_in': standard.file,
                   'enforcement': None
               })

       if gaps:
           return {
               'severity': 'medium',
               'message': f'Found {len(gaps)} standards without enforcement',
               'gaps': gaps,
               'fix': 'Create test/linter/hook for each standard'
           }
       return None
   ```

9. **optionality_language_detector**
   ```python
   def check_optional_step_conditions(file_path, content):
       """Detect steps with 'Optional' but unclear conditions"""
       violations = []

       # Find all steps with "Optional" in title
       optional_steps = re.findall(
           r'(###?\s+Step\s+\d+[^:]*\(Optional\)[^#]*?)(?=###|$)',
           content,
           re.DOTALL
       )

       for step in optional_steps:
           # Check if explicit conditions exist
           has_conditions = bool(re.search(
               r'(MUST execute if|Only skip if|Execute if ANY)',
               step
           ))

           if not has_conditions:
               violations.append({
                   'step': step.split('\n')[0],
                   'issue': 'Optional step lacks explicit execution conditions'
               })

       if violations:
           return {
               'severity': 'medium',
               'message': f'Found {len(violations)} optional steps with unclear conditions',
               'violations': violations,
               'fix': 'Add explicit "MUST execute if" or "Only skip if ALL" conditions'
           }
       return None
   ```

10. **user_correction_detector**
    ```python
    def detect_user_corrections():
        """Parse git history for user corrections"""
        import subprocess

        result = subprocess.run(
            ['git', 'log', '--format=%H|%s|%b', '--all'],
            capture_output=True,
            text=True
        )

        corrections = []
        keywords = ['reject', 'incorrect', 'fix', 'violation', 'user correct']

        for line in result.stdout.split('\n'):
            if not line:
                continue

            commit_hash, subject, body = line.split('|', 2)
            message = subject + ' ' + body

            if any(kw in message.lower() for kw in keywords):
                corrections.append({
                    'commit': commit_hash[:8],
                    'subject': subject,
                    'keywords_matched': [kw for kw in keywords if kw in message.lower()]
                })

        if corrections:
            return {
                'severity': 'info',
                'message': f'Found {len(corrections)} potential user corrections',
                'corrections': corrections,
                'action': 'Review each for missing enforcement mechanism'
            }
        return None
    ```

---

## File Structure for /test Command

```
~/.claude/
├── commands/
│   └── test.md                    # /test command documentation
├── agents/
│   └── test-validator.md          # Test validation subagent
├── scripts/
│   ├── test/
│   │   ├── validators/
│   │   │   ├── __init__.py
│   │   │   ├── venv_checker.py      # Validator 1
│   │   │   ├── step_numbering.py    # Validator 2
│   │   │   ├── todowrite_checker.py # Validator 3
│   │   │   ├── chinese_detector.py  # Validator 4
│   │   │   ├── claude_md_protect.py # Validator 5
│   │   │   ├── file_naming.py       # Validator 6
│   │   │   ├── debug_age.py         # Validator 7
│   │   │   └── architectural.py     # Validators 8-10
│   │   ├── test_runner.py          # Main test orchestrator
│   │   └── report_generator.py     # Test report generator
│   └── todo/
│       └── test.py                 # Todo checklist for /test
└── docs/
    └── test/
        ├── edge-case-analysis.json          # This analysis (machine-readable)
        ├── edge-case-analysis-summary.md    # This analysis (human-readable)
        ├── test-implementation-guide.md     # This document
        └── test-fixtures/                   # Test fixtures for each edge case
            ├── EC001-claude-md/
            ├── EC002-venv-violation/
            ├── EC003-missing-todowrite/
            ├── EC004-decimal-steps/
            ├── EC005-optional-step/
            ├── EC006-chinese-content/
            ├── EC007-bad-naming/
            └── EC008-old-debug-files/
```

---

## Test Runner Implementation

```python
#!/usr/bin/env python3
"""
Main test runner for /test command
"""
import sys
from pathlib import Path
from typing import List, Dict, Any
import json

from validators import (
    venv_checker,
    step_numbering,
    todowrite_checker,
    chinese_detector,
    claude_md_protect,
    file_naming,
    debug_age,
    architectural
)

class TestRunner:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.validators = self._load_validators()
        self.results = []

    def _load_validators(self) -> List:
        """Load all validators based on priority"""
        return [
            # Phase 1: Critical
            ('venv_usage', venv_checker.check_all_files),
            ('step_numbering', step_numbering.check_all_commands),
            ('todowrite_requirement', todowrite_checker.check_all_commands),
            ('chinese_characters', chinese_detector.check_all_files),
            ('claude_md_protection', claude_md_protect.test_protection),

            # Phase 2: High Priority
            ('file_naming', file_naming.check_all_docs),
            ('debug_file_age', debug_age.check_debug_directory),

            # Phase 3: Architectural
            ('enforcement_coverage', architectural.check_enforcement_coverage),
            ('optional_conditions', architectural.check_optional_step_conditions),
            ('user_corrections', architectural.detect_user_corrections),
        ]

    def run_all(self) -> Dict[str, Any]:
        """Run all validators and collect results"""
        for validator_name, validator_func in self.validators:
            print(f"Running {validator_name}...", file=sys.stderr)

            try:
                result = validator_func(self.project_root)
                if result:  # If violations found
                    self.results.append({
                        'validator': validator_name,
                        **result
                    })
            except Exception as e:
                self.results.append({
                    'validator': validator_name,
                    'severity': 'error',
                    'message': f'Validator crashed: {str(e)}'
                })

        return self.generate_report()

    def generate_report(self) -> Dict[str, Any]:
        """Generate test report"""
        critical = [r for r in self.results if r.get('severity') == 'critical']
        high = [r for r in self.results if r.get('severity') == 'high']
        medium = [r for r in self.results if r.get('severity') == 'medium']

        return {
            'status': 'FAIL' if critical or high else 'PASS',
            'summary': {
                'total_validators': len(self.validators),
                'violations_found': len(self.results),
                'critical': len(critical),
                'high': len(high),
                'medium': len(medium)
            },
            'violations': self.results,
            'edge_cases_prevented': self._map_to_edge_cases()
        }

    def _map_to_edge_cases(self) -> List[str]:
        """Map violations to prevented edge cases"""
        mapping = {
            'venv_usage': 'EC002',
            'step_numbering': 'EC004',
            'todowrite_requirement': 'EC003',
            'chinese_characters': 'EC006',
            'claude_md_protection': 'EC001',
            'file_naming': 'EC007',
            'debug_file_age': 'EC008',
        }

        prevented = []
        for result in self.results:
            validator = result.get('validator')
            if validator in mapping and result.get('severity') in ['critical', 'high']:
                prevented.append(mapping[validator])

        return prevented

def main():
    """Main entry point"""
    project_root = Path('/root/.claude')
    runner = TestRunner(project_root)
    report = runner.run_all()

    # Print JSON report
    print(json.dumps(report, indent=2))

    # Exit with non-zero if violations found
    sys.exit(1 if report['status'] == 'FAIL' else 0)

if __name__ == '__main__':
    main()
```

---

## Integration with /test Command Workflow

The /test command (commands/test.md) should:

1. **Initialize**: Load todo checklist from scripts/todo/test.py
2. **Execute**: Run test_runner.py to execute all validators
3. **Report**: Generate comprehensive report with:
   - Summary statistics
   - Violations by severity
   - Edge cases prevented
   - Recommended fixes
4. **Output**: Both JSON (machine-readable) and Markdown (human-readable)

**Example command flow**:

```bash
# Step 1: Initialize
source ~/.claude/venv/bin/activate && python3 scripts/todo/test.py

# Step 2: Execute tests
source ~/.claude/venv/bin/activate && python3 scripts/test/test_runner.py > /tmp/test-report.json

# Step 3: Generate markdown report
source ~/.claude/venv/bin/activate && python3 scripts/test/report_generator.py /tmp/test-report.json > docs/test/latest-report.md

# Step 4: Display results
cat docs/test/latest-report.md
```

---

## Test Fixtures Design

Each edge case should have a test fixture in `docs/test/test-fixtures/`:

**Example: EC002-venv-violation/**
```
EC002-venv-violation/
├── input/
│   ├── settings.json          # Contains: "python script.py" (violation)
│   └── commands/clean.md      # Contains: "python ~/.claude/script.py"
├── expected/
│   └── violations.json        # Expected validator output
└── README.md                  # Explains the test case
```

**Usage in tests**:
```python
def test_venv_checker():
    """Test venv checker against EC002 fixture"""
    fixture = Path('docs/test/test-fixtures/EC002-venv-violation')

    # Run validator on fixture
    result = venv_checker.check_file(fixture / 'input/settings.json')

    # Compare with expected
    expected = json.load(open(fixture / 'expected/violations.json'))
    assert result == expected
```

---

## Success Metrics

A properly implemented /test command should:

✅ **Prevent 100% of identified edge cases from recurring**
✅ **Detect violations in < 5 seconds for full repository scan**
✅ **Generate actionable fix recommendations**
✅ **Integrate with CI/CD for automatic validation**
✅ **Provide both machine-readable (JSON) and human-readable (Markdown) output**
✅ **Map violations to specific edge case IDs for traceability**

---

## Next Steps for Implementation

1. **Week 1**: Implement Phase 1 validators (critical preventers)
2. **Week 2**: Implement Phase 2 validators + test fixtures
3. **Week 3**: Implement Phase 3 validators + CI/CD integration
4. **Week 4**: Documentation, user testing, refinement

---

## References

- **Detailed Analysis**: /root/.claude/docs/test/edge-case-analysis.json
- **Human Summary**: /root/.claude/docs/test/edge-case-analysis-summary.md
- **Violation Reports**: /root/.claude/docs/clean/*violations*.md

---

**Last Updated**: 2026-01-07
**Status**: Ready for implementation
**Confidence**: High (based on comprehensive git history analysis)
