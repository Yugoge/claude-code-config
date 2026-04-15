# Live Preview Implementation Plan

## Status: Ready to Execute

All files have been read and analyzed. Here is the complete implementation plan.

---

## Part 1: ProgressTracker.tsx -- ALREADY DONE
Lines 300-308 already use `useStepLabels()` + `StepRow`. No change needed.

## Part 2: CREATE `backend/app/services/live_preview_service.py`

New file with 4 functions:
- `build_live_preview_html(gen, pipeline_state)` -- dispatches based on pipeline progress
- `_skeleton_html()` -- animated wireframe placeholder (step < 2)
- `_design_spec_to_preview_html(design_spec)` -- section headers + shimmer (steps 2-4)
- `_resume_json_to_preview_html(data, stage)` -- actual resume content (steps 5+)

All HTML is self-contained with inline CSS, A4 proportioned, white background.

Logic:
- If no pipeline_state or step < 2: return skeleton
- If step >= 9 and resume_html_path exists: return the actual rendered HTML
- If step >= 5 and resume_final_json exists: render from JSON
- If step >= 2 and design_spec exists: render section placeholders
- Fallback: skeleton

## Part 3: EDIT `backend/app/api/generations.py`

Add endpoint after the existing preview endpoints (~line 297):
```python
@router.get("/{generation_id}/preview/live", response_class=HTMLResponse)
async def preview_live(generation_id, user_id, db):
    gen = await _get_user_generation(db, generation_id, user_id)
    # No status==completed check -- works during generation
    from app.services.live_preview_service import build_live_preview_html
    html = build_live_preview_html(gen, gen.pipeline_state or {})
    return HTMLResponse(content=html)
```

## Part 4: EDIT `backend/pipeline/orchestrator.py`

Add `preview_milestone=N` kwarg to existing `publish_progress()` calls after:
- Step 2 completion (after `_update_db(2, ...)`) -- milestone 1
- Step 5 completion (after `_update_db(5, ...)`) -- milestone 2  
- Step 8 completion (after `_update_db(8, ...)`) -- milestone 3
- Step 9 completion (after `_update_db(9, ...)`) -- milestone 4

Each is a single `publish_progress(generation_id, step, name, detail, preview_milestone=N)` call.

## Part 5: EDIT `frontend/src/lib/api.ts`

1. Add `preview_milestone?: number` to `ProgressEvent` interface (after `current_sub_step`)
2. Add function:
```typescript
export function getLivePreviewUrl(id: string): string {
  return `${API_BASE}/api/generations/${id}/preview/live`;
}
```

## Part 6: CREATE `frontend/src/components/LiveResumePreview.tsx`

React component:
- Props: `generationId: string`, `refreshKey: number`
- Uses `fetchPreviewBlobUrl(getLivePreviewUrl(generationId))` on mount and when refreshKey changes
- Renders iframe with blob URL src
- Shows loading spinner between refreshes
- A4 aspect ratio container (210:297 ratio)

## Part 7: EDIT `frontend/src/app/generate/[id]/useSseSubscription.ts`

Add `onPreviewMilestone?: (milestone: number) => void` to Params interface.
In handleEvent, after existing logic, add:
```typescript
if (event.preview_milestone != null && onPreviewMilestone) {
  onPreviewMilestone(event.preview_milestone);
}
```

## Part 8: EDIT `frontend/src/app/generate/[id]/useGenerationProgress.ts`

1. Add `previewRefreshKey: number` to `GenerationProgressState` interface
2. Add `[previewRefreshKey, setPreviewRefreshKey] = useState(0)` state
3. Wire to SSE: add `onPreviewMilestone` callback in useSseParams that increments the key
4. Expose `previewRefreshKey` in the return object

## Part 9: EDIT `frontend/src/app/generate/[id]/page.tsx`

1. Import `LiveResumePreview` and `getLivePreviewUrl`
2. Change grid from `md:grid-cols-3` to `md:grid-cols-5`
3. LeftColumn stays `col-span-1` (or becomes `md:col-span-2`)
4. Add LiveResumePreview in a new middle/right column (`md:col-span-3`)
5. Move ActivityLog below the preview, default collapsed
6. Mobile: stack vertically (already handled by grid-cols-1 default)
7. Update skeleton to match new layout

---

## Build Verification
After all edits: `cd /dev/shm/dev-workspace/applio/frontend && npx tsc --noEmit`
