#!/usr/bin/env bash
# Description: Validates all 4 overnight exploration reports exist and are valid JSON
# Usage: check-overnight-reports.sh [report_dir]
# Exit codes: 0=all present and valid, 1=any missing or invalid

set -euo pipefail

REPORT_DIR="${1:-docs/dev/overnight}"

EXPECTED_FILES=(
    "product-owner-report.json"
    "architect-report.json"
    "user-report.json"
    "ui-specialist-report.json"
)

MISSING=0
INVALID=0

for file in "${EXPECTED_FILES[@]}"; do
    filepath="${REPORT_DIR}/${file}"
    if [[ ! -f "$filepath" ]]; then
        echo "MISSING: $filepath" >&2
        MISSING=$((MISSING + 1))
        continue
    fi
    if ! python3 -c "import json; json.load(open('${filepath}'))" 2>/dev/null; then
        echo "INVALID JSON: $filepath" >&2
        INVALID=$((INVALID + 1))
        continue
    fi
    echo "OK: $filepath"
done

TOTAL_ERRORS=$((MISSING + INVALID))
if [[ $TOTAL_ERRORS -gt 0 ]]; then
    echo "FAILED: ${MISSING} missing, ${INVALID} invalid out of ${#EXPECTED_FILES[@]} reports" >&2
    exit 1
fi

echo "ALL ${#EXPECTED_FILES[@]} reports present and valid"
exit 0
