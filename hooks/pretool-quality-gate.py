#!/usr/bin/env python3
"""
PreToolUse Hook: Quality gate for Write/Edit operations.

Blocks file writes that would violate quantified quality thresholds:
- File length: max 800 lines
- Function length: max 30 lines
- Nesting depth: max 3 levels

Hook type: PreToolUse (Write|Edit matcher)
Exit codes: 0 = allow, 2 = block
"""

import json
import re
import sys
from pathlib import Path

MAX_FILE_LINES = 800
MAX_FUNC_LINES = 30
MAX_NESTING = 3

# Paths exempt from quality checks
EXEMPT_PATHS = {
    'node_modules', '.git', '__pycache__', 'vendor', 'dist', 'build',
    '.next', 'coverage', '.venv', 'venv', 'package-lock.json',
    'yarn.lock', 'pnpm-lock.yaml',
}

# Only check these extensions
CHECKABLE_EXTS = {'.py', '.ts', '.js', '.tsx', '.jsx'}


def is_exempt(file_path: str) -> bool:
    """Check if file is exempt from quality checks."""
    parts = Path(file_path).parts
    for part in parts:
        if part in EXEMPT_PATHS:
            return True
    if Path(file_path).suffix not in CHECKABLE_EXTS:
        return True
    return False


def get_final_content(data: dict) -> tuple[str, str]:
    """Get the content that would result from this operation.

    For Write: returns content directly from tool_input.
    For Edit: reads current file, applies the edit, returns result.

    Returns:
        Tuple of (resulting_content, file_path).
    """
    tool_name = data.get('tool_name', '')
    tool_input = data.get('tool_input', {})
    file_path = tool_input.get('file_path', '')

    if tool_name == 'Write':
        return tool_input.get('content', ''), file_path

    if tool_name == 'Edit':
        try:
            current = Path(file_path).read_text()
        except Exception:
            return '', file_path
        old = tool_input.get('old_string', '')
        new = tool_input.get('new_string', '')
        if old and old in current:
            if tool_input.get('replace_all'):
                result = current.replace(old, new)
            else:
                result = current.replace(old, new, 1)
            return result, file_path
        return current, file_path

    return '', file_path


def check_file_length(lines: list[str]) -> list[str]:
    """Check if file exceeds max line count."""
    if len(lines) > MAX_FILE_LINES:
        return [f'File has {len(lines)} lines (max {MAX_FILE_LINES}). Split into modules.']
    return []


def check_function_length_python(lines: list[str]) -> list[str]:
    """Check Python function lengths by tracking def/async def and indentation."""
    violations: list[str] = []
    func_start = -1
    func_name = ''
    func_indent = 0

    for i, line in enumerate(lines):
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if stripped.startswith('def ') or stripped.startswith('async def '):
            # If we were tracking a function, check it
            if func_start >= 0:
                length = i - func_start
                if length > MAX_FUNC_LINES:
                    violations.append(
                        f'Function `{func_name}` (line {func_start + 1}) '
                        f'is {length} lines (max {MAX_FUNC_LINES})')

            func_start = i
            func_indent = indent
            match = re.search(r'(?:async\s+)?def\s+(\w+)', stripped)
            func_name = match.group(1) if match else '?'
        elif (func_start >= 0 and stripped and indent <= func_indent
              and not stripped.startswith('#') and not stripped.startswith('@')):
            # Function ended — non-empty line at same or lower indent
            length = i - func_start
            if length > MAX_FUNC_LINES:
                violations.append(
                    f'Function `{func_name}` (line {func_start + 1}) '
                    f'is {length} lines (max {MAX_FUNC_LINES})')
            func_start = -1

    # Check last function in file
    if func_start >= 0:
        length = len(lines) - func_start
        if length > MAX_FUNC_LINES:
            violations.append(
                f'Function `{func_name}` (line {func_start + 1}) '
                f'is {length} lines (max {MAX_FUNC_LINES})')

    return violations


def check_function_length_ts(lines: list[str]) -> list[str]:
    """Check TypeScript/JavaScript function lengths by brace counting."""
    violations: list[str] = []
    func_pattern = re.compile(
        r'(?:export\s+)?(?:async\s+)?(?:'
        r'function\s+(\w+)'
        r'|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\('
        r'|(\w+)\s*\([^)]*\)\s*(?::\s*\w+)?\s*\{'
        r')'
    )

    i = 0
    while i < len(lines):
        match = func_pattern.search(lines[i])
        if match:
            func_name = match.group(1) or match.group(2) or match.group(3) or '?'
            brace_count = 0
            started = False
            start_line = i
            for j in range(i, len(lines)):
                for ch in lines[j]:
                    if ch == '{':
                        brace_count += 1
                        started = True
                    elif ch == '}':
                        brace_count -= 1
                if started and brace_count == 0:
                    length = j - start_line + 1
                    if length > MAX_FUNC_LINES:
                        violations.append(
                            f'Function `{func_name}` (line {start_line + 1}) '
                            f'is {length} lines (max {MAX_FUNC_LINES})')
                    i = j
                    break
        i += 1

    return violations


def check_nesting_depth(lines: list[str], ext: str) -> list[str]:
    """Check max nesting depth. Python uses indentation, TS/JS uses braces."""
    violations: list[str] = []

    if ext == '.py':
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if not stripped or stripped.startswith('#'):
                continue
            indent = len(line) - len(stripped)
            depth = indent // 4
            if depth > MAX_NESTING:
                violations.append(
                    f'Line {i + 1}: nesting depth {depth} (max {MAX_NESTING}). '
                    f'Extract to helper function.')
                break  # One warning is enough
    else:
        # TypeScript/JavaScript: count braces, subtract 1 for module level
        max_depth = 0
        max_line = 0
        depth = 0
        for i, line in enumerate(lines):
            for ch in line:
                if ch == '{':
                    depth += 1
                    if depth > max_depth:
                        max_depth = depth
                        max_line = i + 1
                elif ch == '}':
                    depth -= 1
        effective = max_depth - 1
        if effective > MAX_NESTING:
            violations.append(
                f'Line {max_line}: nesting depth {effective} (max {MAX_NESTING}). '
                f'Extract to helper function.')

    return violations


def main() -> None:
    """Entry point: read stdin JSON, run quality checks, block or allow."""
    try:
        data = json.load(sys.stdin)
        tool_name = data.get('tool_name', '')

        if tool_name not in ('Write', 'Edit'):
            sys.exit(0)

        content, file_path = get_final_content(data)
        if not content or not file_path:
            sys.exit(0)

        if is_exempt(file_path):
            sys.exit(0)

        ext = Path(file_path).suffix
        lines = content.split('\n')
        violations: list[str] = []

        violations.extend(check_file_length(lines))

        if ext == '.py':
            violations.extend(check_function_length_python(lines))
        elif ext in ('.ts', '.js', '.tsx', '.jsx'):
            violations.extend(check_function_length_ts(lines))

        violations.extend(check_nesting_depth(lines, ext))

        if violations:
            print(f'QUALITY GATE BLOCKED \u2014 {file_path}:', file=sys.stderr)
            for v in violations:
                print(f'  - {v}', file=sys.stderr)
            print('Fix violations before writing. Split large functions into smaller ones.', file=sys.stderr)
            sys.exit(2)

    except Exception:
        pass
    sys.exit(0)


if __name__ == '__main__':
    main()
