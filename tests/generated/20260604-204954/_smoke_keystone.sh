#!/usr/bin/env bash
# Smoke test for the keystone + selftest (dev self-verification, not an AC test).
set +e
REPO="$1"
KEYSTONE="$REPO/hooks/git-keystone/reference-transaction"
TMP="$(mktemp -d /tmp/keystone-smoke.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT
cd "$TMP" || exit 1
git init -q .
git config user.email t@t; git config user.name t
mkdir hooks; cp "$KEYSTONE" hooks/reference-transaction; chmod +x hooks/reference-transaction
git config core.hooksPath "$TMP/hooks"
git symbolic-ref HEAD refs/heads/master
echo x > f; git add f
echo "[1] normal commit (no marker): expect ALLOW"
git commit -qm init && echo "  PASS" || echo "  FAIL"
git branch other
echo "[2] overnight actor branch-switch (git 2.43 symref gap): expect ALLOW here"
CLAUDE_OVERNIGHT_ACTOR=1 git checkout other >/dev/null 2>&1 && echo "  switch allowed (2.43 expected)" || echo "  switch blocked (modern git)"
git checkout -q master 2>/dev/null
echo "[3] overnight actor commit on master (oid change): expect BLOCK"
CLAUDE_OVERNIGHT_ACTOR=1 git commit -q --allow-empty -m x >/dev/null 2>&1 && echo "  FAIL: allowed" || echo "  PASS: blocked"
echo "[4] overnight actor WITH blessed token: expect ALLOW"
GRANT_DIR="$TMP/grants"; mkdir -p "$GRANT_DIR"
TOK=abc123; printf '%s\n' "$(( $(date +%s)+60 ))" > "$GRANT_DIR/$TOK.grant"
CLAUDE_OVERNIGHT_ACTOR=1 CLAUDE_GIT_BLESSED_TOKEN=$TOK CLAUDE_GIT_BLESSED_GRANT_DIR="$GRANT_DIR" git commit -q --allow-empty -m blessed >/dev/null 2>&1 && echo "  PASS" || echo "  FAIL"
echo "[5] normal (non-overnight) master commit: expect ALLOW (no global lockdown)"
git commit -q --allow-empty -m normal2 >/dev/null 2>&1 && echo "  PASS" || echo "  FAIL"
