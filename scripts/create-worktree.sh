#!/bin/bash
# Create a git worktree from local HEAD (not origin/main).
# Usage: bash ~/.claude/scripts/create-worktree.sh <name>
# Output (last line): WORKTREE_PATH=<path> WORKTREE_BRANCH=<branch>

set -euo pipefail

NAME="${1:?Usage: create-worktree.sh <name>}"
GIT_ROOT="$(git rev-parse --show-toplevel)"
BRANCH_NAME="worktree-${NAME}"
WORKTREE_PATH="${GIT_ROOT}/.claude/worktrees/${NAME}"

mkdir -p "$(dirname "$WORKTREE_PATH")"

if [ -d "$WORKTREE_PATH" ]; then
    echo "Worktree already exists at ${WORKTREE_PATH}" >&2
else
    git worktree add -B "$BRANCH_NAME" "$WORKTREE_PATH" HEAD
    echo "Created worktree from $(git rev-parse --short HEAD) at ${WORKTREE_PATH}" >&2
fi

# Auto-renew parent .claude/settings.local.json Write/Edit allow entries for the
# current overnight worktree. Safety boundary is enforced by the overnight hook
# (pretool-overnight-hook-guard.py); these allow entries only skip permission
# prompts inside the worktree. Without renewal, stale overnight-<oldhash> paths
# cause every Write/Edit in the new worktree to hit a prompt.
if [[ "$NAME" == overnight-* ]] && command -v jq >/dev/null 2>&1; then
    SETTINGS="${GIT_ROOT}/.claude/settings.local.json"
    if [ -f "$SETTINGS" ]; then
        WORKTREE_BASE="${GIT_ROOT}/.claude/worktrees/overnight-"
        NEW_WRITE="Write(${WORKTREE_PATH}/**)"
        NEW_EDIT="Edit(${WORKTREE_PATH}/**)"
        TMP="$(mktemp)"
        if jq \
            --arg base "$WORKTREE_BASE" \
            --arg newW "$NEW_WRITE" \
            --arg newE "$NEW_EDIT" '
            .permissions //= {} |
            .permissions.allow //= [] |
            .permissions.allow |= (
                map(select(
                    (startswith("Write(" + $base) | not) and
                    (startswith("Edit("  + $base) | not)
                )) + [$newW, $newE]
            )
        ' "$SETTINGS" > "$TMP" 2>/dev/null; then
            mv "$TMP" "$SETTINGS"
            echo "Refreshed ${SETTINGS} allow entries for ${WORKTREE_PATH}" >&2
        else
            rm -f "$TMP"
            echo "WARN: failed to refresh ${SETTINGS}; keeping existing entries" >&2
        fi
    fi
fi

echo "WORKTREE_PATH=${WORKTREE_PATH} WORKTREE_BRANCH=${BRANCH_NAME}"
