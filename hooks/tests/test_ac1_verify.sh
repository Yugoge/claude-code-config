#!/usr/bin/env bash
set -u
TMPDIR_SELF=$(mktemp -d -t ac1-verify-XXXXXX)
trap 'rm -rf "$TMPDIR_SELF" 2>/dev/null' EXIT INT TERM
PUSH_EXEC="$TMPDIR_SELF/push.sh.exec"
sed -E 's/[[:space:]]*#.*$//' hooks/push.sh > "$PUSH_EXEC"
awk '
  BEGIN { abort = 0 }
  /(^|[[:space:]]|;|&&|\|\|)exit[[:space:]]+[1-9]/ { abort = 1 }
  /(^|[[:space:]]|;|&&|\|\|)return[[:space:]]+[1-9]/ { abort = 1 }
  /(^|[[:space:]]|;|&&|\|\|)exec[[:space:]]+[^[:space:]]+push\.sh/ { abort = 1 }
  /(^|[[:space:]]|;|&&|\|\|)exec[[:space:]]+[^[:space:]]+/ { abort = 1 }
  /(^|[[:space:]]|;|&&|\|\||\$\(|\`)git[[:space:]]+push/ {
    if (!abort) { print "AC1-V1 FAIL: executable git push reached without prior abort action at line " NR ": " $0 ; exit 1 }
  }
  END { exit 0 }
' "$PUSH_EXEC" && echo "AC1-V1 PASS"

echo "--- V2 ---"
grep -nE '\.validated|REQUEST_ID.*sentinel|REQUEST_ID.*\.sentinel' hooks/push.sh | head -5
echo "--- V3 ---"
grep -nE 'trap[[:space:]]+.+EXIT' hooks/push.sh | head -3
