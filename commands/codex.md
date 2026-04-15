---
description: Delegate a task to OpenAI Codex CLI for a second opinion or parallel coding
argument-hint: [prompt or --review]
allowed-tools: [Bash, Read, Glob, Grep]
---

# Codex CLI Integration

Run OpenAI Codex CLI to get a second opinion, delegate coding tasks, or perform code review.

## Instructions

If `$ARGUMENTS` is empty or blank, print this usage guide and stop:

```
Usage: /codex <prompt>    — run codex exec with the given prompt
       /codex --review    — run codex review on the current directory
       /codex --model <model> <prompt> — use a specific model (default: o4-mini)

Examples:
  /codex refactor the auth middleware to use async/await
  /codex --review
  /codex --model o3 add input validation to all API endpoints
```

Otherwise, proceed:

### 1. Detect mode

- If `$ARGUMENTS` starts with `--review`, run **review mode**.
- If `$ARGUMENTS` starts with `--model`, extract the model name and the rest as the prompt, then run **exec mode** with `--model <model>`.
- Otherwise, run **exec mode** with the full `$ARGUMENTS` as the prompt.

### 2. Review mode

Run:
```bash
codex review 2>&1 | head -500
```

### 3. Exec mode

Run:
```bash
codex exec --model <model> "$PROMPT" 2>&1 | head -500
```

Default model is `o4-mini` unless `--model` was specified.

### 4. Present results

Show the full Codex output to the user. If Codex made file changes, summarize what was modified. If it failed, show the error and suggest corrections.
