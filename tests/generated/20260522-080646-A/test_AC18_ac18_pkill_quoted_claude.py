# Regression test added in remediation round 2 (iter2 QA blocker B1).
# AC ID: AC18  ac_uid: ac18_pkill_quoted_claude  type: hook
# Covers the quoted-arg bypass: pkill -f "claude" must exit 2, not 0.

import json
import subprocess

AC_UID = "ac18_pkill_quoted_claude"
AC_TYPE = "hook"


def test_AC18():
    """
    GIVEN: The hook processes 'pkill -f "claude"' (quoted process pattern)
    WHEN:  pretool-bash-safety.sh runs
    THEN:  exit code is 2 (BLOCKED) — pkill rule fires even with quoted arg
    """
    command = 'pkill -f "claude"'
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    result = subprocess.run(
        ["bash", "hooks/pretool-bash-safety.sh"],
        input=payload.encode(),
        cwd="/dev/shm/dev-workspace/dot-claude",
        capture_output=True,
    )
    assert result.returncode == 2, (
        f"Expected exit 2 (BLOCKED) for {AC_UID!r}, got {result.returncode}. "
        f"stderr: {result.stderr.decode()}"
    )
