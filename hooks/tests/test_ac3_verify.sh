#!/usr/bin/env bash
set -u
PHRASE="TodoWrite mark-as-in_progress for step N must precede any Agent() call dispatched within step N"

echo "=== AC3 V1 ==="
grep -nF "$PHRASE" commands/close.md | head -1 && echo "close.md PASS" || { echo "close.md FAIL"; exit 1; }
grep -nF "$PHRASE" commands/dev.md | head -1 && echo "dev.md PASS" || { echo "dev.md FAIL"; exit 1; }

run_v2() {
  local f="$1"
  awk -v PHRASE_RE='TodoWrite mark-as-in_progress for step N must precede any Agent\\(\\) call dispatched within step N' '
    BEGIN { in_fence=0; section=""; section_is_dispatch=0; phrase=0 }
    /^```/ { in_fence = !in_fence; next }
    in_fence { next }
    /^## / { section = $0
             section_is_dispatch = (section ~ /^## Step [0-9]/ || section ~ /[Aa]gent.*[Dd]ispatch/)
             if (section ~ /Appendix|Future Improvements|History|Changelog|Notes/) section_is_dispatch = 0 }
    /^### / { if ($0 ~ /^### Step [0-9]/) { section = $0; section_is_dispatch = 1 }
              if ($0 ~ /[Aa]gent.*[Dd]ispatch|TodoWrite/) section_is_dispatch = 1 }
    $0 ~ PHRASE_RE {
      if (!section_is_dispatch) { print "AC3-V2 FAIL: phrase outside dispatch section, in section: " section ; exit 1 }
      if ($0 ~ /(do not|skip|ignore|not required|optional|examples? of)/) { print "AC3-V2 FAIL: negating polarity at line " NR ": " $0 ; exit 1 }
      phrase = 1
    }
    END { if (!phrase) { print "AC3-V2 FAIL: phrase not found outside fences in " ARGV[1] ; exit 1 } ; print "AC3-V2 PASS for " ARGV[1]; exit 0 }
  ' "$f"
}

echo "=== AC3 V2 ==="
run_v2 commands/close.md || exit 1
run_v2 commands/dev.md || exit 1

echo "=== AC3 V3 ==="
grep -nF -A3 "$PHRASE" commands/close.md | grep -E 'MUST|REQUIRED|Always|Before dispatch' | head -1 && echo "close.md V3 PASS" || { echo "close.md V3 FAIL"; exit 1; }
grep -nF -A3 "$PHRASE" commands/dev.md | grep -E 'MUST|REQUIRED|Always|Before dispatch' | head -1 && echo "dev.md V3 PASS" || { echo "dev.md V3 FAIL"; exit 1; }

echo "=== V_TW ==="
jq -e '._test_writer_skip_reason | type == "string" and length > 0' docs/dev/context-20260519-211515.json && echo "context sentinel PASS"
grep -nE '_test_writer_skip_reason|test.writer.*skip|skip.*test.writer' commands/dev.md | head -3
