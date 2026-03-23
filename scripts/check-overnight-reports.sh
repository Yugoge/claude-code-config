#!/usr/bin/env bash
# Description: Validates all 4 overnight exploration reports exist, are valid JSON,
#              and conform to the expected schema (issues array with required fields).
# Usage: check-overnight-reports.sh <report_dir>
# Exit codes: 0=all present and valid, 1=any missing/invalid/malformed
# Output: per-file status lines + total issue count summary

set -euo pipefail

REPORT_DIR="${1:?Usage: check-overnight-reports.sh <report_dir>}"

EXPECTED_FILES=(
    "product-owner-report.json"
    "architect-report.json"
    "user-report.json"
    "ui-specialist-report.json"
)

MISSING=0
INVALID=0
SCHEMA_ERRORS=0
TOTAL_ISSUES=0

validate_schema() {
    python3 -c "
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
errors = []
if 'issues' not in data or not isinstance(data['issues'], list):
    errors.append('missing or non-array \"issues\" field')
else:
    required = {'description','location','severity','category','estimated_effort'}
    for i, issue in enumerate(data['issues']):
        missing = required - set(issue.keys())
        if missing:
            errors.append(f'issue[{i}] missing fields: {missing}')
    print(len(data['issues']))
if errors:
    print('SCHEMA_ERRORS:' + '|'.join(errors), file=sys.stderr)
    sys.exit(1)
" "$1"
}

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
    count=$(validate_schema "$filepath" 2>/dev/null) || {
        echo "SCHEMA ERROR: $filepath" >&2
        SCHEMA_ERRORS=$((SCHEMA_ERRORS + 1))
        continue
    }
    TOTAL_ISSUES=$((TOTAL_ISSUES + count))
    echo "OK: $filepath ($count issues)"
done

TOTAL_ERRORS=$((MISSING + INVALID + SCHEMA_ERRORS))
if [[ $TOTAL_ERRORS -gt 0 ]]; then
    echo "FAILED: ${MISSING} missing, ${INVALID} invalid, ${SCHEMA_ERRORS} schema errors" >&2
    exit 1
fi

echo "ALL ${#EXPECTED_FILES[@]} reports valid | Total issues: ${TOTAL_ISSUES}"
exit 0
