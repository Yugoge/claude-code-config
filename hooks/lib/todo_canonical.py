"""
Shared canonical todo validation utilities.

Used by both pretool-todo-validate.py and posttool-todo-sequence.py
to avoid code duplication.
"""

from pathlib import Path


def run_todo_script(cmd_name):
    """Load canonical todos from ~/.claude/scripts/todo/{cmd_name}.py.

    Calls get_todos() function if defined, falls back to TODOS variable.
    Returns list of todo dicts or None.
    """
    script_path = Path.home() / '.claude' / 'scripts' / 'todo' / f'{cmd_name}.py'
    if not script_path.exists():
        return None
    try:
        namespace = {}
        with open(script_path) as f:
            exec(f.read(), namespace)
        # Prefer get_todos() function (canonical pattern)
        get_fn = namespace.get('get_todos')
        if callable(get_fn):
            canonical = get_fn()
        else:
            canonical = namespace.get('TODOS')  # fallback
        if not isinstance(canonical, list):
            return None
        for item in canonical:
            if not isinstance(item, dict):
                return None
        return canonical
    except Exception:
        return None


def check_immutability_against_canonical(canonical, new_todos, violations):
    """Check new todos against canonical source of truth.

    Validates that content and activeForm fields match the canonical
    definition. Checks length mismatch before comparing items.
    """
    if len(canonical) != len(new_todos):
        violations.append(
            f'Todo count mismatch: canonical has {len(canonical)}, '
            f'submitted has {len(new_todos)}'
        )
        return
    for i, (c, n) in enumerate(zip(canonical, new_todos)):
        if c.get('content', '') != n.get('content', ''):
            violations.append(
                f'Step {i} content modified from canonical: '
                f'"{c["content"]}" -> "{n["content"]}"'
            )
        if c.get('activeForm', '') != n.get('activeForm', ''):
            violations.append(
                f'Step {i} activeForm modified from canonical: '
                f'"{c["activeForm"]}" -> "{n["activeForm"]}"'
            )


def validate_against_canonical(cmd_name, new_todos):
    """Validate new_todos against canonical script if available.

    Returns list of violations (empty if valid or no canonical exists).
    """
    canonical = run_todo_script(cmd_name) if cmd_name else None
    if not canonical:
        return []
    violations = []
    check_immutability_against_canonical(canonical, new_todos, violations)
    return violations
