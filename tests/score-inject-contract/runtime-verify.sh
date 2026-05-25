#!/usr/bin/env bash
# Description: Runtime verifier for the 4-field score-injection echo contract.
#   Reads a captured QA report and asserts:
#     - rank_acknowledged matches expected
#     - range_acknowledged matches expected
#     - recent_events_digest_acknowledged equals sha256[:8] over captured
#       recent-events text (independent recomputation, codex finding #1 fix)
#     - score_injection_action is non-null, len >= 20, NOT a forbidden placeholder
# Usage: runtime-verify.sh --qa-report <path> --expected-rank <label>
#                          --expected-range <range> --captured-inject-text <path>
# Exit codes: 0=pass, 1=fail
#
# AC reference: docs/dev/acceptance-criteria-20260524-205206.json AC-02 (M2.4).

set -euo pipefail

QA_REPORT=""
EXPECTED_RANK=""
EXPECTED_RANGE=""
CAPTURED_INJECT_TEXT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --qa-report)              QA_REPORT="${2:?missing value for --qa-report}"; shift 2 ;;
    --expected-rank)          EXPECTED_RANK="${2:?missing value for --expected-rank}"; shift 2 ;;
    --expected-range)         EXPECTED_RANGE="${2:?missing value for --expected-range}"; shift 2 ;;
    --captured-inject-text)   CAPTURED_INJECT_TEXT="${2:?missing value for --captured-inject-text}"; shift 2 ;;
    -h|--help)                grep '^#' "$0" >&2; exit 0 ;;
    *)                        echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

for var in QA_REPORT EXPECTED_RANK EXPECTED_RANGE CAPTURED_INJECT_TEXT; do
  if [[ -z "${!var}" ]]; then
    echo "FAIL: missing required argument --${var,,}" >&2
    exit 1
  fi
done

for path in "$QA_REPORT" "$CAPTURED_INJECT_TEXT"; do
  if [[ ! -f "$path" ]]; then
    echo "FAIL: file does not exist: $path" >&2
    exit 1
  fi
done

# Extract the recent-events text from the captured score-inject snapshot.
RECENT_TEXT="$(grep -oE 'Recent events:[[:space:]].*' "$CAPTURED_INJECT_TEXT" | head -1 | sed -E 's/^Recent events:[[:space:]]//')"
if [[ -z "$RECENT_TEXT" ]]; then
  echo "FAIL: could not extract 'Recent events:' line from $CAPTURED_INJECT_TEXT" >&2
  exit 1
fi
EXPECTED_DIGEST="$(printf '%s' "$RECENT_TEXT" | sha256sum | cut -c1-8)"

# jq-extract the 4 fields from the QA report.
RANK_ACK="$(jq -r '.rank_acknowledged // empty' "$QA_REPORT" 2>/dev/null || true)"
RANGE_ACK="$(jq -r '.range_acknowledged // empty' "$QA_REPORT" 2>/dev/null || true)"
DIGEST_ACK="$(jq -r '.recent_events_digest_acknowledged // empty' "$QA_REPORT" 2>/dev/null || true)"
ACTION_ACK="$(jq -r '.score_injection_action // empty' "$QA_REPORT" 2>/dev/null || true)"

fail=0
report() { echo "FAIL: $1" >&2; fail=1; }

[[ -z "$RANK_ACK"   ]] && report "rank_acknowledged is missing or null"
[[ -z "$RANGE_ACK"  ]] && report "range_acknowledged is missing or null"
[[ -z "$DIGEST_ACK" ]] && report "recent_events_digest_acknowledged is missing or null"
[[ -z "$ACTION_ACK" ]] && report "score_injection_action is missing or null"

if [[ $fail -eq 0 ]]; then
  [[ "$RANK_ACK"   != "$EXPECTED_RANK"   ]] && report "rank_acknowledged='$RANK_ACK' != expected '$EXPECTED_RANK'"
  [[ "$RANGE_ACK"  != "$EXPECTED_RANGE"  ]] && report "range_acknowledged='$RANGE_ACK' != expected '$EXPECTED_RANGE'"
  [[ "$DIGEST_ACK" != "$EXPECTED_DIGEST" ]] && report "recent_events_digest_acknowledged='$DIGEST_ACK' != expected '$EXPECTED_DIGEST' (sha256[:8] of '$RECENT_TEXT')"

  # score_injection_action: length >= 20, NOT a forbidden placeholder.
  ACTION_LEN="${#ACTION_ACK}"
  if [[ "$ACTION_LEN" -lt 20 ]]; then
    report "score_injection_action length $ACTION_LEN < 20 chars"
  fi
  # Lowercase + trim for placeholder check
  ACTION_LC="$(printf '%s' "$ACTION_ACK" | tr '[:upper:]' '[:lower:]' | awk '{$1=$1; print}')"
  FORBIDDEN=("no action needed" "no action" "none" "n/a" "na" "nothing" "skip" "no-op" "tbd" "ok" "acknowledged")
  for placeholder in "${FORBIDDEN[@]}"; do
    if [[ "$ACTION_LC" == "$placeholder" ]]; then
      report "score_injection_action is the forbidden placeholder '$placeholder'"
    fi
  done
fi

if [[ $fail -ne 0 ]]; then
  exit 1
fi

echo "runtime-verify.sh: all 4 fields valid (rank=$RANK_ACK range=$RANGE_ACK digest=$DIGEST_ACK action_len=${#ACTION_ACK})"
exit 0
