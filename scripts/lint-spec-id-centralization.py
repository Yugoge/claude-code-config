#!/usr/bin/env python3
"""Static lint (M9 / F5, task 20260530-092123): forbid any /dev*//spec command
markdown from re-deriving a spec-id / views_dir / split_marker / cp_dir from a
path INLINE instead of calling the centralized resolver helper
(scripts/resolve-spec-artifacts.py).

Centralization is the 治本 fix: prose re-derivation is the exact mechanism by
which the spec- prefix rule drifted. This lint mechanically prevents recurrence.

A line FAILS if it contains a forbidden inline spec-id-from-path derivation
pattern AND is NOT whitelisted. Whitelist:
  - the resolver invocation line itself (contains `resolve-spec-artifacts`)
  - the lint script's own name (self-reference)
  - any line carrying the explicit allow-marker `# spec-id-lint: allow`

Usage:
  lint-spec-id-centralization.py --paths <file> [<file> ...]
Exit: 0 = clean ; 1 = forbidden inline derivation found ; 2 = usage error
"""

import argparse
import re
import sys

# Forbidden inline derivation patterns (prose or bash) that re-derive a spec-id /
# views_dir / split_marker / cp_dir from a path instead of consuming the resolver.
FORBIDDEN = [
    # basename(spec_path) style spec-id derivation
    re.compile(r"basename\s*\(?\s*\$?\{?(?:USER_)?SPEC_PATH", re.IGNORECASE),
    re.compile(r"basename\s+\"?\$\{?(?:USER_)?SPEC_PATH", re.IGNORECASE),
    # ${SPEC_PATH%.md} / ${USER_SPEC_PATH%.md} strip-suffix derivation
    re.compile(r"\$\{(?:USER_)?SPEC_PATH%\.md\}"),
    # inline views/split/cp paths built from a $SPEC_ID variable
    re.compile(r"docs/dev/specs/\$\{?SPEC_ID\}?/"),
    re.compile(r"\.claude/specs/\$\{?SPEC_ID\}?\b"),
    # building manifest/split paths from a bare basename-derived id
    re.compile(r"docs/dev/specs/\$\{?(?:ARTIFACT_ID|SPEC_BASENAME)\}?/views", re.IGNORECASE),
]

# Whitelist markers — a line matching any of these is exempt.
WHITELIST = [
    re.compile(r"resolve-spec-artifacts"),
    re.compile(r"lint-spec-id-centralization"),
    re.compile(r"#\s*spec-id-lint:\s*allow"),
]


def lint_file(path):
    violations = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError as exc:
        return [("<read-error>", 0, str(exc))]
    for n, line in enumerate(lines, 1):
        if any(w.search(line) for w in WHITELIST):
            continue
        for pat in FORBIDDEN:
            if pat.search(line):
                violations.append((path, n, line.rstrip()))
                break
    return violations


def main(argv=None):
    parser = argparse.ArgumentParser(description="Lint command markdown for inline spec-id derivation.")
    parser.add_argument("--paths", nargs="+", required=True, help="Files to lint")
    args = parser.parse_args(argv)

    all_violations = []
    for p in args.paths:
        all_violations.extend(lint_file(p))

    if all_violations:
        sys.stderr.write("spec-id centralization lint FAILED — inline spec-id-from-path derivation found:\n")
        for path, n, line in all_violations:
            sys.stderr.write("  %s:%d  %s\n" % (path, n, line))
        sys.stderr.write("Route spec-id/views_dir/split_marker/cp_dir through scripts/resolve-spec-artifacts.py "
                         "(or add `# spec-id-lint: allow` to an intentional example line).\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
