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
    echo "WORKTREE_PATH=${WORKTREE_PATH} WORKTREE_BRANCH=${BRANCH_NAME}"
    exit 0
fi

git worktree add -B "$BRANCH_NAME" "$WORKTREE_PATH" HEAD

echo "Created worktree from $(git rev-parse --short HEAD) at ${WORKTREE_PATH}" >&2
echo "WORKTREE_PATH=${WORKTREE_PATH} WORKTREE_BRANCH=${BRANCH_NAME}"
