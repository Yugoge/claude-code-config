# Implementation Plan: 12-Step Progress + Live Resume Preview

## Status: READY FOR EXECUTION

## Analysis Summary

After reading all affected files, here is the implementation plan organized by part:

### PART 1: Restore 12 Steps in ProgressTracker -- ALREADY DONE

`ProgressTracker.tsx` lines 300-308 already use `useStepLabels()` and `StepRow`. No change needed.

### PART 2: Backend Live Preview Service + Endpoint

**2a: Create `backend/app/services/live_preview_service.py`** (NEW FILE)
- `build_live_preview_html(gen, pipeline_state)` -- main function
- `_skeleton_html()` -- shimmer wireframe for early stages
- `_design_spec_to_preview_html(data)` -- section headers from design_spec
- `_resume_json_to_preview_html(data, stage)` -- actual content rendering
- All HTML is self-contained with inline CSS, A4 proportions

**2b: Add endpoint to `backend/app/api/generations.py`**
- Add `GET /{generation_id}/preview/live` endpoint BEFORE the existing `preview_resume` endpoint (line 232)
- Uses `_get_user_generation` for auth, does NOT require `status=="completed"`
- Returns `HTMLResponse` from `build_live_preview_html`

### PART 3: SSE Preview Milestone Events -- ALREADY DONE

The backend already has `preview_milestone` support:
- `progress_service.py` line 60: `publish_progress` accepts `preview_milestone` parameter
- `progress_service.py` lines 93-108: `_apply_optional_fields` includes `preview_milestone`
- `orchestrator_helpers.py` line 49: `publish_progress` passes through `preview_milestone`
- `orchestrator.py` line 48-50: `publish_progress` passes `**kwargs` to helpers

What's MISSING: The actual milestone event emissions in orchestrator.py at steps 2, 5, 8, 9.

**Insertion points in orchestrator.py:**
- After line 395 (`_update_db(2, "Design", 16.7)`) -- add preview_milestone for step 2
- After line 547 (`_update_db(5, "Assemble", 50.0)`) -- add preview_milestone for step 5
- After line 628 (`_update_db(8, "Final Assembly", 75.0)`) -- add preview_milestone for step 8
- After line 667 (`_update_db(9, "Templates", 83.3)`) -- add preview_milestone for step 9

### PART 4: Frontend LiveResumePreview Component (NEW FILE)

Create `frontend/src/components/LiveResumePreview.tsx`:
- iframe-based preview with A4 ratio container
- Uses `fetchPreviewBlobUrl` from api.ts (auth-aware fetch) to load preview HTML
- Refreshes when `refreshKey` changes (milestone events)
- Shows loading spinner, status bar with "Live Preview" / "Preview" label
- Pulse indicator when actively generating

NOTE: The preview URL needs auth headers. Cannot use plain iframe `src`. Must use `fetchPreviewBlobUrl` pattern (already exists in api.ts line 245) to fetch HTML with auth, create blob URL, set as iframe src.

### PART 5: Wire SSE + Restructure Layout

**5a: `frontend/src/lib/api.ts`** -- Add `preview_milestone` to `ProgressEvent` type + add `getLivePreviewUrl` helper

**5b: `frontend/src/app/generate/[id]/useSseSubscription.ts`** -- Add `onPreviewMilestone` callback param, detect `event.preview_milestone` in handler

**5c: `frontend/src/app/generate/[id]/useGenerationProgress.ts`** -- Add `previewRefreshKey` state, wire `onPreviewMilestone` callback, expose in interface

**5d: `frontend/src/app/generate/[id]/page.tsx`** -- Restructure layout:
- Desktop: `md:grid-cols-5` -- left 2 cols = steps, right 3 cols = preview + status/log
- Import + render LiveResumePreview with generationId, refreshKey, status
- Move activity log below preview, collapsible

### PART 6: API Helper

Add `getLivePreviewUrl` to `frontend/src/lib/api.ts`:
```typescript
export function getLivePreviewUrl(id: string): string {
  return `${API_BASE}/api/generations/${id}/preview/live`;
}
```

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `backend/app/services/live_preview_service.py` | CREATE | Live preview HTML builder |
| `backend/app/api/generations.py` | MODIFY | Add `/preview/live` endpoint |
| `backend/pipeline/orchestrator.py` | MODIFY | Add 4 preview_milestone publish calls |
| `frontend/src/components/LiveResumePreview.tsx` | CREATE | iframe preview component |
| `frontend/src/lib/api.ts` | MODIFY | Add preview_milestone to ProgressEvent + getLivePreviewUrl |
| `frontend/src/app/generate/[id]/useSseSubscription.ts` | MODIFY | Add onPreviewMilestone callback |
| `frontend/src/app/generate/[id]/useGenerationProgress.ts` | MODIFY | Add previewRefreshKey state |
| `frontend/src/app/generate/[id]/page.tsx` | MODIFY | Restructure layout + add LiveResumePreview |

## Blast Radius

Need to grep for importers of each modified file to understand impact scope.

## Build Verification

- Backend: `python -m py_compile backend/app/services/live_preview_service.py` and `python -m py_compile backend/app/api/generations.py`
- Frontend: `cd frontend && npx tsc --noEmit`

## Key Design Decisions

1. **Auth for preview iframe**: Use `fetchPreviewBlobUrl` (blob URL from auth fetch) rather than direct iframe src, since the API requires Bearer token auth
2. **Preview milestone as integer**: Backend already uses `preview_milestone: int | None` -- will pass step number as the value so frontend knows which stage triggered the refresh
3. **Layout**: 5-col grid (2 + 3) on desktop gives good proportions for steps vs preview
