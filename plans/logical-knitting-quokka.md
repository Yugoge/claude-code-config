# Plan: Integrate JD Scorer into Applio Pipeline

## Context

The user has created a `jd-scorer` agent in `application-assistant` that scores every resume YAML item against JD requirements (1-10 scale) before story experts run. This gives story experts pre-scored priorities instead of re-analyzing JD fit themselves. The goal is to add this as Step 2.5a in the applio pipeline.

## Data Flow

```
Step 1: Parse JD → job_data
Step 2: Designer → design_spec
Step 2.5a: JD Scorer [NEW] → jd_scores  
Step 2.5b: Supplementors → supplements
Step 3: Story Experts (receive jd_scores inline in prompt)
```

## Files to Create

### 1. `backend/pipeline/agents/jd-scorer.md`
- Run `sync_prompts.py --agent jd-scorer` to transform from application-assistant
- Verify: no file paths, has TOOL USE PROTOCOL, has negative directive

### 2. `backend/pipeline/steps/step02c_jd_scorer.py`
- `async def step_jd_scorer(job_data, resume_yaml, work_dir, job_id, ts, publish_progress, generation_id) -> dict`
- Calls `call_agent_json("jd-scorer", user_prompt)` with job_data + resume_yaml embedded inline
- Returns parsed jd_scores dict
- Saves to `04_jd_scores_{job_id}_{ts}.json`

## Files to Modify

### 3. `backend/pipeline/agent_registry.py`
- Add to `_AGENT_TAGS`: `"jd-scorer": frozenset({"resume", "scoring"})`
- Add to `_AGENT_PHASES`: `"jd-scorer": "Step 2.5a -- JD Scoring"`
- Add to max_tokens: `"jd-scorer": 16384`
- Add schema `_SCHEMA_JD_SCORER` with flat keys:
  - `job_id` (string), `experience_json` (string), `education_json` (string)
  - `project_json` (string), `skill_rankings_json` (string), `coverage_json` (string)
- Add to `_TOOL_SCHEMAS`: `"jd-scorer": _SCHEMA_JD_SCORER`
- Add reconstructor mapping

### 4. `backend/pipeline/reconstruct.py`
- Add `reconstruct_jd_scorer(inp)` — parses each `*_json` field via `_parse_json_field`
- Register in `RECONSTRUCTORS`

### 5. `backend/pipeline/orchestrator.py` (~line 378)
- Insert Step 2.5a between supplementors and Step 3
- Call `step_jd_scorer()`, catch exceptions (non-fatal, continue with empty dict)
- Pass `jd_scores` to `step_story_experts()`

### 6. `backend/pipeline/steps/step03_story_experts.py`
- Add `jd_scores: dict | None = None` parameter to `step_story_experts()`
- Forward to `_run_both_tracks()` → `run_resume_stories()` / `run_cl_stories()`

### 7. `backend/pipeline/steps/step03_resume_stories.py`
- Add `jd_scores: dict | None = None` to `build_resume_story_prompt()`
- Embed `## JD Scores` section in user prompt (same pattern as job_data)
- Add to `run_resume_stories()` to accept and pass through

### 8. `backend/pipeline/steps/step03_cl_stories.py`
- Same changes as step03_resume_stories.py — add jd_scores to CL story prompt builder

### 9. Agent prompts (via sync_prompts.py)
- `sync_prompts.py` already converts `04_jd_scores_{job_id}.json` → "the job scores data"
- The application-assistant prompts already reference jd_scores in story-expert-professional, -project, -skills
- After sync, prompts will say "Review the job scores data" which matches the inline `## JD Scores` section

## Verification

1. Rebuild Docker, restart containers
2. Trigger generation via API
3. Check worker logs for "Agent jd-scorer" call success
4. Verify `04_jd_scores_*.json` file created in work dir
5. Verify story expert prompts include `## JD Scores` section
6. Full pipeline should complete Steps 1-12
