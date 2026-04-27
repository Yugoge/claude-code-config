---
description: Delegate a task to OpenAI Codex CLI (gpt-5.5, xhigh reasoning) for a second opinion or parallel coding
argument-hint: [prompt or --review or --model <model> <prompt>]
allowed-tools: [Bash, Read, Glob, Grep]
---

# Codex CLI Integration

Run OpenAI Codex CLI to get a second opinion, delegate coding tasks, or perform code review.

## Instructions

If `$ARGUMENTS` is empty or blank, print this usage guide and stop:

```
Usage: /codex <prompt>              — run codex exec with the given prompt (default: gpt-5.5, reasoning: xhigh)
       /codex --review              — run codex review on the current directory
       /codex --model <model> <prompt> — use a specific model (still xhigh reasoning)

Examples:
  /codex refactor the auth middleware to use async/await
  /codex --review
  /codex --model o3 add input validation to all API endpoints
```

Otherwise, proceed:

### 1. Detect mode

- If `$ARGUMENTS` starts with `--review`, run **review mode**.
- If `$ARGUMENTS` starts with `--model`, extract the model name and the rest as the prompt, then run **exec mode** with `--model <model>`.
- Otherwise, run **exec mode** with the full `$ARGUMENTS` as the prompt (no `--model` flag — uses gpt-5.5 default with xhigh reasoning).

### 2. Generate unique output path

Run this first to get a collision-safe output file:
```bash
echo "/tmp/codex-output-$$-$(date +%s).txt"
```

Capture the printed path. Use it as `$CODEX_OUT` in all subsequent commands.

### 3. Review mode

```bash
codex review -c 'model="gpt-5.5"' -c 'reasoning_effort="xhigh"' 2>&1 | tee "$CODEX_OUT"
```

Use 10 minute Bash timeout. Then Read `$CODEX_OUT` with the Read tool.

### 4. Exec mode

**Without --model (default gpt-5.5):**
```bash
codex exec -c 'model="gpt-5.5"' -c 'reasoning_effort="xhigh"' "$PROMPT" 2>&1 | tee "$CODEX_OUT"
```

**With --model (user-specified model, still xhigh reasoning):**
```bash
codex exec -c 'model="<model>"' -c 'reasoning_effort="xhigh"' "$PROMPT" 2>&1 | tee "$CODEX_OUT"
```

Use 10 minute Bash timeout. Then Read `$CODEX_OUT` with the Read tool.

### 5. Present results

Read `$CODEX_OUT` with the Read tool. Show the complete Codex output to the user. If Codex made file changes, summarize what was modified. If it failed, show the error and suggest corrections.
