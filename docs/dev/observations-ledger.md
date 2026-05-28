# Observations Ledger

<!--
Schema:
  ts                 ISO-8601 timestamp
  task_id            task-id of the cycle that logged this row
  file               relative path
  line               line number (or empty for file-level)
  observation        concise description
  in_user_path       always `false` for ledger rows
  security_relevant  bool
-->

| ts | task_id | file | line | observation | in_user_path | security_relevant |
|----|---------|------|------|-------------|--------------|-------------------|
| 2026-05-24T15:45:00Z | 20260524-125300-B | hooks/userprompt-consent-allowlist.sh | 180-182 | Regex-skip exit (IS_REGEX=true) does not clear stale sentinel for same TASK_ID. A later /allow re:... or bare /allow grant with an existing stale sentinel can cause CF-1 to suppress the legacy regex grant (pretool-bash-safety.sh:523-558). Requires sentinel cleanup on IS_REGEX=true exit. | false | false |
| 2026-05-24T15:45:00Z | 20260524-125300-B | hooks/lib/allowlist.py | 320-325 | After Write sentinel is consumed via posttool, the stale legacy pattern-grant file /tmp/claude-bash-allowlist-<sid>.json may remain. Pattern 'Write /tmp/file.json' in the legacy file could later match a Bash command by substring (Bash branch uses substr_only). Codex finding 6. Separate cycle. | false | false |
| 2026-05-24T15:45:00Z | 20260524-125300-B | hooks/lib/allowlist.py | 460-480 | match_sentinel_grant_for_bash_command allows the entire compound Bash command if any single subcommand matches the sentinel grant entry. A grant for 'echo ok' could authorize 'dangerous_command; echo ok'. Codex finding 10. Separate security cycle required. | false | true |
| 2026-05-25T05:33:26Z | dev-20260525-053326-F | tests/integration-test.sh | 57 | Uses hardcoded /tmp/git-test-repo (not mktemp). Has cleanup_test_repo() but no trap for early exits. Full mktemp refactor requires updating 5+ hardcoded path references — not zero-blast. Trap-only fix deferred to Should-Have. | false | false |
| 2026-05-25T05:33:26Z | dev-20260525-053326-F | tests/integration-test.sh | 1 | Filename 'integration-test.sh' does not follow test_*.sh convention. Rename has non-zero blast: referenced in docs/reference/lock-file-handling.md, docs/archive/, tests/INDEX.md. | false | false |
| 2026-05-25T05:33:26Z | dev-20260525-053326-F | tests/score-inject-contract/test-inject-branches.sh | 1 | Filename 'test-inject-branches.sh' does not follow test_*.sh (uses dashes). Rename blocked: path hardcoded in tests/generated/20260524-205206/test_AC_02_b2c4e6f8a1d3b5c8.py:39. | false | false |
| 2026-05-25T05:33:26Z | dev-20260525-053326-F | tests/test-lock-detection.sh | 1 | Filename 'test-lock-detection.sh' does not follow test_*.sh. Rename has blast: referenced in docs/reference/lock-file-handling.md lines 108 and 176. | false | false |
| 2026-05-25T05:33:26Z | dev-20260525-053326-F | tests/verify-stop-spec-session-isolation.sh | 1 | Filename 'verify-stop-spec-session-isolation.sh' does not follow test_*.sh. Rename has blast: referenced in tests/INDEX.md, docs/dev/style-inspector-report-20260522-000000.json. | false | false |
| 2026-05-25T05:33:26Z | dev-20260525-053326-F | scripts/analyze-folder-history.sh | 34 | Contains 'placeholder script' comment — but this is accurate design intent: analysis delegated to rule-inspector subagent. Not stale; not a violation. | false | false |
| 2026-05-26T20:38:08Z | dev-20260526-203808-issubagent | commands/commit.md | null | The /commit --bulk flow currently dispatches changelog-analyst subagent to run git commit -F with auto-bulk: prefix. The new IS_SUBAGENT gate (this cycle) will intentionally break that flow. A forward-fix cycle must migrate commit.md + changelog-analyst.md so the /commit orchestrator runs commits directly from main-agent context. | false | false |
| 2026-05-27T06:37:58Z | dev-20260527-063758-T4 | commands/dev-command.md | 695 | Contains `python ~/.claude/scripts/todo/<script>.py` in a permission-string template (allowlist entry example, not an executable bash line). Not an invocation; does not fail at runtime. Out of user-need path for this cycle — user asked only about commit.md invocations. | false | false |
