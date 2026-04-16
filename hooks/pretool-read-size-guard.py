#!/usr/bin/env python3
"""
PreToolUse Hook: Read Size Guard

Blocks the main agent from reading files larger than 600 lines.
Subagents (agent_id present) are exempt.
Binary files (images, PDFs) are exempt.
"""

import json
import os
import sys

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".bmp", ".pdf",
}
LINE_LIMIT = 600


def is_exempt(data, file_path):
    if data.get("tool_name") != "Read":
        return True
    if data.get("agent_id"):
        return True
    if not file_path or not os.path.exists(file_path):
        return True
    _, ext = os.path.splitext(file_path)
    return ext.lower() in BINARY_EXTENSIONS


def count_lines(file_path):
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except Exception:
        return -1


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "")
    if is_exempt(data, file_path):
        sys.exit(0)

    line_count = count_lines(file_path)
    if line_count < 0 or line_count <= LINE_LIMIT:
        sys.exit(0)

    sys.stderr.write(
        f"[Read Size Guard] File too large: {file_path} "
        f"({line_count} lines, limit {LINE_LIMIT}).\n"
        f"Do NOT retry with offset/limit to fetch the raw content piecewise. Choose one:\n"
        f"  1. Use Grep to locate the specific section you need, then Read that narrow range.\n"
        f"  2. Delegate to an Agent subagent asking it to SUMMARIZE the file (not return raw content).\n"
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
