#!/usr/bin/env bash
# Description: Cache-safe canary that behaviorally verifies the four core PreToolUse hooks.
# Usage: canary-verify.sh [--hooks-dir <path>]
#   Designed to run as a SessionStart hook (registered in settings.json).
# Output contract (spec §5.5):
#   - Healthy run: zero bytes to stdout (exec >/dev/null), exit 0
#   - Failure:     stderr message describing the broken hook, exit 2
#   - Advisory:    stderr message but exit 0 (stdout-polluting prerequisite hooks
#                  such as session-info.sh / session-git-init.sh — declared
#                  Won't Have for this cycle; documented in spec §5.5)

set -uo pipefail

# Suppress ALL stdout for prompt-cache safety per spec §5.5 line 214
# (exec >/dev/null at top; not just at the end). Failures still reach stderr.
exec >/dev/null

HOOKS_DIR_DEFAULT="${HOME}/.claude/hooks"
HOOKS_DIR="${HOOKS_DIR_DEFAULT}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hooks-dir) HOOKS_DIR="${2:?missing value for --hooks-dir}"; shift 2 ;;
    -h|--help)
      echo "Usage: $(basename "$0") [--hooks-dir <path>]" >&2
      exit 0
      ;;
    *) echo "canary-verify.sh: unknown arg '$1'" >&2; exit 1 ;;
  esac
done

failures=0

emit_failure() {
  # Final exit is 2; emit a single composed stderr line per failure.
  echo "canary-verify[FAIL]: $*" >&2
  failures=$((failures + 1))
}

emit_advisory() {
  # Advisory: log to stderr but do not increment failures (spec §5.5 + Won't Have).
  echo "canary-verify[ADVISORY]: $*" >&2
}

# ---------------------------------------------------------------------------
# Behavioural test for each guard. Inputs are synthetic minimal JSON envelopes
# matching Claude's PreToolUse contract. We only check the hook is invocable
# and does not crash; deny outcomes are EXPECTED for unsafe payloads.
# ---------------------------------------------------------------------------

verify_bash_safety() {
  local hook="${HOOKS_DIR}/pretool-bash-safety.sh"
  if [[ ! -x "${hook}" && ! -f "${hook}" ]]; then
    emit_failure "missing or non-executable: ${hook}"
    return
  fi
  # Inputs: a safe payload (echo hello) — expect exit 0
  local payload='{"tool_name":"Bash","tool_input":{"command":"echo hello"}}'
  if ! echo "${payload}" | bash "${hook}" >/dev/null 2>&1; then
    emit_failure "pretool-bash-safety.sh rejected a benign 'echo hello' payload (hook may be broken)"
  fi
}

verify_write_guard() {
  local hook="${HOOKS_DIR}/pretool-write-guard.sh"
  if [[ ! -f "${hook}" ]]; then
    emit_failure "missing: ${hook}"
    return
  fi
  # Safe payload: writing to /tmp — expect non-crash. Exit code variations are
  # acceptable; we only fail if the hook process itself errors with a non-policy
  # signal (>=126 = exec failure, 127 = command not found).
  local payload='{"tool_name":"Write","tool_input":{"file_path":"/tmp/canary-safe.txt","content":"ok"}}'
  echo "${payload}" | bash "${hook}" >/dev/null 2>&1
  local rc=$?
  if [[ "${rc}" -ge 126 ]]; then
    emit_failure "pretool-write-guard.sh exec error rc=${rc}"
  fi
}

verify_read_size_guard() {
  local hook="${HOOKS_DIR}/pretool-read-size-guard.py"
  if [[ ! -f "${hook}" ]]; then
    emit_failure "missing: ${hook}"
    return
  fi
  # Small synthetic Read payload — must not crash
  local payload='{"tool_name":"Read","tool_input":{"file_path":"/dev/null"}}'
  echo "${payload}" | python3 "${hook}" >/dev/null 2>&1
  local rc=$?
  if [[ "${rc}" -ge 126 ]]; then
    emit_failure "pretool-read-size-guard.py exec error rc=${rc}"
  fi
}

verify_git_privilege_guard() {
  local hook="${HOOKS_DIR}/pretool-git-privilege-guard.py"
  if [[ ! -f "${hook}" ]]; then
    emit_failure "missing: ${hook}"
    return
  fi
  # Benign git status payload
  local payload='{"tool_name":"Bash","tool_input":{"command":"git status"}}'
  echo "${payload}" | python3 "${hook}" >/dev/null 2>&1
  local rc=$?
  if [[ "${rc}" -ge 126 ]]; then
    emit_failure "pretool-git-privilege-guard.py exec error rc=${rc}"
  fi
}

# ---------------------------------------------------------------------------
# Advisory checks (spec §5.5 prerequisite — declared Won't Have for this cycle)
# session-info.sh and session-git-init.sh are SessionStart hooks that emit
# stdout. They are not in scope to fix; we log advisory only so existing
# sessions are not blocked.
# ---------------------------------------------------------------------------
check_advisory_prerequisites() {
  for f in "${HOOKS_DIR}/session-info.sh" "${HOOKS_DIR}/session-git-init.sh"; do
    if [[ ! -f "${f}" ]]; then
      continue
    fi
    # If the script writes to stdout (echo / printf without >&2), flag advisory.
    if grep -E '^[[:space:]]*(echo|printf)' "${f}" 2>/dev/null \
       | grep -vE '>\s*&2|>&2' >/dev/null 2>&1; then
      emit_advisory "${f} emits stdout without >&2 (spec §5.5 prerequisite, Won't Have this cycle)"
    fi
  done
}

verify_bash_safety
verify_write_guard
verify_read_size_guard
verify_git_privilege_guard
check_advisory_prerequisites

if [[ "${failures}" -gt 0 ]]; then
  echo "canary-verify[FAIL]: ${failures} hook(s) broken — see preceding lines" >&2
  exit 2
fi

exit 0
