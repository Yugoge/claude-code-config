---
description: Merge an overnight worktree branch to master with full commit history preservation
---

# Merge Overnight Worktree

Merges an overnight development worktree branch into master using a proper `git merge` that preserves full commit history.

## Arguments

```
/merge-overnight <worktree-branch-name>
```

**Example**:
- `/merge-overnight overnight-20260411-3fba4092`

## CRITICAL RULES

- **Use `git merge` ONLY.** Never squash merge. Never cherry-pick. Never manually copy files. Never create a single synthetic commit.
- The worktree branch contains the real development history with individual commits. A proper merge preserves all of that on master.
- If there are merge conflicts, show them to the user and let them resolve. Do NOT auto-resolve.

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
git log master..$BRANCH_NAME --oneline | wc -l

# Show commit list
git log master..$BRANCH_NAME --oneline

# Show diffstat
git diff master...$BRANCH_NAME --stat
```

Print a summary:
```
Branch: <branch_name>
Commits to merge: <count>
Files changed: <count>

Commit history:
  <hash1> <message1>
  <hash2> <message2>
  ...

Proceeding with merge...
```

### Step 3: Merge to master

```bash
# Ensure we are on master
git checkout master

# Perform a proper merge (NOT squash, NOT rebase)
git merge $BRANCH_NAME --no-edit
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

### Step 4: Verify merge

```bash
# Confirm merge commit exists
git log --oneline -1

# Confirm branch is merged
git branch --merged master | grep $BRANCH_NAME
```

### Step 5: Clean up worktree (offer, do not force)

Ask the user if they want to clean up:

```
Merge complete. <count> commits merged to master.

Clean up the worktree?
  The worktree branch and directory can be removed now that changes are on master.
  
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

### Step 6: Remind about deployment

```
Merge complete. Remember to rebuild and deploy if needed:
  - Rebuild affected services
  - Verify the deployment is working
```
