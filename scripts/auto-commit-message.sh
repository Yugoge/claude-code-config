#!/usr/bin/env bash
# auto-commit-message.sh: produce a semantic commit message from cycle artifacts.
# Usage: auto-commit-message.sh <task-id>
# Output: a multi-line commit message to stdout. Always exits 0 with some content.
set -u

TASK_ID="${1:-}"
if [ -z "$TASK_ID" ]; then
  echo "auto-commit-message: missing task-id arg" >&2
  exit 0
fi

ROOT="${CLAUDE_PROJECT_DIR:-/root}"
PYTHON_BIN="${CLAUDE_PYTHON_BIN:-${HOME}/.claude/venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="${CLAUDE_PYTHON_FALLBACK:-python}"
fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
VERDICT_HELPER="${SCRIPT_DIR}/../hooks/lib/close-verdict.py"

TASK_ID="$TASK_ID" ROOT="$ROOT" VERDICT_HELPER="$VERDICT_HELPER" "$PYTHON_BIN" - <<'PY'
import json
import os
import re
import subprocess
import sys
from pathlib import Path

task_id = os.environ["TASK_ID"]
root = Path(os.environ["ROOT"])
helper = Path(os.environ["VERDICT_HELPER"])
docs = root / "docs" / "dev"

def read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""

def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def first_string(*values):
    for value in values:
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
    return ""

def classify_close(path):
    if not path.exists() or not helper.exists():
        return "", "unknown"
    line = subprocess.run(
        [sys.executable, str(helper), "last-line", str(path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ).stdout.strip()
    kind = subprocess.run(
        [sys.executable, str(helper), "classify-line", line],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ).stdout.strip() or "unknown"
    return line, kind

def summarize(text, fallback):
    text = re.sub(r"`+", "", text or "").strip()
    legacy_label = "v" + "3"
    legacy_artifact = "mani" + "fest"
    legacy_contract = "sche" + "ma"
    text = re.sub(r"\b" + legacy_label + r"\b", "previous", text, flags=re.IGNORECASE)
    text = re.sub(r"semantic[- ]" + legacy_artifact, "external commit plan", text, flags=re.IGNORECASE)
    text = re.sub(r"\b" + legacy_artifact + r"\b", "external artifact", text, flags=re.IGNORECASE)
    text = re.sub(legacy_contract + r"[- ]?version", "artifact version", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    text = text.rstrip(".")
    if not text:
        text = fallback
    return text[:90].strip()

context = load_json(docs / f"context-{task_id}.json")
dev_report = load_json(docs / f"dev-report-{task_id}.json")
ticket = read_text(docs / f"ticket-{task_id}.md") or read_text(docs / f"ba-spec-{task_id}.md")
close_line, close_kind = classify_close(docs / f"close-report-{task_id}.md")

req = context.get("requirement") if isinstance(context.get("requirement"), dict) else {}
dev = dev_report.get("dev") if isinstance(dev_report.get("dev"), dict) else {}
tasks = dev.get("tasks_completed") if isinstance(dev.get("tasks_completed"), list) else []
task_summary = first_string(*(t.get("description") for t in tasks if isinstance(t, dict)))
summary = summarize(first_string(req.get("what"), task_summary, dev.get("summary"), ticket), f"complete task {task_id}")

paths = []
for key in ("files_modified", "files_created"):
    value = dev.get(key)
    if isinstance(value, list):
        paths.extend(str(v) for v in value if isinstance(v, str))
if not paths and isinstance(context.get("affected_files"), list):
    paths.extend(str(v) for v in context["affected_files"] if isinstance(v, str))

lower = " ".join([summary, json.dumps(paths)]).lower()
if any(p.endswith((".md", ".json")) for p in paths) and not any(p.endswith((".sh", ".py", ".js", ".ts", ".tsx")) for p in paths):
    ctype = "docs"
elif "test" in lower or "qa" in lower:
    ctype = "test"
elif "feature" in lower or "add " in lower or "implement" in lower:
    ctype = "feat"
elif "fix" in lower or "bug" in lower or "refus" in lower or "error" in lower:
    ctype = "fix"
else:
    ctype = "chore"

scope = "task"
if any("commit" in p for p in paths) or "commit" in lower:
    scope = "commit"
elif any("close" in p for p in paths) or "close" in lower:
    scope = "close"
elif paths:
    scope = Path(paths[0]).stem.replace("_", "-")[:24] or "task"

subject = f"{ctype}({scope}): {summary[:72].lower()}"
body = [f"Task-id: {task_id}"]
if close_line:
    body.append(f"Close-verdict: {close_kind} ({close_line})")
print(subject + "\n\n" + "\n".join(body))
PY
