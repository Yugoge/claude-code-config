#!/bin/bash
#
# /commit wrapper — closed dev task one-shot commit (Scheme 6)
#
# Authority:
#   /root/docs/dev/close-report-20260425-push-commit-debate.md (CLOSE: YES on Scheme 6)
#   /root/docs/dev/ba-spec-20260425-redev2.md §4.3 (AC-C1..AC-C13)
#
# Flow:
#   1. Parse <task-id> argument (positional, required)
#   2. Closure detection (PRIMARY close-report → SECONDARY completion+qa-report; fail-closed)
#   3. Read dev-report; extract allowed_files (multi-schema union)
#   4. Generate deterministic commit message; compute sha256
#   5. Write single-use grant manifest /tmp/claude-commit-grant-<sid>-<nonce>.json
#   6. Stage exactly allowed_files; verify staged set matches
#   7. Export CLAUDE_COMMIT_COMMAND_ACTIVE=1; run blessed git commit
#   8. Append audit log line to /root/.claude/logs/git-privilege-grants.log
#
# Defense:
#   - Closure check is necessary but not sufficient — bulk-commit-detector remains an
#     independent downstream gate. A forged grant whose allowed_files spans 3+ subsystems
#     and whose message looks like 'chore(claude): sync ...' will still be blocked there.
#   - Grant single-use unlink is performed by THIS WRAPPER on the success path.
#     PreToolUse hooks (incl. the privilege-guard) DO NOT fire on subprocesses spawned
#     by a wrapper script, so the guard cannot observe the `git commit` subprocess and
#     cannot unlink the grant. The wrapper must clean up after itself (AC-iter2-9).
#   - On any wrapper failure path, the grant is left in place — the operator may want
#     to retry, and the grant has nonce binding so retries are safe. The EXIT trap
#     unlinks ONLY when the wrapper itself errors out before reaching the success path.

set -euo pipefail

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
DOCS_DIR="/root/docs/dev"
LOG_PATH="/root/.claude/logs/git-privilege-grants.log"
GRANT_FILE=""

# AC-iter2-9: Wrapper-only grant lifecycle.
#   - Success path: Step 7 unlinks GRANT_FILE after `git commit` returns 0
#     (PreToolUse hooks do not fire on subprocesses, so the guard cannot do it).
#   - Failure path: leave the grant in place. The grant is nonce-bound and
#     single-use, so the operator may safely retry. No EXIT trap removal.
# (Earlier revisions removed the grant in an EXIT trap on rc!=0 — that was the
# wrong policy and is no longer in force.)

# -----------------------------------------------------------------------------
# Step 1 — argument parse
# -----------------------------------------------------------------------------
if [ $# -lt 1 ] || [ -z "${1:-}" ]; then
  echo "Usage: commit.sh <task-id>" >&2
  echo "Example: commit.sh dev-20260425-145411" >&2
  exit 2
fi
TASK_ID="$1"

# Reject obvious shell metacharacters in task id (defense in depth).
if [[ "$TASK_ID" =~ [[:space:]\;\&\|\`\$\(\)\<\>\\\"\'\*\?\[\]] ]]; then
  echo "commit.sh: invalid task-id (shell-metacharacters not allowed): $TASK_ID" >&2
  exit 2
fi

# -----------------------------------------------------------------------------
# Step 2 — closure detection (PRIMARY then SECONDARY, fail-closed)
# -----------------------------------------------------------------------------
CLOSE_REPORT="${DOCS_DIR}/close-report-${TASK_ID}.md"
COMPLETION_DOC="${DOCS_DIR}/completion-${TASK_ID}.md"
QA_REPORT="${DOCS_DIR}/qa-report-${TASK_ID}.json"

CLOSURE_PATH=""    # path of the file that satisfied the check (used for title extraction)
CLOSURE_KIND=""    # "primary" | "secondary"

# PRIMARY: close-report exists AND last non-empty line matches '^CLOSE:\s*YES\b'
if [ -f "$CLOSE_REPORT" ]; then
  # Last non-empty line — strip CR, drop blank lines, take final survivor.
  LAST_NONEMPTY="$(tr -d '\r' < "$CLOSE_REPORT" | awk 'NF{line=$0} END{print line}')"
  if [[ "$LAST_NONEMPTY" =~ ^CLOSE:[[:space:]]*YES([[:space:]]|$|\b) ]]; then
    CLOSURE_PATH="$CLOSE_REPORT"
    CLOSURE_KIND="primary"
  fi
fi

# SECONDARY: only if PRIMARY failed.
#
# F2 (close-report-20260425-push-commit-debate.md §3 — task-id content binding):
# the SECONDARY path was previously file-existence-only, which let an attacker
# steer /commit at an unrelated task by simply renaming dropped files.  We now
# require the task-id to appear (a) as the leading H1/title of the
# completion-md, and (b) inside the qa-report.json's task_id / request_id keys
# (UNION at top-level OR under .qa), and (c) inside the dev-report.json's
# task_id / request_id keys (UNION at top-level OR under .dev).  ALL three
# checks must pass; ANY missing -> exit 2 (fail closed).
if [ -z "$CLOSURE_KIND" ]; then
  if [ -f "$COMPLETION_DOC" ] && [ -f "$QA_REPORT" ]; then
    QA_STATUS_OK="$(python3 -c "
import json, sys
try:
    with open(sys.argv[1]) as fh:
        data = json.load(fh)
except Exception:
    sys.exit(1)
status = data.get('qa', {}).get('status') if isinstance(data, dict) else None
sys.exit(0 if status == 'pass' else 1)
" "$QA_REPORT" && echo yes || echo no)"
    if [ "$QA_STATUS_OK" = "yes" ]; then
      # F2 check 1: task_id must appear in completion-md H1/title.
      if ! grep -E "^#[[:space:]]+.*${TASK_ID}" "$COMPLETION_DOC" > /dev/null; then
        echo "SECONDARY closure refused: ${TASK_ID} not in ${COMPLETION_DOC} title/H1" >&2
        exit 2
      fi

      # F2 check 2: task_id must appear in qa-report.json content (UNION rule).
      DEV_REPORT_PRECHECK="${DOCS_DIR}/dev-report-${TASK_ID}.json"
      if python3 -c "
import json, sys
try:
    with open(sys.argv[1]) as fh:
        data = json.load(fh)
except Exception:
    sys.exit(1)
if not isinstance(data, dict):
    sys.exit(1)
qa_node = data.get('qa') if isinstance(data.get('qa'), dict) else {}
keys_to_check = [
    data.get('task_id'),
    data.get('request_id'),
    qa_node.get('task_id'),
    qa_node.get('request_id'),
]
sys.exit(0 if sys.argv[2] in keys_to_check else 1)
" "$QA_REPORT" "$TASK_ID"; then
        :
      else
        echo "SECONDARY closure refused: task_id ${TASK_ID} not found in ${QA_REPORT} (checked task_id, request_id, qa.task_id, qa.request_id)" >&2
        exit 2
      fi

      # F2 check 3: task_id must appear in dev-report.json content (UNION rule).
      if [ ! -f "$DEV_REPORT_PRECHECK" ]; then
        echo "SECONDARY closure refused: dev-report missing at ${DEV_REPORT_PRECHECK}" >&2
        exit 2
      fi
      if python3 -c "
import json, sys
try:
    with open(sys.argv[1]) as fh:
        data = json.load(fh)
except Exception:
    sys.exit(1)
if not isinstance(data, dict):
    sys.exit(1)
dev_node = data.get('dev') if isinstance(data.get('dev'), dict) else {}
keys_to_check = [
    data.get('task_id'),
    data.get('request_id'),
    dev_node.get('task_id'),
    dev_node.get('request_id'),
]
sys.exit(0 if sys.argv[2] in keys_to_check else 1)
" "$DEV_REPORT_PRECHECK" "$TASK_ID"; then
        :
      else
        echo "SECONDARY closure refused: task_id ${TASK_ID} not found in ${DEV_REPORT_PRECHECK} (checked task_id, request_id, dev.task_id, dev.request_id)" >&2
        exit 2
      fi

      CLOSURE_PATH="$COMPLETION_DOC"
      CLOSURE_KIND="secondary"
    fi
  fi
fi

if [ -z "$CLOSURE_KIND" ]; then
  echo "task not closed: no close-report or completion+qa-pass evidence for ${TASK_ID}" >&2
  echo "  looked for PRIMARY:   ${CLOSE_REPORT} (last line ^CLOSE:\\s*YES\\b)" >&2
  echo "  looked for SECONDARY: ${COMPLETION_DOC} + ${QA_REPORT} (.qa.status == 'pass')" >&2
  exit 2
fi

# -----------------------------------------------------------------------------
# Step 3 — resolve dev-report and extract allowed_files
# -----------------------------------------------------------------------------
DEV_REPORT="${DOCS_DIR}/dev-report-${TASK_ID}.json"
if [ ! -f "$DEV_REPORT" ]; then
  echo "dev-report missing: ${DEV_REPORT}" >&2
  exit 2
fi

# Union: top.files_modified ∪ top.files_created ∪ dev.files_modified ∪ dev.files_created
# Output: newline-separated, sorted+deduped. Empty/missing fields ignored.
ALLOWED_RAW="$(python3 - "$DEV_REPORT" <<'PY'
import json, sys
path = sys.argv[1]
try:
    with open(path) as fh:
        data = json.load(fh)
except Exception as e:
    sys.stderr.write(f"dev-report parse error: {e}\n")
    sys.exit(1)

def collect(node, key):
    if not isinstance(node, dict):
        return []
    val = node.get(key)
    if isinstance(val, list):
        return [v for v in val if isinstance(v, str) and v.strip()]
    return []

files = set()
for node in (data, data.get('dev') if isinstance(data, dict) else None):
    files.update(collect(node, 'files_modified'))
    files.update(collect(node, 'files_created'))

# Print one path per line, sorted + deduped.
for f in sorted(files):
    print(f)
PY
)"

if [ -z "$ALLOWED_RAW" ]; then
  echo "dev-report.files_modified/files_created union is empty for ${TASK_ID}" >&2
  echo "  cannot derive allowed_files; refusing to commit." >&2
  exit 2
fi

# Pack into a bash array.
ALLOWED_FILES=()
while IFS= read -r line; do
  [ -n "$line" ] && ALLOWED_FILES+=("$line")
done <<< "$ALLOWED_RAW"

# JSON-encode for the grant manifest.
ALLOWED_JSON="$(python3 -c "
import json, sys
files = [l for l in sys.stdin.read().splitlines() if l.strip()]
print(json.dumps(sorted(set(files))))
" <<< "$ALLOWED_RAW")"

# -----------------------------------------------------------------------------
# Step 4 — generate commit message + sha256
# -----------------------------------------------------------------------------
# Title = first '# ' heading in CLOSURE_PATH (close-report or completion).
TITLE="$(awk '
  /^# / { sub(/^# /, ""); print; exit }
' "$CLOSURE_PATH" 2>/dev/null || true)"
TITLE="${TITLE:-closed dev task}"

# Sanitize: collapse whitespace, trim CR.
TITLE="$(printf '%s' "$TITLE" | tr -d '\r' | sed -E 's/[[:space:]]+/ /g; s/^ //; s/ $//')"
[ -n "$TITLE" ] || TITLE="closed dev task"

COMMIT_MSG="commit(${TASK_ID}): ${TITLE}"

MSG_SHA256="$(python3 -c "
import hashlib, sys
print(hashlib.sha256(sys.argv[1].encode('utf-8')).hexdigest())
" "$COMMIT_MSG")"

# -----------------------------------------------------------------------------
# Step 5 — write single-use grant manifest
# -----------------------------------------------------------------------------
SID="${CLAUDE_SESSION_ID:-$$}"
NONCE="$(python3 -c "import secrets; print(secrets.token_hex(16))")"
GRANT_FILE="/tmp/claude-commit-grant-${SID}-${NONCE}.json"
CREATED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
PPID_VAL="$$"

python3 - "$GRANT_FILE" "$NONCE" "$SID" "$TASK_ID" "$ALLOWED_JSON" "$MSG_SHA256" "$CREATED_AT" "$PPID_VAL" <<'PY'
import json, sys
path, nonce, sid, task_id, allowed_json, msg_sha, created_at, ppid_val = sys.argv[1:9]
grant = {
    "nonce": nonce,
    "sid": sid,
    "task_id": task_id,
    "allowed_files": json.loads(allowed_json),
    "expected_message_sha256": msg_sha,
    "created_at": created_at,
    "ppid": int(ppid_val),
}
with open(path, "w") as fh:
    json.dump(grant, fh, indent=2, sort_keys=True)
PY

# -----------------------------------------------------------------------------
# Step 6 — stage exactly allowed_files; verify
# -----------------------------------------------------------------------------
git add -- "${ALLOWED_FILES[@]}"

STAGED_LIST="$(git diff --cached --name-only | sort -u)"
ALLOWED_LIST="$(printf '%s\n' "${ALLOWED_FILES[@]}" | sort -u)"

if [ "$STAGED_LIST" != "$ALLOWED_LIST" ]; then
  echo "commit.sh: staged-set does not equal allowed_files (refusing to commit)" >&2
  echo "--- staged ---" >&2
  printf '%s\n' "$STAGED_LIST" >&2
  echo "--- allowed ---" >&2
  printf '%s\n' "$ALLOWED_LIST" >&2
  exit 2
fi

# -----------------------------------------------------------------------------
# Step 7 — export env and run blessed commit
# -----------------------------------------------------------------------------
export CLAUDE_COMMIT_COMMAND_ACTIVE=1

# IMPORTANT: HEAD must advance on the current branch. Do NOT touch refs/checkpoints/*.
git commit -m "$COMMIT_MSG"

# AC-iter2-9: wrapper unlinks grant on success path (guard never fires on subprocess)
rm -f "$GRANT_FILE"
GRANT_FILE=""

# -----------------------------------------------------------------------------
# Step 8 — audit log
# -----------------------------------------------------------------------------
mkdir -p "$(dirname "$LOG_PATH")"
NEW_HEAD="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
MSG_SHA_SHORT="${MSG_SHA256:0:12}"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Append a single JSON line for downstream parsing convenience.
python3 - "$LOG_PATH" "$TS" "$SID" "$TASK_ID" "$NONCE" "$PPID_VAL" "$MSG_SHA_SHORT" "$NEW_HEAD" "$CLOSURE_KIND" <<'PY'
import json, sys
path, ts, sid, task_id, nonce, ppid_val, msg_sha_short, head, closure_kind = sys.argv[1:10]
line = {
    "timestamp": ts,
    "sid": sid,
    "command_kind": "commit",
    "task_id": task_id,
    "sentinel_nonce": nonce,
    "ppid": int(ppid_val),
    "message_sha256_short": msg_sha_short,
    "head": head,
    "closure_kind": closure_kind,
}
with open(path, "a") as fh:
    fh.write(json.dumps(line) + "\n")
PY

echo "commit.sh: success — task=${TASK_ID} head=${NEW_HEAD} closure=${CLOSURE_KIND} files=${#ALLOWED_FILES[@]}"
exit 0
