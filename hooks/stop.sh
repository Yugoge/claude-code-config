#!/usr/bin/env bash
# stop.sh - wrapper for /stop slash command
#
# Cancels every active overnight time-lock + workflow-enforce by:
#   1. Backdating end_time on each active overnight-state-*.json file
#   2. Marking every todo in the corresponding todos file as "completed"
#
# After this runs, both Stop hooks (stop-overnight-timelock.py + stop-
# workflow-enforce.py) release on the next stop attempt and the session
# can terminate normally.
#
# Sentinel guard mirrors commit/push/merge: pretool-wrapper-userintent.py
# enforces that this script is only invocable via /stop slash command.
# Model agents using Bash to invoke stop.sh directly will be blocked.
set -euo pipefail

HELPER="/root/.claude/scripts/break-overnight-lock.py"
if [ ! -f "$HELPER" ]; then
  echo "stop.sh: helper $HELPER missing" >&2
  exit 1
fi

python3 "$HELPER"
