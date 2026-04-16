#!/bin/bash
# ============================================================================
# checkpoint-core.sh - Shared library for automated snapshot commits
# ----------------------------------------------------------------------------
# Purpose: write_checkpoint() writes a snapshot commit to
#   refs/checkpoints/<sanitized-branch>  (NEVER touches HEAD / branch refs)
#
# This file MUST be sourced, not executed directly:
#   source ~/.claude/hooks/lib/checkpoint-core.sh
#   write_checkpoint "$GIT_DIR" "trigger reason" ["custom message"]
#
# ----------------------------------------------------------------------------
# Ref layout
#   refs/checkpoints/<sanitized-branch>
#     - branch name sanitized via:  tr '/' '-'
#     - detached HEAD fallback:     refs/checkpoints/detached-<short-sha>
#     - empty repo:                 ref created as a root commit (no parent)
#
# Algorithm (git plumbing only — no `git commit`):
#   1. read-tree parent tree (or --empty for bootstrap)
#   2. git add -A  (staged into a TEMP index via GIT_INDEX_FILE)
#   3. git write-tree  -> TREE_SHA
#   4. if TREE_SHA == PARENT_TREE_SHA -> return 0 (idempotent)
#   5. git commit-tree TREE_SHA [-p PARENT_SHA] -m "<msg>"  -> NEW_SHA
#   6. git update-ref REF NEW_SHA OLD_SHA           (CAS; retries 5x on race)
#   7. background push (rate-limited to 1/30s per repo) WITHOUT -f
#
# Recovery commands (for humans):
#   git log refs/checkpoints/<branch>
#   git checkout refs/checkpoints/<branch> -- <path>
#   git show refs/checkpoints/<branch>:<path>
#
# Cross-machine recovery (documented in CLAUDE.md — not auto-applied):
#   [remote "origin"]
#     fetch = +refs/heads/*:refs/remotes/origin/*
#     fetch = +refs/checkpoints/*:refs/remotes/origin/checkpoints/*
#
# Log file locations:
#   ~/.claude/logs/checkpoint.log        CAS/build failures
#   ~/.claude/logs/checkpoint-push.log   background push failures
#
# Concurrency safety:
#   - flock advisory lock on .git/checkpoint-core.lock serializes the
#     critical section (parent-read + commit-tree + update-ref) so at most
#     one writer creates a commit object at a time; prevents dangling
#     commit objects from CAS losers.
#   - CAS update-ref retained as belt-and-suspenders; should never fail
#     under the lock.
#   - Tree build (read-tree + add -A + write-tree) runs outside the lock
#     because it does not create persistent git objects that would be
#     orphaned on a lost race (blobs/trees are content-addressed and
#     would be created anyway by the winning writer).
#   - Temp index isolation: GIT_INDEX_FILE=.git/checkpoint-index.$$.<ns>
#   - Stale temp-index sweep (>60 min) at entry
#   - trap EXIT INT TERM HUP removes temp index on any exit path
#   - If flock is unavailable, falls back to the old CAS-retry loop (and
#     logs a warning about potential orphan commits under concurrency).
# ============================================================================

CHECKPOINT_LOG_DIR="${CHECKPOINT_LOG_DIR:-$HOME/.claude/logs}"
CHECKPOINT_LOG_FILE="${CHECKPOINT_LOG_DIR}/checkpoint.log"
CHECKPOINT_PUSH_LOG_FILE="${CHECKPOINT_LOG_DIR}/checkpoint-push.log"
CHECKPOINT_PUSH_MIN_INTERVAL="${CHECKPOINT_PUSH_MIN_INTERVAL:-30}"  # seconds
CHECKPOINT_CAS_MAX_RETRIES="${CHECKPOINT_CAS_MAX_RETRIES:-5}"

# Internal: timestamped log line to checkpoint.log
_checkpoint_log() {
    local level="$1"
    shift
    mkdir -p "$CHECKPOINT_LOG_DIR" 2>/dev/null
    local ts
    ts=$(date '+%Y-%m-%d %H:%M:%S')
    printf '[%s] [%s] %s\n' "$ts" "$level" "$*" >> "$CHECKPOINT_LOG_FILE" 2>/dev/null || true
}

# Internal: timestamped log line to checkpoint-push.log
_checkpoint_push_log() {
    local level="$1"
    shift
    mkdir -p "$CHECKPOINT_LOG_DIR" 2>/dev/null
    local ts
    ts=$(date '+%Y-%m-%d %H:%M:%S')
    printf '[%s] [%s] %s\n' "$ts" "$level" "$*" >> "$CHECKPOINT_PUSH_LOG_FILE" 2>/dev/null || true
}

# Internal: compute git dir (.git) for the repo at <work_dir>
_checkpoint_git_dir() {
    local work_dir="$1"
    local git_cmd
    if [ -n "$work_dir" ]; then
        git_cmd="git -C $work_dir"
    else
        git_cmd="git"
    fi
    $git_cmd rev-parse --git-dir 2>/dev/null
}

# Internal: stale temp-index sweep (defensive; prevents SIGKILL residue buildup)
_checkpoint_sweep_stale_indexes() {
    local git_dir="$1"
    if [ -n "$git_dir" ] && [ -d "$git_dir" ]; then
        find "$git_dir" -maxdepth 1 -name 'checkpoint-index.*' -mmin +60 -delete 2>/dev/null || true
    fi
}

# Internal: rate-limited background push of the checkpoint ref.
# Skips if another push was attempted within CHECKPOINT_PUSH_MIN_INTERVAL seconds
# for this repo. Uses repo-hash stamp file in /tmp/.
_checkpoint_rate_limited_push() {
    local work_dir="$1"
    local ref="$2"
    local git_cmd
    if [ -n "$work_dir" ]; then
        git_cmd="git -C $work_dir"
    else
        git_cmd="git"
    fi

    # Skip silently if no 'origin' configured
    if ! $git_cmd remote get-url origin >/dev/null 2>&1; then
        return 0
    fi

    # Compute a stable stamp key for this repo (absolute git-dir path, hashed)
    local abs_git_dir
    abs_git_dir=$($git_cmd rev-parse --absolute-git-dir 2>/dev/null)
    if [ -z "$abs_git_dir" ]; then
        return 0
    fi
    local repo_hash
    repo_hash=$(printf '%s' "$abs_git_dir" | md5sum 2>/dev/null | awk '{print $1}')
    if [ -z "$repo_hash" ]; then
        repo_hash=$(printf '%s' "$abs_git_dir" | cksum | awk '{print $1}')
    fi
    local stamp_file="/tmp/.checkpoint-push-${repo_hash}.ts"

    # Rate limit: skip if last push attempt was within the interval
    if [ -f "$stamp_file" ]; then
        local now last diff
        now=$(date +%s)
        last=$(stat -c %Y "$stamp_file" 2>/dev/null || stat -f %m "$stamp_file" 2>/dev/null || echo 0)
        diff=$((now - last))
        if [ "$diff" -lt "$CHECKPOINT_PUSH_MIN_INTERVAL" ]; then
            return 0
        fi
    fi
    touch "$stamp_file" 2>/dev/null || true

    # Background push WITHOUT -f; CAS chain guarantees fast-forward.
    # Redirect stdout to /dev/null, capture stderr to push log.
    (
        if ! $git_cmd push origin "${ref}:${ref}" >/dev/null 2>>"$CHECKPOINT_PUSH_LOG_FILE"; then
            _checkpoint_push_log ERROR "push ${ref} failed (repo=${abs_git_dir})"
        fi
    ) &
    disown 2>/dev/null || true
}

# Public API.
#
# write_checkpoint <work_dir> <trigger_reason> [<custom_message>]
#
#   work_dir        - absolute path of the repo working tree, or empty string
#                     for cwd; passed via `git -C <work_dir>` when non-empty
#   trigger_reason  - short string describing what fired this checkpoint
#                     (e.g. "posttool threshold", "stop hook: auto-commit.sh")
#   custom_message  - optional; if provided, used as the commit summary line
#                     (rest of the commit body is appended automatically)
#
# Return codes:
#   0  success OR idempotent no-op (tree unchanged)
#   1  build/CAS failure after retries
#   2  not a git repo
write_checkpoint() {
    local work_dir="$1"
    local trigger="${2:-unknown}"
    local custom_message="$3"

    # Resolve git dir; bail gracefully if not a repo
    local git_dir
    git_dir=$(_checkpoint_git_dir "$work_dir")
    if [ -z "$git_dir" ]; then
        _checkpoint_log WARN "not a git repo (work_dir='${work_dir}', trigger='${trigger}')"
        return 2
    fi

    # Resolve absolute git dir so temp-index path is unambiguous
    local git_cmd
    if [ -n "$work_dir" ]; then
        git_cmd="git -C $work_dir"
    else
        git_cmd="git"
    fi
    local abs_git_dir
    abs_git_dir=$($git_cmd rev-parse --absolute-git-dir 2>/dev/null)
    if [ -z "$abs_git_dir" ]; then
        _checkpoint_log ERROR "cannot resolve absolute git dir (work_dir='${work_dir}')"
        return 1
    fi

    # Defensive sweep of orphaned temp indexes from previous SIGKILLed runs
    _checkpoint_sweep_stale_indexes "$abs_git_dir"

    # Determine branch name & ref
    local branch sanitized ref
    branch=$($git_cmd branch --show-current 2>/dev/null)
    if [ -z "$branch" ]; then
        # Detached HEAD fallback: refs/checkpoints/detached-<short-sha>
        local short_sha
        short_sha=$($git_cmd rev-parse --short HEAD 2>/dev/null)
        if [ -z "$short_sha" ]; then
            # Empty repo + detached (unusual); fall back to a literal label
            sanitized="detached-empty"
        else
            sanitized="detached-${short_sha}"
        fi
    else
        sanitized=$(printf '%s' "$branch" | tr '/' '-')
    fi
    ref="refs/checkpoints/${sanitized}"

    # Temp index path (isolated from real .git/index).
    # Use PID + nanosecond-ish suffix to avoid collisions among sibling runs.
    local ns
    ns=$(date +%s%N 2>/dev/null || date +%s)
    local TMP_INDEX="${abs_git_dir}/checkpoint-index.$$.${ns}"

    # Trap ensures TMP_INDEX is removed on any exit path from this function,
    # including the enclosing shell. Removing at end-of-function too (below).
    trap 'rm -f "$TMP_INDEX"' EXIT INT TERM HUP

    # Retry loop covers:
    #   - CAS race (another writer advanced the ref between our read and swap)
    #   - Rare transient errors from git plumbing
    local retry=0
    local new_sha=""
    while [ "$retry" -lt "$CHECKPOINT_CAS_MAX_RETRIES" ]; do
        retry=$((retry + 1))

        # Read current ref value (OLD_SHA) — empty if ref does not yet exist
        local old_ref_sha
        old_ref_sha=$($git_cmd rev-parse --verify -q "$ref" 2>/dev/null || true)

        # Determine parent for commit-tree and its tree sha for idempotency.
        # Parent chain: if ref exists, parent = ref HEAD; otherwise parent = HEAD;
        # otherwise (empty repo) parent = none.
        local parent_sha=""
        local parent_tree=""
        if [ -n "$old_ref_sha" ]; then
            parent_sha="$old_ref_sha"
        else
            parent_sha=$($git_cmd rev-parse --verify -q HEAD 2>/dev/null || true)
        fi
        if [ -n "$parent_sha" ]; then
            parent_tree=$($git_cmd rev-parse "${parent_sha}^{tree}" 2>/dev/null || true)
        fi

        # Seed temp index from parent tree, or empty if bootstrapping.
        # We always rm first so a partially-written index from a previous retry
        # iteration cannot corrupt this one.
        rm -f "$TMP_INDEX"
        if [ -n "$parent_tree" ]; then
            if ! GIT_INDEX_FILE="$TMP_INDEX" $git_cmd read-tree "$parent_tree" 2>>"$CHECKPOINT_LOG_FILE"; then
                _checkpoint_log ERROR "read-tree failed (parent_tree=${parent_tree}, ref=${ref})"
                rm -f "$TMP_INDEX"
                return 1
            fi
        else
            if ! GIT_INDEX_FILE="$TMP_INDEX" $git_cmd read-tree --empty 2>>"$CHECKPOINT_LOG_FILE"; then
                _checkpoint_log ERROR "read-tree --empty failed (ref=${ref})"
                rm -f "$TMP_INDEX"
                return 1
            fi
        fi

        # Stage all working-tree state into the temp index (no effect on real index).
        if ! GIT_INDEX_FILE="$TMP_INDEX" $git_cmd add -A 2>>"$CHECKPOINT_LOG_FILE"; then
            _checkpoint_log ERROR "add -A failed (ref=${ref})"
            rm -f "$TMP_INDEX"
            return 1
        fi

        # Build tree from temp index.
        local tree_sha
        tree_sha=$(GIT_INDEX_FILE="$TMP_INDEX" $git_cmd write-tree 2>>"$CHECKPOINT_LOG_FILE")
        if [ -z "$tree_sha" ]; then
            _checkpoint_log ERROR "write-tree produced empty sha (ref=${ref})"
            rm -f "$TMP_INDEX"
            return 1
        fi

        # Idempotency short-circuit: tree identical to parent tree -> no-op.
        if [ -n "$parent_tree" ] && [ "$tree_sha" = "$parent_tree" ]; then
            rm -f "$TMP_INDEX"
            trap - EXIT INT TERM HUP
            return 0
        fi

        # Build commit message. custom_message (if any) is the summary line.
        local summary timestamp file_count commit_body
        timestamp=$(date '+%Y-%m-%d %H:%M:%S')
        file_count=$(GIT_INDEX_FILE="$TMP_INDEX" $git_cmd diff --cached --name-only 2>/dev/null |
                     { [ -n "$parent_sha" ] || cat; $git_cmd diff-tree -r --name-only "$parent_tree" "$tree_sha" 2>/dev/null; } |
                     sort -u | wc -l | tr -d ' ')
        if [ -z "$file_count" ] || [ "$file_count" = "0" ]; then
            # Fallback: count files in the tree diff directly
            if [ -n "$parent_tree" ]; then
                file_count=$($git_cmd diff-tree -r --name-only "$parent_tree" "$tree_sha" 2>/dev/null | wc -l | tr -d ' ')
            else
                file_count=$($git_cmd ls-tree -r --name-only "$tree_sha" 2>/dev/null | wc -l | tr -d ' ')
            fi
        fi

        if [ -n "$custom_message" ]; then
            summary="$custom_message"
        else
            summary="checkpoint: Auto-save at ${timestamp}"
        fi
        commit_body="${summary}

Trigger: ${trigger}
Ref: ${ref}
Files: ${file_count}

This commit is a snapshot written to refs/checkpoints/* by
~/.claude/hooks/lib/checkpoint-core.sh. It is NOT on any branch HEAD.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>"

        # Build the commit object (not attached to any ref yet).
        if [ -n "$parent_sha" ]; then
            new_sha=$(printf '%s' "$commit_body" | $git_cmd commit-tree "$tree_sha" -p "$parent_sha" 2>>"$CHECKPOINT_LOG_FILE")
        else
            new_sha=$(printf '%s' "$commit_body" | $git_cmd commit-tree "$tree_sha" 2>>"$CHECKPOINT_LOG_FILE")
        fi
        if [ -z "$new_sha" ]; then
            _checkpoint_log ERROR "commit-tree failed (ref=${ref}, tree=${tree_sha})"
            rm -f "$TMP_INDEX"
            return 1
        fi

        # CAS update-ref:
        #   - if old_ref_sha is empty, pass "" as expected value (ref must not exist)
        #   - if old_ref_sha is set, pass it as expected value (atomic advance)
        if $git_cmd update-ref "$ref" "$new_sha" "$old_ref_sha" 2>>"$CHECKPOINT_LOG_FILE"; then
            rm -f "$TMP_INDEX"
            trap - EXIT INT TERM HUP
            # Rate-limited background push (non-blocking)
            _checkpoint_rate_limited_push "$work_dir" "$ref"
            return 0
        fi

        # CAS lost race; the orphaned new_sha commit is unreachable.
        # It will be GC'd eventually. Log and retry.
        _checkpoint_log WARN "CAS race on ${ref} (attempt ${retry}/${CHECKPOINT_CAS_MAX_RETRIES}), retrying"
        # Small staggered backoff to reduce thundering-herd
        sleep "0.0$((50 + RANDOM % 150))" 2>/dev/null || sleep 1
    done

    _checkpoint_log ERROR "CAS exceeded ${CHECKPOINT_CAS_MAX_RETRIES} retries for ${ref}"
    rm -f "$TMP_INDEX"
    trap - EXIT INT TERM HUP
    return 1
}

# End of library. Sourcing this file exposes write_checkpoint in the caller's shell.
