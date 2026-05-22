#!/usr/bin/env bash
set -u
echo "=== AC6 V1 ==="
awk '
  BEGIN { in_fence=0; section="" }
  /^```/ { in_fence = !in_fence; next }
  in_fence { next }
  /^## / { section = $0 }
  /if dev verification recipe differs from AC literal text, raise spec_text_vs_execution_drift regardless of equivalence judgment/ {
    sections[section]++
  }
  END {
    count = 0
    for (s in sections) { count++; print "  section: " s " (" sections[s] " hits)" }
    if (count < 2) { print "AC6-V1 FAIL: phrase in only " count " sections"; exit 1 }
    print "AC6-V1 PASS — phrase in " count " distinct ## sections"
    exit 0
  }
' agents/qa.md

echo "=== AC6 V2 ==="
awk '/^## .*BA.Validation.*Dimension|## .*spec_text_vs_execution_drift|## Counter-Evidence Authority/,/^## [^B#C]/' agents/qa.md | grep -F "if dev verification recipe differs from AC literal text, raise spec_text_vs_execution_drift regardless of equivalence judgment" | head -1 && echo "AC6-V2 PASS" || echo "AC6-V2 FAIL"

echo "=== AC6 V3 ==="
awk '/^## Verification Process|### Step 1: Success Criteria Validation/,/^### Step 2|^## /' agents/qa.md | grep -F "if dev verification recipe differs from AC literal text, raise spec_text_vs_execution_drift regardless of equivalence judgment" | head -1 && echo "AC6-V3 PASS" || echo "AC6-V3 FAIL"

echo "=== AC6 V4 ==="
n=$(grep -nF -A5 "if dev verification recipe differs from AC literal text, raise spec_text_vs_execution_drift regardless of equivalence judgment" agents/qa.md | grep -E 'MUST raise a blocking objection|verdict MUST be FAIL|MUST NOT downgrade to warning|is a blocking BA.validation objection' | wc -l)
echo "match count: $n"
if [ "$n" -ge 2 ]; then echo "AC6-V4 PASS"; else echo "AC6-V4 FAIL"; exit 1; fi
