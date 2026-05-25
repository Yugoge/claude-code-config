#!/bin/bash
# ensure-git-repo.sh - DEPRECATED, scheduled for deletion
# ----------------------------------------------------------------------------
# This hook is a byte-identical copy of session-git-init.sh and was verified
# ORPHAN (not referenced by ~/.claude/settings.json) as of the 2026-04-16
# SaaS-grade blame-hygiene audit (qa-final-blame-audit-20260416-063500.json).
#
# The sole registered SessionStart hook for repo initialization is:
#     ~/.claude/hooks/session-git-init.sh
# which now carries a zero-commits guard so it cannot pollute HEAD on repos
# that already have history.
#
# This stub exits 0 immediately so any stale manual invocation is a no-op.

exit 0
