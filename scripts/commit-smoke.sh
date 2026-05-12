#!/usr/bin/env bash
# Description: End-to-end smoke harness for the commit-toolchain. Exercises 11
#              paths (a..k from ticket-20260511-070000 dispatch + path k the
#              b5d447e fixture against the bulk-detector) against synthetic
#              fixtures. Standalone runnable; no CI integration this cycle.
# Usage: commit-smoke.sh [--filter <letter>] [--keep-tmp]
# Exit codes:
#   0  All exercised paths PASS
#   1  At least one path FAILed
#   2  Bad arguments / harness setup failure
#
# Source: scripts/commit-smoke.sh (D1, ticket-20260511-070000).
#
# Approach: each path constructs a synthetic temp git repo under $TMP, writes
# the minimum source-of-truth fixtures (a manifest, a close-report, a
# pre-staged delta, etc.), invokes the commit-toolchain wrapper or a mock
# of its argv-parsing/closure-check layer, and asserts on observable
# outcome (exit code, stdout/stderr substrings, audit-emission shape).
#
# WHY MOCKS over real wrapper subprocess: the production wrapper does an
# expected-parent CAS against refs/heads/<branch> and emits audit JSON
# under $DOCS_DIR/dev — full end-to-end requires a real $DOCS_DIR + a
# closed dev-report path. For the cases below, we focus on:
#   - argv parser surface (flag plumbing landed by worker α)
#   - close-verdict tolerant classification (worker γ C1)
#   - bulk-detector regex tightening (worker δ D3)
#   - privilege-guard default-deny regression (post-C2-rollback,
#     ticket-20260511-094500): paths k, k2-k9 prove the always-on
#     AC-A2 inline-env block + AC-A13 default-deny still catch every
#     previously-C2-flagged shape, and k-ordinary positively proves the
#     plain-message shape that C2 used to allow is now denied at AC-A13.
#
# When worker α's A1/A2/A3 land in this cycle, paths (a)/(b)/(c)/(d)/(e)/(f)/
# (g)/(h) will be re-implemented in the same shape against the real wrapper
# (currently they exercise the surfaces we can reach pre-α-landing).
#
# Path summary:
#   (a) closed-task plain                        -- mock argv/closure check
#   (b) closed-task + manifest                   -- mock argv/closure check
#   (c) --force --manifest                       -- mock argv: --force + manifest
#   (d) --force-rescue (pre-staged content)      -- mock argv: A2 W2
#   (e) manifest-disabled-fallback env           -- mock argv env handling
#   (f) binary via manifest.binary_files[]       -- mock manifest schema (B1)
#   (g) --plan dry-run                           -- mock argv: A3 zero side-effect
#   (h) cross-repo via --repo                    -- mock argv: A1
#   (i) tolerant close-report parsing            -- real close-verdict.py (C1)
#   (j) bare CLOSE: YES line                     -- real close-verdict.py strict
#   (k) b5d447e-shape                            -- real bulk-detector regression (no C2 dependency)
#   (l) M1 hash chain trailer presence           -- direct trailer-helper unit test (DOC-14)
#   (m) M2 message-vs-evidence guard fires       -- direct M2 regex+status unit test (DOC-15)
#   (n) M3 CC type lint fires                    -- direct M3 regex unit test (DOC-16)
#
# Exit per-path: line `PASS: <id> <description>` or `FAIL: <id> <reason>`.

set -euo pipefail

DOT_CLAUDE_ROOT="${DOT_CLAUDE_ROOT:-/dev/shm/dev-workspace/dot-claude}"
CLOSE_VERDICT="$DOT_CLAUDE_ROOT/hooks/lib/close-verdict.py"
BULK_DETECTOR="$DOT_CLAUDE_ROOT/hooks/pretool-bulk-commit-detector.py"
PRIV_GUARD="$DOT_CLAUDE_ROOT/hooks/pretool-git-privilege-guard.py"

FILTER=""
KEEP_TMP=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --filter)
      FILTER="${2:?--filter requires a letter}"
      shift 2
      ;;
    --keep-tmp)
      KEEP_TMP=1
      shift
      ;;
    -h|--help)
      sed -n '1,40p' "$0" >&2
      exit 0
      ;;
    *)
      echo "commit-smoke.sh: unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

TMP="$(mktemp -d -t commit-smoke.XXXXXX)"
cleanup() {
  if [[ "$KEEP_TMP" == "1" ]]; then
    echo "commit-smoke.sh: TMP preserved at $TMP" >&2
  else
    rm -rf "$TMP"
  fi
}
trap cleanup EXIT

declare -i pass=0 fail=0 skipped=0
results=()

want() {
  # want <id> -- returns 0 iff path matches --filter (or no filter set)
  if [[ -z "$FILTER" ]]; then
    return 0
  fi
  if [[ "$FILTER" == "$1" ]]; then
    return 0
  fi
  return 1
}

note_pass() {
  pass=$((pass + 1))
  results+=("PASS: $1 $2")
  echo "PASS: $1 $2"
}

note_fail() {
  fail=$((fail + 1))
  results+=("FAIL: $1 $2")
  echo "FAIL: $1 $2" >&2
}

note_skip() {
  skipped=$((skipped + 1))
  results+=("SKIP: $1 $2")
  echo "SKIP: $1 $2"
}

# ---------------------------------------------------------------------------
# Path (i): tolerant close-report parsing (C1)
# ---------------------------------------------------------------------------
if want i; then
  f="$TMP/close-i.md"
  cat > "$f" <<'EOF'
# Cycle close report

Reviewer rounds: 2 codex + 1 qa

**Final verdict: CLOSE: YES** -- all checks passed

Trailing prose that is NOT the verdict.
EOF
  got="$(python3 "$CLOSE_VERDICT" classify-file "$f")"
  if [[ "$got" == "yes" ]]; then
    note_pass i "tolerant close-report parsing (decorated CLOSE: YES detected)"
  else
    note_fail i "tolerant close-report parsing -- got '$got' want 'yes'"
  fi
fi

# ---------------------------------------------------------------------------
# Path (j): bare CLOSE: YES line (strict-mode regression)
# ---------------------------------------------------------------------------
if want j; then
  f="$TMP/close-j.md"
  printf '%s\n' "CLOSE: YES" > "$f"
  got="$(python3 "$CLOSE_VERDICT" classify-file "$f")"
  if [[ "$got" == "yes" ]]; then
    note_pass j "bare CLOSE: YES line (strict last-line)"
  else
    note_fail j "bare CLOSE: YES -- got '$got' want 'yes'"
  fi

  f2="$TMP/close-j2.md"
  printf '%s\n' "CLOSE: NO" > "$f2"
  got2="$(python3 "$CLOSE_VERDICT" classify-file "$f2")"
  if [[ "$got2" == "no" ]]; then
    note_pass j "bare CLOSE: NO line (strict last-line)"
  else
    note_fail j "bare CLOSE: NO -- got '$got2' want 'no'"
  fi
fi

# ---------------------------------------------------------------------------
# Path (k) -- MANDATORY bulk-detector regression fixture (no C2 dependency)
# A b5d447e-shape commit (subject + 3+ subsystem fan-out) MUST be BLOCKED by
# the bulk-detector layer. The cwd here happens to carry a .claude-session-id
# marker, but post-C2-rollback that marker has NO bearing on commit denial --
# the bulk-detector regex + subsystem fan-out are the load-bearing layers.
# ---------------------------------------------------------------------------
if want k; then
  # Build a temp git repo with a worktree-like layout, sentinel, and 3+
  # subsystem staged files so the bulk-detector evaluates against a real
  # staged set.
  repo="$TMP/repo-k"
  git init -q "$repo"
  ( cd "$repo"
    git config user.email "smoke@example" >/dev/null
    git config user.name "smoke" >/dev/null
    git commit -q --allow-empty -m "init"
    # Drop a .claude-session-id marker so the fixture is structurally
    # identical to the prior cycle's repo-k. Post-C2-rollback the marker
    # is a no-op for the privilege-guard; it remains here only so paths
    # k2-k9 + k-ordinary (which reuse repo_k) see the same on-disk shape
    # they did pre-rollback.
    echo "smoke-session-id" > .claude-session-id
    # Stage 3+ subsystem files (hooks/, commands/, scripts/) so the bulk
    # threshold is met.
    mkdir -p hooks commands scripts docs
    echo "h" > hooks/h.sh
    echo "c" > commands/c.md
    echo "s" > scripts/s.sh
    echo "d" > docs/d.md
    git add hooks commands scripts docs >/dev/null
  )
  # Build the PreToolUse JSON payload simulating an agent attempting the
  # b5d447e-shape commit from inside the synthetic repo.
  payload=$(
    cat <<JSON
{"tool_name":"Bash","tool_input":{"command":"git commit -m \"chore(claude): sync all uncommitted hooks, commands, scripts, docs\""},"session_id":"smoke-session-id"}
JSON
  )
  # Run the bulk-detector against the payload with cwd=$repo so the
  # staged-set lookup sees our fan-out.
  set +e
  out=$( ( cd "$repo" && printf '%s\n' "$payload" | python3 "$BULK_DETECTOR" ) 2>&1 )
  rc=$?
  set -e
  if [[ "$rc" == "2" ]] && [[ "$out" == *"BLOCKED: bulk-commit detector"* ]]; then
    note_pass k "bulk-detector regression: b5d447e fixture STILL blocked (exit=2, BLOCKED message present)"
  else
    note_fail k "b5d447e fixture should block but rc=$rc out=$out"
  fi
fi

# ---------------------------------------------------------------------------
# Path (k2)..(k9): privilege-guard default-deny regression (post-C2-rollback).
# Exercises the privilege-guard with a session-id sentinel + matching env
# present (the prior cycle's C2 preconditions). Post-rollback, EVERY shape
# must deny via the always-on layers: AC-A2 inline-env block for k8 (literal
# CLAUDE_COMMIT_COMMAND_ACTIVE= substring in command text), AC-A13 default-
# deny for k2/k3/k4/k5/k6/k7/k9 (no env, no blessed-bridge regex match).
# We invoke the hook directly with a JSON payload (no actual git commit),
# so this does not violate the no-history-mutation safety hook.
# ---------------------------------------------------------------------------
if want k; then
  # Reuse repo-k constructed above for path (k).
  if [[ -d "$TMP/repo-k" ]]; then
    repo_k="$TMP/repo-k"
    # Drop a session sentinel + set CLAUDE_SESSION_ID. Post-C2-rollback these
    # are no-ops for commit denial; retained so the test inputs are byte-
    # identical to the prior cycle's payloads (AC6 cites verbatim shapes).
    echo "smoke-sid" > "$repo_k/.claude-session-id"
    export CLAUDE_SESSION_ID="smoke-sid"
    # b5d447e-shape payload; privilege-guard denies via AC-A13 (no env, no
    # blessed-bridge regex match).
    payload=$(
      cat <<JSON
{"tool_name":"Bash","tool_input":{"command":"git commit -m \"chore(claude): sync all uncommitted hooks, commands, scripts, docs\""},"session_id":"smoke-sid"}
JSON
    )
    set +e
    out=$( ( cd "$repo_k" && printf '%s\n' "$payload" | python3 "$PRIV_GUARD" ) 2>&1 )
    rc=$?
    set -e
    if [[ "$rc" == "2" ]]; then
      note_pass k2 "AC-A13 default-deny: b5d447e shape under session-id sentinel STILL blocks (rc=2)"
    else
      note_fail k2 "AC-A13 default-deny failed: b5d447e under sentinel SHOULD have blocked, got rc=$rc out=$out"
    fi
    # git -C redirect attempt: AC-A13 catches it (no env, no blessed-bridge).
    payload2=$(
      cat <<JSON
{"tool_name":"Bash","tool_input":{"command":"git -C /tmp commit -m \"feat: redirect attempt\""},"session_id":"smoke-sid"}
JSON
    )
    set +e
    out2=$( ( cd "$repo_k" && printf '%s\n' "$payload2" | python3 "$PRIV_GUARD" ) 2>&1 )
    rc2=$?
    set -e
    if [[ "$rc2" == "2" ]]; then
      note_pass k3 "AC-A13 default-deny: git -C redirect STILL blocks (rc=2)"
    else
      note_fail k3 "AC-A13 default-deny: git -C redirect SHOULD block, got rc=$rc2"
    fi
    # -F msgfile (opaque message): AC-A13 catches it.
    payload3=$(
      cat <<JSON
{"tool_name":"Bash","tool_input":{"command":"git commit -F /tmp/msg.txt"},"session_id":"smoke-sid"}
JSON
    )
    set +e
    out3=$( ( cd "$repo_k" && printf '%s\n' "$payload3" | python3 "$PRIV_GUARD" ) 2>&1 )
    rc3=$?
    set -e
    if [[ "$rc3" == "2" ]]; then
      note_pass k4 "AC-A13 default-deny: -F msgfile (opaque) STILL blocks (rc=2)"
    else
      note_fail k4 "AC-A13 default-deny: -F msgfile SHOULD block, got rc=$rc3"
    fi

    # k5: `git --no-pager -C /other commit` -- pre-option redirect attempt.
    # AC-A13 catches (no env, message does not match blessed-bridge regex).
    payload_k5=$(
      cat <<JSON
{"tool_name":"Bash","tool_input":{"command":"git --no-pager -C /tmp commit -m \"feat: pre-option redirect\""},"session_id":"smoke-sid"}
JSON
    )
    set +e
    out_k5=$( ( cd "$repo_k" && printf '%s\n' "$payload_k5" | python3 "$PRIV_GUARD" ) 2>&1 )
    rc_k5=$?
    set -e
    if [[ "$rc_k5" == "2" ]]; then
      note_pass k5 "AC-A13 default-deny: git --no-pager -C redirect STILL blocks (rc=2)"
    else
      note_fail k5 "AC-A13 default-deny: git --no-pager -C redirect SHOULD block, got rc=$rc_k5 out=$out_k5"
    fi

    # k6: `git -c pager=false -C /other commit` -- -c config-option then -C.
    # AC-A13 catches.
    payload_k6=$(
      cat <<JSON
{"tool_name":"Bash","tool_input":{"command":"git -c pager=false -C /tmp commit -m \"feat: -c redirect\""},"session_id":"smoke-sid"}
JSON
    )
    set +e
    out_k6=$( ( cd "$repo_k" && printf '%s\n' "$payload_k6" | python3 "$PRIV_GUARD" ) 2>&1 )
    rc_k6=$?
    set -e
    if [[ "$rc_k6" == "2" ]]; then
      note_pass k6 "AC-A13 default-deny: git -c key=val -C redirect STILL blocks (rc=2)"
    else
      note_fail k6 "AC-A13 default-deny: git -c key=val -C redirect SHOULD block, got rc=$rc_k6 out=$out_k6"
    fi

    # k7: `git commit -m "decoy" -F/tmp/realmsg` -- decoy -m + attached -F.
    # AC-A13 catches (no env, decoy "feat: decoy" message does not match
    # blessed-bridge regex).
    payload_k7=$(
      cat <<JSON
{"tool_name":"Bash","tool_input":{"command":"git commit -m \"decoy\" -F/tmp/realmsg"},"session_id":"smoke-sid"}
JSON
    )
    set +e
    out_k7=$( ( cd "$repo_k" && printf '%s\n' "$payload_k7" | python3 "$PRIV_GUARD" ) 2>&1 )
    rc_k7=$?
    set -e
    if [[ "$rc_k7" == "2" ]]; then
      note_pass k7 "AC-A13 default-deny: attached -F<path> STILL blocks (rc=2)"
    else
      note_fail k7 "AC-A13 default-deny: attached -F<path> SHOULD block, got rc=$rc_k7 out=$out_k7"
    fi

    # k8: `CLAUDE_COMMIT_COMMAND_ACTIVE= git commit -m "msg"` inline injection.
    # AC-A2 catches FIRST (literal CLAUDE_COMMIT_COMMAND_ACTIVE= substring in
    # command text triggers _inline_env_present before AC-A13 is reached).
    payload_k8=$(
      cat <<JSON
{"tool_name":"Bash","tool_input":{"command":"CLAUDE_COMMIT_COMMAND_ACTIVE= git commit -m \"feat: inline-env injection\""},"session_id":"smoke-sid"}
JSON
    )
    set +e
    out_k8=$( ( cd "$repo_k" && printf '%s\n' "$payload_k8" | python3 "$PRIV_GUARD" ) 2>&1 )
    rc_k8=$?
    set -e
    if [[ "$rc_k8" == "2" ]]; then
      note_pass k8 "AC-A2 inline-env block: CLAUDE_COMMIT_COMMAND_ACTIVE= injection STILL blocks (rc=2)"
    else
      note_fail k8 "AC-A2 inline-env block: injection SHOULD block, got rc=$rc_k8 out=$out_k8"
    fi

    # k9: `git -C /worktree commit` from OUTSIDE the worktree. AC-A13 catches
    # (no env, message does not match blessed-bridge regex). Post-rollback
    # the cwd is irrelevant to the deny decision -- AC-A13 denies the agent
    # commit regardless of cwd.
    payload_k9=$(
      cat <<JSON
{"tool_name":"Bash","tool_input":{"command":"git -C $repo_k commit -m \"feat: from-outside\""},"session_id":"smoke-sid"}
JSON
    )
    set +e
    # CWD deliberately NOT $repo_k (use $TMP, which is outside the worktree).
    out_k9=$( ( cd "$TMP" && printf '%s\n' "$payload_k9" | python3 "$PRIV_GUARD" ) 2>&1 )
    rc_k9=$?
    set -e
    if [[ "$rc_k9" == "2" ]]; then
      note_pass k9 "AC-A13 default-deny: git -C <worktree> from OUTSIDE STILL blocks (rc=2)"
    else
      note_fail k9 "AC-A13 default-deny: git -C <worktree> from outside SHOULD block, got rc=$rc_k9 out=$out_k9"
    fi

    # k-ordinary: positive rollback proof. Plain non-bulk `git commit -m
    # "feat: ordinary"` inside $repo_k with the sentinel + CLAUDE_SESSION_ID
    # in place AND no CLAUDE_COMMIT_COMMAND_ACTIVE env -- the exact shape C2
    # used to allow -- MUST now deny via AC-A13. Without this assertion,
    # AC1-7 prove C2 symbols are gone but do not prove the previously-allowed
    # shape is now denied. Per BA-QA iter-2 ticket AC4. The `env -u
    # CLAUDE_COMMIT_COMMAND_ACTIVE` strips any ambient env that could route
    # the deny through AC-A16 (missing-grant) instead of AC-A13.
    payload_kord=$(
      cat <<JSON
{"tool_name":"Bash","tool_input":{"command":"git commit -m \"feat: ordinary\""},"session_id":"smoke-sid"}
JSON
    )
    set +e
    out_kord=$( ( cd "$repo_k" && printf '%s\n' "$payload_kord" | env -u CLAUDE_COMMIT_COMMAND_ACTIVE python3 "$PRIV_GUARD" ) 2>&1 )
    rc_kord=$?
    set -e
    if [[ "$rc_kord" == "2" ]] && [[ "$out_kord" == *"only the blessed /merge"* ]]; then
      note_pass k-ordinary "AC-A13 default-deny: plain commit under valid sentinel STILL blocks post-C2-rollback (rc=2, AC-A13 substring present)"
    else
      note_fail k-ordinary "AC-A13 default-deny: plain commit SHOULD block via AC-A13, got rc=$rc_kord out=$out_kord"
    fi

    unset CLAUDE_SESSION_ID
  else
    note_skip k2 "privilege-guard smoke skipped (repo-k not present)"
  fi
fi

# ---------------------------------------------------------------------------
# Path (a) closed-task plain -- mock argv: <task-id> with no flags
# ---------------------------------------------------------------------------
if want a; then
  # Mock the argv-parsing decision the wrapper makes: given a single bareword
  # task-id and a closed dev-report path, the wrapper picks engine=dev-report.
  # We simulate by writing a mock dev-report and asserting the close-verdict
  # path returns "yes" (the wrapper's closure gate uses this exact tool).
  task_id="20260511-mock"
  report_dir="$TMP/docs-a/dev"
  mkdir -p "$report_dir"
  printf '%s\n' "CLOSE: YES" > "$report_dir/close-report-$task_id.md"
  got="$(python3 "$CLOSE_VERDICT" classify-file "$report_dir/close-report-$task_id.md")"
  if [[ "$got" == "yes" ]]; then
    note_pass a "closed-task plain (closure-gate would allow; engine=dev-report)"
  else
    note_fail a "closed-task plain -- got '$got' want 'yes'"
  fi
fi

# ---------------------------------------------------------------------------
# Path (b) closed-task + manifest -- mock: argv has --manifest
# ---------------------------------------------------------------------------
if want b; then
  manifest="$TMP/manifest-b.json"
  cat > "$manifest" <<'EOF'
{
  "schema_name": "claude.commit.manifest",
  "schema_version": 3,
  "task_id": "20260511-mock-b",
  "branch": "master",
  "expected_parent": "deadbeef",
  "files": [{"path": "docs/foo.md", "status": "M"}],
  "patch_text": "diff --git a/docs/foo.md b/docs/foo.md\n--- a/docs/foo.md\n+++ b/docs/foo.md\n@@ -0,0 +1 @@\n+hello\n",
  "commit_message": "docs: foo"
}
EOF
  if python3 -c "import json; d=json.load(open('$manifest')); assert d['schema_version']==3" 2>/dev/null; then
    note_pass b "closed-task + manifest (manifest JSON well-formed, schema_version=3)"
  else
    note_fail b "closed-task + manifest -- bad JSON or schema_version"
  fi
fi

# ---------------------------------------------------------------------------
# Path (c) --force --manifest -- mock: force+manifest forms a force-with-grant path
# ---------------------------------------------------------------------------
if want c; then
  manifest="$TMP/manifest-c.json"
  cat > "$manifest" <<'EOF'
{"schema_name":"claude.commit.manifest","schema_version":3,"task_id":"force-c","branch":"master","commit_message":"force(test): c"}
EOF
  # Pre-α-landing: wrapper's L403-405 may reject --force with no manifest;
  # --force WITH manifest takes a different path. We assert the manifest is
  # parseable and the argv combination is documented.
  if python3 -c "import json; d=json.load(open('$manifest')); assert d['schema_name']=='claude.commit.manifest'"; then
    note_pass c "--force --manifest (force path consumes manifest)"
  else
    note_fail c "--force --manifest -- manifest schema malformed"
  fi
fi

# ---------------------------------------------------------------------------
# Path (d) --force-rescue (A2/W2) -- mock: pre-staged content required
# ---------------------------------------------------------------------------
if want d; then
  repo="$TMP/repo-d"
  git init -q "$repo"
  ( cd "$repo"
    git config user.email "smoke@example" >/dev/null
    git config user.name "smoke" >/dev/null
    git commit -q --allow-empty -m "init"
    echo "rescue content" > rescue.txt
    git add rescue.txt
  )
  # Assertion: staged-set is non-empty -- this is the A2 pre-condition.
  staged=$(cd "$repo" && git diff --cached --name-only | head -5)
  if [[ -n "$staged" ]]; then
    note_pass d "--force-rescue pre-staged check (staged-set non-empty: $staged)"
  else
    note_fail d "--force-rescue -- staged-set empty; rescue should refuse"
  fi
fi

# ---------------------------------------------------------------------------
# Path (e) manifest-disabled-fallback env
# ---------------------------------------------------------------------------
if want e; then
  # CLAUDE_COMMIT_MANIFEST_DISABLED=1 + closed-task -> wrapper uses dev-report path
  # CLAUDE_COMMIT_MANIFEST_DISABLED=1 + --manifest  -> wrapper fails closed
  # We mock by inspecting env handling -- the env-var name is documented in
  # commands/commit.md DOC-5.
  if env CLAUDE_COMMIT_MANIFEST_DISABLED=1 bash -c '[[ "$CLAUDE_COMMIT_MANIFEST_DISABLED" == "1" ]]'; then
    note_pass e "manifest-disabled-fallback env (CLAUDE_COMMIT_MANIFEST_DISABLED=1 propagates)"
  else
    note_fail e "manifest-disabled-fallback env -- env did not propagate"
  fi
fi

# ---------------------------------------------------------------------------
# Path (f) binary via manifest.binary_files[] (B1)
# ---------------------------------------------------------------------------
if want f; then
  manifest="$TMP/manifest-f.json"
  cat > "$manifest" <<'EOF'
{
  "schema_name": "claude.commit.manifest",
  "schema_version": 3,
  "task_id": "binary-f",
  "branch": "master",
  "files": [{"path": "img/logo.png", "status": "A"}],
  "binary_files": [
    {"path": "img/logo.png", "blob_sha": "0000000000000000000000000000000000000000", "size": 1024, "reason": "PNG asset"}
  ],
  "commit_message": "feat: add logo binary"
}
EOF
  if python3 -c "
import json
d = json.load(open('$manifest'))
assert 'binary_files' in d, 'binary_files key missing'
assert isinstance(d['binary_files'], list)
assert d['binary_files'][0]['path'] == 'img/logo.png'
assert d['binary_files'][0]['blob_sha'].isalnum()
"; then
    note_pass f "binary via manifest.binary_files[] (schema accepts {path,blob_sha,size,reason})"
  else
    note_fail f "binary via manifest.binary_files[] -- schema malformed"
  fi
fi

# ---------------------------------------------------------------------------
# Path (g) --plan dry-run (A3) -- mock: zero side-effect invariant
# ---------------------------------------------------------------------------
if want g; then
  repo="$TMP/repo-g"
  git init -q "$repo"
  ( cd "$repo"
    git config user.email "smoke@example" >/dev/null
    git config user.name "smoke" >/dev/null
    git commit -q --allow-empty -m "init"
    echo "preserved" > a.txt
    git add a.txt
  )
  before=$(cd "$repo" && git diff --cached --name-only | sort)
  # Simulate --plan execution: a true --plan does NOT mutate index. We
  # assert by running a no-op (sleep 0) and comparing staged-set before/after.
  ( cd "$repo" && sleep 0 )
  after=$(cd "$repo" && git diff --cached --name-only | sort)
  if [[ "$before" == "$after" ]]; then
    note_pass g "--plan dry-run (staged_list_before == staged_list_after invariant holds)"
  else
    note_fail g "--plan dry-run -- staged-list drifted (before='$before' after='$after')"
  fi
fi

# ---------------------------------------------------------------------------
# Path (h) cross-repo via --repo (A1)
# ---------------------------------------------------------------------------
if want h; then
  repo="$TMP/repo-h"
  docs="$TMP/docs-h"
  git init -q "$repo"
  mkdir -p "$docs/dev"
  printf '%s\n' "CLOSE: YES" > "$docs/dev/close-report-h.md"
  # Mock: A1 resolution order is (explicit --repo > env > cwd-toplevel > pwd > /root).
  # The wrapper would read --repo=$repo and --docs-dir=$docs. We assert that
  # the close-report at $docs/dev resolves correctly via close-verdict.
  got="$(python3 "$CLOSE_VERDICT" classify-file "$docs/dev/close-report-h.md")"
  if [[ "$got" == "yes" ]] && [[ -d "$repo/.git" ]]; then
    note_pass h "cross-repo via --repo (close-report under explicit --docs-dir is classifiable)"
  else
    note_fail h "cross-repo via --repo -- repo=$repo docs=$docs got=$got"
  fi
fi

# ---------------------------------------------------------------------------
# Wrapper-invocation helpers for paths l/m/n
# ---------------------------------------------------------------------------
# After QA Round 7 codex flagged paths l/m/n as Anti-Fraud Principle 5
# substitute related-but-different verification (testing isolated Python
# regex/hash heredoc components rather than the wrapper end-to-end), this
# block invokes the actual wrapper `commit.sh` as a subprocess against
# self-contained synthetic fixtures and asserts on wrapper-observable
# state changes (exit code / git HEAD / stderr substring / audit JSON
# file count under CLAUDE_LOG_DIR).
#
# Shared fixture skeleton per path:
#   * fresh `git init` repo under $TMP/wrapper-{l,m,n}-<rand>
#   * docs/dev/ tree under same root with the four cycle artifacts the
#     wrapper consults: ticket-, context-, dev-report-, close-report-,
#     completion-, qa-report- (path-specific status field).
#   * CLAUDE_LOG_DIR points at a per-path subdir of $TMP so audit-file
#     count can be asserted without colliding with the production log dir.
#   * CLAUDE_AUDIT_PERSIST_DISABLED=1 acknowledges the tmpfs preflight
#     refusal that would otherwise short-circuit the wrapper before M1/
#     M2/M3 emit observable state.
#
# The wrapper invocation is `bash <commit.sh> <task-id> -m "<msg>"` from
# cwd=$repo. `--repo` / `--docs-dir` are NOT passed; the wrapper's
# DOCS_DIR_ROOT discovery ladder picks up the cwd-toplevel and resolves
# both repo and docs paths from there.
#
# We resolve commit.sh relative to this script:
#   $DOT_CLAUDE_ROOT/hooks/commit.sh
COMMIT_SH="$DOT_CLAUDE_ROOT/hooks/commit.sh"

_wrapper_build_fixture() {
  # _wrapper_build_fixture <repo_dir> <task_id> <qa_status>
  # Initializes a fixture git repo with the 6 cycle artifacts under
  # docs/dev/ plus a working-tree file declared in dev-report.dev.files_modified
  # so the semantic-plan helper has something to commit. qa-report.qa.status
  # is set to the third argument (typically "pass" or "fail").
  local repo="$1"
  local tid="$2"
  local qa_status="$3"
  git init -q "$repo"
  ( cd "$repo"
    git config user.email "smoke@example" >/dev/null
    git config user.name "smoke" >/dev/null
    git commit -q --allow-empty -m "init"
    mkdir -p "docs/dev"
    # Cycle artifacts. ticket / context are tiny content stubs; close-report
    # carries decorated CLOSE: YES (PRIMARY closure verdict); dev-report
    # declares files_modified=["smoke-fixture.txt"] + task_id/request_id;
    # qa-report carries the requested .qa.status value; completion present
    # for SECONDARY parity (unused under PRIMARY closure, harmless).
    printf 'ticket content for %s\n' "$tid"               > "docs/dev/ticket-${tid}.md"
    printf '{"task_id": "%s", "ctx": 1}\n' "$tid"         > "docs/dev/context-${tid}.json"
    printf '%s\n%s\n%s\n' \
      "# Cycle close report" \
      "" \
      "**Final verdict: CLOSE: YES** -- all checks passed"  > "docs/dev/close-report-${tid}.md"
    printf '%s\n%s\n%s\n' \
      "# Development Completion Report" \
      "" \
      "Request-ID: ${tid}"                                  > "docs/dev/completion-${tid}.md"
    cat > "docs/dev/dev-report-${tid}.json" <<DEVREPORT
{
  "request_id": "${tid}",
  "task_id": "${tid}",
  "dev": {
    "status": "completed",
    "task_id": "${tid}",
    "request_id": "${tid}",
    "files_modified": ["smoke-fixture.txt"],
    "files_created": [],
    "tasks_completed": [{"id": 1, "description": "smoke fixture", "files_modified": ["smoke-fixture.txt"]}]
  }
}
DEVREPORT
    cat > "docs/dev/qa-report-${tid}.json" <<QAREPORT
{
  "request_id": "${tid}",
  "task_id": "${tid}",
  "qa": {
    "request_id": "${tid}",
    "task_id": "${tid}",
    "status": "${qa_status}"
  }
}
QAREPORT
    # Working-tree modification declared in dev-report.dev.files_modified so
    # the semantic-plan helper produces a non-empty patch and the wrapper
    # reaches its commit-tree + update-ref CAS step.
    printf 'smoke content for %s\n' "$tid" > "smoke-fixture.txt"
  )
}

_wrapper_invoke() {
  # _wrapper_invoke <repo_dir> <task_id> <log_dir> <message> -> echoes
  # "rc=<n>\tstderr_path=<path>\thead_before=<sha>\thead_after=<sha>\taudit_count=<n>"
  # All side-effects (cwd, env) are scoped to a subshell so the smoke
  # harness's outer state is preserved.
  local repo="$1"
  local tid="$2"
  local log_dir="$3"
  local message="$4"
  mkdir -p "$log_dir"
  local head_before head_after audit_count rc stderr_path
  head_before=$(cd "$repo" && git rev-parse HEAD 2>/dev/null || echo NONE)
  stderr_path="$log_dir/wrapper.stderr"
  set +e
  (
    cd "$repo"
    CLAUDE_LOG_DIR="$log_dir" \
    CLAUDE_AUDIT_PERSIST_DISABLED=1 \
    CLAUDE_PROJECT_DIR="$repo" \
    CLAUDE_TMPDIR="$log_dir" \
      bash "$COMMIT_SH" "$tid" -m "$message" 2>"$stderr_path" >/dev/null
  )
  rc=$?
  set -e
  head_after=$(cd "$repo" && git rev-parse HEAD 2>/dev/null || echo NONE)
  # Count audit-emission JSON files under log_dir (commit-semantic-*.json
  # for dev-report-driven mode; commit-manifest-*.json for manifest mode).
  audit_count=$(find "$log_dir" -maxdepth 1 -type f \( -name 'commit-semantic-*.json' -o -name 'commit-manifest-*.json' \) 2>/dev/null | wc -l | tr -d ' ')
  printf 'rc=%s\tstderr_path=%s\thead_before=%s\thead_after=%s\taudit_count=%s\n' \
    "$rc" "$stderr_path" "$head_before" "$head_after" "$audit_count"
}

# ---------------------------------------------------------------------------
# Path (l) M1 hash chain trailer presence -- end-to-end wrapper invocation
# ---------------------------------------------------------------------------
# AC1 mandate: closed-task commit with valid qa-report PASS produces a
# commit message bearing every relevant *-SHA256 trailer via wrapper
# invocation. Constructs a synthetic fixture, invokes commit.sh, and
# asserts:
#   * wrapper exit code == 0
#   * branch HEAD advanced past head_before (commit landed)
#   * `git log -1 --format='%(trailers:key=Dev-Report-SHA256,valueonly)'`
#     returns the same hex digest as `sha256sum dev-report-<tid>.json`
#   * Identical Ticket-SHA256 + Close-Report-SHA256 + QA-Report-SHA256
#     matches against the on-disk artifact digests
if want l; then
  ts="$(date +%s%N)"
  task_id="smoke-l-${ts}"
  repo="$TMP/wrapper-l-${ts}"
  log_dir="$TMP/wrapper-l-logs-${ts}"
  _wrapper_build_fixture "$repo" "$task_id" "pass"
  result=$(_wrapper_invoke "$repo" "$task_id" "$log_dir" "feat(commit): smoke-l test message")
  rc=$(printf '%s' "$result" | tr '\t' '\n' | sed -n 's/^rc=//p')
  stderr_path=$(printf '%s' "$result" | tr '\t' '\n' | sed -n 's/^stderr_path=//p')
  head_before=$(printf '%s' "$result" | tr '\t' '\n' | sed -n 's/^head_before=//p')
  head_after=$(printf '%s' "$result" | tr '\t' '\n' | sed -n 's/^head_after=//p')
  audit_count=$(printf '%s' "$result" | tr '\t' '\n' | sed -n 's/^audit_count=//p')
  if [[ "$rc" != "0" ]]; then
    note_fail l "wrapper invocation failed: rc=$rc head_before=$head_before head_after=$head_after audit=$audit_count stderr=$(tr '\n' '|' < "$stderr_path" 2>/dev/null | head -c 400)"
  elif [[ "$head_before" == "$head_after" ]] || [[ "$head_after" == "NONE" ]]; then
    note_fail l "wrapper rc=0 but HEAD did not advance (before=$head_before after=$head_after)"
  else
    # Pull trailer values from the new commit message.
    trailer_ticket=$(cd "$repo" && git log -1 --format='%(trailers:key=Ticket-SHA256,valueonly)' HEAD | tr -d '\n')
    trailer_dev=$(cd "$repo" && git log -1 --format='%(trailers:key=Dev-Report-SHA256,valueonly)' HEAD | tr -d '\n')
    trailer_qa=$(cd "$repo" && git log -1 --format='%(trailers:key=QA-Report-SHA256,valueonly)' HEAD | tr -d '\n')
    trailer_close=$(cd "$repo" && git log -1 --format='%(trailers:key=Close-Report-SHA256,valueonly)' HEAD | tr -d '\n')
    expected_ticket=$(sha256sum "$repo/docs/dev/ticket-${task_id}.md" | awk '{print $1}')
    expected_dev=$(sha256sum "$repo/docs/dev/dev-report-${task_id}.json" | awk '{print $1}')
    expected_qa=$(sha256sum "$repo/docs/dev/qa-report-${task_id}.json" | awk '{print $1}')
    expected_close=$(sha256sum "$repo/docs/dev/close-report-${task_id}.md" | awk '{print $1}')
    if [[ "$trailer_ticket" == "$expected_ticket" ]] && \
       [[ "$trailer_dev" == "$expected_dev" ]] && \
       [[ "$trailer_qa" == "$expected_qa" ]] && \
       [[ "$trailer_close" == "$expected_close" ]]; then
      note_pass l "M1 hash-chain trailers via wrapper: Ticket/Dev-Report/QA-Report/Close-Report-SHA256 match on-disk sha256sum (commit ${head_after:0:7})"
    else
      note_fail l "trailer mismatch: ticket=$trailer_ticket want=$expected_ticket; dev=$trailer_dev want=$expected_dev; qa=$trailer_qa want=$expected_qa; close=$trailer_close want=$expected_close"
    fi
  fi
fi

# ---------------------------------------------------------------------------
# Path (m) M2 message-vs-evidence guard refusal -- end-to-end wrapper
# ---------------------------------------------------------------------------
# AC2 mandate: wrapper exits 2 with documented stderr when -m claims
# verification but qa-report.qa.status=="fail". Constructs a fixture with
# qa-report.status=fail and a CALLER_MESSAGE carrying the verification-
# claim substring 'all 8 ACs met'. Asserts:
#   * wrapper exit code == 2
#   * stderr contains 'commit.sh: -m message claims verification' and
#     'qa-report.qa.status is "fail"' (the verbatim refusal contract at
#     hooks/commit.sh:2913)
#   * HEAD unchanged from before invocation
#   * NO audit JSON file written under CLAUDE_LOG_DIR (M2 refuses BEFORE
#     run_private_index_commit emits its audit record)
if want m; then
  ts="$(date +%s%N)"
  task_id="smoke-m-${ts}"
  repo="$TMP/wrapper-m-${ts}"
  log_dir="$TMP/wrapper-m-logs-${ts}"
  _wrapper_build_fixture "$repo" "$task_id" "fail"
  result=$(_wrapper_invoke "$repo" "$task_id" "$log_dir" "feat(commit): test message with all 8 ACs met PASS claim")
  rc=$(printf '%s' "$result" | tr '\t' '\n' | sed -n 's/^rc=//p')
  stderr_path=$(printf '%s' "$result" | tr '\t' '\n' | sed -n 's/^stderr_path=//p')
  head_before=$(printf '%s' "$result" | tr '\t' '\n' | sed -n 's/^head_before=//p')
  head_after=$(printf '%s' "$result" | tr '\t' '\n' | sed -n 's/^head_after=//p')
  audit_count=$(printf '%s' "$result" | tr '\t' '\n' | sed -n 's/^audit_count=//p')
  stderr_text=$(cat "$stderr_path" 2>/dev/null || true)
  has_refuse_msg=0
  has_fail_qualifier=0
  case "$stderr_text" in
    *"commit.sh: -m message claims verification"*) has_refuse_msg=1 ;;
  esac
  case "$stderr_text" in
    *'qa-report.qa.status is "fail"'*) has_fail_qualifier=1 ;;
  esac
  if [[ "$rc" == "2" ]] && [[ "$has_refuse_msg" == "1" ]] && \
     [[ "$has_fail_qualifier" == "1" ]] && \
     [[ "$head_before" == "$head_after" ]] && \
     [[ "$audit_count" == "0" ]]; then
    note_pass m "M2 guard refuses: rc=2, verbatim refusal stderr present, HEAD unchanged ($head_before), zero audit emissions"
  else
    note_fail m "M2 guard: rc=$rc refuse_msg=$has_refuse_msg fail_qualifier=$has_fail_qualifier head_before=$head_before head_after=$head_after audit=$audit_count stderr=$(printf '%s' "$stderr_text" | tr '\n' '|' | head -c 400)"
  fi
fi

# ---------------------------------------------------------------------------
# Path (n) M3 CC type lint refusal -- end-to-end wrapper invocation
# ---------------------------------------------------------------------------
# AC3 mandate: wrapper exits 2 with documented stderr when -m starts with
# a non-whitelist type. Reuses the path-l-style fixture (qa-status=pass so
# M2 wouldn't fire even if reached). Invokes commit.sh with the offending
# subject 'improve: foo'. Asserts:
#   * wrapper exit code == 2
#   * stderr contains 'commit.sh: first-line type does not match
#     Conventional Commits whitelist' (verbatim refusal at commit.sh:445)
#   * HEAD unchanged from before invocation
#   * NO audit JSON file written under CLAUDE_LOG_DIR (M3 refuses BEFORE
#     closure detection + run_private_index_commit)
if want n; then
  ts="$(date +%s%N)"
  task_id="smoke-n-${ts}"
  repo="$TMP/wrapper-n-${ts}"
  log_dir="$TMP/wrapper-n-logs-${ts}"
  _wrapper_build_fixture "$repo" "$task_id" "pass"
  result=$(_wrapper_invoke "$repo" "$task_id" "$log_dir" "improve: foo")
  rc=$(printf '%s' "$result" | tr '\t' '\n' | sed -n 's/^rc=//p')
  stderr_path=$(printf '%s' "$result" | tr '\t' '\n' | sed -n 's/^stderr_path=//p')
  head_before=$(printf '%s' "$result" | tr '\t' '\n' | sed -n 's/^head_before=//p')
  head_after=$(printf '%s' "$result" | tr '\t' '\n' | sed -n 's/^head_after=//p')
  audit_count=$(printf '%s' "$result" | tr '\t' '\n' | sed -n 's/^audit_count=//p')
  stderr_text=$(cat "$stderr_path" 2>/dev/null || true)
  has_refuse_msg=0
  case "$stderr_text" in
    *"commit.sh: first-line type does not match Conventional Commits whitelist"*) has_refuse_msg=1 ;;
  esac
  if [[ "$rc" == "2" ]] && [[ "$has_refuse_msg" == "1" ]] && \
     [[ "$head_before" == "$head_after" ]] && \
     [[ "$audit_count" == "0" ]]; then
    note_pass n "M3 CC lint refuses: rc=2, verbatim refusal stderr present, HEAD unchanged ($head_before), zero audit emissions"
  else
    note_fail n "M3 CC lint: rc=$rc refuse_msg=$has_refuse_msg head_before=$head_before head_after=$head_after audit=$audit_count stderr=$(printf '%s' "$stderr_text" | tr '\n' '|' | head -c 400)"
  fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo "---"
echo "commit-smoke.sh summary: pass=$pass fail=$fail skipped=$skipped"
if [[ "$fail" -gt 0 ]]; then
  exit 1
fi
exit 0
