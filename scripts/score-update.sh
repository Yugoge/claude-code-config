#!/usr/bin/env bash
# Description: Update agent score state file based on a canonical event.
# Usage: score-update.sh --agent <name> --event <event_name> [--note <text>] [--scores-file <path>]
# Exit codes:
#   0 = success (score updated, history appended)
#   1 = invalid argument or unknown event (no modification made)
#   2 = file/IO error

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
SCORES_FILE_DEFAULT="${HOME}/.claude/agent-scores.json"

usage() {
  cat >&2 <<EOF
Usage: ${SCRIPT_NAME} --agent <name> --event <event_name> [--note <text>] [--scores-file <path>]

Canonical events (from spec 5.1 table):
  close_success_qa_pass, close_success_qa_fail_fixed,
  close_fail_qa_pass, close_fail_qa_fail,
  qa_first_pass, qa_reject_dev, qa_reject_ba, qa_second_pass,
  user_rating_5, user_rating_4, user_rating_3, user_rating_2, user_rating_1

Score is clamped to [0,100]. Rank is recomputed from final score:
  0-20 = rank-1 (apprentice), 21-40 = rank-2 (junior), 41-60 = rank-3 (skilled),
  61-80 = rank-4 (senior), 81-100 = rank-5 (master)
  Note: the bound CJK rank labels emitted to stdout (per spec-20260518-225715
  §5.1 / agents/style-inspector.md Standard 6 Cycle-2 exemption) remain the
  source-language labels; this usage block is English-only stderr text.
EOF
  exit 1
}

AGENT=""
EVENT=""
NOTE=""
SCORES_FILE="${SCORES_FILE_DEFAULT}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)       AGENT="${2:?missing value for --agent}"; shift 2 ;;
    --event)       EVENT="${2:?missing value for --event}"; shift 2 ;;
    --note)        NOTE="${2:?missing value for --note}"; shift 2 ;;
    --scores-file) SCORES_FILE="${2:?missing value for --scores-file}"; shift 2 ;;
    -h|--help)     usage ;;
    *)             echo "Unknown argument: $1" >&2; usage ;;
  esac
done

[[ -z "${AGENT}" ]] && { echo "Missing required --agent" >&2; usage; }
[[ -z "${EVENT}" ]] && { echo "Missing required --event" >&2; usage; }

# Ensure scores file exists; if not, create empty schema
SCORES_DIR="$(dirname "${SCORES_FILE}")"
mkdir -p "${SCORES_DIR}"
if [[ ! -f "${SCORES_FILE}" ]]; then
  echo '{"global":{"agents":{}},"projects":{}}' > "${SCORES_FILE}"
fi

# Lock file alongside the scores file
LOCK_FILE="${SCORES_FILE}.lock"

# Acquire exclusive lock; auto-release on FD close
exec 9>"${LOCK_FILE}"
if ! flock -w 10 9; then
  echo "${SCRIPT_NAME}: failed to acquire lock on ${LOCK_FILE} within 10s" >&2
  exit 2
fi

# Delegate the JSON mutation + event-name validation to Python (atomic write).
# Python prints the resulting delta to stdout for callers to capture, or exits 1
# on unknown event (no modification made). venv activation is co-located on the
# same line as python3 per /dev Standard 3 (use source venv) — spec-20260518-225715 Cycle 2 P3.6.
( source ~/.claude/venv/bin/activate && python3 - "${SCORES_FILE}" "${AGENT}" "${EVENT}" "${NOTE}" <<'PYEOF'
import json
import os
import sys
import tempfile
import datetime

scores_file, agent, event, note = sys.argv[1:5]

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

RANK_BOUNDARIES = [
    (0, 20, "Apprentice"),
    (21, 40, "Journeyman"),
    (41, 60, "Skilled Craftsman"),
    (61, 80, "Senior Craftsman"),
    (81, 100, "Master"),
]

def rank_for_score(score):
    score = max(0, min(100, score))
    for lo, hi, name in RANK_BOUNDARIES:
        if lo <= score <= hi:
            return name
    return "Skilled Craftsman"

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

# Determine delta for this agent. Agents not in the delta map (e.g. ui-specialist)
# still get an event logged but with delta 0 (schema-reserved, no triggers yet).
delta_map = EVENT_DELTAS[event]
delta = delta_map.get(agent, 0)

with open(scores_file, "r", encoding="utf-8") as f:
    data = json.load(f)

data.setdefault("global", {}).setdefault("agents", {})
agents = data["global"]["agents"]
if agent not in agents:
    agents[agent] = {"score": 50, "rank": "Skilled Craftsman", "history": []}

old_score = int(agents[agent].get("score", 50))
uncapped_delta = old_score + delta
new_score = max(0, min(100, old_score + delta))

agents[agent]["score"] = new_score
agents[agent]["rank"] = rank_for_score(new_score)
history = agents[agent].setdefault("history", [])
history.append({
    "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "event": event,
    "delta": delta,
    "old_score": old_score,
    "new_score": new_score,
    "uncapped_delta": uncapped_delta,
    "note": note or "",
})

# Atomic write via tempfile + rename
fd, tmp_path = tempfile.mkstemp(
    prefix=os.path.basename(scores_file) + ".",
    suffix=".tmp",
    dir=os.path.dirname(scores_file),
)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp_path, scores_file)
except Exception:
    try: os.unlink(tmp_path)
    except OSError: pass
    raise

print(f"{agent}:{event}:{old_score}->{new_score} (delta={delta})")
PYEOF
)

# Lock auto-releases on shell exit
exit 0
