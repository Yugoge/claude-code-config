#!/usr/bin/env bash
# pretool-bisect-gate.sh
# Triggers: PreToolUse on Agent tool when subagent_type is "dev".
# Purpose: When BA context indicates a regression, require git_bisect_result
#          (either suspect_commit or bisect_blocked reason).
# Non-blocking: always exit 0. Degrades gracefully.

set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0

ctx=$(ls -t docs/dev/context-*.json 2>/dev/null | head -1 || true)
[ -z "$ctx" ] && exit 0

# Gather complaint text and explicit regression trigger flag
complaint=$(jq -r '.user_verbatim_complaint // .requirement // ""' "$ctx" 2>/dev/null || true)
triggered=$(jq -r '.regression_investigation_checklist.triggered // false' "$ctx" 2>/dev/null || true)

is_regression=false
if [ "$triggered" = "true" ]; then
  is_regression=true
fi
# Keyword detection (EN + common ZH)
if printf '%s' "$complaint" | grep -qiE "was working|used to|broke|regression|以前|原本"; then
  is_regression=true
fi

if [ "$is_regression" = "false" ]; then
  exit 0
fi

# Require git_bisect_result — accept both nested and flat placements
bisect_ok=$(jq -r '
  if (.root_cause_analysis.git_bisect_result.suspect_commit // "") != ""
     or (.root_cause_analysis.git_bisect_result.bisect_blocked // "") != ""
     or (.git_bisect_result.suspect_commit // "") != ""
     or (.git_bisect_result.bisect_blocked // "") != ""
  then "ok" else "missing" end
' "$ctx" 2>/dev/null || echo "missing")

if [ "$bisect_ok" != "ok" ]; then
  cat >&2 <<EOF
REGRESSION BUG WITHOUT BISECT
User complaint appears to be a regression but BA's context has no git_bisect_result.
Required: root_cause_analysis.git_bisect_result must have either suspect_commit or bisect_blocked reason.
BA should re-run with git bisect before Dev proceeds.
Context: $ctx
EOF
fi

exit 0
