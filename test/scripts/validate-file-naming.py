#!/usr/bin/env python3
"""
Validator: validate-file-naming
Edge Case: EC007
Purpose: Ensure consistent file naming - docs/ files must use kebab-case

Root Cause: Mixed naming (UPPERCASE, snake_case, kebab-case) without enforcement.
This validator prevents EC007 by checking docs/ files follow kebab-case convention.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict


def is_kebab_case(name: str) -> bool:
    """Check if name follows kebab-case convention."""
    # Kebab-case: lowercase with hyphens (my-file-name.md)
    kebab_pattern = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*\.[a-z]+$')
    return bool(kebab_pattern.match(name))


def is_special_file(name: str) -> bool:
    """Check if file is special (README, INDEX, LICENSE, etc)."""
    special = ["README.md", "INDEX.md", "LICENSE", "CLAUDE.md", "ARCHITECTURE.md", "CONTRIBUTING.md"]
    return name in special


def validate(project_root: Path) -> Dict:
    """
    Validate file naming conventions in docs/ directory.

    Checks that .md files in docs/ use kebab-case (except special files).

    Args:
        project_root: Root directory of project to validate

    Returns:
        dict: Validation result with status and violations
    """
    violations = []

    docs_dir = project_root / "docs"
    if not docs_dir.exists():
        return {
            "validator": "validate-file-naming",
            "edge_case": "EC007",
            "status": "pass",
            "violations": [],
            "summary": {
                "total_files_checked": 0,
                "violations_found": 0
            },
            "recommendations": []
        }

    files_checked = 0

    for md_file in docs_dir.rglob("*.md"):
        # Skip archived files
        if "archive" in str(md_file):
            continue

        files_checked += 1
        filename = md_file.name

        # Skip special files
        if is_special_file(filename):
            continue

        if not is_kebab_case(filename):
            # Identify issue type
            if re.search(r'[A-Z]', filename):
                issue = "UPPERCASE or CamelCase"
            elif '_' in filename:
                issue = "snake_case"
            else:
                issue = "non-standard naming"

            violations.append({
                "file": str(md_file.relative_to(project_root)),
                "current_name": filename,
                "issue": issue,
                "suggested_name": filename.lower().replace('_', '-'),
                "severity": "minor"
            })

    return {
        "validator": "validate-file-naming",
        "edge_case": "EC007",
        "status": "pass" if not violations else "fail",
        "violations": violations,
        "summary": {
            "total_files_checked": files_checked,
            "violations_found": len(violations)
        },
        "recommendations": [
            "Rename files to kebab-case: lowercase-with-hyphens.md",
            "Keep special files UPPERCASE: README.md, INDEX.md, CLAUDE.md",
            "Use /clean command to normalize naming automatically"
        ] if violations else []
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate file naming conventions (EC007 prevention)"
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
