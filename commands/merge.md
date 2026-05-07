---
description: Merge the current overnight worktree branch into the default branch (agent infers branch from active overnight state). Bare /merge typical; explicit /merge <branch> overrides. Auto-cleans worktree + branch + overnight-state file when merge succeeds and the diff is clean.
disable-model-invocation: true
---

# /merge - Overnight Worktree Merge

After an overnight cycle, merge the worktree branch into the repository default branch using a proper merge that preserves full commit history. After a clean successful merge, the wrapper auto-cleans the worktree, deletes the merged branch, and removes any overnight-state-*.json referencing it.

## Usage

```
/merge                          # agent infers worktree branch from active overnight-state-*.json (typical)
/merge <worktree-branch>        # explicit override
```

When invoked bare, the orchestrator identifies the active overnight cycle branch from conversation context (most recent overnight-state-*.json with worktree_branch field) and embeds the resolved branch name into the wrapper invocation. No filesystem fallback to "newest branch", no guessing - if context cannot resolve a branch, exit with error asking the user to pass an explicit branch.

## Implementation

The orchestrator calls the wrapper exactly once with the resolved branch:

```bash
bash ~/.claude/hooks/merge.sh "<resolved-branch-name>"
```

The wrapper handles every step internally so that the privilege-guard literal-string match on the merge command does not fire on main-agent PreToolUse (the wrapper runs git operations in its OWN subprocess, which is not seen by main-agent hooks):

1. User-intent sentinel check (must come from /merge slash command, not bash tool)
2. Default-branch resolution (via ~/.claude/scripts/derive-default-branch.sh)
3. Worktree-branch existence check
4. Untracked-overlap preflight (per spec 5.2.1.3 R3b)
5. Checkout default branch + perform the merge with --no-edit
6. Post-merge sanity check (diff vs branch must be empty)
7. Cleanup ONLY when sanity passes:
   - git worktree remove --force for the worktree directory
   - git branch -d for the merged branch
   - rm any overnight-state-*.json whose worktree_branch field matches

If the merge has conflicts, the wrapper exits non-zero and the user resolves manually. The wrapper does NOT auto-resolve.

## Critical rules

- The orchestrator MUST call the wrapper, NOT inline git commands. Inline forms get string-matched by pretool-git-privilege-guard.py and rejected; the wrapper is the only authorized path from agent context.
- If the user wants a manual merge (e.g., to inspect partial state first), they should run from their own terminal - the hook only restricts the agent bash tool, not the user shell.

## Out of scope

- Squash merge / rebase / cherry-pick - never. The worktree branch individual commits must be preserved on the default branch.
- Pushing to remote - see /push.
- Three-step composite (commit + merge + push) - /ship-overnight was retired; run the three commands separately so each carries its own audit trail.
