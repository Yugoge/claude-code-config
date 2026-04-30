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
resolve_project_dir() {
    # 4-tier fallback: env -> pwd -> git toplevel -> /root literal.
    # (No stdin tier; this is a CLI script, not a stdin-payload hook.)
    if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then
        printf '%s\n' "$CLAUDE_PROJECT_DIR"
        return 0
    fi
    local cwd
    cwd="$(pwd 2>/dev/null)" || cwd=""
    if [[ -n "$cwd" ]]; then
        printf '%s\n' "$cwd"
        return 0
    fi
    local toplevel
    toplevel="$(git rev-parse --show-toplevel 2>/dev/null)" || toplevel=""
    if [[ -n "$toplevel" ]]; then
        printf '%s\n' "$toplevel"
        return 0
    fi
    printf '%s\n' "/root"
}
PROJECT_DIR="$(resolve_project_dir)"

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

    # M5 (harness-fixes 20260428): the Python layer (prompt-workflow.py)
    # forwards INVALID:<token> when it sees an unparseable +token. Surface
    # an explicit error here rather than silent fallback to +8h.
    if [[ "$input" == INVALID:* ]]; then
        echo "Cannot parse end-time: ${input#INVALID:}" >&2
        exit 1
    fi

    # T1.6 (redev-tier123): accept bare-form Nh / N.Mh / Nm by stripping
    # an optional leading '+' before the existing match below. Per user
    # directive (e), the '+' prefix is documented no-op compat; bare form
    # is the primary spelling.
    local stripped="${input#+}"

    # M5: relative-time forms Nh / N.Mh / Nm (with optional leading +
    # already stripped). GNU date does not accept fractional hours
    # ("+0.5 hours" errors), so we always normalize to whole-minute
    # offsets via integer arithmetic. Any token NOT matching this
    # pattern errors loudly (no silent fallback to +8h).
    if [[ "$stripped" =~ ^([0-9]+)(\.([0-9]+))?([hm])$ ]]; then
        local whole="${BASH_REMATCH[1]}"
        local frac="${BASH_REMATCH[3]}"
        local unit="${BASH_REMATCH[4]}"
        local minutes
        if [[ "$unit" == "h" ]]; then
            minutes=$((whole * 60))
            if [[ -n "$frac" ]]; then
                # Compute fractional-hours minutes: frac/10^len(frac) * 60
                local pad="${#frac}"
                local denom=$((10 ** pad))
                minutes=$((minutes + (10#$frac * 60) / denom))
            fi
        else
            if [[ -n "$frac" ]]; then
                echo "Cannot parse end-time: $input (fractional minutes not supported)" >&2
                exit 1
            fi
            minutes="$whole"
        fi
        date -u -d "+${minutes} minutes" +%Y-%m-%dT%H:%M:%SZ
        return
    fi
    if [[ "$input" == +* ]]; then
        echo "Cannot parse end-time: $input" >&2
        exit 1
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

# C12 (redev-tier123): warn (do not error) when time budget is <60 min.
target_epoch=$(date -u -d "$END_TIME" +%s 2>/dev/null || echo 0)
now_epoch=$(date +%s)
if [[ "$target_epoch" -gt 0 ]]; then
    delta_min=$(( (target_epoch - now_epoch) / 60 ))
    if [[ "$delta_min" -lt 60 ]]; then
        echo "WARNING: time budget <1h (${delta_min}m). Recommended minimum: 1h for 1 pipeline; 2h for 2-3 pipelines; 6h+ for overnight." >&2
    fi
fi

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

# --- Create worktree ---
WORKTREE_PATH=""
WORKTREE_BRANCH=""
WORKTREE_SCRIPT="$(dirname "$0")/create-worktree.sh"
WORKTREE_NAME="overnight-$(date +%Y%m%d)-${SESSION_ID:0:8}"
if [[ -x "$WORKTREE_SCRIPT" ]] && WORKTREE_RESULT=$(bash "$WORKTREE_SCRIPT" "$WORKTREE_NAME" 2>/dev/null); then
    WORKTREE_PATH=$(echo "$WORKTREE_RESULT" | grep -oP 'WORKTREE_PATH=\K\S+')
    WORKTREE_BRANCH=$(echo "$WORKTREE_RESULT" | grep -oP 'WORKTREE_BRANCH=\K\S+')
    echo "Created worktree: $WORKTREE_PATH (branch: $WORKTREE_BRANCH)" >&2
else
    echo "Warning: worktree creation failed, continuing without worktree" >&2
fi

# --- Detect view_paths from spec views manifest ---
VIEW_PATHS="{}"
if [[ "$USER_SPEC_PATH" != "null" && -n "$USER_SPEC_PATH" ]]; then
    SPEC_DIR="${USER_SPEC_PATH%.md}"
    MANIFEST="$SPEC_DIR/views/manifest.json"
    if [[ -f "$MANIFEST" ]]; then
        SCHEMA_VER=$(jq -r '.schema_version // empty' "$MANIFEST" 2>/dev/null)
        if [[ "$SCHEMA_VER" == "1" ]]; then
            VIEW_PATHS=$(jq -c '.views // {}' "$MANIFEST" 2>/dev/null || echo '{}')
            echo "Loaded view_paths from manifest ($MANIFEST)" >&2
        else
            echo "Warning: manifest schema_version is '$SCHEMA_VER', expected 1; ignoring" >&2
        fi
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
    --arg worktree_path "$WORKTREE_PATH" \
    --arg worktree_branch "$WORKTREE_BRANCH" \
    --argjson view_paths "$VIEW_PATHS" \
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
        current_phase: (if $worktree_path == "" then "initializing" else "exploring" end),
        current_issues: [],
        failed_attempts: {},
        addressed_issues: [],
        cycle_log: [],
        consecutive_clean_sweeps: 0,
        worktree_path: (if $worktree_path == "" then null else $worktree_path end),
        worktree_branch: (if $worktree_branch == "" then null else $worktree_branch end),
        view_paths: $view_paths,
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
if [[ -n "$WORKTREE_PATH" ]]; then
    echo "  Worktree: $WORKTREE_PATH" >&2
fi
echo "STATE_PATH=$STATE_FILE"
