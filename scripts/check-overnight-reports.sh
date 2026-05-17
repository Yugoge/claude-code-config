#!/usr/bin/env bash
# DEPRECATED — replaced by check-overnight-reports.py per spec-20260426-090235 P0/M5.
# This shim forwards to the Python implementation for any external callers
# still invoking the .sh path. The .py reads cycle-contract.json instead of
# the legacy hardcoded 4-specialist list (product-owner, architect, user,
# ui-specialist). See /root/docs/dev/specs/spec-20260426-090235.md Section 7
# (P0 #5) for the rationale.
#
# New callers MUST use:
#   check-overnight-reports.py --session-id <sid> [--cycle <N>]
#
# This shim accepts the legacy positional <report_dir> argument and ignores
# it (the .py resolves the cycle directory from the session id) so that
# stale crontabs / docs do not break loudly during the transition.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_SCRIPT="$SCRIPT_DIR/check-overnight-reports.py"

if [[ ! -f "$PY_SCRIPT" ]]; then
    echo "ERROR: $PY_SCRIPT missing — contract-driven validator not installed" >&2
    exit 1
fi

# Activate venv if available
VENV_DIR="${SCRIPT_DIR}/../venv"
if [[ -f "${VENV_DIR}/bin/activate" ]]; then
    source "${VENV_DIR}/bin/activate"
elif [[ -f "${SCRIPT_DIR}/../.venv/bin/activate" ]]; then
    source "${SCRIPT_DIR}/../.venv/bin/activate"
fi

# Best-effort: if a single positional argument is supplied (legacy
# <report_dir>), try to derive a session id from the directory name. Any
# caller that needs full control should switch to the .py directly.
if [[ "$#" -eq 1 && -d "$1" ]]; then
    SESSION_ID="$(basename "$1")"
    exec python3 "$PY_SCRIPT" --session-id "$SESSION_ID"
fi

exec python3 "$PY_SCRIPT" "$@"
