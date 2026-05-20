# User Requirement — dev-20260519-161035

## Verbatim user final selection

> 实施全部

User selected this after an in-session debate with codex about systematically preventing `/tmp` and `/dev/shm` (tmpfs, RAM-backed) from filling up again on this server. The plan below is the codex-debated, user-confirmed scope.

## Verbatim user framing (Chinese, preserved)

> 现在和codex辩论思考如何系统性预防这种问题再次发生（tmp或者ramdisk爆满），在不更改现有架构和功能的情况下

Translation: "Now debate with codex how to systematically prevent this problem from recurring (tmp or ramdisk filling up), without changing existing architecture or functionality."

## Incident context (the trigger event)

- `/tmp` hit 85% (3.4G / 4.0G tmpfs) — at risk of ENOSPC failures for subagents
- `/dev/shm` hit 69% (11G / 16G tmpfs) — 14.4G of system RAM held by tmpfs mounts
- Real disk `/` was only 27% used — this is RAM pressure, not disk pressure
- Manual cleanup recovered ~2.8G; recurrence prevention is the actual concern

## Constraints (binding red lines)

- NO architectural changes: do not move `/tmp/claude-0` off tmpfs, do not relocate the workspace
- NO functional changes: do not alter Claude Code, codex CLI, or any subagent runtime behavior
- Additive only: cron extensions, SessionStart/UserPromptSubmit hook additions, conventions
- No new monitoring daemons, no PreToolUse blocking, no aggressive systemd-tmpfiles changes

## Codex-debated implementation plan (user confirmed: "实施全部")

### Layer 1 — Visibility (SessionStart, zero behavioral change)
On every new Claude Code session, the user must see one compact line showing `df -h /tmp /dev/shm`, with a highlight/warning marker when either filesystem exceeds 75% usage. The SessionStart hook surface already exists in the project — this is an extension, not a replacement.

### Layer 1.5 — Mid-session pressure warning (UserPromptSubmit, non-blocking)
A UserPromptSubmit hook that, on each user prompt, checks `/tmp` and `/dev/shm` usage. If either exceeds 75%, print a non-blocking informational warning showing `df -h` for those two mounts plus the top 5 largest directories under the pressured mount. Rate-limit: at most 3 warnings per session (keyed by `CLAUDE_SESSION_ID` or equivalent) to avoid spam. Non-blocking: the user prompt proceeds normally regardless; the hook only emits informational stdout.

### Layer 2 — Scheduled GC (extend existing `/usr/local/sbin/tmp-cleanup.sh`)
The existing daily cron at `/etc/cron.d/tmp-cleanup-daily` invokes `/usr/local/sbin/tmp-cleanup.sh`. The script currently only prunes `/var/tmp/codex-outputs >7d` and recovered only 28K on 2026-05-19 — pattern coverage is too narrow. Extend the script. CRITICAL: **EXCLUSION ORDER FIRST** (the hard-exclusion list is applied before any pattern matching, so wildcard patterns like `*-debug-*` cannot accidentally match the live `/tmp/chrome-debug-profile`).

Hard exclusions (never delete, applied before patterns):
- `/tmp/chrome-debug-profile` (active Chrome instance)
- `/tmp/happy-attachments` (live attachment store)
- `/tmp/claude-0` directory body (active Claude Code state) — its `*.output` files may be pruned per rule below, everything else under it is preserved
- `/tmp/claude-commit-plan-*` (live commit plan workdirs)
- `/tmp/happy-p05-cdp-*` (live CDP profiles)
- Any path matching `*debug-profile*`

Prune by pattern + age (mtime older than threshold):
- Age >3 days: `qa-semantic-*`, `tier-*`, `qa-*`, `dev-semantic-*`, `dev-same*`, `dev-root*`, `dev-broad*`
- Age >1 day: `/tmp/claude-0/**/*.output` (use exactly `-mtime +1` — codex verified open_older_count=0 at this threshold)
- Age >7 days: `map-*`, `career-*`, `*-app-check`, `*-deploy`, `playwright-artifacts-*`, `expo-ui-*`, `.cleanup-staging-*`, `sort[A-Za-z0-9]*`, `*-bundle.js`, `*-main.js`, `happy-app-build-test`, `ocr_env`

The script must log what it removed and how much space was freed (sum in human-readable form).

### Layer 3 — Convention (documentation only, no enforcement)
Document a convention for future ad-hoc scratch directories: use the suffix `*-scratch-<ts>` so the daily cron sweep can pick them up generically. No hook enforcement — pure convention added to project documentation.

## Acceptance criteria

1. New Claude Code session prints a `df -h /tmp /dev/shm` line on session start.
2. Line is highlighted when either mount is >75% used.
3. A user prompt issued while either mount is >75% triggers a non-blocking warning; the warning appears at most 3 times per session.
4. `/usr/local/sbin/tmp-cleanup.sh` now sweeps the extended pattern list with EXCLUSION-FIRST ordering — verifiable via dry-run mode.
5. Dry-run, with all hard-exclusion paths populated, lists none of them for deletion.
6. Cleanup script logs actions taken and total bytes freed per run.
7. Existing behavior is preserved: existing SessionStart hook still fires its current content, existing daily cron still triggers at 02:07, claude-0 directory body untouched, chrome-debug-profile untouched.
8. A convention note for `*-scratch-<ts>` is recorded in project documentation.

## Out of scope (do not expand)

- Moving anything off tmpfs
- Adding monitoring daemons / Prometheus / alerting stacks
- PreToolUse hooks that block tool calls on tmpfs pressure
- Aggressive systemd-tmpfiles policy changes
- Modifying the `/dev/shm/dev-workspace` workspace structure
- Pruning `/dev/shm` contents (only warnings are in scope for /dev/shm)