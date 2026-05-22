#!/usr/bin/env bash
# Description: Emit a prompt-injection text block describing an agent's current rank/range
#              and last 3 history events, plus a role-specific tail phrase.
# Usage: score-inject.sh --agent <name> [--scores-file <path>]
# Output: stdout = injection text block (rank + range + last-3 events + tail phrase)
#         stderr = empty on success
# Exit codes: 0 = ok, 1 = bad argument

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
SCORES_FILE_DEFAULT="${HOME}/.claude/agent-scores.json"

usage() {
  echo "Usage: ${SCRIPT_NAME} --agent <name> [--scores-file <path>]" >&2
  exit 1
}

AGENT=""
SCORES_FILE="${SCORES_FILE_DEFAULT}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)       AGENT="${2:?missing value for --agent}"; shift 2 ;;
    --scores-file) SCORES_FILE="${2:?missing value for --scores-file}"; shift 2 ;;
    -h|--help)     usage ;;
    *)             echo "Unknown argument: $1" >&2; usage ;;
  esac
done

[[ -z "${AGENT}" ]] && usage

# If the scores file doesn't exist, emit a neutral mid-tier header (rank-3 /
# range 41-60 / no-recent-events) rather than fail — the orchestrator can run
# the inject in fresh checkouts. The CJK rank label inside the cat heredoc
# below is the bound user-facing prompt-output per spec-20260518-225715 §5.1
# Cycle-2 exemption (agents/style-inspector.md Standard 6).
if [[ ! -f "${SCORES_FILE}" ]]; then
  cat <<'EOF'
[Rank: Skilled Craftsman] [Range: 41-60] Recent events: none
NOTE: User satisfaction is the final standard for measuring the value of your work. 5 stars means you have only completed your basic job — this is the starting point, not a reward. Below 5 stars will bring punishment far exceeding any other event, and is irreversible.
EOF
  exit 0
fi

( source ~/.claude/venv/bin/activate && python3 - "${SCORES_FILE}" "${AGENT}" <<'PYEOF'
import json
import sys

scores_file, agent = sys.argv[1:3]

RANK_BOUNDARIES = [
    (0, 20, "Apprentice"),
    (21, 40, "Journeyman"),
    (41, 60, "Skilled Craftsman"),
    (61, 80, "Senior Craftsman"),
    (81, 100, "Master"),
]

def rank_and_range(score):
    s = max(0, min(100, score))
    for lo, hi, name in RANK_BOUNDARIES:
        if lo <= s <= hi:
            return name, f"{lo}-{hi}"
    return "Skilled Craftsman", "41-60"

try:
    with open(scores_file, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception as e:
    sys.stdout.write(
        "[Rank: Skilled Craftsman] [Range: 41-60] Recent events: none\n"
        "NOTE: User satisfaction is the final standard for measuring the value of your work.\n"
    )
    sys.exit(0)

agents = data.get("global", {}).get("agents", {})
entry = agents.get(agent, {"score": 50, "rank": "Skilled Craftsman", "history": []})
score = int(entry.get("score", 50))
rank, rng = rank_and_range(score)
history = entry.get("history", [])

# Take only the last 3 events. Each event presented compactly: event name (delta).
recent = history[-3:] if history else []
if recent:
    parts = []
    for h in recent:
        ev = h.get("event", "?")
        d = h.get("delta", 0)
        sign = "+" if d >= 0 else ""
        parts.append(f"{ev}({sign}{d})")
    recent_str = ", ".join(parts)
else:
    recent_str = "none"

# Role-specific tail phrase per spec 5.1 line 154 (verbatim user-rating reminder)
tail = (
    "User satisfaction is the final standard for measuring the value of your work, and the highest-weighted signal in the scoring system."
    "5 stars means you have only completed your basic job — this is not a reward, it is the starting point."
    "Below 5 stars will bring punishment far exceeding any other event, and is irreversible."
)

# IMPORTANT: per spec 5.1 line 112 — show rank+range only, NOT the exact score.
sys.stdout.write(f"[Rank: {rank}] [Range: {rng}] Recent events: {recent_str}\n")
sys.stdout.write(tail + "\n")
PYEOF
)

exit 0
