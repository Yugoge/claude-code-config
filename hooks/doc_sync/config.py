#!/usr/bin/env python3
"""Load doc-sync project-local config."""

import json
from pathlib import Path


def load_config(project_dir: Path) -> dict:
    """Load <project_dir>/.claude/doc-sync.json. Return {} when missing or malformed."""
    config_path = project_dir / '.claude' / 'doc-sync.json'
    if not config_path.is_file():
        return {}
    try:
        return json.loads(config_path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
