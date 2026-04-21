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
FAILED_COUNT=0

# rebuild_ref <ref>
#   Rewrite the named ref so its chain is exactly RETENTION commits long,
#   keeping the NEWEST RETENTION commits (by topo order from the current tip).
#   Echoes the new tip SHA on stdout; returns non-zero on any rebuild error.
rebuild_ref() {
    local ref="$1"
    local current_tip
    current_tip=$(git rev-parse "$ref")

    # Collect the newest RETENTION commits (rev-list is tip-first).
    local commits
    commits=$(git rev-list --topo-order "$ref" | head -n "$RETENTION")
    local got
    got=$(printf '%s\n' "$commits" | grep -c '^[0-9a-f]' || true)
    if [ "$got" -lt "$RETENTION" ]; then
        echo "Error: expected ${RETENTION} commits, rev-list produced ${got}" >&2
        return 1
    fi

    # Reverse so we walk oldest-kept -> newest (tip). Use awk for portability
    # (tac is GNU-only on some platforms).
    local reversed
    reversed=$(printf '%s\n' "$commits" | awk '{a[NR]=$0} END{for(i=NR;i>=1;i--) print a[i]}')

    local msg_file
    msg_file=$(mktemp)
    # shellcheck disable=SC2064
    trap "rm -f '$msg_file'" RETURN

    local new_parent=""
    local new_tip=""
    local c tree author_name author_email author_date committer_name committer_email committer_date
    while IFS= read -r c; do
        [ -z "$c" ] && continue
        tree=$(git rev-parse "${c}^{tree}")
        git log -1 --format='%B' "$c" >"$msg_file"
        author_name=$(git log -1 --format='%an' "$c")
        author_email=$(git log -1 --format='%ae' "$c")
        author_date=$(git log -1 --format='%aI' "$c")
        committer_name=$(git log -1 --format='%cn' "$c")
        committer_email=$(git log -1 --format='%ce' "$c")
        committer_date=$(git log -1 --format='%cI' "$c")

        if [ -z "$new_parent" ]; then
            # Oldest-kept commit becomes the parentless root of the new chain.
            new_tip=$(
                GIT_AUTHOR_NAME="$author_name" \
                GIT_AUTHOR_EMAIL="$author_email" \
                GIT_AUTHOR_DATE="$author_date" \
                GIT_COMMITTER_NAME="$committer_name" \
                GIT_COMMITTER_EMAIL="$committer_email" \
                GIT_COMMITTER_DATE="$committer_date" \
                git commit-tree "$tree" -F "$msg_file"
            )
        else
            new_tip=$(
                GIT_AUTHOR_NAME="$author_name" \
                GIT_AUTHOR_EMAIL="$author_email" \
                GIT_AUTHOR_DATE="$author_date" \
                GIT_COMMITTER_NAME="$committer_name" \
                GIT_COMMITTER_EMAIL="$committer_email" \
                GIT_COMMITTER_DATE="$committer_date" \
                git commit-tree "$tree" -p "$new_parent" -F "$msg_file"
            )
        fi
        new_parent="$new_tip"
    done <<< "$reversed"

    if [ -z "$new_tip" ]; then
        echo "Error: rebuild produced empty new_tip for ${ref}" >&2
        return 1
    fi

    # Sanity: rewritten tip must carry the same tree as the original tip.
    local orig_tree new_tree
    orig_tree=$(git rev-parse "${current_tip}^{tree}")
    new_tree=$(git rev-parse "${new_tip}^{tree}")
    if [ "$orig_tree" != "$new_tree" ]; then
        echo "Error: tree mismatch after rebuild (orig=${orig_tree} new=${new_tree})" >&2
        return 1
    fi

    # CAS update-ref — aborts if a concurrent writer has advanced the ref
    # since we snapshotted current_tip.
    if ! git update-ref "$ref" "$new_tip" "$current_tip"; then
        echo "Error: update-ref failed for ${ref} (CAS mismatch?)" >&2
        return 1
    fi

    printf '%s\n' "$new_tip"
    return 0
}

while IFS= read -r ref; do
    [ -z "$ref" ] && continue

    before=$(git rev-list --count "$ref" 2>/dev/null || echo 0)
    if [ "$before" -le "$RETENTION" ]; then
        echo "  ${ref}: ${before} commits (<= ${RETENTION}) — no pruning needed"
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        continue
    fi

    if new_tip=$(rebuild_ref "$ref"); then
        after=$(git rev-list --count "$ref" 2>/dev/null || echo 0)
        echo "  ${ref}: ${before} -> ${after} commits (rewrote chain, new tip ${new_tip:0:12})"
        PRUNED_COUNT=$((PRUNED_COUNT + 1))
    else
        echo "  ${ref}: rebuild failed — leaving ref unchanged" >&2
        FAILED_COUNT=$((FAILED_COUNT + 1))
    fi
done <<< "$REFS"

echo "checkpoint-prune: pruned=${PRUNED_COUNT} skipped=${SKIPPED_COUNT} failed=${FAILED_COUNT}"

# ---------- reclaim storage ----------------------------------------------
if [ "$PRUNED_COUNT" -gt 0 ]; then
    echo "checkpoint-prune: reflog expire (--expire=${REFLOG_EXPIRE}) + gc (--prune=${GC_PRUNE})"
    git reflog expire --expire="$REFLOG_EXPIRE" --all 2>/dev/null || true
    git gc --prune="$GC_PRUNE" 2>/dev/null || true
else
    echo "checkpoint-prune: no pruning performed — skipping gc"
fi

if [ "$FAILED_COUNT" -gt 0 ]; then
    exit 1
fi
exit 0
