#!/usr/bin/env python3
"""
Validator: validate-claude-md-protection
Edge Case: EC001
Purpose: Verify CLAUDE.md never flagged for relocation - protects official Claude Code files

Root Cause: Cleanliness inspector didn't know CLAUDE.md is an official Claude Code file and
recommended moving it to docs/. This validator prevents EC001 by checking that CLAUDE.md,
README.md, and ARCHITECTURE.md are explicitly protected in inspector logic.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List


def check_file_protected(content: str, filename: str) -> bool:
    """Check if filename is mentioned as protected/allowed in content."""
    # Look for patterns like "ALLOWED: README.md, CLAUDE.md" or explicit mentions
    protected_pattern = re.compile(
        rf'(?:ALLOWED|official|preserve|protect).*{re.escape(filename)}',
        re.IGNORECASE
    )
    return bool(protected_pattern.search(content))


def validate(project_root: Path) -> Dict:
    """
    Validate CLAUDE.md protection across inspection logic.

    Checks that official files are explicitly protected in:
    - agents/cleanliness-inspector.md
    - commands/clean.md
    - Recent inspection reports (no relocation recommendations)

    Args:
        project_root: Root directory of project to validate

    Returns:
        dict: Validation result with status and violations
    """
    violations = []

    official_files = ["CLAUDE.md", "README.md", "ARCHITECTURE.md"]

    # Check cleanliness-inspector.md
    inspector_path = project_root / "agents" / "cleanliness-inspector.md"
    if inspector_path.exists():
        try:
            with open(inspector_path, 'r', encoding='utf-8') as f:
                inspector_content = f.read()

            for official_file in official_files:
                if not check_file_protected(inspector_content, official_file):
                    violations.append({
                        "file": "agents/cleanliness-inspector.md",
                        "missing_protection": official_file,
                        "severity": "critical",
                        "reason": f"{official_file} not explicitly listed in official files allow-list"
                    })
        except Exception:
            pass

    # Check commands/clean.md
    clean_cmd_path = project_root / "commands" / "clean.md"
    if clean_cmd_path.exists():
        try:
            with open(clean_cmd_path, 'r', encoding='utf-8') as f:
                clean_content = f.read()

            for official_file in official_files:
                if not check_file_protected(clean_content, official_file):
                    violations.append({
                        "file": "commands/clean.md",
                        "missing_protection": official_file,
                        "severity": "major",
                        "reason": f"{official_file} not mentioned in documentation structure rules"
                    })
        except Exception:
            pass

    # Check recent inspection reports for relocation recommendations
    clean_reports_dir = project_root / "docs" / "clean"
    if clean_reports_dir.exists():
        try:
            for report_file in clean_reports_dir.glob("*-report-*.json"):
                # Skip archived reports
                if "archive" in str(report_file):
                    continue

                with open(report_file, 'r', encoding='utf-8') as f:
                    report = json.load(f)

                # Check for misplaced_docs recommendations
                if "findings" in report and "misplaced_docs" in report["findings"]:
                    for item in report["findings"]["misplaced_docs"]:
                        if any(official in item.get("file", "") for official in official_files):
                            violations.append({
                                "file": str(report_file.relative_to(project_root)),
                                "recommended_relocation": item.get("file"),
                                "severity": "critical",
                                "reason": "Official file flagged for relocation in inspection report"
                            })
        except Exception:
            pass

    return {
        "validator": "validate-claude-md-protection",
        "edge_case": "EC001",
        "status": "pass" if not violations else "fail",
        "violations": violations,
        "summary": {
            "official_files_checked": len(official_files),
            "violations_found": len(violations)
        },
        "recommendations": [
            "Add official files to allow-list in agents/cleanliness-inspector.md",
            "Document official files in commands/clean.md Step 1",
            "Format: 'ALLOWED: README.md, ARCHITECTURE.md, CLAUDE.md (official Claude Code files)'",
            "Review and update inspection reports to remove relocation recommendations"
        ] if violations else []
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate CLAUDE.md protection (EC001 prevention)"
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
