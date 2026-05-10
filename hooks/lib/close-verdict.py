#!/usr/bin/env python3
"""Shared CLOSE verdict classifier for commit/close tooling."""
from __future__ import annotations

import sys
from pathlib import Path


def last_nonempty(text: str) -> str:
    line = ""
    for raw in text.replace("\r", "").splitlines():
        if raw.strip():
            line = raw.strip()
    return line


def classify_line(line: str) -> str:
    text = (line or "").strip()
    if not text.upper().startswith("CLOSE:"):
        return "unknown"
    rest = text.split(":", 1)[1].strip().replace("—", "-")
    upper = rest.upper()
    if upper == "YES" or upper.startswith(("YES ", "YES-", "YES(")):
        return "yes"
    if upper == "NO" or upper.startswith(("NO ", "NO-", "NO(")):
        return "no"
    return "unknown"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: close-verdict.py classify-line <line> | classify-file <path> | last-line <path>", file=sys.stderr)
        return 2
    mode = argv[1]
    if mode == "classify-line":
        print(classify_line(" ".join(argv[2:])))
        return 0
    if mode in {"classify-file", "last-line"}:
        if len(argv) != 3:
            print(f"close-verdict.py: {mode} requires a path", file=sys.stderr)
            return 2
        text = Path(argv[2]).read_text(encoding="utf-8", errors="replace")
        line = last_nonempty(text)
        print(line if mode == "last-line" else classify_line(line))
        return 0
    print(f"close-verdict.py: unknown mode: {mode}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
