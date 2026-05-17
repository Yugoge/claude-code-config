#!/usr/bin/env bash
# Write or update qa_mode field in the QA sentinel file for a dev-registry session.
# Usage: write-qa-mode.sh --session-id <dev-SESSION_ID> --mode <ba_validation|final_verification>
# Exits 1 on failure; callers must abort if this script fails.
set -euo pipefail

SESSION_ID=""
MODE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --session-id) SESSION_ID="$2"; shift 2 ;;
    --mode)       MODE="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

[[ -n "$SESSION_ID" ]] || { echo "ERROR: --session-id required" >&2; exit 1; }
[[ -n "$MODE" ]] || { echo "ERROR: --mode required" >&2; exit 1; }

REGISTRY_DIR="${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR not set}/.claude/dev-registry/$SESSION_ID"
QA_PATH="$REGISTRY_DIR/qa.json"

python3 - <<PYEOF
import json, os, sys
path = "$QA_PATH"
mode = "$MODE"
data = {}
if os.path.exists(path):
    try:
        with open(path) as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            data = loaded
    except Exception:
        pass
data['qa_mode'] = mode
with open(path, 'w') as f:
    json.dump(data, f)
print(f"qa_mode={mode} written to {path}", file=sys.stderr)
PYEOF
