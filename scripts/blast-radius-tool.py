#!/usr/bin/env python3
"""blast-radius-tool.py — TDAD blast-radius analyser (spec-20260518-225715 §5.3).

Two phases:
  Phase 1 (BA-side, prediction):  --files <file_list> --output <path>
  Phase 2 (QA-side, verification): --git-diff [--base <ref>] --output <path>

The tool uses Python ast + subprocess grep (no jedi/rope) to produce a JSON
blast-radius-map.json with these top-level keys:
    schema_version, task_id, phase, generated_at,
    scope_filter_applied, analyzed_files, files_to_modify, files_to_create,
    edges[], coverage_gaps[], required_validation[]

Edges carry a confidence label (high|medium) indicating import vs textual reference.
hooks/ coverage_gaps are tagged severity=critical per spec §5.3.

Exits 0 on success, 1 on bad arguments, 2 on IO error.
"""
from __future__ import annotations

import argparse
import ast
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Scope filtering -- spec §5.3 mandates excluding venv/, worktrees/, .archive,
# plugins/. Tool runs from project root; paths are made relative for output.
# ---------------------------------------------------------------------------
EXCLUDE_FRAGMENTS = (
    "/venv/", "/worktrees/", "/.archive/", "/plugins/",
    "/.git/", "/__pycache__/", "/node_modules/",
)


def in_scope(path: str) -> bool:
    norm = "/" + path.replace("\\", "/").lstrip("/") + "/"
    return not any(frag in norm for frag in EXCLUDE_FRAGMENTS)


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Python AST analysis
# ---------------------------------------------------------------------------
def python_imports(file_path: Path) -> list[str]:
    """Return imported module dotted names (best-effort) for a .py file."""
    try:
        src = file_path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(file_path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            out.append(mod)
    return out


def find_callers_via_grep(root: Path, basename: str) -> list[str]:
    """Use grep to find files that textually reference `basename`. In-scope filter applied."""
    try:
        result = subprocess.run(
            ["grep", "-r", "-l", "--exclude-dir=.git",
             "--exclude-dir=venv", "--exclude-dir=__pycache__",
             "--exclude-dir=.archive", "--exclude-dir=worktrees",
             "--exclude-dir=plugins", "--exclude-dir=node_modules",
             "-F", basename, str(root)],
            capture_output=True, text=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    hits: list[str] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        rel = os.path.relpath(line, str(root))
        if in_scope(rel):
            hits.append(rel)
    return hits


def find_dependent_tests(root: Path, target_rel: str) -> list[str]:
    """Search tests/** for files that reference the target by basename, module
    path, or relative path. Returns relative paths of matching test files.
    Limited to .py / .sh / .md test descriptors under tests/.
    """
    tests_root = root / "tests"
    if not tests_root.exists():
        return []
    basename = os.path.basename(target_rel)
    needles = {basename}
    # If the target is a Python module, also search for its dotted module path.
    if target_rel.endswith(".py"):
        mod = target_rel[:-3].replace("/", ".").lstrip(".")
        if mod:
            needles.add(mod)
    hits: set[str] = set()
    for needle in needles:
        try:
            result = subprocess.run(
                ["grep", "-r", "-l",
                 "--include=*.py", "--include=*.sh", "--include=*.md",
                 "--exclude-dir=__pycache__", "--exclude-dir=.archive",
                 "-F", needle, str(tests_root)],
                capture_output=True, text=True, timeout=20,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            rel = os.path.relpath(line, str(root))
            if in_scope(rel) and rel != target_rel:
                hits.add(rel)
    return sorted(hits)


def severity_for(rel_path: str) -> str:
    """Per spec §5.3: hooks/ coverage gaps are critical."""
    norm = rel_path.replace("\\", "/").lstrip("./")
    if norm.startswith("hooks/") or "/hooks/" in norm:
        return "critical"
    return "medium"


# ---------------------------------------------------------------------------
# Edge + coverage_gap construction
# ---------------------------------------------------------------------------
def build_report(
    root: Path,
    target_files: list[str],
    phase: str,
    task_id: str | None,
) -> dict:
    analyzed: list[str] = []
    edges: list[dict] = []
    coverage_gaps: list[dict] = []
    required_validation: list[dict] = []
    seen_edges: set[tuple] = set()

    for tf in target_files:
        tf_norm = tf.replace("\\", "/")
        if not in_scope(tf_norm):
            continue
        abs_p = root / tf_norm
        analyzed.append(tf_norm)

        # Import-based edges (Python files only)
        if tf_norm.endswith(".py") and abs_p.exists():
            for mod in python_imports(abs_p):
                if mod:
                    edges.append({
                        "from": tf_norm,
                        "to": mod,
                        "confidence": "high",
                        "edge_type": "python_import",
                    })

        # Reverse-direction textual references: who calls / imports this file?
        bn = os.path.basename(tf_norm)
        if bn:
            for caller in find_callers_via_grep(root, bn):
                if caller == tf_norm:
                    continue
                key = (caller, tf_norm)
                if key in seen_edges:
                    continue
                seen_edges.add(key)
                edges.append({
                    "from": caller,
                    "to": tf_norm,
                    "confidence": "medium",
                    "edge_type": "textual_reference",
                })

        # Coverage gap detection: every file flagged for change has no automated
        # test in this codebase (no tests/ dir yet). Per spec 5.3, hooks/ gaps
        # are critical; everything else is medium unless an explicit override.
        sev = severity_for(tf_norm)
        is_hook = sev == "critical" and "hooks/" in tf_norm
        coverage_gaps.append({
            "file": tf_norm,
            "gap_type": "no_automated_test",
            "severity": sev,
            "behavioral_test_only": is_hook,
            "exemption_hint": (
                "canary-verify.sh tests this hook without modifying it; "
                "Dev should declare an explicit exemption with this reason"
                if is_hook else None
            ),
            "dependent_tests": [],
            "note": (
                "spec 5.3: hooks/ severity critical" if is_hook
                else f"No automated test for {tf_norm}; declare validation in dev-report"
            ),
        })

        # Required validation entries for callers of modified files
        callers = [e["from"] for e in edges if e["to"] == tf_norm]
        if callers:
            required_validation.append({
                "file": tf_norm,
                "callers": sorted(set(callers))[:10],
                "validation_required": (
                    f"Verify edits to {tf_norm} do not break callers; "
                    "read full modified sections before and after edit."
                ),
            })

    report = {
        "schema_version": "1.2",
        "task_id": task_id,
        "phase": phase,
        "generated_at": now_iso(),
        "scope_filter_applied": "exclude: venv/, worktrees/, .archive, plugins/",
        "analyzed_files": sorted(set(analyzed)),
        "files_to_modify": sorted(set(analyzed)),
        "files_to_create": [],
        "edges": edges,
        "coverage_gaps": coverage_gaps,
        "required_validation": required_validation,
    }
    return report


# ---------------------------------------------------------------------------
# Git diff source for Phase 2
# ---------------------------------------------------------------------------
def git_diff_files(base: str) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    files = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line and in_scope(line):
            files.append(line)
    return files


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="TDAD blast-radius tool (spec-20260518-225715 §5.3)"
    )
    parser.add_argument("--files", nargs="*", default=None,
                        help="Phase 1: comma- or space-separated file list to analyse")
    parser.add_argument("--git-diff", action="store_true",
                        help="Phase 2: take file list from `git diff --name-only <base>`")
    parser.add_argument("--base", default="HEAD",
                        help="Phase 2 git base ref (default HEAD)")
    parser.add_argument("--output", required=True,
                        help="Output JSON path")
    parser.add_argument("--task-id", default=None,
                        help="Optional task_id to embed in the JSON (for dev-registry/<task_id>/)")
    parser.add_argument("--root", default=os.getcwd(),
                        help="Project root (default: cwd)")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    phase = "2-verification" if args.git_diff else "1-prediction"

    # Collect target files
    if args.git_diff:
        target_files = git_diff_files(args.base)
    else:
        if not args.files:
            print("blast-radius-tool: --files <list> required (or use --git-diff)",
                  file=sys.stderr)
            return 1
        # Accept either repeated args or a single comma-separated string.
        target_files = []
        for entry in args.files:
            target_files.extend(p.strip() for p in entry.split(",") if p.strip())

    report = build_report(root, target_files, phase, args.task_id)

    out_path = Path(args.output)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except OSError as e:
        print(f"blast-radius-tool: failed to write {out_path}: {e}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
