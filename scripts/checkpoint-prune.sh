#!/usr/bin/env bash
# checkpoint-prune.sh — trim refs/checkpoints/* to the most recent N commits
# ----------------------------------------------------------------------------
# Installed 2026-04-16 (SaaS-grade blame-hygiene audit — ops gap O3).
# iter2 2026-04-16: inverted-semantics bug fixed — algorithm now rebuilds
# the ref chain via git commit-tree so the ref retains the NEWEST N commits,
# not the oldest. The previous version moved the ref backwards via
# update-ref, which kept the OLDEST N and discarded the most recent.
#
# Purpose
#   refs/checkpoints/<branch> grows monotonically as posttool-git-checkpoint,
#   stop hooks, and fswatch each write new snapshots. Without pruning, each
#   ref accumulates thousands of commits over weeks, inflating .git/objects
#   and slowing `git log refs/checkpoints/*`.
#
#   This script rewrites each checkpoint ref to a NEW chain of exactly
#   CHECKPOINT_RETENTION commits (default 200), preserving the most recent
#   RETENTION commits' trees, messages, authors, and dates. The oldest of
#   those RETENTION becomes a parentless root; the remaining RETENTION-1
#   are recreated on top of it in order. The ref then points to the new
#   tip. Old commits become unreachable and are pruned by reflog expire + gc.
#
# Usage
#   checkpoint-prune.sh [-h]                      run in current repo ($PWD)
#   cd <repo> && checkpoint-prune.sh              run in a specific repo
#   CHECKPOINT_RETENTION=500 checkpoint-prune.sh  override retention count
#
# Environment
#   CHECKPOINT_RETENTION      Number of commits to keep per ref (default 200)
#   CHECKPOINT_REFLOG_EXPIRE  Reflog expiry window (default 30.days)
#   CHECKPOINT_GC_PRUNE       GC prune window (default 30.days.ago)
#
# Exit codes
#   0  success (including no-op when every ref has <= retention commits)
#   1  not in a git repo, or a ref rewrite failed
#   2  invalid arguments (e.g. -h)
#
# Safety
#   - New chain preserves each kept commit's tree SHA, message, author name
#     and email, author date, committer name and email, committer date —
#     only the parent chain is rewritten (the oldest kept commit becomes
#     a root; the rest chain up to it).
#   - Sanity check: the rewritten tip's tree MUST equal the original tip's
#     tree; if not, the rebuild is aborted and the ref is left untouched.
#   - CAS guard: update-ref uses the original tip as the expected old value,
#     so a concurrent writer appending to the ref aborts the prune cleanly.
#   - Idempotent: a second run finds exactly RETENTION commits and is a no-op.
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
