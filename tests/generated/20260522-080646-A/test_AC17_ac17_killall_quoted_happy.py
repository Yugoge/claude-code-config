# Regression test added in remediation round 2 (iter2 QA blocker B1).
# AC ID: AC17  ac_uid: ac17_killall_quoted_happy  type: hook
# Covers the quoted-arg bypass: killall "happy" must exit 2, not 0.

import json
import subprocess

AC_UID = "ac17_killall_quoted_happy"
AC_TYPE = "hook"


def test_AC17():
    """
    GIVEN: The hook processes 'killall "happy"' (quoted target)
    WHEN:  pretool-bash-safety.sh runs
    THEN:  exit code is 2 (BLOCKED) — killall rule fires even with quoted arg
    """
    command = 'killall "happy"'
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
