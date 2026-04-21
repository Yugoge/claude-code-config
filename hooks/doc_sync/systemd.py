#!/usr/bin/env python3
"""Query systemctl for project-configured services and generate a markdown table."""

import subprocess
from pathlib import Path
from .config import load_config


def _run_systemctl() -> str:
    try:
        result = subprocess.run(
            ['systemctl', 'list-unit-files', '--type=service', '--no-pager', '--plain'],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return ''
    if result.returncode != 0:
        return ''
    return result.stdout


def _find_service_status(stdout: str, svc: str) -> str:
    prefix = f'{svc}.service'
    for line in stdout.split('\n'):
        if not line.startswith(prefix):
            continue
        parts = line.split()
        return parts[1] if len(parts) >= 2 else 'unknown'
    return 'unknown'


def build_systemd_table(project_dir: Path) -> str:
    """Build systemd status table from project-local config.

    Reads `systemd_services` list from `<project_dir>/.claude/doc-sync.json`.
    Returns '' when no config or empty list — caller should no-op the patch.
    """
    config = load_config(project_dir)
    services = config.get('systemd_services') or []
    if not services:
        return ''
    stdout = _run_systemctl()
    lines = ['| Service | Status | Purpose |', '|---------|--------|---------|']
    for svc in services:
        status = _find_service_status(stdout, svc) if stdout else 'unknown'
        lines.append(f'| {svc} | {status} | |')
    return '\n'.join(lines)
