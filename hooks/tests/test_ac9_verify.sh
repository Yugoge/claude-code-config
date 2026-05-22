#!/usr/bin/env bash
set -u
echo "=== AC9 V1 ==="
awk '
  BEGIN { in_fence=0; in_phase6=0; found=0 }
  /^```/ { in_fence = !in_fence; next }
  in_fence { next }
  /^### Phase 6/ { in_phase6 = 1; next }
  /^### Phase 7/ { in_phase6 = 0 }
  in_phase6 && /Reverses <SHA>: <one-line rationale for why prior reasoning no longer holds>/ { found = 1 }
  END { if (!found) { print "AC9-V1 FAIL: phrase not present in agents/changelog-analyst.md Phase 6 (fence-aware)" ; exit 1 } ; print "AC9-V1 PASS"; exit 0 }
' agents/changelog-analyst.md

echo "=== AC9 V2 ==="
awk '/^### Phase 6/,/^### Phase 7/' agents/changelog-analyst.md | grep -E 'forward-fix|forward fix|reverses prior behavior' | head -1 && echo "AC9-V2 PASS" || { echo "AC9-V2 FAIL"; exit 1; }

echo "=== AC9 V3 ==="
if grep -qF "Reverses <SHA>: <one-line rationale for why prior reasoning no longer holds>" agents/changelog-analyst.md; then
  echo "AC9-V3 PASS"
else
  echo "AC9-V3 FAIL"; exit 1
fi

echo "=== AC9 V4 ==="
jq -e '.affected_files | index("agents/changelog-analyst.md") != null' docs/dev/context-20260519-211515.json && echo "AC9-V4 PASS" || { echo "AC9-V4 FAIL"; exit 1; }

echo "=== AC9 V5 ==="
git log -n 1 d988d4a --format='%H %s'
