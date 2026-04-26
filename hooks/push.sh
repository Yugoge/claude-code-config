#!/bin/bash
# push.sh - Executable version of /push command
# Location: ~/.claude/hooks/push.sh
# Usage: bash ~/.claude/hooks/push.sh [--auto]
#
# Options:
#   --auto    Non-interactive mode (auto-remove stale locks only; does NOT
#             auto-commit. A dirty working tree no longer blocks /push
#             (redev7 P-PUSH-DIRTY-OK) — the wrapper shows an informational
#             warning and proceeds, since git push only ships already-
#             committed commits to remote. Automated snapshots live on
#             refs/checkpoints/<branch> and must NOT be promoted to HEAD.)

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Check for --auto flag or if running in non-interactive environment
AUTO_MODE=0
if [ "$1" = "--auto" ] || [ ! -t 0 ]; then
  AUTO_MODE=1
fi

echo -e "${BLUE}🚀 Starting validated push...${NC}"
if [ "$AUTO_MODE" = "1" ]; then
  echo -e "${CYAN}(Non-interactive mode)${NC}"
fi
echo ""

# Step 1: Get current branch
BRANCH=$(git branch --show-current)
if [ -z "$BRANCH" ]; then
  echo -e "${RED}❌ Error: Not on a branch (detached HEAD)${NC}"
  echo "Checkout a branch first: git checkout <branch-name>"
  exit 1
fi

# Step 2: Check git status
echo "📊 Checking repository status..."
echo ""

# Get staged files
# F-STAGED-COUNT (redev8): explicit empty-string guard. The previous form
# `echo "$STAGED" | grep -c '^'` returned 1 for empty $STAGED because echo
# always emits a single newline. Use parameter expansion to short-circuit
# to 0 when the variable is empty.
STAGED=$(git diff --cached --name-only 2>/dev/null)
if [ -z "$STAGED" ]; then STAGED_COUNT=0; else STAGED_COUNT=$(echo "$STAGED" | wc -l); fi

# Get modified but unstaged files
MODIFIED=$(git diff --name-only 2>/dev/null)
if [ -z "$MODIFIED" ]; then MODIFIED_COUNT=0; else MODIFIED_COUNT=$(echo "$MODIFIED" | wc -l); fi

# Get untracked files (respecting .gitignore)
UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null)
if [ -z "$UNTRACKED" ]; then UNTRACKED_COUNT=0; else UNTRACKED_COUNT=$(echo "$UNTRACKED" | wc -l); fi

# Step 3: Display status summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${CYAN}Git Status Summary${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$STAGED_COUNT" != "0" ] && [ -n "$STAGED" ]; then
  echo -e "${GREEN}Staged files ($STAGED_COUNT):${NC}"
  echo "$STAGED" | sed 's/^/   ✓ /'
  echo ""
fi

if [ "$MODIFIED_COUNT" != "0" ] && [ -n "$MODIFIED" ]; then
  echo -e "${YELLOW}Modified but not staged ($MODIFIED_COUNT):${NC}"
  echo "$MODIFIED" | sed 's/^/   ⚠ /'
  echo ""
fi

if [ "$UNTRACKED_COUNT" != "0" ] && [ -n "$UNTRACKED" ]; then
  echo -e "${YELLOW}Untracked files ($UNTRACKED_COUNT):${NC}"
  echo "$UNTRACKED" | sed 's/^/   ? /'
  echo ""
fi

if [ "$STAGED_COUNT" = "0" ] && [ "$MODIFIED_COUNT" = "0" ] && [ "$UNTRACKED_COUNT" = "0" ]; then
  echo -e "${GREEN}✓ Working directory clean${NC}"
  echo ""
fi

# Step 4: Dirty-tree informational warning (redev7 P-PUSH-DIRTY-OK).
# Working tree drift does NOT block push. git push only ships already-committed
# commits to remote — the working tree state is irrelevant to git push semantics.
# This was a vestigial gate from an old design where /push auto-committed.
# The b5d447e snapshots-off-HEAD design guarantees /push cannot promote
# working-tree content to HEAD, so the gate is unnecessary.
DIRTY_STATUS=$(git status --porcelain 2>/dev/null)
if [ -n "$DIRTY_STATUS" ]; then
  DIRTY_COUNT=$(echo "$DIRTY_STATUS" | grep -c '^' 2>/dev/null || echo "0")
  echo -e "${YELLOW}ℹ  Working tree has ${DIRTY_COUNT} dirty file(s) (not blocking).${NC}"
  echo "   These files (modified/staged/untracked) are NOT being pushed —"
  echo "   git push only ships already-committed commits to remote."
  echo "   To push your local changes, commit them first via /commit."
  echo ""
fi

# Step 5: No staged/unstaged/untracked content at this point. Verify there is
# actually something to push; otherwise exit cleanly.
if [ "$STAGED_COUNT" = "0" ]; then
  COMMITS_AHEAD=$(git rev-list --count @{u}..HEAD 2>/dev/null || echo "0")
  if [ "$COMMITS_AHEAD" != "0" ] && [ "$COMMITS_AHEAD" != "" ]; then
    echo "Working tree clean. $COMMITS_AHEAD commit(s) ahead of remote — proceeding with push."
    echo ""
  else
    echo "Nothing to push (working tree clean, no commits ahead of remote)."
    echo ""
    exit 0
  fi
fi

# Step 8.5: Write Scheme 6 grant manifest for guard validation
# The privilege-guard (pretool-git-privilege-guard.py) is always-on and rejects
# every agent-issued `git push`. This wrapper emits a single-use grant file
# (binding branch+expected_head+remote+sid+ppid+nonce) and exports the
# wrapper-set env-var so the guard admits exactly THIS push and no other.
# Inline-env injection (e.g., `CLAUDE_PUSH_COMMAND_ACTIVE=1 git push ...` typed
# by the agent on a single Bash call) is rejected by the guard's literal-
# substring defense — only env-vars set by a parent process (this wrapper) are
# admitted.
SID="${CLAUDE_SESSION_ID:-default}"
NONCE=$(python3 -c "import secrets; print(secrets.token_hex(16))")
GRANT_PATH="/tmp/claude-push-grant-${SID}-${NONCE}.json"
CURRENT_HEAD=$(git rev-parse HEAD)
CREATED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

python3 - <<PYEOF
import json
data = {
    "branch": "$BRANCH",
    "expected_head": "$CURRENT_HEAD",
    "remote": "origin",
    "nonce": "$NONCE",
    "sid": "$SID",
    "ppid": $$,
    "created_at": "$CREATED_AT",
}
with open("$GRANT_PATH", "w") as f:
    json.dump(data, f, indent=2)
PYEOF

# Step 8.6: Export env-var so guard sees the authorized context
export CLAUDE_PUSH_COMMAND_ACTIVE=1

# Step 9: Push to remote
echo "🌐 Pushing to remote..."
echo ""

# Check if upstream is set
UPSTREAM=$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null)

if [ -z "$UPSTREAM" ]; then
  # No upstream set, push with -u
  echo "Setting upstream to origin/$BRANCH..."
  git push -u origin "$BRANCH"
  PUSH_STATUS=$?
else
  # Upstream exists, normal push
  git push origin "$BRANCH"
  PUSH_STATUS=$?
fi

# Step 10: Handle push result
if [ $PUSH_STATUS -ne 0 ]; then
  echo ""
  echo -e "${RED}❌ Push failed${NC}"
  echo ""
  echo "Possible causes:"
  echo "  • Remote has changes you don't have (pull first)"
  echo "  • Network connectivity issues"
  echo "  • Authentication failure"
  echo ""
  echo "Suggestions:"
  echo "  • Pull first: git pull --rebase"
  echo "  • Check network connection"
  echo "  • Verify remote access: git remote -v"
  # AC-iter2-9: leave the grant in place on failure — operator may retry, and
  # the grant is nonce-bound so retries are safe.
  exit 1
fi

# AC-iter2-9: wrapper unlinks grant on success path (guard never fires on subprocess)
rm -f "$GRANT_PATH"

# Step 10.5: Append audit log line (AC-B6 / AC-AUDIT-1)
# Records every successful /push invocation for forensic review. Append-only.
# The grant file itself is unlinked by THIS WRAPPER on the success path above —
# PreToolUse hooks do not fire on subprocesses, so the guard cannot do it. This
# log is the durable record independent of grant-file lifecycle.
mkdir -p ~/.claude/logs
AUDIT_TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf '%s sid=%s command_kind=push branch=%s head=%s sentinel_nonce=%s ppid=%s\n' \
  "$AUDIT_TS" "$SID" "$BRANCH" "$CURRENT_HEAD" "$NONCE" "$$" \
  >> ~/.claude/logs/git-privilege-grants.log

# Step 11: Success summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Successfully pushed to origin/$BRANCH${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Get latest commit info
LATEST_COMMIT=$(git log -1 --oneline)
FILES_CHANGED=$(git diff --stat HEAD~1 HEAD 2>/dev/null | tail -n 1)

echo "Summary:"
echo "  • Branch: $BRANCH"
echo "  • Latest commit: $LATEST_COMMIT"
if [ -n "$FILES_CHANGED" ]; then
  echo "  • Changes: $FILES_CHANGED"
fi
echo ""

# Get remote URL
REMOTE_URL=$(git remote get-url origin 2>/dev/null)
if [ -n "$REMOTE_URL" ]; then
  echo "Remote: $REMOTE_URL"
  echo ""
fi

echo "Next steps:"
echo "  • View commit: git show HEAD"
echo "  • Check status: git status"
