# Fix deploy script: SSH-first + travel.life-ai.app

## Context
The deploy script (`scripts/deploy-travel-plans.sh`) crashes at line 216 because `$GITHUB_TOKEN` is unbound and `set -euo pipefail` is active. The local deployment to `travel.life-ai.app` (Step 8.5, lines 550-577) already exists but never executes because the script dies before reaching it.

## Root Cause
Line 216: `if [ -n "$GITHUB_TOKEN" ]; then` — with `-u` flag, referencing an unset variable is a fatal error.

## Changes

### File: `/root/travel-planner/scripts/deploy-travel-plans.sh`

**Change 1**: Line 216 — Use `${GITHUB_TOKEN:-}` to safely handle unbound variable:
```bash
# Before:
if [ -n "$GITHUB_TOKEN" ]; then
# After:
if [ -n "${GITHUB_TOKEN:-}" ]; then
```

**Change 2**: Restructure auth priority — SSH first (since that's what works on this server), token as fallback. Swap the if/elif order at lines 216-232:
```bash
if [ -f ~/.ssh/id_rsa ] || [ -f ~/.ssh/id_ed25519 ]; then
    # SSH first (preferred on this server)
    ...
    USE_SSH=true
elif [ -n "${GITHUB_TOKEN:-}" ]; then
    # Token fallback
    ...
    USE_TOKEN=true
else
    ...
fi
```

**Change 3**: Ensure local deployment runs even if GitHub push fails. Move Step 8.5 (lines 550-577) before Step 7 (git push), or wrap the git push in a non-fatal block so local deploy always happens.

Better approach: restructure so local deploy happens BEFORE GitHub push (local is more important since it's immediate):
- Move Step 8.5 (local deploy) to run right after Step 6 (index generation), before Step 7 (git push)
- This ensures travel.life-ai.app always gets updated regardless of GitHub push status

## Verification
```bash
# Test with no GITHUB_TOKEN set:
unset GITHUB_TOKEN
bash /root/travel-planner/scripts/deploy-travel-plans.sh /root/travel-planner/output/travel-plan-wangfujing-dongdan-beijing-20260405-192905.html

# Verify:
# 1. SSH auth detected
# 2. Local deploy to /var/www/travel/ succeeds
# 3. GitHub push via SSH succeeds
# 4. https://travel.life-ai.app/wangfujing-dongdan-beijing/2026-04-05/ accessible
# 5. https://yugoge.github.io/travel-planner-graph/wangfujing-dongdan-beijing/2026-04-05/ accessible
```
