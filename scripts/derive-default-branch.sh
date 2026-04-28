#!/usr/bin/env bash
# Description: Resolve the repository's default branch name dynamically (handles main/master/any other).
# Usage: derive-default-branch.sh
# Output (stdout): a single line — the resolved default branch name (e.g., "main" or "master").
# Exit codes: 0 always (the function emits a fallback name rather than failing).
#
# Resolution tiers (first non-empty wins):
#   1. git symbolic-ref --short refs/remotes/origin/HEAD  (strip "origin/" prefix)
#   2. git remote show origin                              (extract "HEAD branch:" line)
#   3. literal "master"                                    (final fallback)
#
# Rationale: a hardcoded "master" literal regressed at commit b5d447e (2026-04-21) and
# never tracked the project's "main" migration. Per spec-20260424-233926 Section 5.2.1.1,
# all command-execution paths must derive the default branch dynamically.

set -uo pipefail

DEFAULT_BRANCH="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's@^origin/@@')"
if [ -z "$DEFAULT_BRANCH" ]; then
  DEFAULT_BRANCH="$(git remote show origin 2>/dev/null | sed -n 's/.*HEAD branch: //p')"
fi
if [ -z "$DEFAULT_BRANCH" ]; then
  DEFAULT_BRANCH="master"  # final fallback
fi

printf '%s\n' "$DEFAULT_BRANCH"
