#!/usr/bin/env bash
# SubagentStop hook: flag large diffs without minimum-diff justification
#
# Purpose: After a subagent finishes, if cumulative git diff exceeds THRESHOLD
# lines and no justification is found in recent dev-report-*.json, emit a
# WARNING to stderr (visible to orchestrator). Does NOT block.
#
# Rationale: Enforces the Minimum-Diff Rule — dev subagents should produce
# surgical fixes. Large diffs without documented scope expansion are suspicious
# and likely represent unauthorized refactoring.

set -euo pipefail

# Skip if CLAUDE_PROJECT_DIR not set or not a git repo
[ -n "${CLAUDE_PROJECT_DIR:-}" ] || exit 0
cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || exit 0
git rev-parse --git-dir >/dev/null 2>&1 || exit 0

# Count lines added in recent auto-commits (HEAD~5..HEAD) + uncommitted working tree.
# Auto-commit hook may checkpoint subagent work before SubagentStop fires, so
# we look back a few commits to catch those.
lines_committed=$(git diff --shortstat HEAD~5..HEAD 2>/dev/null | grep -oE '[0-9]+ insertion' | grep -oE '[0-9]+' || echo 0)
lines_uncommitted=$(git diff --shortstat 2>/dev/null | grep -oE '[0-9]+ insertion' | grep -oE '[0-9]+' || echo 0)
# Normalize empty values to 0
lines_committed=${lines_committed:-0}
lines_uncommitted=${lines_uncommitted:-0}
total=$((lines_committed + lines_uncommitted))

THRESHOLD=30
if [ "$total" -le "$THRESHOLD" ]; then
  exit 0
fi

# Check if any recent (mtime < 10 min) dev-report-*.json contains a justification
# or explicit scope-review request.
recent_reports=$(find "$CLAUDE_PROJECT_DIR/docs/dev" -name "dev-report-*.json" -mmin -10 2>/dev/null || true)
if [ -n "$recent_reports" ]; then
  for report in $recent_reports; do
    if jq -e '.dev.diff_stats.justification_for_overage // .dev.scope_review_requested // empty' "$report" >/dev/null 2>&1; then
      # Justification present — silent pass
      exit 0
    fi
  done
fi

# No justification found — warn the orchestrator via stderr
cat >&2 <<EOF
MINIMUM-DIFF RULE WARNING
Subagent produced a diff of ${total} lines (threshold: ${THRESHOLD}).
No justification found in recent dev-report-*.json.

Expected one of:
  dev.diff_stats.justification_for_overage = "<why the minimum diff cannot be smaller>"
OR
  dev.scope_review_requested = true

If this was a legitimately large fix, the subagent should have populated the
justification field. If this was unauthorized refactoring, the orchestrator
should reject and request a surgical redo.
EOF

# Exit 0 — warn, don't block. Blocking would break legitimate large-refactor work.
exit 0
