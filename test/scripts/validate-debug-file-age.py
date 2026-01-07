#!/usr/bin/env python3
"""
Validator: validate-debug-file-age
Edge Case: EC008
Purpose: Prevent debug file accumulation - no files older than 30 days in debug/

Root Cause: 1923 debug files older than 30 days accumulated to 103MB without cleanup.
This validator prevents EC008 by checking debug/ directory for old files.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict


def validate(project_root: Path, max_age_days: int = 30) -> Dict:
    """
    Validate debug file age across debug/ directory.

    Checks that no files in debug/ are older than max_age_days.

    Args:
        project_root: Root directory of project to validate
        max_age_days: Maximum age in days (default 30)

    Returns:
        dict: Validation result with status and violations
    """
    violations = []

    debug_dir = project_root / "debug"
    if not debug_dir.exists():
        return {
            "validator": "validate-debug-file-age",
            "edge_case": "EC008",
            "status": "pass",
            "violations": [],
            "summary": {
                "total_files_checked": 0,
                "violations_found": 0,
                "oldest_file_days": 0
            },
            "recommendations": []
        }

    cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
    files_checked = 0
    total_size = 0
    oldest_file_age = 0

    for file_path in debug_dir.rglob("*"):
        if not file_path.is_file():
            continue

        # Skip archive directories (already archived files should not be counted)
        relative_parts = file_path.relative_to(debug_dir).parts
        if any(part.startswith('archive') for part in relative_parts):
            continue

        files_checked += 1
        file_mtime = file_path.stat().st_mtime
        file_age_days = (time.time() - file_mtime) / (24 * 60 * 60)

        oldest_file_age = max(oldest_file_age, file_age_days)

        if file_mtime < cutoff_time:
            file_size = file_path.stat().st_size
            total_size += file_size

            violations.append({
                "file": str(file_path.relative_to(project_root)),
                "age_days": int(file_age_days),
                "size_bytes": file_size,
                "last_modified": datetime.fromtimestamp(file_mtime).isoformat(),
                "severity": "critical",
                "reason": f"File older than {max_age_days} days"
            })

    return {
        "validator": "validate-debug-file-age",
        "edge_case": "EC008",
        "status": "pass" if not violations else "fail",
        "violations": violations,
        "summary": {
            "total_files_checked": files_checked,
            "violations_found": len(violations),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "oldest_file_days": int(oldest_file_age),
            "max_age_days": max_age_days
        },
        "recommendations": [
            f"Archive files older than {max_age_days} days to debug/archive-YYYY-MM/",
            f"Total space to free: {round(total_size / (1024 * 1024), 2)} MB",
            "Use /clean command to archive old debug files automatically",
            "Consider setting up automated cleanup (cron/systemd timer)"
        ] if violations else []
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate debug file age (EC008 prevention)"
    )
    parser.add_argument(
        "--project-root",
        required=True,
        help="Project root directory"
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=30,
        help="Maximum file age in days (default: 30)"
    )
    args = parser.parse_args()

    project_root = Path(args.project_root)
    if not project_root.exists():
        print(json.dumps({"error": "Project root does not exist"}), file=sys.stderr)
        sys.exit(1)

    result = validate(project_root, args.max_age_days)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    sys.exit(0 if result["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
