#!/usr/bin/env bash
# pretool-layer-match-gate.sh
# Triggers: SubagentStop (despite the "pretool" name; retained for naming continuity with the spec)
# Purpose: After a dev subagent finishes, compare latest dev-report-*.json's fix_layer
#          against latest context-*.json's diagnosis_layer. Warn on mismatch.
# Non-blocking: always exit 0. Degrades gracefully when fields/files are missing.

set -euo pipefail

# Resolve project dir; exit silently if not available
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0

# Find most recent context and dev-report
ctx=$(ls -t docs/dev/context-*.json 2>/dev/null | head -1 || true)
rep=$(ls -t docs/dev/dev-report-*.json 2>/dev/null | head -1 || true)

if [ -z "$ctx" ] || [ -z "$rep" ]; then
  exit 0
fi

# Read layers; tolerate both nested (.dev.fix_layer) and flat (.fix_layer) shapes
diag=$(jq -r '.diagnosis_layer // empty' "$ctx" 2>/dev/null || true)
fix=$(jq -r '.dev.fix_layer // .fix_layer // empty' "$rep" 2>/dev/null || true)

if [ -z "$diag" ] || [ -z "$fix" ]; then
  exit 0
fi

if [ "$diag" != "$fix" ]; then
  cat >&2 <<EOF
LAYER MISMATCH
BA diagnosed at $diag, Dev fixed at $fix.
If intentional, dev must declare scope_review_requested with justification.
Otherwise the orchestrator should reject this fix and request BA re-analysis.
Context: $ctx
Report:  $rep
EOF
fi

exit 0
