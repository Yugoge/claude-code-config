#!/usr/bin/env bash
# Description: Merge test/ folder into tests/ preserving all content (idempotent)
# Usage: migrate-test-to-tests.sh --project-root <path>
# Exit codes: 0=success, 1=failure, 2=nothing to migrate

set -euo pipefail

# Parse parameters
PROJECT_ROOT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-root)
      PROJECT_ROOT="$2"
      shift 2
      ;;
    *)
      echo "Error: Unknown parameter: $1" >&2
      echo "Usage: migrate-test-to-tests.sh --project-root <path>" >&2
      exit 1
      ;;
  esac
done

# Validate required parameters
if [[ -z "$PROJECT_ROOT" ]]; then
  echo "Error: --project-root is required" >&2
  exit 1
fi

if [[ ! -d "$PROJECT_ROOT" ]]; then
  echo "Error: Project root not found: $PROJECT_ROOT" >&2
  exit 1
fi

TEST_DIR="$PROJECT_ROOT/test"
TESTS_DIR="$PROJECT_ROOT/tests"

# Check if test/ folder exists
if [[ ! -d "$TEST_DIR" ]]; then
  echo "No test/ folder found - nothing to migrate" >&2
  exit 2
fi

echo "Found test/ folder - migrating to tests/" >&2

# Create tests/ folder if it doesn't exist
if [[ ! -d "$TESTS_DIR" ]]; then
  echo "Creating tests/ folder..." >&2
  mkdir -p "$TESTS_DIR"
fi

# Track migration statistics
FILES_MIGRATED=0
FILES_SKIPPED=0
DIRS_CREATED=0

# Function to migrate files/directories
migrate_content() {
  local source_path="$1"
  local relative_path="${source_path#$TEST_DIR/}"
  local dest_path="$TESTS_DIR/$relative_path"

  # Skip if source doesn't exist
  if [[ ! -e "$source_path" ]]; then
    return
  fi

  # If it's a directory
  if [[ -d "$source_path" ]]; then
    # Create destination directory if it doesn't exist
    if [[ ! -d "$dest_path" ]]; then
      echo "  Creating directory: $relative_path" >&2
      mkdir -p "$dest_path"
      DIRS_CREATED=$((DIRS_CREATED + 1))
    fi

    # Recursively process contents
    for item in "$source_path"/* "$source_path"/.*; do
      # Skip . and ..
      if [[ "$(basename "$item")" == "." ]] || [[ "$(basename "$item")" == ".." ]]; then
        continue
      fi

      # Skip if item doesn't exist (handles empty globs)
      if [[ ! -e "$item" ]]; then
        continue
      fi

      migrate_content "$item"
    done
  # If it's a file
  elif [[ -f "$source_path" ]]; then
    # Check if destination file already exists
    if [[ -f "$dest_path" ]]; then
      # Compare contents
      if cmp -s "$source_path" "$dest_path"; then
        echo "  Skipping $relative_path - identical file exists in tests/" >&2
        FILES_SKIPPED=$((FILES_SKIPPED + 1))
      else
        # Files differ - create backup and copy
        echo "  ⚠️  $relative_path exists in both locations with different content" >&2
        echo "     Creating backup: ${dest_path}.from-test-folder" >&2
        cp "$source_path" "${dest_path}.from-test-folder"
        FILES_MIGRATED=$((FILES_MIGRATED + 1))
      fi
    else
      # Destination doesn't exist - copy file
      echo "  Migrating: $relative_path" >&2
      cp -a "$source_path" "$dest_path"
      FILES_MIGRATED=$((FILES_MIGRATED + 1))
    fi
  fi
}

# Migrate all content from test/ to tests/
echo "Migrating content from test/ to tests/..." >&2

# Process top-level items in test/
for item in "$TEST_DIR"/* "$TEST_DIR"/.*; do
  # Skip . and ..
  if [[ "$(basename "$item")" == "." ]] || [[ "$(basename "$item")" == ".." ]]; then
    continue
  fi

  # Skip if item doesn't exist (handles empty globs)
  if [[ ! -e "$item" ]]; then
    continue
  fi

  migrate_content "$item"
done

echo "" >&2
echo "Migration summary:" >&2
echo "  Files migrated: $FILES_MIGRATED" >&2
echo "  Files skipped (identical): $FILES_SKIPPED" >&2
echo "  Directories created: $DIRS_CREATED" >&2

# Ask user if they want to remove test/ folder
echo "" >&2
echo "Migration complete. The test/ folder is now redundant." >&2
echo "To remove test/ folder, run:" >&2
echo "  rm -rf $TEST_DIR" >&2
echo "" >&2
echo "⚠️  Review migrated content in tests/ before removing test/" >&2

exit 0
