# FSWatch Command

Real-time file monitoring with automatic git commit/push/pull.

## Quick Start

```bash
# Start watching a directory
bash ~/.claude/hooks/fswatch-manager.sh start ~/my-project

# Check status
bash ~/.claude/hooks/fswatch-manager.sh status

# View logs
bash ~/.claude/hooks/fswatch-manager.sh logs

# Stop watching
bash ~/.claude/hooks/fswatch-manager.sh stop
```

## Features

✅ Automatic git add/commit/push
✅ Periodic pull (every 5 minutes)
✅ Conflict detection & user prompts
✅ Lock file handling
✅ Network retry logic (3 attempts)
✅ Debouncing (5 second delay)
✅ Comprehensive logging

## When to Use

**✅ Good for:**
- Personal notes/documentation
- Configuration files (dotfiles)
- Prototype development
- Learning/experimental projects

**❌ Not recommended for:**
- Production code
- Team collaboration repositories
- Projects needing clean commit history
- Large repositories (>100K files)

## Configuration

```bash
# Debounce delay (seconds)
export FSWATCH_DEBOUNCE=5

# Auto-pull interval (seconds)
export FSWATCH_PULL_INTERVAL=300

# Max push retries
export FSWATCH_MAX_RETRIES=3
```

## Error Handling

The watcher automatically handles:

1. **Merge Conflicts**: Pauses and prompts user
2. **Lock Files**: Cleans stale locks
3. **Network Failures**: Retries with backoff
4. **Diverged Branches**: Auto-pulls before push
5. **Detached HEAD**: Stops with clear message

## Full Documentation

See: `~/.claude/docs/git-fswatch.md`

## Comparison with Smart Checkpoint

| Feature | Smart Checkpoint | FSWatch |
|---------|-----------------|---------|
| Trigger | Claude Edit/Write | File system |
| Token Cost | +16% | 0% |
| Scope | Claude changes | All changes |
| Delay | Instant | 5s debounce |

**Best practice**: Use both for maximum protection!

---

**Related**:
- Smart checkpoint: `~/.claude/docs/auto-sync-analysis.md`
- Lock handling: `~/.claude/docs/lock-file-handling.md`
