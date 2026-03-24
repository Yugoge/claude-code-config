#!/usr/bin/env python3
"""Build directory trees for INDEX.md."""

from pathlib import Path
from .extract import extract_description

SKIP_FILES = {'INDEX.md', 'README.md', '__init__.py', '.DS_Store'}
IGNORE_DIRS = {
    'node_modules', '.git', '__pycache__', '.venv', 'venv',
    'dist', 'build', '.next', '.cache', 'coverage',
}


def build_tree(dir_path: Path, prefix: str = '', depth: int = 0,
               max_depth: int = 3) -> list[str]:
    if depth >= max_depth or not dir_path.is_dir():
        return []
    items = sorted(
        dir_path.iterdir(),
        key=lambda x: (x.is_file(), x.name.lower()),
    )
    items = [
        i for i in items
        if i.name not in SKIP_FILES
        and i.name not in IGNORE_DIRS
        and not i.name.startswith('.')
    ]
    lines = []
    for idx, item in enumerate(items):
        is_last = (idx == len(items) - 1)
        conn = '\u2514\u2500\u2500 ' if is_last else '\u251c\u2500\u2500 '
        if item.is_dir():
            ext = '    ' if is_last else '\u2502   '
            lines.append(f'{prefix}{conn}{item.name}/')
            lines.extend(build_tree(item, prefix + ext, depth + 1, max_depth))
        else:
            desc = extract_description(item)
            lines.append(f'{prefix}{conn}`{item.name}` - {desc}')
    return lines
