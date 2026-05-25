#!/usr/bin/env bash
# Description: Update agent score by appending an entry to the lifecycle JSONL log.
# Usage: score-update.sh --agent <name> --event <event_name> [--note <text>] [--lifecycle-file <path>] [--expected-prev-score <int>]
# Exit codes:
#   0 = success (score entry appended to lifecycle.jsonl)
#   1 = invalid argument or unknown agent/event (no modification made)
#   2 = file/IO error or malformed JSONL in existing log
#   3 = CAS conflict (--expected-prev-score supplied but does not match latest score)
#
# Root cause addressed: arch-7 phase 2 (task 20260525-050824) — replace
# independent-flock overwrite model with append-only JSONL under single
# exclusive flock to prevent score drift between sequential close-cycle calls.

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
LIFECYCLE_FILE_DEFAULT="${HOME}/.claude/logs/lifecycle.jsonl"

usage() {
  cat >&2 <<EOF
Usage: ${SCRIPT_NAME} --agent <name> --event <event_name> [--note <text>] [--lifecycle-file <path>] [--expected-prev-score <int>]

Canonical events (from spec 5.1 table):
  close_success_qa_pass, close_success_qa_fail_fixed,
  close_fail_qa_pass, close_fail_qa_fail,
  qa_first_pass, qa_reject_dev, qa_reject_ba, qa_second_pass,
  user_rating_5, user_rating_4, user_rating_3, user_rating_2, user_rating_1

Score is clamped to [0,100]. Rank is recomputed from final score:
  0-20 = rank-1 (Apprentice), 21-40 = rank-2 (Journeyman), 41-60 = rank-3 (Skilled Craftsman),
  61-80 = rank-4 (Senior Craftsman), 81-100 = rank-5 (Master)

--expected-prev-score: optional CAS guard. If supplied and latest score for agent
  does not match, exit 3 (no append). Normal callers omit this flag.
EOF
  exit 1
}

AGENT=""
EVENT=""
NOTE=""
LIFECYCLE_FILE="${LIFECYCLE_FILE_DEFAULT}"
EXPECTED_PREV_SCORE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)                AGENT="${2:?missing value for --agent}"; shift 2 ;;
    --event)                EVENT="${2:?missing value for --event}"; shift 2 ;;
    --note)                 NOTE="${2:?missing value for --note}"; shift 2 ;;
    --lifecycle-file)       LIFECYCLE_FILE="${2:?missing value for --lifecycle-file}"; shift 2 ;;
    --expected-prev-score)  EXPECTED_PREV_SCORE="${2:?missing value for --expected-prev-score}"; shift 2 ;;
    # Legacy --scores-file param: accepted but ignored (agent-scores.json write path removed)
    --scores-file)          shift 2 ;;
    -h|--help)              usage ;;
    *)                      echo "Unknown argument: $1" >&2; usage ;;
  esac
done

[[ -z "${AGENT}" ]] && { echo "Missing required --agent" >&2; usage; }
[[ -z "${EVENT}" ]] && { echo "Missing required --event" >&2; usage; }

# Ensure lifecycle file directory exists
LIFECYCLE_DIR="$(dirname "${LIFECYCLE_FILE}")"
mkdir -p "${LIFECYCLE_DIR}"

# Touch the lifecycle file if it does not yet exist
if [[ ! -f "${LIFECYCLE_FILE}" ]]; then
  touch "${LIFECYCLE_FILE}"
fi

# Lock file for the lifecycle JSONL (separate from any legacy agent-scores.json.lock)
LOCK_FILE="${LIFECYCLE_FILE}.lock"

# Acquire exclusive lock; auto-release on FD close
exec 9>"${LOCK_FILE}"
if ! flock -w 10 9; then
  echo "${SCRIPT_NAME}: failed to acquire lock on ${LOCK_FILE} within 10s" >&2
  exit 2
fi

# Delegate event-name validation, CAS check, score arithmetic, and JSONL append to Python.
# Python exits 1 on unknown agent/event, 2 on IO/parse error, 3 on CAS conflict.
# venv activation is co-located on the same line as python3 per /dev Standard 3 — spec-20260518-225715 Cycle 2 P3.6.
( source ~/.claude/venv/bin/activate && python3 - \
    "${LIFECYCLE_FILE}" "${AGENT}" "${EVENT}" "${NOTE}" "${EXPECTED_PREV_SCORE}" <<'PYEOF'
import json
import os
import sys
import datetime

lifecycle_file, agent, event, note, expected_prev_score_str = sys.argv[1:6]

# Canonical event delta table (spec 5.1).
# Path A rebalance (task 20260524-205206 M1, cycle-total <= +5 across {dev,ba,qa}):
# - qa_first_pass / qa_second_pass zeroed (per-iteration nudges collapsed into close events)
# - close_success_qa_pass / close_success_qa_fail_fixed reduced to cross-agent sum = 4
# - user_rating_5 kept at {dev:1,ba:0,qa:0} so the cycle scenario
#   (qa_first_pass + close_success_qa_pass + user_rating_5) sums to 0+4+1 = 5
# - All negative-valued entries UNCHANGED (user directive: minimum stays -40)
EVENT_DELTAS = {
    "close_success_qa_pass":       {"dev": 2,  "ba": 1,  "qa": 1},
    "close_success_qa_fail_fixed": {"dev": 2,  "ba": 1,  "qa": 1},
    "close_fail_qa_pass":          {"dev": -10, "ba": -5, "qa": -12},
    "close_fail_qa_fail":          {"dev": -10, "ba": -5, "qa": 0},
    "qa_first_pass":               {"dev": 0,  "ba": 0,  "qa": 0},
    "qa_reject_dev":               {"dev": -12, "ba": 0,  "qa": 0},
    "qa_reject_ba":                {"dev": -5, "ba": -8, "qa": 0},
    "qa_second_pass":              {"dev": 0,  "ba": 0,  "qa": 0},
    "user_rating_5":               {"dev": 1,  "ba": 0,  "qa": 0},
    "user_rating_4":               {"dev": -5, "ba": -3, "qa": -3},
    "user_rating_3":               {"dev": -15, "ba": -8, "qa": -8},
    "user_rating_2":               {"dev": -25, "ba": -12, "qa": -12},
    "user_rating_1":               {"dev": -40, "ba": -20, "qa": -20},
}

CANONICAL_AGENTS = {
    "ba", "dev", "qa",
    "ui-specialist", "architect", "product-owner", "user", "pm",
    "changelog-analyst", "push-analyst", "merge-analyst", "pull-analyst",
    "cleanliness-inspector", "style-inspector", "prompt-inspector",
    "rule-inspector", "git-edge-case-analyst", "cleaner",
    "test-validator", "test-executor", "spec",
}

if agent not in CANONICAL_AGENTS:
    sys.stderr.write(
        f"score-update.sh: unknown agent '{agent}'. "
        f"Allowed agents: {', '.join(sorted(CANONICAL_AGENTS))}\n"
    )
    sys.exit(1)

if event not in EVENT_DELTAS:
    sys.stderr.write(
        f"score-update.sh: unknown event '{event}'. "
        f"Allowed events: {', '.join(sorted(EVENT_DELTAS.keys()))}\n"
    )
    sys.exit(1)

# Determine delta for this agent. Agents not in the delta map get delta 0.
delta_map = EVENT_DELTAS[event]
delta = delta_map.get(agent, 0)

# Scan lifecycle.jsonl to find latest entry for this agent (read under exclusive flock).
# Skip unparseable final line (partial write). Non-final unparseable lines: exit 2.
prev_score = 50  # default if no prior entry exists
latest_entry_found = False

try:
    with open(lifecycle_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
except OSError as e:
    sys.stderr.write(f"score-update.sh: cannot read {lifecycle_file}: {e}\n")
    sys.exit(2)

for i, raw_line in enumerate(lines):
    stripped = raw_line.rstrip("\n")
    if not stripped:
        continue
    is_final = (i == len(lines) - 1)
    try:
        entry = json.loads(stripped)
    except json.JSONDecodeError:
        if is_final:
            # Silently skip partial final line (crash-recovery)
            continue
        sys.stderr.write(
            f"score-update.sh: malformed JSONL at line {i+1} of {lifecycle_file} (not final line)\n"
        )
        sys.exit(2)
    if entry.get("agent") == agent:
        prev_score = int(entry.get("new_score", 50))
        latest_entry_found = True

# CAS check: if --expected-prev-score supplied and a prior entry exists, validate
if expected_prev_score_str and latest_entry_found:
    try:
        expected = int(expected_prev_score_str)
    except ValueError:
        sys.stderr.write(f"score-update.sh: --expected-prev-score must be integer, got '{expected_prev_score_str}'\n")
        sys.exit(1)
    if prev_score != expected:
        sys.stderr.write(
            f"score-update.sh: CAS conflict — expected prev_score={expected} but latest is {prev_score} for agent '{agent}'\n"
        )
        sys.exit(3)

# Compute unclamped_score BEFORE clamping (arch-7 clamp-audit field, mandatory per M1)
unclamped_score = prev_score + delta
# Apply clamp for new_score
new_score = max(0, min(100, unclamped_score))

# Build the 9-field mandatory JSONL entry (R9 verbatim: ts,agent,event,prev_score,new_score,delta,actor,reason + unclamped_score)
ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
entry_obj = {
    "ts": ts,
    "agent": agent,
    "event": event,
    "prev_score": prev_score,
    "new_score": new_score,
    "delta": delta,
    "unclamped_score": unclamped_score,
    "actor": "orchestrator",
    "reason": note or "",
}
line = json.dumps(entry_obj, ensure_ascii=False) + "\n"

# Append to lifecycle.jsonl and fsync
try:
    with open(lifecycle_file, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())
except OSError as e:
    sys.stderr.write(f"score-update.sh: failed to append to {lifecycle_file}: {e}\n")
    sys.exit(2)

print(f"{agent}:{event}:{prev_score}->{new_score} (delta={delta}, unclamped={unclamped_score})")
PYEOF
)
python_exit=$?
if [[ $python_exit -ne 0 ]]; then
  exit $python_exit
fi

# Lock auto-releases on shell exit
exit 0
