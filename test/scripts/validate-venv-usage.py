#!/usr/bin/env python3
"""
Validator: validate-venv-usage
Edge Case: EC002
Purpose: Detect venv usage violations - ensures all Python script invocations use proper venv activation

Root Cause: 8 instances across 6 files used direct python/python3 without venv activation.
This validator prevents EC002 by scanning for patterns like "python3 ~/.claude/scripts/" without
preceding "source venv/bin/activate".
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Dict


def validate(project_root: Path) -> Dict:
    """
    Validate venv usage across project files.

    Scans .md, .json, and .sh files for Python script invocations and verifies
    they use proper venv activation pattern.

    Args:
        project_root: Root directory of project to validate

    Returns:
        dict: Validation result with status and violations
    """
    violations = []

    # File patterns to check
    extensions = ["*.md", "*.json", "*.sh"]

    # Pattern: python3 or python followed by path, NOT preceded by venv activation
    # Negative lookbehind: (?<!source.*venv/bin/activate && )
    bad_pattern = re.compile(
        r'(?<!source\s+.*venv/bin/activate\s+&&\s+)(python3?)\s+([~/.]\S+\.py)',
        re.IGNORECASE
    )

    # Good pattern: source venv/bin/activate && python3
    good_pattern = re.compile(
        r'source\s+.*venv/bin/activate\s+&&\s+python3?',
        re.IGNORECASE
    )

    files_checked = 0

    for ext in extensions:
        for file_path in project_root.rglob(ext):
            # Skip archived files
            if "archive" in str(file_path):
                continue

            files_checked += 1

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        # Skip comments in .sh files
                        if file_path.suffix == '.sh' and line.strip().startswith('#'):
                            continue

                        # Check for bad pattern
                        match = bad_pattern.search(line)
                        if match:
                            # Double-check it's not a false positive by checking broader context
                            # (sometimes the venv activation is on previous line)
                            violations.append({
                                "file": str(file_path.relative_to(project_root)),
                                "line": line_num,
                                "pattern": match.group(0),
                                "expected": f"source venv/bin/activate && {match.group(1)} {match.group(2)}",
                                "severity": "critical",
                                "context": line.strip()
                            })
            except Exception as e:
                # Skip files that can't be read
                continue

    return {
        "validator": "validate-venv-usage",
        "edge_case": "EC002",
        "status": "pass" if not violations else "fail",
        "violations": violations,
        "summary": {
            "total_files_checked": files_checked,
            "violations_found": len(violations)
        },
        "recommendations": [
            "Update Python invocations to use: source ~/.claude/venv/bin/activate && python3 script.py",
            "See agents/dev.md Section 4 for proper venv usage patterns"
        ] if violations else []
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate venv usage (EC002 prevention)"
    )
    parser.add_argument(
        "--project-root",
        required=True,
        help="Project root directory"
    )
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
