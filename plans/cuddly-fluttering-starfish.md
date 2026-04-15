# Plan: Integrate Story Supplementor into Both Projects

## Context

Two story supplementor agents (`story-supplementor-resume.md`, `story-supplementor-cl.md`) exist as fully designed prompt files in both projects but are never invoked. The resume supplementor generates JD-targeted Type A/B/C stories; the CL supplementor generates personal narrative stories. They were briefly implemented in application-assistant (commit `5f64e0b`) then removed 17 minutes later (commit `760002d`). The agents, file paths, and downstream consumption hooks are all ready — only the orchestration wiring is missing.

## Changes

### Part 1: Applio Pipeline (5 files)

**1. `backend/pipeline/agent_registry.py`** — Register both agents:
- Add to `_AGENT_TAGS`, `_AGENT_PHASES`, `_MAX_TOKENS_OVERRIDES` (16384 each)
- Add two flat schemas: `_SCHEMA_SUPPLEMENTOR_RESUME` (source, experience_supplements_json, project_supplements_json) and `_SCHEMA_SUPPLEMENTOR_CL` (source, personal_stories_json)
- Map both in `_TOOL_SCHEMAS`

**2. `backend/pipeline/reconstruct.py`** — Add two reconstruction functions:
- `reconstruct_supplementor_resume`: experience_supplements_json → experience_supplements, project_supplements_json → project_supplements
- `reconstruct_supplementor_cl`: personal_stories_json → personal_stories
- Register in `RECONSTRUCTORS` dict

**3. `backend/pipeline/steps/step02b_supplementor.py`** (NEW) — Step file:
- `_build_resume_supplementor_prompt()` — embeds design_spec, job_data, resume_yaml inline
- `_build_cl_supplementor_prompt()` — embeds cl_design, job_data, resume_yaml inline
- Validators for both outputs
- `run_step02b_supplementors()` — runs both in parallel via `asyncio.gather`, each wrapped in try/except returning `{}` on failure

**4. `backend/pipeline/orchestrator.py`** — Wire Step 2.5:
- Import `run_step02b_supplementors`
- Insert between Step 2 validation and Step 3
- Does NOT add a new step number (keeps 12-step UI intact)
- Pass `resume_supplements` and `cl_supplements` to Step 3

**5. `backend/pipeline/steps/step03_resume_stories.py` + `step03_cl_stories.py`** — Thread supplements:
- Add optional `supplements` parameter to prompt builders
- Append supplementary context section to prompts when non-empty

### Part 2: Application-Assistant (1 file)

**`/root/application-assistant/.claude/commands/generate.md`** — Re-add Step 2.5:
- Add file path rows to the table
- Add to workflow overview
- Insert full Step 2.5 section (two parallel Task invocations)
- Re-add optional supplementary input references to Step 3 agent prompts

## Key Design Decisions

- **Graceful degradation**: supplementor failure → pipeline continues with `{}` supplements
- **No UI step change**: stays 12 steps, supplementors piggyback on Step 2 progress
- **Parallel execution**: both supplementors run concurrently
- **Optional consumption**: Step 3 agents treat supplements as enrichment hints, not requirements

## Verification

1. `py_compile` all modified Python files
2. Docker rebuild + redeploy
3. Trigger E2E generation via browser
4. Check docker logs for supplementor agent calls
5. Verify generation completes all 12 steps
6. Verify supplementary files exist in work directory (or graceful skip if agent fails)
