#!/usr/bin/env bash
# pretool-layer-escalation-check.sh
# Triggers: PreToolUse on Agent tool when subagent_type is "dev".
# Purpose: Warn when the current dev cycle is about to retry the same layer
#          that already failed >=2 prior attempts.
# Non-blocking: always exit 0. Degrades gracefully.

set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0

ctx=$(ls -t docs/dev/context-*.json 2>/dev/null | head -1 || true)
[ -z "$ctx" ] && exit 0

# Total number of prior attempts recorded in context
total_attempts=$(jq -r '.prior_attempts | length // 0' "$ctx" 2>/dev/null || echo 0)
# Number of distinct target_layer values across all prior_attempts (999 sentinel if <2)
same_layer_count=$(jq -r '
  if .prior_attempts and (.prior_attempts | length >= 2) then
    [.prior_attempts[].target_layer // empty] | unique | length
  else 999 end
' "$ctx" 2>/dev/null || echo 999)
current_layer=$(jq -r '.diagnosis_layer // empty' "$ctx" 2>/dev/null || true)
last_attempt_layer=$(jq -r '.prior_attempts[-1].target_layer // empty' "$ctx" 2>/dev/null || true)

# Guard against non-numeric values (jq errors)
case "$total_attempts" in
  ''|*[!0-9]*) total_attempts=0 ;;
esac
case "$same_layer_count" in
  ''|*[!0-9]*) same_layer_count=999 ;;
esac

if [ "$total_attempts" -ge 2 ] && [ "$same_layer_count" = "1" ] && \
   [ -n "$current_layer" ] && [ "$current_layer" = "$last_attempt_layer" ]; then
  cat >&2 <<EOF
SAME-LAYER RETRY DETECTED
${total_attempts} prior attempts all at layer ${current_layer} failed.
This cycle is ALSO targeting ${current_layer}. Policy: escalate to a different layer.
BA should re-analyze at an upstream layer before Dev proceeds.
Context: $ctx
EOF
fi

exit 0
