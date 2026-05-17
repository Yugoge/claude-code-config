#!/usr/bin/env bash
# Description: Audit always-on security-critical hook files against a cycle baseline SHA
#              and flag any drift. Drift is allowed only when explicitly listed via
#              --allow <path> for the current cycle.
# Usage: check-security-hook-drift.sh [--baseline <sha>] [--allow <path>]... [--frontmatter-lines <N>]
# Exit codes:
#   0  All security hooks match the baseline (or any drift is on an --allow list)
#   1  At least one tracked file diverged from baseline and was not on --allow list
#   2  Bad arguments / cannot resolve baseline / not in git repo
#
# Source: scripts/check-security-hook-drift.sh (C3, ticket-20260511-070000).
# Purpose (ticket §γ.AC3 / ticket §AC-CYCLE-3): mechanical enforcement that the
# 4 always-on safety layers (privilege-guard, bulk-detector, close-verdict,
# commit.md disable-model-invocation frontmatter) do not silently drift between
# cycles. Operator runs this manually; no CI integration this cycle.

set -euo pipefail

print_usage() {
  cat <<'USAGE' >&2
Usage: check-security-hook-drift.sh [--baseline <sha>] [--allow <path>]...

  --baseline <sha>   Compare HEAD against this SHA. Defaults to the contents of
                     .claude-cycle-baseline-sha at the repo root (if present).
  --allow <path>     Mark this tracked path as ALLOWED to drift (repeatable).
                     Pass paths relative to the repo root, matching the form
                     used in TRACKED_FILES below.

Tracked files (always-on safety layers):
  - hooks/pretool-git-privilege-guard.py
  - hooks/pretool-bulk-commit-detector.py
  - hooks/lib/close-verdict.py
  - commands/commit.md (frontmatter only -- the disable-model-invocation block,
    lines 1-5)

Exit 0 if all tracked files match baseline (or are on --allow list);
exit 1 if any tracked file drifted without being --allow'd; exit 2 on usage error.
USAGE
}

BASELINE=""
declare -a ALLOWED_PATHS=()
# Number of frontmatter lines to compare; override via --frontmatter-lines or env var
FRONTMATTER_LINES="${CHECK_SECURITY_FRONTMATTER_LINES:-5}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --baseline)
      BASELINE="${2:?--baseline requires a sha}"
      shift 2
      ;;
    --baseline=*)
      BASELINE="${1#--baseline=}"
      shift
      ;;
    --allow)
      ALLOWED_PATHS+=("${2:?--allow requires a path}")
      shift 2
      ;;
    --allow=*)
      ALLOWED_PATHS+=("${1#--allow=}")
      shift
      ;;
    --frontmatter-lines)
      FRONTMATTER_LINES="${2:?--frontmatter-lines requires a number}"
      shift 2
      ;;
    --frontmatter-lines=*)
      FRONTMATTER_LINES="${1#--frontmatter-lines=}"
      shift
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo "check-security-hook-drift.sh: unknown argument: $1" >&2
      print_usage
      exit 2
      ;;
  esac
done

# Resolve repo root (script may be invoked from anywhere)
if ! REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "check-security-hook-drift.sh: not inside a git repository" >&2
  exit 2
fi

# Resolve baseline: explicit flag > .claude-cycle-baseline-sha file
if [[ -z "$BASELINE" ]]; then
  baseline_file="$REPO_ROOT/.claude-cycle-baseline-sha"
  if [[ -f "$baseline_file" ]]; then
    BASELINE="$(tr -d '[:space:]' < "$baseline_file")"
  fi
fi
if [[ -z "$BASELINE" ]]; then
  echo "check-security-hook-drift.sh: no baseline given (use --baseline <sha> or write a SHA into .claude-cycle-baseline-sha)" >&2
  exit 2
fi

# Verify baseline ref exists
if ! git -C "$REPO_ROOT" rev-parse --verify "$BASELINE^{commit}" >/dev/null 2>&1; then
  echo "check-security-hook-drift.sh: baseline sha not resolvable: $BASELINE" >&2
  exit 2
fi

# Tracked files: format "<mode>:<path>" where mode is FULL (diff entire file)
# or FRONTMATTER (diff lines 1-5 only).
TRACKED_FILES=(
  "FULL:hooks/pretool-git-privilege-guard.py"
  "FULL:hooks/pretool-bulk-commit-detector.py"
  "FULL:hooks/lib/close-verdict.py"
  "FRONTMATTER:commands/commit.md"
)

is_allowed() {
  local path="$1"
  local allowed
  for allowed in "${ALLOWED_PATHS[@]:-}"; do
    [[ -z "$allowed" ]] && continue
    if [[ "$allowed" == "$path" ]]; then
      return 0
    fi
  done
  return 1
}

fail_count=0
allow_count=0
pass_count=0

echo "check-security-hook-drift.sh: baseline=$BASELINE repo=$REPO_ROOT"
echo "check-security-hook-drift.sh: allow list (${#ALLOWED_PATHS[@]} entries): ${ALLOWED_PATHS[*]:-<none>}"
echo "---"

for entry in "${TRACKED_FILES[@]}"; do
  mode="${entry%%:*}"
  path="${entry#*:}"
  diff_output=""

  case "$mode" in
    FULL)
      diff_output="$(git -C "$REPO_ROOT" diff "$BASELINE" -- "$path" 2>/dev/null || true)"
      ;;
    FRONTMATTER)
      # Capture only the first-5-line slice from each side.
      baseline_slice="$(git -C "$REPO_ROOT" show "$BASELINE:$path" 2>/dev/null | sed -n '1,5p' || true)"
      head_slice="$(sed -n '1,5p' "$REPO_ROOT/$path" 2>/dev/null || true)"
      if [[ "$baseline_slice" != "$head_slice" ]]; then
        diff_output="$(diff <(printf '%s' "$baseline_slice") <(printf '%s' "$head_slice") || true)"
      fi
      ;;
    *)
      echo "check-security-hook-drift.sh: internal error -- unknown mode '$mode' for '$path'" >&2
      exit 2
      ;;
  esac

  if [[ -z "$diff_output" ]]; then
    echo "PASS: $path ($mode unchanged vs $BASELINE)"
    pass_count=$((pass_count + 1))
  elif is_allowed "$path"; then
    echo "ALLOWED: $path ($mode drifted vs $BASELINE; on --allow list)"
    allow_count=$((allow_count + 1))
  else
    echo "FAIL: $path ($mode drifted vs $BASELINE; not on --allow list)"
    fail_count=$((fail_count + 1))
  fi
done

echo "---"
echo "Summary: pass=$pass_count allowed=$allow_count fail=$fail_count"

if [[ "$fail_count" -gt 0 ]]; then
  exit 1
fi
exit 0
