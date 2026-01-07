#!/usr/bin/env python3
"""
Validator: validate-todowrite-requirement
Edge Case: EC003
Purpose: Verify TodoWrite requirement enforced - multi-step workflows must have todo scripts

Root Cause: User explicitly required TodoWrite for multi-step workflows but dev.md checklist
had no verification item. This validator prevents EC003 by checking that commands with 3+
steps have corresponding todo scripts in scripts/todo/.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Dict


def count_workflow_steps(content: str) -> int:
    """Count workflow steps in markdown content."""
    # Pattern: Step N: or ### Step N
    step_pattern = re.compile(r'(?:^###?\s+Step\s+\d+|^Step\s+\d+:)', re.MULTILINE)
    matches = step_pattern.findall(content)
    return len(matches)


def validate(project_root: Path) -> Dict:
    """
    Validate TodoWrite requirement across command files.

    Checks that commands with 3+ steps have corresponding todo scripts.

    Args:
        project_root: Root directory of project to validate

    Returns:
        dict: Validation result with status and violations
    """
    violations = []

    commands_dir = project_root / "commands"
    todo_dir = project_root / "scripts" / "todo"

    if not commands_dir.exists():
        return {
            "validator": "validate-todowrite-requirement",
            "edge_case": "EC003",
            "status": "pass",
            "violations": [],
            "summary": {
                "total_commands_checked": 0,
                "violations_found": 0
            },
            "recommendations": []
        }

    files_checked = 0

    for cmd_file in commands_dir.glob("*.md"):
        files_checked += 1

        try:
            with open(cmd_file, 'r', encoding='utf-8') as f:
                content = f.read()

            step_count = count_workflow_steps(content)

            # If 3+ steps, must have todo script
            if step_count >= 3:
                todo_script = todo_dir / f"{cmd_file.stem}.py"

                if not todo_script.exists():
                    violations.append({
                        "file": str(cmd_file.relative_to(project_root)),
                        "steps": step_count,
                        "missing_todo_script": str(todo_script.relative_to(project_root)),
                        "severity": "critical",
                        "reason": f"Command has {step_count} steps but no todo script"
                    })
                else:
                    # Verify todo script has matching step count
                    with open(todo_script, 'r', encoding='utf-8') as f:
                        todo_content = f.read()

                    # Count todo items in script
                    todo_pattern = re.compile(r'\{"content":', re.MULTILINE)
                    todo_count = len(todo_pattern.findall(todo_content))

                    if todo_count != step_count:
                        violations.append({
                            "file": str(cmd_file.relative_to(project_root)),
                            "steps_in_command": step_count,
                            "steps_in_todo": todo_count,
                            "todo_script": str(todo_script.relative_to(project_root)),
                            "severity": "major",
                            "reason": f"Step count mismatch: {step_count} in command vs {todo_count} in todo"
                        })

        except Exception:
            continue

    return {
        "validator": "validate-todowrite-requirement",
        "edge_case": "EC003",
        "status": "pass" if not violations else "fail",
        "violations": violations,
        "summary": {
            "total_commands_checked": files_checked,
            "violations_found": len(violations)
        },
        "recommendations": [
            "Create todo script: scripts/todo/{command-name}.py",
            "Use clean.py or dev.py as template",
            "Ensure todo script step count matches command step count",
            "See agents/dev.md Section 7 for todo script requirements"
        ] if violations else []
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate TodoWrite requirement (EC003 prevention)"
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
