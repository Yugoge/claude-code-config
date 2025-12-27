# Push Command

Execute validated git push with untracked file detection and optional auto-staging.

## Overview

The `/push` command provides a comprehensive push workflow with:
- Untracked file detection and warnings
- Optional auto-staging of all files
- Automatic commit creation if needed
- Upstream tracking setup
- Clear error handling and guidance

## Usage

Simply type:
```
/push
```

## Command Implementation

Execute the push script in **fully automatic mode**:

```bash
bash ~/.claude/hooks/push.sh
```

The script automatically detects non-interactive environments (like Claude Code) and runs in auto mode without prompts.

## Features

### Comprehensive Status Check
- Detects staged files
- Detects modified but unstaged files
- Detects untracked files
- Displays color-coded summary

### Auto-Staging Option
- Prompts to stage all files (if `GIT_PUSH_AUTO_STAGE=1`)
- Respects `.gitignore` rules
- Shows exactly what will be staged
- User confirmation required

### Automatic Commit Creation
- Only creates commit if staged changes exist
- Follows Claude Code commit message conventions
- Includes co-author attribution
- Generates descriptive commit messages

### Upstream Tracking
- Automatically sets upstream for new branches
- Uses `git push -u origin <branch>` when needed
- Handles existing upstream tracking

### Error Handling
- Push rejection (remote has changes)
- Network failures
- No staged changes
- Detached HEAD state

## Example Scenarios

### Scenario 1: Push with Untracked Files

```
User: /push

🚀 Starting validated push...

📊 Checking repository status...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Git Status Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Modified but not staged (1):
   ⚠ settings.json

Untracked files (2):
   ? new-file.txt
   ? docs/README.md

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Auto-Staging Available
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Found 3 file(s) not staged for commit.

Stage all files including untracked? (y/n)
y

📦 Staging all files...
✅ Staged 3 file(s)

📝 Creating commit...
✅ Commit created: a1b2c3d

🌐 Pushing to remote...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Successfully pushed to origin/master
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Summary:
  • Branch: master
  • Latest commit: a1b2c3d Update: Comprehensive changes via push script
  • Changes: 3 files changed, 42 insertions(+), 5 deletions(-)
```

### Scenario 2: Push Already Staged Files

```
User: /push

🚀 Starting validated push...

📊 Checking repository status...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Git Status Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Staged files (3):
   ✓ commands/pull.md
   ✓ commands/push.md
   ✓ settings.json

📝 Creating commit...
✅ Commit created: e4f5g6h

🌐 Pushing to remote...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Successfully pushed to origin/master
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Scenario 3: Nothing to Push

```
User: /push

🚀 Starting validated push...

📊 Checking repository status...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Git Status Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ Working directory clean

⚠️  No staged changes to commit

Nothing to commit or push.
```

## Configuration

Control auto-staging behavior via environment variable in `~/.claude/settings.json`:

```json
{
  "env": {
    "GIT_PUSH_AUTO_STAGE": "1"  // Prompt to stage all files (default: 1)
  }
}
```

**Values:**
- `"1"` - Prompt to stage all files when untracked/modified files exist
- `"0"` - Only push already staged files, no prompt

## Safety Features

- **Preview before staging**: Shows exactly what files will be affected
- **User confirmation**: Prompts before auto-staging
- **Respects .gitignore**: Never stages ignored files
- **Clear status display**: Always shows current state
- **Upstream tracking**: Automatically sets up tracking for new branches
- **Error guidance**: Provides specific suggestions for each error type

## Error Scenarios

### Push Rejected (Remote Has Changes)

```
❌ Push failed

Possible causes:
  • Remote has changes you don't have (pull first)
  • Network connectivity issues
  • Authentication failure

Suggestions:
  • Pull first: git pull --rebase
  • Check network connection
  • Verify remote access: git remote -v
```

### No Upstream Branch

```
Setting upstream to origin/feature-branch...

To https://github.com/user/repo.git
 * [new branch]      feature-branch -> feature-branch
Branch 'feature-branch' set up to track remote branch 'feature-branch' from 'origin'.

✅ Successfully pushed to origin/feature-branch
```

### Detached HEAD

```
❌ Error: Not on a branch (detached HEAD)
Checkout a branch first: git checkout <branch-name>
```

## Related Commands

- **`/pull`** - Pull changes with stash management
- **`git status`** - Check working directory state
- **`git add .`** - Manually stage all files

## Notes

- Commit messages follow Claude Code conventions
- Co-author attribution included automatically
- Safe to use multiple times
- Won't push sensitive files (respects deny rules in settings.json)
- Works with both new and existing branches

## Script Location

The actual implementation is in: `~/.claude/hooks/push.sh`

You can also run it directly:
```bash
bash ~/.claude/hooks/push.sh
```
