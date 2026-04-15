# Plan: Restore 12-Step Progress + Dynamic Resume Rendering

## Context
The generation progress page currently shows only 4 compressed "phases" instead of the original 12 pipeline steps. The user wants the full 12 steps restored for a more professional feel. Additionally, the resume is completely invisible during generation — the user cannot see any output until the entire pipeline completes. The user wants progressive/dynamic rendering: as each step produces output, it should be visually reflected in a live resume preview.

## Current State
- **ProgressTracker.tsx**: Uses `PhaseRow` (4 phases) via `usePhaseLabels()`. The original 12-step `StepRow` and `useStepLabels()` still exist but are unused.
- **Generation page** (`/generate/[id]/page.tsx`): 3-column grid — left (1col) = progress tracker, right (2col) = status/activity log. No resume preview.
- **Preview endpoint** (`/api/generations/{id}/preview/resume`): Requires `status == "completed"`, serves final HTML only.
- **Backend pipeline**: 12 steps produce intermediate JSON files in `work_dir` at each stage.

## Changes

### 1. Restore 12 Steps in ProgressTracker (frontend only)

**File**: `frontend/src/components/ProgressTracker.tsx`

Switch `VerticalTimeline` from rendering `PhaseRow` (4 phases) back to `StepRow` (12 steps). The `StepRow` component and `useStepLabels()` already exist in the file — just wire them into the default export.

- Change `VerticalTimeline` to use `useStepLabels()` instead of `usePhaseLabels()`
- Render `StepRow` components instead of `PhaseRow`
- Keep `PhaseRow` code intact (dead code is fine for now)

### 2. Backend: Live Preview Endpoint

**File**: `backend/app/api/generations.py`

Add new endpoint: `GET /api/generations/{id}/preview/live`
- Does NOT require `status == "completed"`
- Reads `pipeline_state` from DB to determine current step
- Returns appropriate HTML based on generation progress:

| Current Step | Preview Source | Content |
|---|---|---|
| 1 | None | Skeleton wireframe HTML (static) |
| 2-4 | `design_spec` JSON | Section headers + placeholder blocks |
| 5-7 | `assembled_resume` JSON | Assembled content with draft bullets |
| 8 | `final_resume` JSON | Final content, simple HTML layout |
| 9+ | `resume_html_path` | Actual rendered template HTML |

Each preview level generates a simple styled HTML document. Use inline CSS for self-contained rendering in an iframe.

Helper functions:
- `_design_spec_to_preview_html(design_spec)` — renders section names + empty placeholder boxes
- `_assembled_to_preview_html(assembled)` — renders real section content with bullets
- `_final_resume_to_preview_html(final_resume)` — renders polished content layout

### 3. Backend: SSE Preview Signal

**File**: `backend/pipeline/orchestrator.py` + `backend/pipeline/orchestrator_helpers.py`

After steps 2, 5, 8, 9 complete, publish a SSE event with `preview_milestone: N` field in the progress payload. This tells the frontend "new preview data is available, refresh the iframe."

**File**: `backend/app/services/progress_service.py`

Pass through the `preview_milestone` field in `build_progress_event()`.

### 4. Frontend: Live Preview Component

**New file**: `frontend/src/components/LiveResumePreview.tsx`

A component that:
- Renders an iframe pointing to `/api/generations/{id}/preview/live`
- Listens for `preview_milestone` changes from SSE
- Reloads the iframe (by appending `?v={milestone}` query param) when milestone changes
- Shows a skeleton/shimmer while loading
- Shows a subtle "Building..." overlay with current step context
- Smooth fade transition between preview states

### 5. Frontend: Restructure Generation Page Layout

**File**: `frontend/src/app/generate/[id]/page.tsx`

Restructure from current 3-column to new layout:

**Desktop**: 
```
[Steps (narrow)] | [Live Resume Preview (wide)] 
                  | [Activity Log (collapsible, below preview)]
```
- Grid: `md:grid-cols-5` — left 2 cols = steps, right 3 cols = preview + log
- Activity log defaults to collapsed during generation

**Mobile**:
```
[Steps (compact)]
[Live Resume Preview]
[Activity Log (collapsed)]
```

### 6. Frontend: Wire SSE preview_milestone to state

**File**: `frontend/src/app/generate/[id]/useSseSubscription.ts`

Extract `preview_milestone` from SSE events and expose it in `GenerationProgressState`.

**File**: `frontend/src/app/generate/[id]/useGenerationProgress.ts`

Add `previewMilestone` state, pass to `LiveResumePreview`.

## File Change Summary

| File | Action | Scope |
|---|---|---|
| `frontend/src/components/ProgressTracker.tsx` | Edit | Switch to 12 StepRows |
| `frontend/src/components/LiveResumePreview.tsx` | **New** | Live iframe preview component |
| `frontend/src/app/generate/[id]/page.tsx` | Edit | New layout with preview panel |
| `frontend/src/app/generate/[id]/useGenerationProgress.ts` | Edit | Add previewMilestone state |
| `frontend/src/app/generate/[id]/useSseSubscription.ts` | Edit | Extract preview_milestone |
| `backend/app/api/generations.py` | Edit | Add live preview endpoint |
| `backend/pipeline/orchestrator.py` | Edit | Emit preview_milestone at steps 2,5,8,9 |
| `backend/app/services/progress_service.py` | Edit | Pass preview_milestone field |

## Verification
1. Start a new generation via the UI
2. Confirm all 12 steps appear in the progress tracker
3. Watch the live preview panel — should show:
   - Skeleton at step 1
   - Section layout wireframe after step 2
   - Draft content after step 5
   - Final content after step 8  
   - Full HTML template after step 9
4. Verify mobile layout works
5. Verify SSE reconnection restores correct preview state
