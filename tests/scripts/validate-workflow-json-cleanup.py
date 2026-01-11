#!/usr/bin/env python3
"""
Validator: validate-workflow-json-cleanup
Edge Case: General enforcement
Purpose: Ensure workflow JSONs are archived after completion - prevent accumulation

Root Cause: Workflow JSONs accumulated without archival policy (22 files in docs/dev/).
This validator checks that completed workflow JSONs older than 30 days are archived.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict


def validate(project_root: Path, max_age_days: int = 30) -> Dict:
    """
    Validate workflow JSON cleanup in docs/dev/ and docs/clean/.

    Checks that old workflow JSONs are archived.

    Args:
        project_root: Root directory of project to validate
        max_age_days: Maximum age before archival (default 30)

    Returns:
        dict: Validation result with status and violations
    """
    violations = []

    workflow_dirs = [
        project_root / "docs" / "dev",
        project_root / "docs" / "clean"
    ]

    cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
    files_checked = 0

    for workflow_dir in workflow_dirs:
        if not workflow_dir.exists():
            continue

        for json_file in workflow_dir.glob("*.json"):
            # Skip if already in archive/
            if "archive" in json_file.parts:
                continue

            files_checked += 1
            file_mtime = json_file.stat().st_mtime

            if file_mtime < cutoff_time:
                file_age_days = (time.time() - file_mtime) / (24 * 60 * 60)

                violations.append({
                    "file": str(json_file.relative_to(project_root)),
                    "age_days": int(file_age_days),
                    "severity": "medium",
                    "reason": f"Workflow JSON older than {max_age_days} days not archived",
                    "suggested_archive_path": str(
                        json_file.parent / f"archive/{json_file.parent.name}-YYYY-MM" / json_file.name
                    )
                })

    return {
        "validator": "validate-workflow-json-cleanup",
        "edge_case": "General",
        "status": "pass" if not violations else "fail",
        "violations": violations,
        "summary": {
            "total_files_checked": files_checked,
            "violations_found": len(violations)
        },
        "recommendations": [
            "Archive old workflow JSONs to docs/{workflow}/archive/YYYY-MM/",
            "Use /clean command to archive automatically",
            "Retention policy: Keep 30 days, archive older, delete after 90 days"
        ] if violations else []
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate workflow JSON cleanup"
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
