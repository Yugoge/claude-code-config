# Pull Command

Execute safe git pull with automatic stash management and conflict detection.

## Overview

The `/pull` command safely pulls changes from the remote repository with:
- Automatic stash management for uncommitted changes
- Rebase strategy to maintain clean history
- Conflict detection and resolution guidance
- Safe restoration of stashed work

## Usage

Simply type:
```
/pull
```

## Command Implementation

Execute the pull script:

```bash
bash ~/.claude/hooks/pull.sh
```

## Features

### Automatic Stashing
- Detects uncommitted changes automatically
- Creates timestamped stash before pull
- Restores stash after successful pull

### Rebase Strategy
- Uses `git pull --rebase` for clean history
- Avoids unnecessary merge commits
- Maintains linear commit history

### Conflict Detection
- Detects merge conflicts during rebase
- Lists all conflicted files
- Provides clear resolution steps
- Guides through rebase continuation

### Error Handling
- Detached HEAD detection
- Network failure handling
- No upstream branch handling
- Stash conflict resolution

## Example Scenarios

### Scenario 1: Clean Working Directory

```
User: /pull

🔄 Starting safe pull...

Working directory clean, no stash needed

Pulling from origin/master with rebase...
Successfully rebased and updated refs/heads/master.

✅ Pull completed successfully

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Pull complete!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Summary:
  • Branch: master
  • New commits: 3

Recent commits:
a1b2c3d Update documentation
e4f5g6h Fix bug in authentication
i7j8k9l Add new feature
```

### Scenario 2: With Uncommitted Changes

```
User: /pull

🔄 Starting safe pull...

📦 Uncommitted changes detected
Stashing changes before pull...
✅ Stashed as: stash@{0}

Pulling from origin/master with rebase...
Successfully rebased and updated refs/heads/master.

✅ Pull completed successfully

📦 Restoring stashed changes...
✅ Stashed changes restored

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Pull complete!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Summary:
  • Branch: master
  • New commits: 2
  • Stashed changes: Restored
```

### Scenario 3: With Conflicts

```
User: /pull

🔄 Starting safe pull...

Working directory clean, no stash needed

Pulling from origin/master with rebase...

⚠️  Conflicts detected during rebase!

Conflicted files:
   - src/config.json
   - README.md

Resolution steps:
  1. Edit conflicted files to resolve conflicts
  2. Stage resolved files: git add <file>
  3. Continue rebase: git rebase --continue

Or abort the rebase: git rebase --abort
```

## Safety Features

- **Automatic stashing**: Uncommitted work is preserved
- **Rebase strategy**: Maintains clean, linear history
- **Conflict detection**: Clear guidance for resolution
- **Rollback capability**: `git rebase --abort` if needed
- **Stash preservation**: Changes never lost

## Related Commands

- **`/push`** - Push changes with untracked file detection
- **`git status`** - Check current working directory state
- **`git stash list`** - View all stashes

## Notes

- The command uses `--rebase` to maintain a clean history
- Stashes are automatically named with timestamps
- All operations respect `.gitignore` rules
- Safe to use multiple times consecutively

## Script Location

The actual implementation is in: `~/.claude/hooks/pull.sh`

You can also run it directly:
```bash
bash ~/.claude/hooks/pull.sh
```
