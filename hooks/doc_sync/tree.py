#!/usr/bin/env python3
"""Build directory trees for INDEX.md."""

from pathlib import Path
from .extract import extract_description

SKIP_FILES = {
    'INDEX.md', 'README.md', '__init__.py', '.DS_Store',
    # Runtime telemetry — gitignored per spec-20260518-225715 Cycle 2 P2.3;
    # excluding from the rendered tree prevents re-leakage on regen.
    'agent-scores.json', 'agent-scores.json.lock',
}
IGNORE_DIRS = {
    'node_modules', '.git', '__pycache__', '.venv', 'venv',
    'dist', 'build', '.next', '.cache', 'coverage',
}
# PATH-AWARE leak suppression (spec-20260518-225715 Cycle 2 P2.4b): suppress
# `.claude/specs/...` cp-state telemetry subtrees while preserving any
# legitimate non-.claude `specs/` sibling (e.g. `ordinary/specs/`). The
# predicate matches a directory whose own name is `specs` AND whose parent's
# name is `.claude`; a blanket `i.name == 'specs'` check would also suppress
# `ordinary/specs/` and is explicitly forbidden by the AC-09 negative control.
def _is_dot_claude_specs(item: Path) -> bool:
    return item.is_dir() and item.name == 'specs' and item.parent.name == '.claude'


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
        and not _is_dot_claude_specs(i)
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
