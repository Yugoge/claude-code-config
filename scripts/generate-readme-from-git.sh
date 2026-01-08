#!/usr/bin/env bash
# Generate README.md from Git history analysis
# Part of rule-inspector workflow

set -euo pipefail

FOLDER="${1:?Missing folder path}"
UPDATE_MODE="${2:-create}"  # create, full, incremental

# Get current timestamp
CURRENT_ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
CURRENT_TIMESTAMP=$(date +%s)

# README path
README_PATH="$FOLDER/README.md"
FOLDER_NAME=$(basename "$FOLDER")

# Function: Analyze Git history for folder
analyze_git_history() {
    local folder="$1"
    local analysis=""

    # Get first commit that created files in this folder
    first_commit=$(git log --diff-filter=A --format="%ai|%H|%s" --reverse -- "$folder" 2>/dev/null | head -n 1 || echo "")

    if [[ -n "$first_commit" ]]; then
        first_date=$(echo "$first_commit" | cut -d'|' -f1 | cut -d' ' -f1)
        first_msg=$(echo "$first_commit" | cut -d'|' -f3-)
        analysis="First created: $first_date\n"
        analysis+="Creation context: $first_msg\n"
    fi

    # Count total commits affecting this folder
    total_commits=$(git log --format="%H" -- "$folder" 2>/dev/null | wc -l || echo "0")
    analysis+="Total commits: $total_commits\n"

    # Get last significant update (excluding INDEX/README updates)
    last_update=$(git log --format="%ai" -- "$folder" ! -- "$folder/INDEX.md" ! -- "$folder/README.md" 2>/dev/null | head -n 1 || echo "")
    if [[ -n "$last_update" ]]; then
        last_date=$(echo "$last_update" | cut -d' ' -f1)
        analysis+="Last significant update: $last_date\n"
    fi

    echo -e "$analysis"
}

# Function: Detect naming convention
detect_naming_convention() {
    local folder="$1"

    # Count different naming patterns
    local kebab_count=$(find "$folder" -maxdepth 1 -type f -name "*-*.*" 2>/dev/null | wc -l || echo "0")
    local snake_count=$(find "$folder" -maxdepth 1 -type f -name "*_*.*" 2>/dev/null | wc -l || echo "0")
    local total_files=$(find "$folder" -maxdepth 1 -type f 2>/dev/null | wc -l || echo "1")

    # Avoid division by zero
    if [[ $total_files -eq 0 ]]; then
        echo "No files to analyze"
        return
    fi

    local kebab_percent=$((kebab_count * 100 / total_files))
    local snake_percent=$((snake_count * 100 / total_files))

    if [[ $kebab_percent -gt 60 ]]; then
        echo "kebab-case (lowercase with hyphens, e.g., \`my-file.md\`)"
    elif [[ $snake_percent -gt 60 ]]; then
        echo "snake_case (lowercase with underscores, e.g., \`my_file.py\`)"
    else
        echo "Mixed naming conventions (no dominant pattern)"
    fi
}

# Function: Detect allowed file types
detect_file_types() {
    local folder="$1"

    # Get all unique extensions
    local extensions=$(find "$folder" -maxdepth 1 -type f -name "*.*" 2>/dev/null | sed 's/.*\.//' | sort | uniq || echo "")

    if [[ -z "$extensions" ]]; then
        echo "No specific file type restrictions detected"
        return
    fi

    # Count files per extension
    local result=""
    while IFS= read -r ext; do
        if [[ -n "$ext" ]]; then
            count=$(find "$folder" -maxdepth 1 -type f -name "*.$ext" 2>/dev/null | wc -l || echo "0")
            result+="- \`.$ext\` files: $count found\n"
        fi
    done <<< "$extensions"

    echo -e "$result"
}

# Function: Detect file creation patterns
detect_creation_patterns() {
    local folder="$1"
    local patterns=""

    # Analyze commit messages for pattern detection
    local commit_messages=$(git log --format="%s" -- "$folder" 2>/dev/null | head -n 50 || echo "")

    # Count pattern occurrences (use grep -c with proper handling)
    local command_count=0
    local manual_count=0
    local auto_count=0

    if [[ -n "$commit_messages" ]]; then
        command_count=$(echo "$commit_messages" | grep -c "^/" 2>/dev/null || echo "0")
        manual_count=$(echo "$commit_messages" | grep -c -i "manual\|add\|create" 2>/dev/null || echo "0")
        auto_count=$(echo "$commit_messages" | grep -c -i "auto\|script\|generated" 2>/dev/null || echo "0")
    fi

    # Trim whitespace and ensure numeric
    command_count=$(echo "$command_count" | tr -d '[:space:]')
    manual_count=$(echo "$manual_count" | tr -d '[:space:]')
    auto_count=$(echo "$auto_count" | tr -d '[:space:]')

    patterns+="Based on Git history analysis:\n\n"

    if [[ ${command_count:-0} -gt 5 ]]; then
        patterns+="- Primarily created by slash commands (automated workflow)\n"
    fi

    if [[ ${auto_count:-0} -gt 5 ]]; then
        patterns+="- Many auto-generated files (scripts/tools)\n"
    fi

    if [[ ${manual_count:-0} -gt 5 ]]; then
        patterns+="- Contains manually created content\n"
    fi

    if [[ ${command_count:-0} -eq 0 ]] && [[ ${auto_count:-0} -eq 0 ]]; then
        patterns+="- Manually maintained folder\n"
    fi

    echo -e "$patterns"
}

# Function: Get folder purpose
get_folder_purpose() {
    local folder_name="$1"

    case "$folder_name" in
        docs|documentation) echo "Project documentation and guides" ;;
        scripts) echo "Automation scripts and utilities for project workflows" ;;
        tests|test) echo "Test files and test utilities" ;;
        examples) echo "Example code and demonstrations" ;;
        templates) echo "Template files and boilerplates" ;;
        hooks) echo "Git hooks and automation triggers" ;;
        agents) echo "AI agent definitions and configurations for orchestrated workflows" ;;
        commands) echo "Command definitions and slash commands" ;;
        skills) echo "Skill packages and capabilities" ;;
        debug) echo "Debug files and troubleshooting artifacts" ;;
        logs) echo "Log files and execution history" ;;
        archive) echo "Archived files for historical reference" ;;
        session-env) echo "Session-specific environment and state files" ;;
        bin) echo "Binary files and compiled executables" ;;
        plugins) echo "Plugin files and extensions" ;;
        projects) echo "Project-specific files and configurations" ;;
        learning-materials) echo "Personal learning resources and study materials" ;;
        todos) echo "Task tracking and TODO lists" ;;
        *) echo "Folder for ${folder_name//-/ }" ;;
    esac
}

# Function: Generate organization rules
generate_organization_rules() {
    local folder="$1"
    local rules=""

    # Check for subdirectory structure
    local subdir_count=$(find "$folder" -maxdepth 1 -type d ! -path "$folder" 2>/dev/null | wc -l || echo "0")

    if [[ $subdir_count -gt 0 ]]; then
        rules+="- Files organized into subdirectories by category\n"

        # List subdirectories
        while IFS= read -r subdir; do
            local subdir_name=$(basename "$subdir")
            rules+="  - \`$subdir_name/\`: $(get_folder_purpose "$subdir_name")\n"
        done < <(find "$folder" -maxdepth 1 -type d ! -path "$folder" 2>/dev/null | sort || true)
    fi

    # Check for archive pattern
    if echo "$folder" | grep -q "archive"; then
        rules+="- Archive folder: historical files for reference only\n"
        rules+="- Do not modify archived files\n"
    fi

    # Check for date-based organization
    if ls "$folder"/*-202* 2>/dev/null | head -n 1 | grep -q "202"; then
        rules+="- Files organized by date (YYYY-MM-DD pattern)\n"
    fi

    echo -e "$rules"
}

# Main README generation
generate_readme() {
    local mode="$1"

    # Get analysis data
    local purpose=$(get_folder_purpose "$FOLDER_NAME")
    local git_analysis=$(analyze_git_history "$FOLDER")
    local naming_conv=$(detect_naming_convention "$FOLDER")
    local file_types=$(detect_file_types "$FOLDER")
    local creation_patterns=$(detect_creation_patterns "$FOLDER")
    local org_rules=$(generate_organization_rules "$FOLDER")

    # Build README content
    local content=""

    content+="# $FOLDER_NAME\n\n"
    content+="$purpose\n\n"
    content+="---\n\n"

    content+="## Purpose\n\n"
    content+="This folder contains files and resources for: $purpose\n\n"

    content+="## File Organization\n\n"
    if [[ -n "$org_rules" ]]; then
        content+="$org_rules\n"
    else
        content+="Files are stored at the root level of this folder.\n\n"
    fi

    content+="## Allowed File Types\n\n"
    content+="$file_types\n"

    content+="## Naming Convention\n\n"
    content+="$naming_conv\n\n"

    content+="## File Creation Patterns\n\n"
    content+="$creation_patterns\n"

    content+="## Standards\n\n"
    content+="- Follow the naming convention specified above\n"
    content+="- Keep files organized according to the folder structure\n"
    content+="- See INDEX.md for complete file inventory\n\n"

    content+="---\n\n"
    content+="## Git Analysis\n\n"
    content+="<!-- AUTO-GENERATED by rule-inspector - DO NOT EDIT -->\n"
    content+="$git_analysis"
    content+="<!-- END AUTO-GENERATED -->\n\n"

    content+="---\n\n"
    content+="*This README documents the discovered organization patterns for this folder.*\n"
    content+="*Generated by rule-inspector from git history analysis on $CURRENT_ISO*\n"

    # Write README
    echo -e "$content" > "$README_PATH"
}

# Handle different update modes
case "$UPDATE_MODE" in
    create)
        generate_readme "create"
        echo "Created: $README_PATH"
        ;;
    full)
        generate_readme "full"
        echo "Updated (full): $README_PATH"
        ;;
    incremental)
        # For incremental, only update Git Analysis section
        if [[ -f "$README_PATH" ]]; then
            git_analysis=$(analyze_git_history "$FOLDER")

            # Replace Git Analysis section
            if grep -q "<!-- AUTO-GENERATED by rule-inspector" "$README_PATH"; then
                # Update existing auto-generated section
                sed -i '/<!-- AUTO-GENERATED by rule-inspector/,/<!-- END AUTO-GENERATED -->/c\<!-- AUTO-GENERATED by rule-inspector - DO NOT EDIT -->\n'"$git_analysis"'\n<!-- END AUTO-GENERATED -->' "$README_PATH"
                echo "Updated (incremental): $README_PATH"
            else
                # No auto-generated section, do full update
                generate_readme "full"
                echo "Updated (full, no auto-gen section found): $README_PATH"
            fi
        else
            generate_readme "create"
            echo "Created: $README_PATH"
        fi
        ;;
    skip)
        echo "Skipped (fresh): $README_PATH"
        ;;
    *)
        echo "Unknown update mode: $UPDATE_MODE" >&2
        exit 1
        ;;
esac
