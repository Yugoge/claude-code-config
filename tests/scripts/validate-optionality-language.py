#!/usr/bin/env python3
"""
Validator: validate-optionality-language
Edge Case: EC005
Purpose: Detect ambiguous optionality - ensures steps labeled "(Optional)" have clear conditions

Root Cause: Step 3.5 labeled "(Optional)" was routinely skipped despite being conditionally mandatory.
This validator prevents EC005 by detecting "(Optional)" in step titles and verifying execution conditions.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict


def validate(project_root: Path) -> Dict:
    """
    Validate optionality language in workflow steps.

    Checks for "(Optional)" in step titles and verifies clear execution conditions present.

    Args:
        project_root: Root directory of project to validate

    Returns:
        dict: Validation result with status and violations
    """
    violations = []

    commands_dir = project_root / "commands"
    if not commands_dir.exists():
        return {
            "validator": "validate-optionality-language",
            "edge_case": "EC005",
            "status": "pass",
            "violations": [],
            "summary": {
                "total_files_checked": 0,
                "violations_found": 0
            },
            "recommendations": []
        }

    # Pattern: Step N: Title (Optional)
    optional_pattern = re.compile(r'((?:###?\s+)?Step\s+\d+:?\s+[^\n]*\(Optional\))', re.IGNORECASE)

    # Positive condition patterns (good)
    condition_patterns = [
        re.compile(r'MUST\s+execute\s+if', re.IGNORECASE),
        re.compile(r'Only\s+(?:execute|run)\s+if', re.IGNORECASE),
        re.compile(r'Execute\s+when', re.IGNORECASE),
        re.compile(r'Run\s+this\s+step\s+if', re.IGNORECASE)
    ]

    files_checked = 0

    for md_file in commands_dir.glob("*.md"):
        files_checked += 1

        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Find all optional steps
            for line_num, line in enumerate(content.split('\n'), 1):
                match = optional_pattern.search(line)
                if match:
                    # Found "(Optional)" in step title
                    # Check if clear conditions are documented within next 20 lines
                    start_pos = content.find(line)
                    if start_pos != -1:
                        context = content[start_pos:start_pos + 1000]  # Check next ~20 lines
                        has_clear_conditions = any(p.search(context) for p in condition_patterns)

                        if not has_clear_conditions:
                            violations.append({
                                "file": str(md_file.relative_to(project_root)),
                                "line": line_num,
                                "step_title": match.group(1).strip(),
                                "severity": "critical",
                                "reason": "Step labeled '(Optional)' lacks clear execution conditions",
                                "context": line.strip()
                            })
        except Exception:
            continue

    return {
        "validator": "validate-optionality-language",
        "edge_case": "EC005",
        "status": "pass" if not violations else "fail",
        "violations": violations,
        "summary": {
            "total_files_checked": files_checked,
            "violations_found": len(violations)
        },
        "recommendations": [
            "Remove '(Optional)' label from conditionally-mandatory steps",
            "Use explicit conditions: 'MUST execute if X' or 'Only run if Y'",
            "Use positive conditions (execute if) not negative (skip unless)",
            "Add verification checkpoint with bash validation",
            "See commands/clean.md Step 4 for proper conditional step documentation"
        ] if violations else []
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate optionality language (EC005 prevention)"
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
