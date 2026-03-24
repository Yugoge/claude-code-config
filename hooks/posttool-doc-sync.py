#!/usr/bin/env python3
"""
PostToolUse Hook: Auto-sync INDEX.md and CLAUDE.md when structural files change.

Delegates to doc_sync module. See doc_sync/ directory for implementation.
Hook type: PostToolUse (Write|Edit|NotebookEdit matcher)
Exit codes: 0 always (never blocks)
"""

from doc_sync.main import main

if __name__ == '__main__':
    main()
