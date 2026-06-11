#!/usr/bin/env bash
# overnight-git-env.sh — prepare the overnight actor's git PATH + env (M11/AC9).
#
# Builds a per-launch bin dir whose `git` is the MODERN-GIT SELECTOR (puts the
# pinned >=2.46 distribution first, else system git) and ALSO installs the
# SEPARATE policy shim. The selector dir is prepended to PATH ahead of system
# git, so the overnight actor's `git` resolves to harness-owned wrappers.
#
# It exports the overnight-actor markers the keystone + policy shim key on:
#   CLAUDE_OVERNIGHT_ACTOR=1
#   CLAUDE_OVERNIGHT_MAIN_ROOT=<main_root>
# and NEVER sets CLAUDE_GIT_BLESSED_TOKEN (the overnight env must not hold it).
#
# Usage (source it):  source overnight-git-env.sh --main-root <m> --worktree <w>
# Output (when not sourced): prints export lines to stdout.
# The selector is SEPARATE from the policy shim (codex round-2 #7): two files,
# so relaxing policy never drops the selector.

set -euo pipefail

MAIN_ROOT=""
WORKTREE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --main-root) MAIN_ROOT="$2"; shift 2 ;;
    --worktree) WORKTREE="$2"; shift 2 ;;
    *) shift ;;
  esac
done
[[ -n "$MAIN_ROOT" ]] || { echo "Error: --main-root required" >&2; exit 1; }

SRC_DIR="$(cd "$(dirname "$0")/overnight-git" && pwd)"
BIN_DIR="${CLAUDE_OVERNIGHT_GIT_BINDIR:-$MAIN_ROOT/.claude/overnight-git-bin}"
mkdir -p "$BIN_DIR"
# `git` on PATH == the SELECTOR (puts modern git first, else system git).
install -m 0755 "$SRC_DIR/git-selector" "$BIN_DIR/git"
# the policy shim is installed under its own name AND chained: the selector
# delegates to the real git; the shim enforces policy. We name the shim `git`
# inside a policy-prefixed dir so it runs FIRST, then delegates to the selector
# as its real git.
SHIM_DIR="${CLAUDE_OVERNIGHT_GIT_POLICY_BINDIR:-$MAIN_ROOT/.claude/overnight-git-policy-bin}"
mkdir -p "$SHIM_DIR"
install -m 0755 "$SRC_DIR/git-policy-shim" "$SHIM_DIR/git"

# Order on PATH: policy shim FIRST (enforces), then selector (modern git), then
# system. The shim's real-git is the selector (via CLAUDE_OVERNIGHT_REAL_GIT).
export CLAUDE_OVERNIGHT_ACTOR=1
export CLAUDE_OVERNIGHT_MAIN_ROOT="$MAIN_ROOT"
export CLAUDE_OVERNIGHT_REAL_GIT="$BIN_DIR/git"   # shim delegates to the selector
unset CLAUDE_GIT_BLESSED_TOKEN 2>/dev/null || true
export PATH="$SHIM_DIR:$BIN_DIR:$PATH"

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  # Not sourced: emit export lines for eval.
  echo "export CLAUDE_OVERNIGHT_ACTOR=1;"
  echo "export CLAUDE_OVERNIGHT_MAIN_ROOT=$MAIN_ROOT;"
  echo "export CLAUDE_OVERNIGHT_REAL_GIT=$BIN_DIR/git;"
  echo "unset CLAUDE_GIT_BLESSED_TOKEN;"
  echo "export PATH=$SHIM_DIR:$BIN_DIR:\$PATH;"
fi
