#!/usr/bin/env bash
# commit.sh -- /commit slash command executor
# Usage: bash ~/.claude/hooks/commit.sh "Conventional Commit message"
#
# Consumes the session-scoped staging ledger (posttool-ledger-writer.py)
# and advances the branch via CAS. No flags. No modes. No helpers.

set -euo pipefail

LEDGER_BASE="${CLAUDE_LEDGER_BASE:-/var/lib/claude/ledger}"
AUDIT_BASE="${CLAUDE_AUDIT_BASE:-/var/lib/claude/audit}"

# Step 1: Arg parse
if [ "$#" -ne 1 ]; then
  echo "Usage: /commit \"<Conventional Commit message>\"" >&2
  echo "Exactly one positional argument required. No flags." >&2
  exit 2
fi
MSG="$1"

# Step 2: M3 CC type lint (subject line only; multi-line body must not bypass)
if [ "${CLAUDE_COMMIT_SKIP_TYPE_LINT:-0}" != "1" ]; then
  CC_TYPES="feat|fix|refactor|docs|test|chore|build|ci|perf|style|revert"
  CC_PATTERN="^(${CC_TYPES})(\\([A-Za-z0-9_-]+\\))?(!)?: .{1,}$"
  SUBJECT="${MSG%%$'\n'*}"
  if ! printf '%s' "$SUBJECT" | grep -qE "$CC_PATTERN"; then
    echo "BLOCKED: invalid Conventional Commit type in message: $MSG" >&2
    echo "Allowed: feat fix refactor docs test chore build ci perf style revert" >&2
    echo "Format: <type>(<optional-scope>): <description>" >&2
    echo "Set CLAUDE_COMMIT_SKIP_TYPE_LINT=1 to bypass." >&2
    exit 2
  fi
fi

# Step 3: Session ID (runtime injects CLAUDE_CODE_SESSION_ID; accept either)
SID="${CLAUDE_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-}}"
if [ -z "$SID" ]; then
  echo "BLOCKED: CLAUDE_SESSION_ID not set -- cannot identify session ledger." >&2
  exit 2
fi

LEDGER_FILE="${LEDGER_BASE}/${SID}.jsonl"
CONSUMED_FILE="${LEDGER_BASE}/${SID}.consumed.json"

export SID LEDGER_FILE CONSUMED_FILE AUDIT_BASE MSG

# Delegate all git plumbing to Python
SCRIPT_DIR=$(dirname "$(realpath "$0")")
exec python3 "${SCRIPT_DIR}/commit-cas.py"
