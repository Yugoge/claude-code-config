#!/usr/bin/env python3
"""
Validator: validate-checklist-completeness
Edge Case: General enforcement
Purpose: Verify Quality Checklist covers all user requirements

Root Cause: User requirements existed but weren't in Quality Checklist (TodoWrite, decimal steps).
This validator checks that critical requirements are present in agents/dev.md checklist.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List


# Critical requirements that MUST be in checklist
REQUIRED_CHECKLIST_ITEMS = [
    "Todo script created",
    "No decimal step numbering",
    "source venv",
    "No hardcoded values",
    "Meaningful naming",
    "Git root cause",
    "Exit codes documented"
]


def validate(project_root: Path) -> Dict:
    """
    Validate Quality Checklist completeness in agents/dev.md.

    Checks that all critical requirements are present in checklist.

    Args:
        project_root: Root directory of project to validate

    Returns:
        dict: Validation result with status and violations
    """
    violations = []

    dev_agent_path = project_root / "agents" / "dev.md"
    if not dev_agent_path.exists():
        return {
            "validator": "validate-checklist-completeness",
            "edge_case": "General",
            "status": "fail",
            "violations": [{
                "file": "agents/dev.md",
                "reason": "File not found",
                "severity": "critical"
            }],
            "summary": {
                "required_items": len(REQUIRED_CHECKLIST_ITEMS),
                "found_items": 0,
                "missing_items": len(REQUIRED_CHECKLIST_ITEMS)
            },
            "recommendations": ["Create agents/dev.md with complete Quality Checklist"]
        }

    try:
        with open(dev_agent_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find Quality Checklist section
        checklist_start = content.find("## Quality Checklist")
        if checklist_start == -1:
            violations.append({
                "file": "agents/dev.md",
                "reason": "Quality Checklist section not found",
                "severity": "critical"
            })
            checklist_content = ""
        else:
            # Extract checklist section (until next ## heading)
            next_section = content.find("\n##", checklist_start + 1)
            if next_section == -1:
                checklist_content = content[checklist_start:]
            else:
                checklist_content = content[checklist_start:next_section]

        # Check each required item
        missing_items = []
        for required_item in REQUIRED_CHECKLIST_ITEMS:
            # Case-insensitive search
            if required_item.lower() not in checklist_content.lower():
                missing_items.append(required_item)
                violations.append({
                    "file": "agents/dev.md",
                    "missing_item": required_item,
                    "severity": "major",
                    "reason": f"Required checklist item '{required_item}' not found"
                })

    except Exception as e:
        violations.append({
            "file": "agents/dev.md",
            "reason": f"Error reading file: {e}",
            "severity": "critical"
        })
        missing_items = REQUIRED_CHECKLIST_ITEMS

    return {
        "validator": "validate-checklist-completeness",
        "edge_case": "General",
        "status": "pass" if not violations else "fail",
        "violations": violations,
        "summary": {
            "required_items": len(REQUIRED_CHECKLIST_ITEMS),
            "found_items": len(REQUIRED_CHECKLIST_ITEMS) - len(missing_items),
            "missing_items": len(missing_items)
        },
        "recommendations": [
            "Add missing items to Quality Checklist in agents/dev.md",
            "Ensure checklist is within '## Quality Checklist' section",
            f"Missing: {', '.join(missing_items)}" if missing_items else "All required items present"
        ] if violations else []
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate Quality Checklist completeness"
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
