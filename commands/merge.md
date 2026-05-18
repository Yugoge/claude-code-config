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

### Step 0: Resolve branch name

The orchestrator resolves the source branch from conversation context (most recent
overnight-state-*.json with `worktree_branch` field) or from the explicit argument.
Do NOT guess from filesystem listing. If context cannot resolve a branch and no explicit
argument was supplied, exit with an error asking the user to pass an explicit branch.

### Step 1: Compute pre-merge snapshot

```bash
RESOLVED_BRANCH=<the-resolved-branch>
SOURCE_TIP=$(git rev-parse "refs/heads/${RESOLVED_BRANCH}" 2>/dev/null || echo "MISSING")
DEFAULT_BRANCH=$(bash ~/.claude/scripts/derive-default-branch.sh)
DEFAULT_TIP=$(git rev-parse "refs/heads/${DEFAULT_BRANCH}" 2>/dev/null || echo "MISSING")
REPO_HASH=$(printf '%s' "$(realpath "$(git rev-parse --show-toplevel)")" | sha256sum | cut -c1-16)
REQUEST_ID=$(openssl rand -hex 16)
SESSION_ID="${CLAUDE_SESSION_ID}"
```

If `SESSION_ID` is empty or unset, abort immediately with:
"Cannot dispatch merge-analyst: CLAUDE_SESSION_ID not set. Invoke /merge from within a Claude Code session."

If either tip is "MISSING", abort with an error describing which branch was not found.

### Step 2: Dispatch merge-analyst subagent

Dispatch the `merge-analyst` subagent with the following context:

```
RESOLVED_BRANCH=<RESOLVED_BRANCH>
SOURCE_TIP=<SOURCE_TIP>
DEFAULT_BRANCH=<DEFAULT_BRANCH>
DEFAULT_TIP=<DEFAULT_TIP>
REQUEST_ID=<REQUEST_ID>
SESSION_ID=<SESSION_ID>
REPO_HASH=<REPO_HASH>
```

Wait for the subagent to complete before proceeding.

### Step 3: Read and validate merge-analyst grant

Read the grant at:
```
/tmp/agentic-commit/merge-analyst/<REPO_HASH>/<SESSION_ID>/<REQUEST_ID>.json
```

Validate the following fields:
- File exists (if absent: abort with "merge-analyst did not write a grant — aborting merge")
- Grant is valid JSON (if not: abort with "merge-analyst grant is not valid JSON — aborting merge")
- `nonce` field matches `REQUEST_ID`
- `branch` field matches `RESOLVED_BRANCH`
- `source_tip` field matches `SOURCE_TIP`
- `default_tip` field matches `DEFAULT_TIP`
- `default_branch` field matches `DEFAULT_BRANCH`
- `session_id` field matches `SESSION_ID`
- `verdict` field is one of: `"approved"`, `"blocked"` (reject unknown verdicts)
- `risks` field is a JSON array (even if empty)
- `expires_at` is in the future (60s expiry — parse ISO-8601, compare to current UTC time)

If expired: re-dispatch merge-analyst (return to Step 2 with a fresh REQUEST_ID). Report
to the user that the grant expired and a fresh analysis is running.

If any non-expiry field mismatches, is absent, or has wrong type: abort with a descriptive error naming the failing field.

Consume (unlink) the grant:
```bash
rm -f "/tmp/agentic-commit/merge-analyst/${REPO_HASH}/${SESSION_ID}/${REQUEST_ID}.json"
```

If verdict=blocked: display `risks[]` to the user and abort. Do NOT call merge.sh.

### Step 4: Revalidate branch tips

Immediately before calling merge.sh, re-read current branch tips:

```bash
CURRENT_SOURCE_TIP=$(git rev-parse "refs/heads/${RESOLVED_BRANCH}" 2>/dev/null)
CURRENT_DEFAULT_TIP=$(git rev-parse "refs/heads/${DEFAULT_BRANCH}" 2>/dev/null)
```

If either tip differs from the value stored in the grant (`source_tip`, `default_tip`):
abort with "Branch tips changed since merge-analyst ran — re-run /merge to get a fresh analysis".

### Step 5: Call merge.sh

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
