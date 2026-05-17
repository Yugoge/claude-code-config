#!/usr/bin/env bash
# Removes the force-close sentinel file for a given dev session.
# Errors are swallowed — sentinel cleanup must not block the close.
set -euo pipefail

SENTINEL_PATH="${1:-}"

if [[ -z "$SENTINEL_PATH" ]]; then
  echo "Usage: $0 <sentinel-path>" >&2
  exit 1
fi

rm -f "$SENTINEL_PATH" 2>/dev/null || true
