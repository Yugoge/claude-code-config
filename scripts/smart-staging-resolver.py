#!/usr/bin/env python3
"""smart-staging-resolver.py — the single deterministic staging gate.

WHY THIS EXISTS
---------------
gitignore has zero effect on already-tracked files and only excludes junk that
someone remembered to enumerate. Every commit path in this framework
(changelog-analyst BULK=false / BULK=true, the `git add .` escape hatches in
session-git-init.sh and pre-commit-check.sh) needs ONE deterministic answer to
"may this path be staged?" that does NOT depend on a per-repo gitignore being
up to date. This script is that single source of truth.

DESIGN (converged via codex 2-round debate, 2026-06):
  - The gate is DETERMINISTIC provenance + transient-category logic, never an
    LLM "looks like junk" judgement.
  - `transient_deny` is a HIGH-PRECISION category matcher for runtime/generated
    junk that is NEVER legitimately tracked. It is a belt, not the main line of
    defense —
    it is intentionally narrow so it can be used as a SUBTRACTIVE filter without
    risk of dropping a legitimate source file.
  - Untracked-new files require an explicit INTENT signal to be staged
    (dev-report/manifest provenance, an explicit pathspec, or a policy-declared
    user-data root). No intent → `unclassified_new` → not staged. This is the
    type-agnostic systemic property: a brand-new junk type with no intent signal
    is excluded by default, without anyone enumerating it.

MODES
-----
  is-transient PATH...   exit 0 if EVERY path is transient junk, 1 otherwise
                         (also prints the verdict per path to stdout)
  filter                 read repo-rel paths from stdin (newline or NUL with -z),
                         print the KEPT (non-transient) subset to stdout,
                         print excluded paths to stderr. Purely subtractive —
                         safe to layer on top of any existing candidate set.
  autostage              compute the stage list for an explicit "stage all" intent
                         (repo init / GIT_AUTO_STAGE_ALL): all changed + untracked
                         paths MINUS transient junk. Honours the user's explicit
                         opt-in but still hard-excludes known junk. Prints repo-rel
                         paths (NUL-separated with -z) for `git add --`.
  classify               full resolver: emit stage_plan.json (stage[]/exclude[]/
                         unclassified_new[]/abort_reason). Untracked-new requires
                         provenance/pathspec/user-data-root intent.

This module is pure Python stdlib — no venv, no third-party deps — so it can run
from a SessionStart hook on a bare machine.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import subprocess
import sys

SCHEMA = "stage-plan/v1"

# --- High-precision transient-junk matcher -------------------------------------
# Segment-anywhere directory names that are NEVER legitimate source. A path is
# transient if any of its ancestor segments (or its own basename, for a dir
# entry) is one of these.
JUNK_DIR_SEGMENTS = {
    "__pycache__",
    "dev-registry",        # .claude/dev-registry/
    "worktrees",           # .claude/worktrees/
    ".codex",
    ".codex-harness",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "venv",
    ".venv",
}

# Basenames that are junk wherever they appear.
JUNK_BASENAMES = {
    ".DS_Store",
    "Thumbs.db",
    ".last-update-result.json",
    ".update.lock",
    "settings.local.json",   # .claude/settings.local.json (basename is unambiguous)
    ".cp-checkin.lock",
}

# Basename glob patterns that are junk wherever they appear.
JUNK_BASENAME_GLOBS = ("*.pyc", "*.pyo", "*.swp", "*.swo")


def _git(args, cwd):
    # capture as BYTES (no text=True): git paths may not be valid UTF-8, and a
    # decode crash here would empty the stage list and silently drop files.
    return subprocess.run(
        ["git", "-C", cwd, *args],
        capture_output=True,
    )


def load_policy(repo, policy_path):
    """Optional per-repo override at <repo>/.claude/staging-policy.json or --policy.

    Shape: {"transient_deny_extra": ["build/", "*.generated.ts"],
            "user_data_roots": ["data/", "knowledge-base/"]}
    Entries ending in "/" are treated as path-prefix/dir rules; others as
    basename globs.
    """
    path = policy_path or os.path.join(repo, ".claude", "staging-policy.json")
    if not os.path.isfile(path):
        return {"transient_deny_extra": [], "user_data_roots": []}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"WARNING: ignoring unreadable staging-policy {path}: {exc}", file=sys.stderr)
        return {"transient_deny_extra": [], "user_data_roots": []}
    return {
        "transient_deny_extra": list(data.get("transient_deny_extra", []) or []),
        "user_data_roots": [r.rstrip("/") + "/" for r in (data.get("user_data_roots", []) or [])],
    }


def is_transient(rel_path, policy=None):
    """Return True iff rel_path is high-precision runtime/generated junk.

    Intentionally conservative: scoped rules (e.g. *.lock only under
    .claude/specs/) so legitimate lockfiles (Cargo.lock, poetry.lock,
    package-lock.json) are NEVER matched.
    """
    rel_path = rel_path.strip().strip("/")
    if not rel_path:
        return False
    parts = rel_path.split("/")
    base = parts[-1]
    ancestors = parts[:-1]

    # segment-anywhere junk directories (or a junk dir as the leaf itself)
    if JUNK_DIR_SEGMENTS.intersection(ancestors) or base in JUNK_DIR_SEGMENTS:
        return True
    # *.egg-info dir anywhere in the path
    if any(seg.endswith(".egg-info") for seg in parts):
        return True
    # junk basenames
    if base in JUNK_BASENAMES:
        return True
    if any(fnmatch.fnmatch(base, g) for g in JUNK_BASENAME_GLOBS):
        return True

    in_claude = ".claude" in parts
    # Repo-root-aware: the dot-claude repo IS the .claude dir, so its cp-state
    # files are repo-relative as `specs/<id>/cp-state-*.json`, WITHOUT a
    # `.claude/` path segment. Keying on a `specs` segment OR a `.claude`
    # segment catches both the nested .claude repo and project repos.
    in_specs_ctx = in_claude or "specs" in parts
    at_root = len(parts) == 1

    # workflow-*.json under .claude/ or at repo root (covers both repo shapes —
    # in the .claude repo it sits at repo root, i.e. at_root)
    if fnmatch.fnmatch(base, "workflow-*.json") and (in_claude or at_root):
        return True
    # cp-state-* matches BOTH the cp-state JSON and its sibling `.lock`, scoped
    # to a specs/ or .claude/ context. This replaces a broad `*.lock` rule that
    # would have killed legitimate lockfiles (Cargo.lock / poetry.lock / flake.lock).
    if fnmatch.fnmatch(base, "cp-state-*") and in_specs_ctx:
        return True

    # per-repo policy extras
    if policy:
        for rule in policy.get("transient_deny_extra", []):
            if rule.endswith("/"):
                seg = rule.rstrip("/")
                if seg in ancestors or base == seg:
                    return True
            elif fnmatch.fnmatch(base, rule) or fnmatch.fnmatch(rel_path, rule):
                return True
    return False


def parse_status(repo):
    """Return (tracked_changes, untracked_new) as lists of repo-rel paths.

    Uses NUL-separated porcelain v1 to be quotePath/Unicode safe.
    tracked_changes covers M/A/D/R/C (staged or unstaged); untracked_new is `??`.
    `--untracked-files=all` is REQUIRED: without it git collapses an untracked
    directory into a single `dir/` entry, so junk nested under an otherwise
    legitimate-looking directory (e.g. `.claude/dev-registry/x.json` collapsed
    to `.claude/`) would escape the transient filter.
    """
    res = _git(["status", "--porcelain=v1", "-z", "--untracked-files=all"], repo)
    if res.returncode != 0:
        return None, None
    tracked, untracked = [], []
    tokens = res.stdout.split(b"\x00")  # bytes — paths may be non-UTF-8
    i = 0
    while i < len(tokens):
        entry = tokens[i]
        if not entry:
            i += 1
            continue
        xy = entry[:2].decode("ascii", "replace")
        path = entry[3:].decode("utf-8", "surrogateescape")
        if xy == "??":
            untracked.append(path)
            i += 1
        elif "R" in xy or "C" in xy:
            # rename/copy: porcelain -z emits "<new>\x00<old>"
            tracked.append(path)
            i += 2  # consume the paired origin path token
        else:
            tracked.append(path)
            i += 1
    return tracked, untracked


def load_provenance(dev_report, manifest):
    """Collect declared paths (intent) from a dev-report and/or commit manifest."""
    declared = set()
    for path in (dev_report, manifest):
        if not path or not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        # dev-report shape: {"dev"|"do": {files_created[], files_modified[], files_deleted[]}}
        for key in ("dev", "do"):
            blk = data.get(key) or {}
            for fld in ("files_created", "files_modified", "files_deleted"):
                declared.update(blk.get(fld, []) or [])
        # flat shapes
        for fld in ("files_created", "files_modified", "files_at_dispatch"):
            declared.update(data.get(fld, []) or [])
    return declared


def normalize(repo, declared):
    """Reduce declared (possibly absolute) paths to repo-relative form."""
    real_root = os.path.realpath(repo)
    out = set()
    for p in declared:
        if not p:
            continue
        rp = os.path.realpath(p) if os.path.isabs(p) else os.path.realpath(os.path.join(real_root, p))
        if rp.startswith(real_root + os.sep):
            out.add(os.path.relpath(rp, real_root))
        else:
            out.add(p.strip("/"))
    return out


def under_user_data_root(rel_path, policy):
    for root in policy.get("user_data_roots", []):
        if rel_path == root.rstrip("/") or rel_path.startswith(root):
            return True
    return False


def matches_pathspec(rel_path, pathspecs):
    for spec in pathspecs:
        spec = spec.strip("/")
        if rel_path == spec or rel_path.startswith(spec + "/") or fnmatch.fnmatch(rel_path, spec):
            return True
    return False


def attestation(repo, mode, stage_paths):
    h = hashlib.sha256()
    h.update(os.path.realpath(repo).encode())
    h.update(b"\x00" + mode.encode() + b"\x00")
    for p in sorted(stage_paths):
        h.update(p.encode() + b"\x00")
    return h.hexdigest()[:32]


# --- modes ---------------------------------------------------------------------

def mode_is_transient(args):
    policy = load_policy(args.repo, args.policy)
    all_junk = True
    for p in args.paths:
        verdict = is_transient(p, policy)
        print(f"{'transient' if verdict else 'keep'}\t{p}")
        all_junk = all_junk and verdict
    return 0 if (args.paths and all_junk) else 1


def _read_stdin_paths(use_nul):
    # Read bytes (non-UTF-8 path safety) and split on the exact separator.
    # Do NOT strip path content — a leading/trailing space is part of the name.
    # Drop only empty tokens (e.g. the trailing one after the final separator).
    data = sys.stdin.buffer.read()
    sep = b"\x00" if use_nul else b"\n"
    return [p.decode("utf-8", "surrogateescape") for p in data.split(sep) if p != b""]


def _emit_paths(paths, use_nul):
    sep = b"\x00" if use_nul else b"\n"
    out = sep.join(p.encode("utf-8", "surrogateescape") for p in paths)
    sys.stdout.buffer.write(out)
    if paths and not use_nul:
        sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()


def mode_filter(args):
    policy = load_policy(args.repo, args.policy)
    kept, excluded = [], []
    for p in _read_stdin_paths(args.z):
        (excluded if is_transient(p, policy) else kept).append(p)  # raw — never strip
    for p in excluded:
        sys.stderr.write(f"EXCLUDED (transient): {p}\n")
    _emit_paths(kept, args.z)
    return 0


def mode_autostage(args):
    policy = load_policy(args.repo, args.policy)
    tracked, untracked = parse_status(args.repo)
    if tracked is None:
        print("ERROR: not a git repository or git status failed", file=sys.stderr)
        return 2
    allpaths = tracked + untracked
    stage = [p for p in allpaths if not is_transient(p, policy)]
    for p in allpaths:
        if is_transient(p, policy):
            sys.stderr.write(f"EXCLUDED (transient): {p}\n")
    _emit_paths(stage, args.z)
    return 0


def mode_classify(args):
    policy = load_policy(args.repo, args.policy)
    tracked, untracked = parse_status(args.repo)
    if tracked is None:
        print(json.dumps({"schema": SCHEMA, "abort_reason": "not a git repo / git status failed"}))
        return 2
    declared = normalize(args.repo, load_provenance(args.dev_report, args.manifest))
    pathspecs = args.pathspec or []
    permissive = args.mode == "classify" and args.permissive

    stage, exclude, unclassified = [], [], []

    for p in tracked:
        if is_transient(p, policy):
            exclude.append({"path": p, "reason": "transient"})
        else:
            stage.append({"path": p, "reason": "tracked-change"})

    for p in untracked:
        if is_transient(p, policy):
            exclude.append({"path": p, "reason": "transient"})
        elif p in declared:
            stage.append({"path": p, "reason": "provenance"})
        elif matches_pathspec(p, pathspecs):
            stage.append({"path": p, "reason": "pathspec"})
        elif under_user_data_root(p, policy):
            stage.append({"path": p, "reason": "policy-user-data"})
        elif permissive:
            stage.append({"path": p, "reason": "autostage-opt-in"})
        else:
            unclassified.append(p)
            exclude.append({"path": p, "reason": "no-intent"})

    abort_reason = None
    if args.mode == "classify" and not args.permissive and not declared and not pathspecs and untracked:
        # No intent source at all but new files exist: surface, do not stage them.
        abort_reason = None  # advisory only — unclassified_new carries the signal

    plan = {
        "schema": SCHEMA,
        "repo": os.path.realpath(args.repo),
        "mode": args.mode,
        "task_id": args.task_id,
        "generated_by": "smart-staging-resolver",
        "stage": stage,
        "exclude": exclude,
        "unclassified_new": unclassified,
        "abort_reason": abort_reason,
        "attestation": attestation(args.repo, args.mode, [s["path"] for s in stage]),
    }
    out = json.dumps(plan, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out + "\n")
    else:
        print(out)
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="Deterministic staging gate.")
    p.add_argument("mode", choices=["is-transient", "filter", "autostage", "classify"])
    p.add_argument("paths", nargs="*", help="paths (is-transient mode)")
    p.add_argument("--repo", default=".", help="git repo root (default: cwd)")
    p.add_argument("--policy", default=None, help="path to staging-policy.json override")
    p.add_argument("--dev-report", default=None, help="dev-report JSON (classify provenance)")
    p.add_argument("--manifest", default=None, help="commit manifest JSON (classify provenance)")
    p.add_argument("--pathspec", action="append", help="explicit intent path (repeatable)")
    p.add_argument("--task-id", default=None)
    p.add_argument("--out", default=None, help="write stage_plan.json here (classify)")
    p.add_argument("-z", action="store_true", help="NUL-separated I/O (filter/autostage)")
    p.add_argument("--permissive", action="store_true",
                   help="classify: stage untracked-new without intent (autostage semantics)")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.repo = os.path.abspath(args.repo)
    if args.mode == "is-transient":
        return mode_is_transient(args)
    if args.mode == "filter":
        return mode_filter(args)
    if args.mode == "autostage":
        return mode_autostage(args)
    return mode_classify(args)


if __name__ == "__main__":
    sys.exit(main())
