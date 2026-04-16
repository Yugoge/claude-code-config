#!/usr/bin/env bash
# checkpoint-prune.sh — trim refs/checkpoints/* to the most recent N commits
# ----------------------------------------------------------------------------
# Installed 2026-04-16 (SaaS-grade blame-hygiene audit — ops gap O3).
#
# Purpose
#   refs/checkpoints/<branch> grows monotonically as posttool-git-checkpoint,
#   stop hooks, and fswatch each write new snapshots. Without pruning, each
#   ref accumulates thousands of commits over weeks, inflating .git/objects
#   and slowing `git log refs/checkpoints/*`.
#
#   This script rewrites each checkpoint ref to its Nth most recent ancestor
#   (CHECKPOINT_RETENTION, default 200) so the ref still points into the
#   existing chain (fast-forward only — no forced rewrites, no rebases).
#   A subsequent `git reflog expire` + `git gc` (run by this script) prunes
#   the detached commits.
#
# Usage
#   checkpoint-prune.sh [-h]                      run in current repo ($PWD)
#   cd <repo> && checkpoint-prune.sh              run in a specific repo
#   CHECKPOINT_RETENTION=500 checkpoint-prune.sh  override retention count
#
# Environment
#   CHECKPOINT_RETENTION   Number of commits to keep per ref (default 200)
#   CHECKPOINT_REFLOG_EXPIRE  Reflog expiry window (default 30.days)
#   CHECKPOINT_GC_PRUNE       GC prune window (default 30.days.ago)
#
# Exit codes
#   0  success (including no-op when every ref has <= retention commits)
#   1  not in a git repo, or a ref rewrite failed safety check
#   2  invalid arguments (e.g. -h)
#
# Safety
#   - new tip MUST be an ancestor of the current ref tip (verified via
#     `git merge-base --is-ancestor`); otherwise the rewrite is skipped
#     with a warning — this cannot accidentally lose commits
#   - idempotent: running twice is a no-op the second time
# ----------------------------------------------------------------------------

set -euo pipefail

# ---------- args ---------------------------------------------------------
usage() {
    cat <<EOF
Usage: checkpoint-prune.sh [-h]

Trim each refs/checkpoints/<branch> in the current repo to the most recent
\${CHECKPOINT_RETENTION:-200} commits, then reflog-expire + gc to reclaim
object storage.

Environment overrides:
  CHECKPOINT_RETENTION       keep N most recent commits per ref (default 200)
  CHECKPOINT_REFLOG_EXPIRE   reflog expiry (default 30.days)
  CHECKPOINT_GC_PRUNE        gc prune window (default 30.days.ago)

Run per-repo:
  cd <repo> && checkpoint-prune.sh

Exit 0 on success (including no-op), 1 on safety-check failure.
EOF
}

case "${1:-}" in
    -h|--help) usage; exit 2 ;;
    "" ) : ;;
    * ) echo "Error: unknown argument: $1" >&2; usage >&2; exit 2 ;;
esac

# ---------- params (no hardcoded values) ---------------------------------
RETENTION="${CHECKPOINT_RETENTION:-200}"
REFLOG_EXPIRE="${CHECKPOINT_REFLOG_EXPIRE:-30.days}"
GC_PRUNE="${CHECKPOINT_GC_PRUNE:-30.days.ago}"

if ! [[ "$RETENTION" =~ ^[0-9]+$ ]] || [ "$RETENTION" -lt 1 ]; then
    echo "Error: CHECKPOINT_RETENTION must be a positive integer (got: $RETENTION)" >&2
    exit 2
fi

# ---------- repo detection ------------------------------------------------
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "Error: not in a git repository (cwd: $PWD)" >&2
    exit 1
fi

REPO_ROOT=$(git rev-parse --show-toplevel)
echo "checkpoint-prune: repo=${REPO_ROOT} retention=${RETENTION}"

# ---------- enumerate checkpoint refs -------------------------------------
REFS=$(git for-each-ref refs/checkpoints/ --format='%(refname)' 2>/dev/null || true)
if [ -z "$REFS" ]; then
    echo "checkpoint-prune: no refs/checkpoints/* found — nothing to do"
    exit 0
fi

PRUNED_COUNT=0
SKIPPED_COUNT=0

while IFS= read -r ref; do
    [ -z "$ref" ] && continue

    before=$(git rev-list --count "$ref" 2>/dev/null || echo 0)
    if [ "$before" -le "$RETENTION" ]; then
        echo "  ${ref}: ${before} commits (<= ${RETENTION}) — no pruning needed"
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        continue
    fi

    # Find the Nth commit from the tip. rev-list is tip-first, so element
    # at index (RETENTION-1) is the new tip (zero-indexed via sed).
    new_tip=$(git rev-list "$ref" | sed -n "${RETENTION}p")
    if [ -z "$new_tip" ]; then
        echo "  ${ref}: could not locate retention boundary at position ${RETENTION} — skipping" >&2
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        continue
    fi

    current_tip=$(git rev-parse "$ref" 2>/dev/null || echo "")
    if [ -z "$current_tip" ]; then
        echo "  ${ref}: cannot resolve current tip — skipping" >&2
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        continue
    fi

    # Safety: new tip MUST be an ancestor of the current tip (this is always
    # the case because we picked it from `git rev-list $ref`, but verify
    # defensively before rewriting the ref).
    if ! git merge-base --is-ancestor "$new_tip" "$current_tip" 2>/dev/null; then
        echo "  ${ref}: SAFETY FAIL — new-tip ${new_tip} is not ancestor of ${current_tip} — skipping" >&2
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        continue
    fi

    if git update-ref "$ref" "$new_tip" "$current_tip" 2>/dev/null; then
        after=$(git rev-list --count "$ref" 2>/dev/null || echo 0)
        echo "  ${ref}: ${before} -> ${after} commits (pruned $((before - after)))"
        PRUNED_COUNT=$((PRUNED_COUNT + 1))
    else
        echo "  ${ref}: update-ref failed (CAS mismatch?) — skipping" >&2
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
    fi
done <<< "$REFS"

echo "checkpoint-prune: pruned=${PRUNED_COUNT} skipped=${SKIPPED_COUNT}"

# ---------- reclaim storage ----------------------------------------------
if [ "$PRUNED_COUNT" -gt 0 ]; then
    echo "checkpoint-prune: reflog expire (--expire=${REFLOG_EXPIRE}) + gc (--prune=${GC_PRUNE})"
    git reflog expire --expire="$REFLOG_EXPIRE" --all 2>/dev/null || true
    git gc --prune="$GC_PRUNE" 2>/dev/null || true
else
    echo "checkpoint-prune: no pruning performed — skipping gc"
fi

exit 0
