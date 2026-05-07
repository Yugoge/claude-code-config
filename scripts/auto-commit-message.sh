#!/usr/bin/env bash
# auto-commit-message.sh: produce a commit message from cycle artifacts.
# Usage: auto-commit-message.sh <task-id>
# Output: a multi-line commit message to stdout. Always exits 0 with some content.
set -u
TASK_ID="${1:-}"
if [ -z "$TASK_ID" ]; then
  echo "auto-commit-message: missing task-id arg" >&2
  exit 0
fi
ROOT="${CLAUDE_PROJECT_DIR:-/root}"
TASK_ID="$TASK_ID" ROOT="$ROOT" python3 -c '
import os, json, sys
task_id = os.environ["TASK_ID"]
root = os.environ["ROOT"]

def first_h1_para(text):
    lines = text.splitlines()
    h1 = ""
    para_lines = []
    in_para = False
    for line in lines:
        if not h1 and line.startswith("# "):
            h1 = line[2:].strip()
            continue
        if h1:
            if not in_para:
                if line.strip() == "":
                    continue
                if line[:1] in ("#", "-", "*", "|", "`", ">"):
                    continue
                in_para = True
            if in_para:
                if line.strip() == "" or (line[:1] in ("#", "|", "`", ">")):
                    break
                para_lines.append(line.strip())
                if len(para_lines) >= 5:
                    break
    return h1, " ".join(para_lines)

def last_verdict(text):
    for line in reversed(text.strip().splitlines()):
        ls = line.strip()
        if ls.startswith("CLOSE:"):
            return ls
    return ""

close_path = root + "/docs/dev/close-report-" + task_id + ".md"
if os.path.exists(close_path):
    txt = open(close_path).read()
    h1, para = first_h1_para(txt)
    verdict = last_verdict(txt)
    out = []
    if h1: out.append(h1)
    if para:
        out.append("")
        out.append(para)
    if verdict:
        out.append("")
        out.append("(" + verdict + ")")
    if out:
        print("\n".join(out))
        sys.exit(0)

comp_path = root + "/docs/dev/completion-" + task_id + ".md"
if os.path.exists(comp_path):
    txt = open(comp_path).read()
    h1, para = first_h1_para(txt)
    if h1 or para:
        out = []
        if h1: out.append(h1)
        if para:
            out.append("")
            out.append(para)
        print("\n".join(out))
        sys.exit(0)

dev_path = root + "/docs/dev/dev-report-" + task_id + ".json"
if os.path.exists(dev_path):
    try:
        d = json.load(open(dev_path))
    except Exception:
        d = {}
    dev_node = d.get("dev")
    summary = ""
    if isinstance(dev_node, dict):
        summary = dev_node.get("summary") or ""
    if not summary:
        recs = d.get("recommendations") or []
        summary = recs[0] if recs else ""
    if summary:
        print("task " + task_id + ": " + str(summary)[:120])
        sys.exit(0)

print("task " + task_id + ": see docs/dev/")
'
