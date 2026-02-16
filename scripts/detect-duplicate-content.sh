#!/bin/bash
set -e

PROJECT_ROOT="${1:-.}"
cd "$PROJECT_ROOT"

# Find all text files, compute checksums, find duplicates
# Exclude: .git, venv, node_modules, __pycache__, binary files
temp_file=$(mktemp)

find . -type f \
    -not -path './.git/*' \
    -not -path './venv/*' \
    -not -path './node_modules/*' \
    -not -path './__pycache__/*' \
    -not -path './docs/archive/*' \
    -not -path './archive/*' \
    -not -name '*.pyc' \
    -not -name '*.pyo' \
    -not -name '*.so' \
    -not -name '*.o' \
    -size +0c \
    -print0 2>/dev/null | xargs -0 sha256sum 2>/dev/null | sort > "$temp_file"

# Find duplicate checksums
items="[]"
dup_hashes=$(awk '{print $1}' "$temp_file" | sort | uniq -d)

if [ -n "$dup_hashes" ]; then
    items=$(echo "$dup_hashes" | while IFS= read -r hash; do
        files=$(grep "^$hash " "$temp_file" | awk '{print $2}' | jq -R . | jq -s .)
        size=$(grep "^$hash " "$temp_file" | head -1 | awk '{print $2}' | xargs wc -c 2>/dev/null | awk '{print $1}')
        echo "{\"checksum\": \"${hash:0:16}...\", \"files\": $files, \"file_size_bytes\": ${size:-0}, \"severity\": \"minor\"}"
    done | jq -s '.')
fi

rm -f "$temp_file"

total=$(echo "$items" | jq 'length')
cat <<EOF
{
  "detector": "duplicate-content",
  "project_root": "$PROJECT_ROOT",
  "findings": $items,
  "summary": {
    "total_duplicate_groups": $total,
    "severity": $([ "$total" -gt 0 ] && echo '"minor"' || echo '"none"')
  }
}
EOF
