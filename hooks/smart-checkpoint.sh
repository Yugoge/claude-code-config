#!/bin/bash
# smart-checkpoint.sh - DEPRECATED, scheduled for deletion
# ----------------------------------------------------------------------------
# This hook is a historical duplicate of posttool-git-checkpoint.sh and was
# verified dormant (not referenced by ~/.claude/settings.json or any live
# settings.local.json) as of the 2026-04-16 refs/checkpoints migration.
#
# The live replacement is:  ~/.claude/hooks/posttool-git-checkpoint.sh
# which sources ~/.claude/hooks/lib/checkpoint-core.sh and writes to
# refs/checkpoints/<branch> instead of branch HEAD.
#
# This stub exits 0 immediately so any stale reference is a no-op.

exit 0
