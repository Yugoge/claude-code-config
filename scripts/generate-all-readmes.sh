#!/usr/bin/env bash
# Generate all README files based on freshness analysis
# Part of rule-inspector workflow

set -euo pipefail

PROJECT_ROOT="${1:?Missing project root}"
FRESHNESS_JSON="${2:?Missing freshness analysis JSON}"
OUTPUT_JSON="${3:?Missing output JSON path}"

# Read freshness analysis
UPDATED_READMES=$(jq -r '.details.updated_readmes[] | "\(.folder)|\(.reason)"' "$FRESHNESS_JSON")
CREATED_READMES=$(jq -r '.details.created_readmes[]' "$FRESHNESS_JSON")

# Initialize counters
READMES_GENERATED=0
READMES_UPDATED=0
READMES_CREATED=0

# Arrays for tracking
GENERATED_LIST='[]'
ERRORS='[]'

# Function: Generate README for folder
generate_readme_for_folder() {
    local folder="$1"
    local mode="$2"
    local full_path="$PROJECT_ROOT/$folder"

    if [[ ! -d "$full_path" ]]; then
        ERRORS=$(echo "$ERRORS" | jq --arg f "$folder" --arg e "Folder not found" '. + [{folder: $f, error: $e}]')
        return 1
    fi

    # Run README generator
    if /root/.claude/scripts/generate-readme-from-git.sh "$full_path" "$mode" 2>&1; then
        READMES_GENERATED=$((READMES_GENERATED + 1))
        GENERATED_LIST=$(echo "$GENERATED_LIST" | jq --arg f "$folder/$README.md" '. + [$f]')

        if [[ "$mode" == "create" ]]; then
            READMES_CREATED=$((READMES_CREATED + 1))
        else
            READMES_UPDATED=$((READMES_UPDATED + 1))
        fi

        return 0
    else
        ERRORS=$(echo "$ERRORS" | jq --arg f "$folder" --arg e "README generation failed" '. + [{folder: $f, error: $e}]')
        return 1
    fi
}

echo "Generating README files..."

# Process updated READMEs
if [[ -n "$UPDATED_READMES" ]]; then
    while IFS='|' read -r folder reason; do
        echo "Updating: $folder ($reason)"

        # Determine mode from reason
        if echo "$reason" | grep -q ">7 days"; then
            mode="full"
        else
            mode="incremental"
        fi

        generate_readme_for_folder "$folder" "$mode" || true
    done <<< "$UPDATED_READMES"
fi

# Process new READMEs
if [[ -n "$CREATED_READMES" ]]; then
    while IFS= read -r folder; do
        echo "Creating: $folder"
        generate_readme_for_folder "$folder" "create" || true
    done <<< "$CREATED_READMES"
fi

# Create output report
CURRENT_ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cat > "$OUTPUT_JSON" <<EOF
{
  "request_id": "clean-20260108-130050",
  "timestamp": "${CURRENT_ISO}",
  "inspector": "rule-inspector",
  "readme_generation": {
    "total_generated": ${READMES_GENERATED},
    "created": ${READMES_CREATED},
    "updated": ${READMES_UPDATED},
    "errors": $(echo "$ERRORS" | jq -c .)
  },
  "generated_files": $(echo "$GENERATED_LIST" | jq -c .),
  "summary": {
    "message": "Generated ${READMES_GENERATED} README files (${READMES_CREATED} new, ${READMES_UPDATED} updated)"
  }
}
EOF

echo ""
echo "README generation complete!"
echo "Total generated: $READMES_GENERATED"
echo "New: $READMES_CREATED"
echo "Updated: $READMES_UPDATED"
echo "Results: $OUTPUT_JSON"
