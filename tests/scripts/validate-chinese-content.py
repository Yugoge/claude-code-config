#!/usr/bin/env python3
"""
Validator: validate-chinese-content
Edge Case: EC006
Purpose: Detect Chinese content in functional code - ensures English-only in .sh/.py/.json

Root Cause: 7 files contained Chinese violating English-only standard for functional code.
This validator prevents EC006 by scanning functional files for Chinese Unicode characters.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict


def has_chinese(text: str) -> bool:
    """Check if text contains Chinese characters."""
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
    return bool(chinese_pattern.search(text))


def validate(project_root: Path) -> Dict:
    """
    Validate no Chinese content in functional code files.

    Scans .sh, .py, .json files (excluding docs/) for Chinese Unicode characters.

    Args:
        project_root: Root directory of project to validate

    Returns:
        dict: Validation result with status and violations
    """
    violations = []

    # Functional file extensions
    extensions = ["*.sh", "*.py", "*.json"]

    files_checked = 0

    for ext in extensions:
        for file_path in project_root.rglob(ext):
            # Skip docs/, archive/, venv/ directories entirely
            # For test/, only allow test/scripts/ to be checked
            relative_parts = file_path.relative_to(project_root).parts

            # Exclude these directories entirely
            if any(part in ["docs", "archive", "venv"] for part in relative_parts):
                continue

            # For test/, exclude test/reports/ and test/data/
            if "test" in relative_parts:
                if not ("scripts" in relative_parts):
                    continue

            files_checked += 1

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if has_chinese(line):
                            violations.append({
                                "file": str(file_path.relative_to(project_root)),
                                "line": line_num,
                                "content": line.strip()[:100],  # First 100 chars
                                "severity": "major",
                                "context": "Chinese characters in functional code"
                            })
            except Exception:
                continue

    return {
        "validator": "validate-chinese-content",
        "edge_case": "EC006",
        "status": "pass" if not violations else "fail",
        "violations": violations,
        "summary": {
            "total_files_checked": files_checked,
            "violations_found": len(violations)
        },
        "recommendations": [
            "Translate Chinese content to English",
            "Move bilingual documentation to docs/ (allowed there)",
            "Archive legacy Chinese files to docs/archive/legacy-chinese/",
            "Use English-only for .sh, .py, .json files"
        ] if violations else []
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate no Chinese in functional code (EC006 prevention)"
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
