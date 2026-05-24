# Regression test added in remediation round 2 (iter2 QA blocker B1).
# AC ID: AC19  ac_uid: ac19_kill_quoted_signal  type: hook
# Covers the quoted-arg bypass: kill "-9" 1234 must exit 2, not 0.

import json
import subprocess

AC_UID = "ac19_kill_quoted_signal"
AC_TYPE = "hook"


def test_AC19():
    """
    GIVEN: The hook processes 'kill "-9" 1234' (quoted signal flag)
    WHEN:  pretool-bash-safety.sh runs
    THEN:  exit code is 2 (BLOCKED) — kill rule fires even with quoted signal
    """
    command = 'kill "-9" 1234'
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
