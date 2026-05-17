---
description: "Pull Command"
disable-model-invocation: true
---

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

- Automatically stashes uncommitted changes before pulling, restores after
- Uses `git pull --rebase` for clean linear history
- Detects conflicts during rebase and lists conflicted files with resolution steps
- Handles detached HEAD, network failures, and no upstream branch

## Related Commands

- `/push` - Push changes with untracked file detection
- `git status` - Check current working directory state

The implementation is in `~/.claude/hooks/pull.sh`.
