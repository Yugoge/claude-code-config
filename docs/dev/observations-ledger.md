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
