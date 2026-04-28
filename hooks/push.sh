#!/bin/bash
# push.sh - Executable version of /push command
# Location: ~/.claude/hooks/push.sh
# Usage: bash ~/.claude/hooks/push.sh [<remote>] [--auto]
#
# Args:
#   <remote>  Optional remote name (default: "origin"). Forwarded into
#             the Scheme 6 grant manifest's "remote" field AND the
#             `git push <remote> <branch>` invocation. The privilege-guard
#             (_validate_push_grant_remote) requires the command's remote
#             token to match grant.remote, so passing a remote here keeps
#             both sides aligned. Useful for fork-based workflows where
#             `origin` points at upstream (no write access) and a separate
#             remote (e.g., `fork`) points at the user's writable fork.
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

# Parse args: optional [<remote>], [--auto], [--force-with-lease], [--delete <branch>]
# Default remote: prefer "fork" if configured locally (typical fork-based workflow),
# else fall back to "origin". Explicit /push <remote> overrides via the case below.
if git remote get-url fork >/dev/null 2>&1; then
  REMOTE="fork"
else
  REMOTE="origin"
fi
AUTO_MODE=0
FORCE_WITH_LEASE=0
DELETE_MODE=0
DELETE_BRANCH=""
while [ $# -gt 0 ]; do
  case "$1" in
    --auto) AUTO_MODE=1 ;;
    --force-with-lease)
      # Force-replace remote branch IF its tip is what we expect (i.e., we have its
      # current state fetched and visible). Refuses when remote moved beyond our
      # last fetch — strictly safer than `--force` which clobbers unconditionally.
      # The privilege-guard's _extract_push_remote skips flags (anything starting
      # with `-`), so this flag is invisible to the remote-binding check; env-var
      # + grant-manifest validation still runs unchanged.
      FORCE_WITH_LEASE=1
      ;;
    --delete)
      # Delete a remote branch. The next positional arg is the branch name on the remote.
      # Skips the working-tree status report, ahead-count check, and grant-manifest's
      # head-binding (the manifest still binds remote+ppid+sid+nonce; head is set to
      # the branch tip we observed locally for audit-trail completeness).
      DELETE_MODE=1
      shift
      DELETE_BRANCH="$1"
      if [ -z "$DELETE_BRANCH" ] || [ "${DELETE_BRANCH:0:1}" = "-" ]; then
        echo -e "${RED}❌ --delete requires a remote branch name as the next positional argument${NC}" >&2
        echo "Usage: bash ~/.claude/hooks/push.sh [<remote>] --delete <branch-name>" >&2
        exit 2
      fi
      ;;
    -*)
      echo -e "${RED}❌ Unknown flag: $1${NC}" >&2
      echo "Usage: bash ~/.claude/hooks/push.sh [<remote>] [--auto] [--force-with-lease] [--delete <branch>]" >&2
      exit 2
      ;;
    *) REMOTE="$1" ;;
  esac
  shift
done

# --force-with-lease and --delete are mutually exclusive
if [ "$FORCE_WITH_LEASE" = "1" ] && [ "$DELETE_MODE" = "1" ]; then
  echo -e "${RED}❌ --force-with-lease and --delete are mutually exclusive${NC}" >&2
  exit 2
fi
# Non-interactive stdin also engages auto-mode regardless of explicit flag
if [ ! -t 0 ]; then
  AUTO_MODE=1
fi

# Validate remote exists locally before continuing — fail fast with a helpful
# message instead of producing a broken grant + cryptic git push error.
if ! git remote get-url "$REMOTE" >/dev/null 2>&1; then
  echo -e "${RED}❌ Error: remote '$REMOTE' not found.${NC}" >&2
  echo "Configured remotes:" >&2
  git remote -v | sed 's/^/   /' >&2
  echo "" >&2
  echo "Configure with: git remote add $REMOTE <url>" >&2
  exit 1
fi

echo -e "${BLUE}🚀 Starting validated push...${NC}"
if [ "$AUTO_MODE" = "1" ]; then
  echo -e "${CYAN}(Non-interactive mode)${NC}"
fi
echo ""

# Delete-mode short-circuit: skip the working-tree report, ahead-count, and head-binding.
# We still emit a grant manifest (for audit + privilege-guard match) but use the deleted
# branch name as the manifest "branch" so the guard's remote-binding check passes.
if [ "$DELETE_MODE" = "1" ]; then
  echo -e "${CYAN}Delete mode: $REMOTE/$DELETE_BRANCH${NC}"
  echo ""
  SID="${CLAUDE_SESSION_ID:-default}"
  NONCE=$(python3 -c "import secrets; print(secrets.token_hex(16))")
  GRANT_PATH="/tmp/claude-push-grant-${SID}-${NONCE}.json"
  CREATED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  # For delete we don't have a meaningful HEAD — record the soon-to-be-deleted ref's tip on remote
  # if knowable, else "0000000000000000000000000000000000000000" (git's null sha for delete refspec).
  CURRENT_HEAD=$(git rev-parse "$REMOTE/$DELETE_BRANCH" 2>/dev/null || echo "0000000000000000000000000000000000000000")
  python3 - <<PYEOF
import json
data = {
    "branch": "$DELETE_BRANCH",
    "expected_head": "$CURRENT_HEAD",
    "remote": "$REMOTE",
    "nonce": "$NONCE",
    "sid": "$SID",
    "ppid": $$,
    "created_at": "$CREATED_AT",
    "mode": "delete",
}
with open("$GRANT_PATH", "w") as f:
    json.dump(data, f, indent=2)
PYEOF
  export CLAUDE_PUSH_COMMAND_ACTIVE=1
  echo "🗑️  Deleting $REMOTE/$DELETE_BRANCH..."
  echo ""
  git push "$REMOTE" --delete "$DELETE_BRANCH"
  PUSH_STATUS=$?
  if [ $PUSH_STATUS -ne 0 ]; then
    echo ""
    echo -e "${RED}❌ Delete push failed${NC}"
    exit 1
  fi
  rm -f "$GRANT_PATH"
  mkdir -p ~/.claude/logs
  AUDIT_TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  printf '%s sid=%s command_kind=push remote=%s branch=%s head=%s sentinel_nonce=%s ppid=%s mode=delete\n' \
    "$AUDIT_TS" "$SID" "$REMOTE" "$DELETE_BRANCH" "$CURRENT_HEAD" "$NONCE" "$$" \
    >> ~/.claude/logs/git-privilege-grants.log
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo -e "${GREEN}✅ Successfully deleted $REMOTE/$DELETE_BRANCH${NC}"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  exit 0
fi

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
#
# Two distinct cases must be handled:
#   (a) Branch HAS an upstream: ahead-count comes from `@{u}..HEAD`.
#   (b) Branch has NO upstream yet (first push of a new local branch): the entire branch
#       counts as "to push" — git push -u <REMOTE> <BRANCH> will publish it. We must NOT
#       exit early just because @{u} is unresolvable.
#
# Earlier versions used `git rev-list --count @{u}..HEAD 2>/dev/null || echo "0"` which
# silently coerced the no-upstream case to "0 ahead" and exited "Nothing to push". That
# blocked legitimate first-push flows for branches like cycle6-fixes-* pushed to fork.
if [ "$STAGED_COUNT" = "0" ]; then
  HAS_UPSTREAM=$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null)
  if [ -z "$HAS_UPSTREAM" ]; then
    # Case (b): no upstream → first-push flow is the right path. Fall through to step 9.
    BRANCH_COMMIT_COUNT=$(git rev-list --count HEAD 2>/dev/null || echo "0")
    if [ "$BRANCH_COMMIT_COUNT" = "0" ] || [ -z "$BRANCH_COMMIT_COUNT" ]; then
      echo "Nothing to push (branch has zero commits)."
      echo ""
      exit 0
    fi
    echo "Working tree clean. Branch '$BRANCH' has no upstream yet — first-push flow ($BRANCH_COMMIT_COUNT commit(s) total) will set upstream to $REMOTE/$BRANCH."
    echo ""
  else
    # Case (a): upstream exists, normal ahead-count check.
    COMMITS_AHEAD=$(git rev-list --count @{u}..HEAD 2>/dev/null || echo "0")
    if [ "$COMMITS_AHEAD" != "0" ] && [ -n "$COMMITS_AHEAD" ]; then
      echo "Working tree clean. $COMMITS_AHEAD commit(s) ahead of remote — proceeding with push."
      echo ""
    else
      echo "Nothing to push (working tree clean, no commits ahead of remote)."
      echo ""
      exit 0
    fi
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
    "remote": "$REMOTE",
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
echo "🌐 Pushing to $REMOTE..."
echo ""

# Check if upstream is set
UPSTREAM=$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null)

if [ -z "$UPSTREAM" ]; then
  # No upstream set, push with -u
  echo "Setting upstream to $REMOTE/$BRANCH..."
  if [ "$FORCE_WITH_LEASE" = "1" ]; then
    echo -e "${YELLOW}⚠  --force-with-lease engaged on first push (refuses if remote ref already exists with diverging tip).${NC}"
    git push --force-with-lease -u "$REMOTE" "$BRANCH"
  else
    git push -u "$REMOTE" "$BRANCH"
  fi
  PUSH_STATUS=$?
else
  # Upstream exists, normal push
  if [ "$FORCE_WITH_LEASE" = "1" ]; then
    echo -e "${YELLOW}⚠  --force-with-lease engaged: remote ref will be replaced if its tip matches our last-fetched value.${NC}"
    git push --force-with-lease "$REMOTE" "$BRANCH"
  else
    git push "$REMOTE" "$BRANCH"
  fi
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
printf '%s sid=%s command_kind=push remote=%s branch=%s head=%s sentinel_nonce=%s ppid=%s\n' \
  "$AUDIT_TS" "$SID" "$REMOTE" "$BRANCH" "$CURRENT_HEAD" "$NONCE" "$$" \
  >> ~/.claude/logs/git-privilege-grants.log

# Step 11: Success summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Successfully pushed to $REMOTE/$BRANCH${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Get latest commit info
LATEST_COMMIT=$(git log -1 --oneline)
FILES_CHANGED=$(git diff --stat HEAD~1 HEAD 2>/dev/null | tail -n 1)

echo "Summary:"
echo "  • Remote: $REMOTE"
echo "  • Branch: $BRANCH"
echo "  • Latest commit: $LATEST_COMMIT"
if [ -n "$FILES_CHANGED" ]; then
  echo "  • Changes: $FILES_CHANGED"
fi
echo ""

# Get remote URL
REMOTE_URL=$(git remote get-url "$REMOTE" 2>/dev/null)
if [ -n "$REMOTE_URL" ]; then
  echo "Remote URL: $REMOTE_URL"
  echo ""
fi

echo "Next steps:"
echo "  • View commit: git show HEAD"
echo "  • Check status: git status"
