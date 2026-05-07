#!/usr/bin/env python3
"""Preloaded TodoList for /redev workflow. Delegates to dev.py (single source of truth)."""

from dev import get_todos


if __name__ == "__main__":
    import json
    print(json.dumps(get_todos(), indent=2, ensure_ascii=False))
