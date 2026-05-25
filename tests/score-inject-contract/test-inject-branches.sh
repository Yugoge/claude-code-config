#!/usr/bin/env bash
# Description: Verify scripts/score-inject.sh emits INJECTION_PROOF block with
#   all 4 fields + correct sha256[:8] digest in all three branches
#   (populated scores file, missing scores file, malformed scores file).
# Usage: test-inject-branches.sh [--score-inject <path>]
# Exit codes: 0=pass, 1=fail
#
# AC reference: docs/dev/acceptance-criteria-20260524-205206.json AC-02 (M2.3).
# Codex finding #1 fix: INDEPENDENTLY recompute sha256[:8] over the actual
# emitted recent-events text and assert equality with the substituted
# <RECENT_EVENTS_DIGEST> in INJECTION_PROOF (not merely valid-hex regex).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCORE_INJECT_DEFAULT="$(cd "$SCRIPT_DIR/../.." && pwd)/scripts/score-inject.sh"
SCORE_INJECT="${1:-$SCORE_INJECT_DEFAULT}"

if [[ ! -x "$SCORE_INJECT" && ! -r "$SCORE_INJECT" ]]; then
  echo "FAIL: score-inject.sh not found at $SCORE_INJECT" >&2
  exit 1
fi

WORK_DIR="$(mktemp -d -t score-inject-test-XXXXXX)"
trap 'rm -rf "$WORK_DIR"' EXIT INT TERM

POPULATED="$WORK_DIR/populated.json"
MISSING="$WORK_DIR/missing.json"   # intentionally not created
MALFORMED="$WORK_DIR/malformed.json"

cat > "$POPULATED" <<'EOF'
{
  "global": {
    "agents": {
      "dev": {
        "score": 55,
        "rank": "Skilled Craftsman",
        "history": [
          {"ts": "2026-05-20T10:00:00Z", "event": "close_success_qa_pass", "delta": 2},
          {"ts": "2026-05-21T10:00:00Z", "event": "qa_first_pass", "delta": 0},
          {"ts": "2026-05-22T10:00:00Z", "event": "user_rating_5", "delta": 1}
        ]
      }
    }
  }
}
EOF

cat > "$MALFORMED" <<'EOF'
{invalid: not, json,,
EOF

REQUIRED_TOKENS=(
  "INJECTION_PROOF:"
  "rank_acknowledged"
  "range_acknowledged"
  "recent_events_digest_acknowledged"
  "score_injection_action"
)

FORBIDDEN_PLACEHOLDERS=(
  "<RANK_LABEL>"
  "<RANGE>"
  "<RECENT_EVENTS_DIGEST>"
)

run_branch() {
  local label="$1"
  local scores_path="$2"
  local out
  out="$(bash "$SCORE_INJECT" --agent dev --scores-file "$scores_path" 2>/dev/null)"

  # Check required tokens
  for tok in "${REQUIRED_TOKENS[@]}"; do
    if ! printf '%s' "$out" | grep -qF "$tok"; then
      echo "FAIL [$label]: missing required token: $tok" >&2
      echo "----- output -----" >&2
      printf '%s\n' "$out" >&2
      return 1
    fi
  done

  # Check unsubstituted placeholders absent for rank/range/digest
  # (score_injection_action <text> placeholder is fine — it's instructional)
  for ph in "${FORBIDDEN_PLACEHOLDERS[@]}"; do
    if printf '%s' "$out" | grep -F "$ph" | grep -qE '"(rank_acknowledged|range_acknowledged|recent_events_digest_acknowledged)":[[:space:]]*"[^"]*<'; then
      echo "FAIL [$label]: unsubstituted placeholder $ph found inside required field value" >&2
      return 1
    fi
  done

  # Extract the recent_events text from the "Recent events: <text>" line, and
  # the substituted digest from the INJECTION_PROOF line. Recompute sha256[:8]
  # over the recent_events text and assert equality.
  local recent_text emitted_digest expected_digest
  recent_text="$(printf '%s\n' "$out" | grep -oE 'Recent events:[[:space:]].*' | head -1 | sed -E 's/^Recent events:[[:space:]]//')"
  if [[ -z "$recent_text" ]]; then
    echo "FAIL [$label]: could not extract 'Recent events:' text from output" >&2
    return 1
  fi
  emitted_digest="$(printf '%s\n' "$out" | grep -oE '"recent_events_digest_acknowledged":[[:space:]]*"[0-9a-f]+"' | head -1 | sed -E 's/.*"([0-9a-f]+)".*/\1/')"
  if [[ -z "$emitted_digest" ]]; then
    echo "FAIL [$label]: could not extract recent_events_digest_acknowledged from output" >&2
    return 1
  fi
  if ! [[ "$emitted_digest" =~ ^[0-9a-f]{8}$ ]]; then
    echo "FAIL [$label]: digest is not 8 lowercase hex chars: '$emitted_digest'" >&2
    return 1
  fi
  expected_digest="$(printf '%s' "$recent_text" | sha256sum | cut -c1-8)"
  if [[ "$emitted_digest" != "$expected_digest" ]]; then
    echo "FAIL [$label]: digest mismatch — recent_events='$recent_text' expected=$expected_digest emitted=$emitted_digest" >&2
    return 1
  fi

  echo "PASS [$label]: all 4 fields present, digest recomputation OK ($emitted_digest)"
}

ec=0
run_branch "populated" "$POPULATED" || ec=1
run_branch "missing"   "$MISSING"   || ec=1
run_branch "malformed" "$MALFORMED" || ec=1

if [[ $ec -ne 0 ]]; then
  echo "test-inject-branches.sh: at least one branch failed" >&2
  exit 1
fi
echo "test-inject-branches.sh: all 3 branches PASSED"
exit 0
