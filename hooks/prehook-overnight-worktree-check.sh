#!/bin/bash
# UserPromptSubmit hook — block /dev-overnight launch if an applio worktree already exists.
# Enforces: max 1 active overnight worktree at a time.
#
# Input: JSON on stdin, schema: { "prompt": "...", "cwd": "...", ... }
# Exit 0 = allow; exit 2 = block with stderr shown to user.

set -euo pipefail

# Read the hook payload
payload="$(cat 2>/dev/null || true)"
prompt="$(printf '%s' "$payload" | python3 -c 'import json,sys;
try:
    d=json.load(sys.stdin)
    print(d.get("prompt","") or "")
except Exception:
    pass' 2>/dev/null || true)"

# Only fire when the user prompt contains /dev-overnight (as a slash command token)
if ! printf '%s' "$prompt" | grep -qE '(^|[[:space:]])/dev-overnight([[:space:]]|$)'; then
    exit 0
fi

# Determine repo root (prefer git toplevel, fall back to cwd).
cwd="$(printf '%s' "$payload" | python3 -c 'import json,sys;
try:
    d=json.load(sys.stdin); print(d.get("cwd","") or "")
except Exception:
    pass' 2>/dev/null || true)"
if [ -z "$cwd" ]; then
    cwd="$PWD"
fi

# Only enforce on applio project paths.
case "$cwd" in
    *applio*) ;;
    *) exit 0 ;;
esac

repo_root="$(cd "$cwd" 2>/dev/null && git rev-parse --show-toplevel 2>/dev/null || true)"
[ -z "$repo_root" ] && repo_root="$cwd"

# Only applio repos
case "$repo_root" in
    *applio*) ;;
    *) exit 0 ;;
esac

wt_dir="$repo_root/.claude/worktrees"
if [ ! -d "$wt_dir" ]; then
    exit 0
fi

# Count subdirs (depth 1 only)
existing=$(find "$wt_dir" -mindepth 1 -maxdepth 1 -type d 2>/dev/null || true)
count=$(printf '%s\n' "$existing" | grep -c '.' || true)

if [ "${count:-0}" -gt 0 ]; then
    {
        echo "[BLOCKED] Existing overnight worktree(s) detected under $wt_dir:"
        printf '%s\n' "$existing" | sed 's|^|  - |'
        echo ""
        echo "Remove them before starting a new /dev-overnight cycle."
        echo "Max 1 worktree allowed at a time."
        echo ""
        echo "Remove with:"
        echo "  for wt in \$(ls $wt_dir); do"
        echo "    git -C $repo_root worktree remove $wt_dir/\$wt --force"
        echo "    git -C $repo_root branch -D worktree-\$wt 2>/dev/null || true"
        echo "  done"
        echo "  git -C $repo_root worktree prune"
    } >&2
    exit 2
fi

exit 0
