#!/usr/bin/env python3
"""Query systemctl for known services and generate markdown table."""

import subprocess

KNOWN_SVCS = [
    'happy-daemon', 'happy-daemon-jade', 'happy-session-watcher',
    'hapi-hub', 'hapi-runner', 'hapi-restore', 'hapi-session-watcher',
]


def _run_systemctl() -> str:
    """Run systemctl command and return stdout or empty string on error."""
    try:
        result = subprocess.run(
            ['systemctl', 'list-unit-files', '--type=service', '--no-pager', '--plain'],
            capture_output=True, text=True, timeout=5
        )
    except Exception:
        return ''
    if result.returncode != 0:
        return ''
    return result.stdout


def _find_service_status(stdout: str, svc: str) -> str:
    """Find service status in systemctl output."""
    prefix = f'{svc}.service'
    for line in stdout.split('\n'):
        if not line.startswith(prefix):
            continue
        parts = line.split()
        return parts[1] if len(parts) >= 2 else 'unknown'
    return 'unknown'


def _get_service_status(svc: str) -> str:
    stdout = _run_systemctl()
    if not stdout:
        return 'unknown'
    return _find_service_status(stdout, svc)


def build_systemd_table() -> str:
    lines = ['| Service | Status | Purpose |', '|---------|--------|---------|']
    for svc in KNOWN_SVCS:
        status = _get_service_status(svc)
        lines.append(f'| {svc} | {status} | |')
    return '\n'.join(lines)
