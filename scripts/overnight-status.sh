#!/bin/bash
# overnight-status.sh — Zero-LLM overnight session status query
# Uses jq to parse state file directly. No token cost.
#
# Usage: bash ~/.claude/scripts/overnight-status.sh [session_id]

set -euo pipefail

# Find the most recent state file (or by session_id if provided)
if [ -n "${1:-}" ]; then
    STATE=$(find docs/dev/overnight/ -name "overnight-state-$1.json" 2>/dev/null | head -1)
else
    STATE=$(find docs/dev/overnight/ -name "overnight-state-*.json" -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2)
fi

if [ -z "$STATE" ] || [ ! -f "$STATE" ]; then
    echo "No overnight session found."
    exit 0
fi

# Extract key metrics
jq -r '
"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
+ "\n  Overnight Session Status"
+ "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
+ "\n  Session:  " + (.session_id // "unknown")
+ "\n  Phase:    " + (.current_phase // "unknown")
+ "\n  Cycle:    " + (.cycle_count // 0 | tostring)
+ "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
+ "\n  Issues found:   " + (.issues_found // 0 | tostring)
+ "\n  Issues fixed:   " + (.issues_fixed // 0 | tostring)
+ "\n  Issues skipped: " + (.issues_skipped // 0 | tostring)
+ "\n  Fix rate:       " + (if .issues_found > 0 then ((.issues_fixed / .issues_found * 100) | floor | tostring) + "%" else "N/A" end)
+ "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
+ "\n  Start:    " + (.start_time // "unknown")
+ "\n  End:      " + (.end_time // "unknown")
+ "\n  Clean sweeps: " + (.consecutive_clean_sweeps // 0 | tostring)
+ "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
+ "\n  Unresolved: " + ((.unresolved_issues // []) | length | tostring) + " issues"
+ (if ((.unresolved_issues // []) | length) > 0 then
    "\n" + ((.unresolved_issues // []) | map("    - [" + (.severity // "?") + "] " + (.description // "?")[0:60]) | join("\n"))
  else "" end)
+ "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
' "$STATE"
