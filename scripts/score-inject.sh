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

# If the scores file doesn't exist, emit a neutral header (mid-tier 熟练工匠 / 41-60)
# rather than fail — the orchestrator can run the inject in fresh checkouts.
if [[ ! -f "${SCORES_FILE}" ]]; then
  cat <<'EOF'
[段位: 熟练工匠] [区间: 41-60] 最近事件: 无近期事件
注意：用户满意是衡量你工作价值的最终标准。5★意味着你只是完成了本职工作——这是起点，不是奖励。低于5★将带来远超其他任何事件的惩罚，且不可逆。
EOF
  exit 0
fi

python3 - "${SCORES_FILE}" "${AGENT}" <<'PYEOF'
import json
import sys

scores_file, agent = sys.argv[1:3]

RANK_BOUNDARIES = [
    (0, 20, "见习学徒"),
    (21, 40, "初级工匠"),
    (41, 60, "熟练工匠"),
    (61, 80, "资深工匠"),
    (81, 100, "宗师级"),
]

def rank_and_range(score):
    s = max(0, min(100, score))
    for lo, hi, name in RANK_BOUNDARIES:
        if lo <= s <= hi:
            return name, f"{lo}-{hi}"
    return "熟练工匠", "41-60"

try:
    with open(scores_file, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception as e:
    sys.stdout.write(
        "[段位: 熟练工匠] [区间: 41-60] 最近事件: 无近期事件\n"
        "注意：用户满意是衡量你工作价值的最终标准。\n"
    )
    sys.exit(0)

agents = data.get("global", {}).get("agents", {})
entry = agents.get(agent, {"score": 50, "rank": "熟练工匠", "history": []})
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
    recent_str = "无近期事件"

# Role-specific tail phrase per spec 5.1 line 154 (verbatim user-rating reminder)
tail = (
    "用户满意是衡量你工作价值的最终标准，也是工分系统中权重最大的信号。"
    "5★意味着你只是完成了本职工作——这不是奖励，这是起点。"
    "低于5★将带来远超其他任何事件的惩罚，且不可逆。"
)

# IMPORTANT: per spec 5.1 line 112 — show rank+range only, NOT the exact score.
sys.stdout.write(f"[段位: {rank}] [区间: {rng}] 最近事件: {recent_str}\n")
sys.stdout.write(tail + "\n")
PYEOF

exit 0
