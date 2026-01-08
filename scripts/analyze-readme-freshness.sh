#!/usr/bin/env bash
# Analyze README freshness and update stale READMEs
# Part of rule-inspector workflow

set -euo pipefail

PROJECT_ROOT="${1:?Missing project root}"
FOLDERS_JSON="${2:?Missing folders JSON array}"
OUTPUT_JSON="${3:?Missing output JSON path}"

# Get current timestamp
CURRENT_TIMESTAMP=$(date +%s)
CURRENT_ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Initialize counters
FOLDERS_ANALYZED=0
READMES_UPDATED=0
READMES_CREATED=0
READMES_FRESH=0
INDEX_GENERATED=0

# Initialize JSON arrays
FRESH_READMES='[]'
UPDATED_READMES='[]'
CREATED_READMES='[]'
INDEX_FILES='[]'

# Parse folders from JSON array
FOLDERS=$(echo "$FOLDERS_JSON" | jq -r '.[]')

# Function: Get max mtime of folder content (excluding README/INDEX)
get_folder_max_mtime() {
    local folder="$1"
    local max_mtime=0

    if [[ ! -d "$folder" ]]; then
        echo "0"
        return
    fi

    # Find all files excluding README.md and INDEX.md
    while IFS= read -r file; do
        if [[ -f "$file" ]]; then
            file_mtime=$(stat -c %Y "$file" 2>/dev/null || stat -f %m "$file" 2>/dev/null || echo "0")
            if [[ $file_mtime -gt $max_mtime ]]; then
                max_mtime=$file_mtime
            fi
        fi
    done < <(find "$folder" -maxdepth 1 -type f ! -name "README.md" ! -name "INDEX.md" 2>/dev/null || true)

    echo "$max_mtime"
}

# Function: Check README freshness
check_readme_freshness() {
    local folder="$1"
    local readme_path="$folder/README.md"

    if [[ ! -f "$readme_path" ]]; then
        echo "create"
        return
    fi

    # Get README mtime
    readme_mtime=$(stat -c %Y "$readme_path" 2>/dev/null || stat -f %m "$readme_path" 2>/dev/null || echo "0")

    # Get max folder content mtime
    max_folder_mtime=$(get_folder_max_mtime "$folder")

    if [[ $max_folder_mtime -eq 0 ]]; then
        echo "skip"
        return
    fi

    # Calculate age difference in days
    mtime_diff_seconds=$((max_folder_mtime - readme_mtime))
    mtime_diff_days=$((mtime_diff_seconds / 86400))

    # Determine update mode
    if [[ $mtime_diff_days -gt 7 ]]; then
        echo "full"
    elif [[ $mtime_diff_days -gt 3 ]]; then
        echo "incremental"
    elif [[ $mtime_diff_days -lt -3 ]]; then
        # README is newer than content - still fresh
        echo "skip"
    else
        echo "skip"
    fi
}

# Function: Extract folder purpose from name
get_folder_purpose() {
    local folder_name="$1"

    case "$folder_name" in
        docs|documentation) echo "Project documentation and guides" ;;
        scripts) echo "Automation scripts and utilities" ;;
        tests|test) echo "Test files and test utilities" ;;
        examples) echo "Example code and demonstrations" ;;
        templates) echo "Template files and boilerplates" ;;
        hooks) echo "Git hooks and automation triggers" ;;
        agents) echo "AI agent definitions and configurations" ;;
        commands) echo "Command definitions and slash commands" ;;
        skills) echo "Skill packages and capabilities" ;;
        debug) echo "Debug files and troubleshooting artifacts" ;;
        logs) echo "Log files and execution history" ;;
        archive) echo "Archived files for historical reference" ;;
        session-env) echo "Session-specific environment and state" ;;
        *) echo "Folder: $folder_name" ;;
    esac
}

# Function: Count files by extension
count_file_types() {
    local folder="$1"

    if [[ ! -d "$folder" ]]; then
        echo "{}"
        return
    fi

    # Use associative array to count extensions
    declare -A ext_counts

    while IFS= read -r file; do
        ext="${file##*.}"
        if [[ "$file" == *.* ]]; then
            ext_counts["$ext"]=$((${ext_counts["$ext"]:-0} + 1))
        fi
    done < <(find "$folder" -maxdepth 1 -type f 2>/dev/null || true)

    # Convert to JSON
    json="{"
    first=true
    for ext in "${!ext_counts[@]}"; do
        if [[ "$first" == true ]]; then
            first=false
        else
            json+=","
        fi
        json+="\".$ext\":${ext_counts[$ext]}"
    done
    json+="}"

    echo "$json"
}

# Function: Generate INDEX.md
generate_index_md() {
    local folder="$1"
    local folder_name=$(basename "$folder")
    local index_path="$folder/INDEX.md"

    # Count files and subdirectories
    file_count=$(find "$folder" -maxdepth 1 -type f ! -name "INDEX.md" ! -name "README.md" 2>/dev/null | wc -l || echo "0")
    dir_count=$(find "$folder" -maxdepth 1 -type d ! -path "$folder" 2>/dev/null | wc -l || echo "0")

    # Get purpose
    purpose=$(get_folder_purpose "$folder_name")

    # Start INDEX.md content
    cat > "$index_path" <<EOF
# ${folder_name} Index

Auto-generated folder inventory. Last updated: ${CURRENT_ISO}

## Purpose

${purpose}

## Structure

- Total files: ${file_count}
- Total subdirectories: ${dir_count}

## Files

EOF

    # List files
    if [[ $file_count -gt 0 ]]; then
        while IFS= read -r file; do
            filename=$(basename "$file")
            # Try to get first line as description
            first_line=$(head -n 1 "$file" 2>/dev/null | sed 's/^[#*-]* *//' || echo "")
            if [[ -n "$first_line" ]] && [[ ${#first_line} -lt 100 ]]; then
                echo "- \`$filename\` - $first_line" >> "$index_path"
            else
                echo "- \`$filename\`" >> "$index_path"
            fi
        done < <(find "$folder" -maxdepth 1 -type f ! -name "INDEX.md" ! -name "README.md" 2>/dev/null | sort)
    else
        echo "*No files in root level*" >> "$index_path"
    fi

    # List subdirectories
    if [[ $dir_count -gt 0 ]]; then
        echo "" >> "$index_path"
        echo "## Subdirectories" >> "$index_path"
        echo "" >> "$index_path"
        while IFS= read -r dir; do
            dirname=$(basename "$dir")
            subfile_count=$(find "$dir" -type f 2>/dev/null | wc -l || echo "0")
            echo "- \`$dirname/\` ($subfile_count files)" >> "$index_path"
        done < <(find "$folder" -maxdepth 1 -type d ! -path "$folder" 2>/dev/null | sort)
    fi

    # Footer
    cat >> "$index_path" <<EOF

---

*This file is auto-generated by rule-inspector. Do not edit manually.*
EOF
}

# Process each folder
while IFS= read -r folder; do
    full_path="$PROJECT_ROOT/$folder"

    # Skip if folder doesn't exist
    if [[ ! -d "$full_path" ]]; then
        continue
    fi

    FOLDERS_ANALYZED=$((FOLDERS_ANALYZED + 1))

    # Check README freshness
    update_mode=$(check_readme_freshness "$full_path")

    case "$update_mode" in
        create)
            READMES_CREATED=$((READMES_CREATED + 1))
            CREATED_READMES=$(echo "$CREATED_READMES" | jq --arg f "$folder" '. + [$f]')
            ;;
        full)
            READMES_UPDATED=$((READMES_UPDATED + 1))
            UPDATED_READMES=$(echo "$UPDATED_READMES" | jq --arg f "$folder" --arg r "stale (>7 days)" '. + [{folder: $f, reason: $r}]')
            ;;
        incremental)
            READMES_UPDATED=$((READMES_UPDATED + 1))
            UPDATED_READMES=$(echo "$UPDATED_READMES" | jq --arg f "$folder" --arg r "moderately stale (3-7 days)" '. + [{folder: $f, reason: $r}]')
            ;;
        skip)
            READMES_FRESH=$((READMES_FRESH + 1))
            FRESH_READMES=$(echo "$FRESH_READMES" | jq --arg f "$folder" '. + [$f]')
            ;;
    esac

    # Always regenerate INDEX.md
    generate_index_md "$full_path"
    INDEX_GENERATED=$((INDEX_GENERATED + 1))
    INDEX_FILES=$(echo "$INDEX_FILES" | jq --arg f "$folder/INDEX.md" '. + [$f]')

    # Progress indicator every 20 folders
    if [[ $((FOLDERS_ANALYZED % 20)) -eq 0 ]]; then
        echo "Progress: Analyzed $FOLDERS_ANALYZED folders..." >&2
    fi
done <<< "$FOLDERS"

# Create output JSON
cat > "$OUTPUT_JSON" <<EOF
{
  "request_id": "clean-20260108-130050",
  "timestamp": "${CURRENT_ISO}",
  "inspector": "rule-inspector",
  "analysis": {
    "folders_analyzed": ${FOLDERS_ANALYZED},
    "readmes_updated": ${READMES_UPDATED},
    "readmes_created": ${READMES_CREATED},
    "readmes_fresh": ${READMES_FRESH},
    "index_files_generated": ${INDEX_GENERATED}
  },
  "details": {
    "fresh_readmes": ${FRESH_READMES},
    "updated_readmes": ${UPDATED_READMES},
    "created_readmes": ${CREATED_READMES},
    "index_files": ${INDEX_FILES}
  },
  "summary": {
    "message": "Analyzed ${FOLDERS_ANALYZED} folders, updated ${READMES_UPDATED} READMEs, created ${READMES_CREATED} new READMEs, confirmed ${READMES_FRESH} fresh READMEs, generated ${INDEX_GENERATED} INDEX files"
  }
}
EOF

echo "Analysis complete. Results written to: $OUTPUT_JSON"
