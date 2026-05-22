#!/usr/bin/env bash
set -u
echo "=== AC10 V1 ==="
grep -nF "### Verification harness cleanup contract (MANDATORY)" agents/qa.md
all_ok=1
for clause in \
  "DO NOT use this cleanup pattern to clean files outside the verification recipe's own temp artifacts" \
  "DO NOT bypass any PreToolUse / PostToolUse / Stop hook in the cleanup path" \
  "DO NOT broadcast signals to PIDs the recipe did not itself spawn" \
  "DO NOT edit \`docs/dev/specs/spec-20260520-044700.md\`"; do
  if grep -nF "$clause" agents/qa.md >/dev/null; then
    echo "  PASS: $clause"
  else
    echo "  FAIL: missing clause: $clause"
    all_ok=0
  fi
done
[ "$all_ok" -eq 1 ] && echo "AC10-V1 PASS" || { echo "AC10-V1 FAIL"; exit 1; }

echo "=== AC10 V2 ==="
awk '
  BEGIN { in_fence=0; in_section=0; init=0; trap_line=0; spawn=0 }
  /^### Verification harness cleanup contract \(MANDATORY\)/ { in_section=1; next }
  in_section && /^### / { in_section=0 }
  in_section && /^```/ { in_fence = !in_fence; next }
  in_section && /PID[[:space:]]*=[[:space:]]*""/ { init = NR }
  in_section && /trap[[:space:]].*EXIT/ && /"\$\{PID\}"/ { trap_line = NR }
  in_section && /PID=\$!/ { spawn = NR }
  END {
    if (!init) { print "AC10-V2 FAIL: PID=\"\" init line missing in subsection"; exit 1 }
    if (!trap_line) { print "AC10-V2 FAIL: trap line with EXIT and \"${PID}\" runtime ref missing"; exit 1 }
    if (!spawn) { print "AC10-V2 FAIL: PID=$! spawn capture missing"; exit 1 }
    if (!(init < trap_line && trap_line < spawn)) { print "AC10-V2 FAIL: ordering violated — init=" init " trap=" trap_line " spawn=" spawn; exit 1 }
    print "AC10-V2 PASS init=" init " trap=" trap_line " spawn=" spawn
    exit 0
  }
' agents/qa.md

echo "=== AC10 V3 ==="
grep -nE 'Verification harness cleanup contract|harness cleanup|trap.*EXIT INT TERM' agents/ba.md | head -3 || echo "AC10-V3 FAIL: no match in agents/ba.md"

echo "=== AC10 V4 ==="
n=$(git diff d988d4a -- docs/dev/specs/spec-20260520-044700.md | wc -l)
if [ "$n" -eq 0 ]; then echo "AC10-V4 PASS"; else echo "AC10-V4 FAIL: $n diff lines"; exit 1; fi

echo "=== AC10 V5 ==="
git log -n 1 d988d4a --format='%H %s'
