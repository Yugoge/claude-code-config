---
description: Merge an overnight worktree branch to the default branch with full commit history preservation
---

# Merge Overnight Worktree

Merges an overnight development worktree branch into the repository's default branch using a proper `git merge` that preserves full commit history.

## Arguments

```
/merge <worktree-branch-name>
```

**Example**:
- `/merge overnight-20260411-3fba4092`

## CRITICAL RULES

- **Use `git merge` ONLY.** Never squash merge. Never cherry-pick. Never manually copy files. Never create a single synthetic commit.
- The worktree branch contains the real development history with individual commits. A proper merge preserves all of that on the default branch.
- If there are merge conflicts, show them to the user and let them resolve. Do NOT auto-resolve.

## Default-branch resolver

Run this resolver block FIRST, before any other step. It detects the repository's default branch dynamically (`main`, `master`, or any other) by reading `refs/remotes/origin/HEAD`. Every subsequent step references `$DEFAULT_BRANCH` rather than a hardcoded literal.

Rationale: a hardcoded `master` literal regressed at commit `b5d447e` (2026-04-21) and earlier never tracked the project's `main` migration. Per spec-20260424-233926 Section 5.2.1.1, all command-execution paths must derive the default branch dynamically.

```bash
# Detect default branch dynamically (handles main/master/any other)
DEFAULT_BRANCH="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's@^origin/@@')"
if [ -z "$DEFAULT_BRANCH" ]; then
  DEFAULT_BRANCH="$(git remote show origin 2>/dev/null | sed -n 's/.*HEAD branch: //p')"
fi
if [ -z "$DEFAULT_BRANCH" ]; then
  DEFAULT_BRANCH="master"  # final fallback
fi
echo "target=$DEFAULT_BRANCH"
```

## Steps

### Step 1: Validate the branch

```bash
# Verify the branch exists
git branch --list "$BRANCH_NAME"

# If empty, check if it is a worktree branch
git worktree list
```

If the branch does not exist, inform the user and stop.

### Step 2: Show what will be merged

Before merging, show the user what they are about to merge:

```bash
# Show commit count
git rev-list --count "$DEFAULT_BRANCH..$BRANCH_NAME"

# Show commit list (one-line, oldest-first via --reverse if preferred)
git log --oneline "$DEFAULT_BRANCH..$BRANCH_NAME"

# Show diffstat
git diff --stat "$DEFAULT_BRANCH...$BRANCH_NAME"
```

Print a summary:
```
Branch: <branch_name>
Default branch: <default_branch>
Commits to merge: <count>
Files changed: <count>

Commit history:
  <hash1> <message1>
  <hash2> <message2>
  ...

Proceeding with merge...
```

### Step 3: Untracked-overlap preflight (R3b stash-aware preflight)

Before any auto-bulk commit or merge, detect untracked files in the parent at paths the merge would touch. If overlap exists, abort with a structured report and exit non-zero. This prevents `git merge` from clobbering uncommitted parent state.

Per spec 5.2.1.3, the literal phrase `untracked overlap detected:` MUST appear in stdout when overlap is found, followed by the file list. The command MUST NOT call `git merge` on overlap.

```bash
# Compute paths the merge would touch (ref-based diff between default branch tip and worktree branch tip)
TOUCHED=$(git diff --name-only "$DEFAULT_BRANCH...$BRANCH_NAME" 2>/dev/null | sort -u)

# Compute parent's untracked-and-not-ignored files
UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null | sort -u)

# Intersect (files that appear in both sets)
if [ -n "$TOUCHED" ] && [ -n "$UNTRACKED" ]; then
  OVERLAP=$(comm -12 <(printf '%s\n' "$TOUCHED") <(printf '%s\n' "$UNTRACKED"))
else
  OVERLAP=""
fi

if [ -n "$OVERLAP" ]; then
  echo "untracked overlap detected:"
  printf '%s\n' "$OVERLAP"
  echo ""
  echo "Resolution: stash, commit, or remove the listed parent untracked files before retrying /merge."
  exit 2
fi
```

### Step 4: Auto-bulk-commit bridge for zero-ahead worktree (R2 option d)

If the worktree branch has zero commits ahead of the default branch but its working tree is dirty, produce ONE blessed semantic commit FROM the worktree's working tree before merging. The commit message MUST match the regex `^auto-bulk: end-of-cycle commit for ` so the R4.3 git-privilege-guard whitelists it.

Per spec 5.2.1.2, this bridge replaces the auto-commit-to-branch-HEAD behavior that commit `b5d447e` removed when it ratified the snapshots-off-HEAD design (`refs/checkpoints/*` per `f2f8741`). The bridge does NOT touch `refs/checkpoints/*`; it produces a fresh semantic commit at `/merge` invocation time.

```bash
# Locate the worktree path for the named branch (printed earlier by `git worktree list` in Step 1)
WORKTREE_PATH=$(git worktree list | awk -v b="$BRANCH_NAME" '$0 ~ "\\["b"\\]$" {print $1; exit}')

# Count commits the branch has ahead of the default branch
AHEAD_COUNT=$(git rev-list --count "$DEFAULT_BRANCH..$BRANCH_NAME" 2>/dev/null || echo 0)

if [ "$AHEAD_COUNT" -eq 0 ]; then
  if [ -z "$WORKTREE_PATH" ] || [ ! -d "$WORKTREE_PATH" ]; then
    echo "Worktree branch '$BRANCH_NAME' has zero commits ahead of '$DEFAULT_BRANCH' and no worktree directory was found."
    echo "Cannot auto-bulk-commit because there is no working tree to capture."
    exit 2
  fi

  echo "Branch '$BRANCH_NAME' has zero commits ahead of '$DEFAULT_BRANCH'."
  echo "Checking worktree at $WORKTREE_PATH for uncommitted changes..."

  # Stage and inspect from inside the worktree (the commit's tree object must reflect the worktree's working state)
  if ( cd "$WORKTREE_PATH" && git add -A && ! git diff --cached --quiet ); then
    (
      cd "$WORKTREE_PATH" && \
      git commit -m "auto-bulk: end-of-cycle commit for $BRANCH_NAME" \
        -m "Generated by /merge bridge: worktree had zero commits ahead of $DEFAULT_BRANCH but a dirty working tree at /merge invocation time. This single semantic commit captures the cycle's work without touching refs/checkpoints/* (locked by f2f8741 design)."
    )
    echo "Auto-bulk commit landed on $BRANCH_NAME at $WORKTREE_PATH."
    AHEAD_COUNT=$(git rev-list --count "$DEFAULT_BRANCH..$BRANCH_NAME" 2>/dev/null || echo 0)
  else
    echo "Worktree at $WORKTREE_PATH is clean (nothing staged after 'git add -A'); no auto-bulk commit needed."
    echo "Branch is at the same hash as $DEFAULT_BRANCH; '/merge' has nothing to merge. Exiting."
    exit 0
  fi
fi
```

### Step 5: Merge to the default branch

```bash
# Ensure we are on the default branch
git checkout "$DEFAULT_BRANCH"

# Perform a proper merge (NOT squash, NOT rebase)
git merge "$BRANCH_NAME" --no-edit
```

**If merge succeeds**: Proceed to Step 4.

**If merge conflicts**:

```bash
# Show conflicting files
git diff --name-only --diff-filter=U
```

Print the conflicts and tell the user:
```
Merge conflicts detected in:
  <file1>
  <file2>

Please resolve conflicts manually, then run:
  git add <resolved-files>
  git commit
```

**Do NOT auto-resolve conflicts.** Stop and let the user handle them.

### Step 6: Verify merge

```bash
# Confirm merge commit exists
git log --oneline -1

# Confirm branch is merged
git branch --merged "$DEFAULT_BRANCH" | grep "$BRANCH_NAME"
```

### Step 7: Clean up worktree (offer, do not force)

Ask the user if they want to clean up:

```
Merge complete. <count> commits merged to <default_branch>.

Clean up the worktree?
  The worktree branch and directory can be removed now that changes are on the default branch.
  
  To clean up: git worktree remove <worktree_path> && git branch -d <branch_name>
  To keep: do nothing (worktree stays for reference)
```

If the user confirms cleanup:

```bash
# Find the worktree path for this branch
WORKTREE_PATH=$(git worktree list | grep "$BRANCH_NAME" | awk '{print $1}')

# Remove worktree and branch
git worktree remove "$WORKTREE_PATH"
git branch -d "$BRANCH_NAME"
```

Use `-d` (not `-D`) for the branch delete -- this is safe because the branch is already merged. If `-d` fails, it means something went wrong with the merge and the user should investigate.

### Step 8: Remind about deployment

```
Merge complete. Remember to rebuild and deploy if needed:
  - Rebuild affected services
  - Verify the deployment is working
```
