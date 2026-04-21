#!/bin/bash
# create-overnight-state.sh — Create overnight state file (v7 schema)
# Replaces inline JSON creation so the LLM agent never writes JSON itself.
#
# Usage: create-overnight-state.sh [OPTIONS]
#   --end-time <ISO-8601|HH:MM>   End time (default: now + 8h)
#   --focus <string>               Discovery focus hint (default: empty)
#   --spec <path>                  User-provided spec file path
#   --session-id <uuid>            Session ID (default: $CLAUDE_SESSION_ID or generated)
#   --project-dir <path>           Project directory (default: $CLAUDE_PROJECT_DIR or pwd)
#
# Output (last line): STATE_PATH=<path>
# Exit: 0=success, 1=error

set -euo pipefail

# --- Defaults ---
END_TIME=""
FOCUS=""
SPEC_PATH=""
SESSION_ID="${CLAUDE_SESSION_ID:-}"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# --- Parse arguments ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --end-time)  END_TIME="$2"; shift 2 ;;
        --focus)     FOCUS="$2"; shift 2 ;;
        --spec)      SPEC_PATH="$2"; shift 2 ;;
        --session-id) SESSION_ID="$2"; shift 2 ;;
        --project-dir) PROJECT_DIR="$2"; shift 2 ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Usage: create-overnight-state.sh [--end-time <time>] [--focus <str>] [--spec <path>] [--session-id <uuid>] [--project-dir <path>]" >&2
            exit 1
            ;;
    esac
done

# --- Session ID ---
if [[ -z "$SESSION_ID" ]]; then
    SESSION_ID="$(uuidgen)"
    echo "Generated session ID: $SESSION_ID" >&2
fi

# --- Start time ---
START_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# --- End time parsing ---
parse_end_time() {
    local input="$1"

    # Empty → now + 8 hours
    if [[ -z "$input" ]]; then
        date -u -d "+8 hours" +%Y-%m-%dT%H:%M:%SZ
        return
    fi

    # Already ISO-8601 (contains T or full date pattern)
    if [[ "$input" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2} ]]; then
        date -u -d "$input" +%Y-%m-%dT%H:%M:%SZ
        return
    fi

    # HH:MM or HH:MM AM/PM → parse as clock time today, if past → tomorrow
    local target_epoch
    target_epoch=$(date -d "today $input" +%s 2>/dev/null) || {
        echo "Cannot parse end-time: $input" >&2
        exit 1
    }
    local now_epoch
    now_epoch=$(date +%s)

    if [[ "$target_epoch" -le "$now_epoch" ]]; then
        # Already past today → use tomorrow
        target_epoch=$(date -d "tomorrow $input" +%s)
    fi

    date -u -d "@$target_epoch" +%Y-%m-%dT%H:%M:%SZ
}

END_TIME="$(parse_end_time "$END_TIME")"

# --- Spec mode detection ---
SPEC_MODE="autonomous"
USER_SPEC_PATH="null"

if [[ -n "$SPEC_PATH" ]]; then
    # Explicit --spec provided
    if [[ ! -f "$SPEC_PATH" ]]; then
        echo "Error: Spec file not found: $SPEC_PATH" >&2
        exit 1
    fi
    SPEC_MODE="user-provided"
    USER_SPEC_PATH="$SPEC_PATH"
elif [[ -d "$PROJECT_DIR/docs/dev/specs" ]]; then
    # Auto-detect: newest .md in docs/dev/specs/, excluding INDEX.md and README.md
    DETECTED=$(find "$PROJECT_DIR/docs/dev/specs" -maxdepth 1 -name '*.md' \
        ! -name 'INDEX.md' ! -name 'README.md' \
        -printf '%T@ %p\n' 2>/dev/null \
        | sort -rn | head -1 | cut -d' ' -f2-)
    if [[ -n "$DETECTED" && -f "$DETECTED" ]]; then
        SPEC_MODE="user-provided"
        USER_SPEC_PATH="$DETECTED"
        echo "Auto-detected spec: $USER_SPEC_PATH" >&2
    fi
fi

# --- Ensure output directory exists ---
STATE_DIR="$PROJECT_DIR/.claude"
mkdir -p "$STATE_DIR"

STATE_FILE="$STATE_DIR/overnight-state-${SESSION_ID}.json"
TMP_FILE="${STATE_FILE}.tmp"

# --- Build JSON with jq ---
jq -n \
    --arg session_id "$SESSION_ID" \
    --arg end_time "$END_TIME" \
    --arg start_time "$START_TIME" \
    --arg focus "$FOCUS" \
    --arg spec_mode "$SPEC_MODE" \
    --arg user_spec_path "$USER_SPEC_PATH" \
    '{
        session_id: $session_id,
        end_time: $end_time,
        start_time: $start_time,
        focus: $focus,
        spec_mode: $spec_mode,
        user_spec_path: (if $user_spec_path == "null" then null else $user_spec_path end),
        cycle_count: 0,
        issues_found: 0,
        issues_fixed: 0,
        issues_skipped: 0,
        current_phase: "initializing",
        current_issues: [],
        failed_attempts: {},
        addressed_issues: [],
        cycle_log: [],
        consecutive_clean_sweeps: 0,
        worktree_path: null,
        worktree_branch: null,
        pm_triage_reports: [],
        pm_retro_reports: [],
        unresolved_issues: []
    }' > "$TMP_FILE"

# Atomic move
mv "$TMP_FILE" "$STATE_FILE"

echo "Created overnight state v7: $STATE_FILE" >&2
echo "  Session: $SESSION_ID" >&2
echo "  End time: $END_TIME" >&2
echo "  Spec mode: $SPEC_MODE" >&2
echo "STATE_PATH=$STATE_FILE"
