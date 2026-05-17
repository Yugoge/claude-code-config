#!/usr/bin/env bash
# refine-context.sh — merge QA-refined context with original context
# Usage: refine-context.sh <orig-ctx> <qa-report> <iteration> [out]
set -euo pipefail

resolve_project_dir() {
  for v in "${CLAUDE_PROJECT_DIR:-}" "$(pwd)"; do
    [ -n "$v" ] && [ -d "$v" ] && { echo "$v"; return; }
  done
  git rev-parse --show-toplevel 2>/dev/null || { echo "Error: cannot determine project directory; set CLAUDE_PROJECT_DIR" >&2; exit 1; }
}

ORIG="${1:?Missing original context}"
QA="${2:?Missing QA report}"
ITER="${3:?Missing iteration number}"
OUT="${4:-/dev/stdout}"
PROJECT_DIR="$(resolve_project_dir)"

jq --argjson it "$ITER" -s '.[0] * {
  iteration: $it,
  previous_attempts: ((.[0].previous_attempts // []) + [{
    iteration: ($it - 1), dev: .[1].dev, qa: .[1].qa,
    timestamp: (now | strftime("%Y-%m-%dT%H:%M:%SZ"))
  }]),
  refined_requirements: (.[1].qa.refined_context // {})
}' "$ORIG" "$QA" > "$OUT"
