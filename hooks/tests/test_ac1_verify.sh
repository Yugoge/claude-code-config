#!/usr/bin/env bash
set -u
sed -E 's/[[:space:]]*#.*$//' hooks/push.sh > /tmp/push.sh.exec
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
' /tmp/push.sh.exec && echo "AC1-V1 PASS"

echo "--- V2 ---"
grep -nE '\.validated|REQUEST_ID.*sentinel|REQUEST_ID.*\.sentinel' hooks/push.sh | head -5
echo "--- V3 ---"
grep -nE 'trap[[:space:]]+.+EXIT' hooks/push.sh | head -3
