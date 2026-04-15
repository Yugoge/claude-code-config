# Plan: Portal Detail Page — View Company Openings

## Context
Users have loaded company portals and want to browse all openings from a specific company. Currently the only way to find portal jobs is via the global search bar (ILIKE match). There's no way to click into a portal and see all its cached jobs. This adds that flow.

## What's Needed

### 1. Backend — new endpoint in `backend/app/api/portals.py`

Add `GET /api/portals/{portal_id}/jobs`:
```python
@router.get("/{portal_id}/jobs")
async def list_portal_jobs(
    portal_id: str,
    user_id: CurrentUserId,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
```
- First call `_get_user_portal(db, portal_id, user_id)` — ownership check (already exists)
- Query `PortalJob` where `portal_id == portal_id`, `is_active == True`
- Order by `first_seen_at DESC`
- Paginate with offset/limit
- Return `{ jobs: [...], total: int, page: int, pages: int }`

Response shape per job (matches `JobSearchResult` on frontend):
```python
{
  "id": job.id,
  "title": job.title,
  "company": job.company,
  "location": job.location,
  "description": job.description,
  "salary_range": job.salary_range,
  "job_url": job.job_url,
  "source": job.source,
  "source_id": job.source_id,
  "posted_at": job.posted_at.isoformat() if job.posted_at else None,
  "is_saved": False,      # portal jobs aren't pre-checked against saved list
  "saved_job_id": None,
}
```

### 2. Frontend hook — new `usePortalJobs` in `frontend/src/app/jobs/portals/use-portals.ts`

```typescript
export function usePortalJobs(portalId: string, page: number) {
  // fetches GET /api/portals/{portalId}/jobs?page={page}&limit=20
  // returns { data, loading, error }
  // data: { jobs: JobSearchResult[], total: number, page: number, pages: number }
}
```

Also add `usePortal(id)` to fetch a single portal for the page header (reuse the existing Portal interface).

### 3. Frontend page — `frontend/src/app/jobs/portals/[id]/page.tsx` (new file)

Structure:
```
AuthGuard → PortalJobsContent
  PortalJobsHeader  — company name, ATS type badge, "Back" link, "Scan Now" button
  Job list (reuse JobCard + save handlers pattern from jobs/page.tsx)
  PaginationBar (copy from jobs/page.tsx)
```

Key patterns to reuse from `frontend/src/app/jobs/page.tsx`:
- `useLocalJobs` + `useSaveHandlers` hooks (exact same, copy)
- `JobCardList` component (via import of `JobCard`)
- `PaginationBar` component

Portal jobs have no status/notes — show `JobCard` with save/unsave only (no `StatusBadge`).

### 4. Portals list page — add "View Jobs" link per row

In `frontend/src/app/jobs/portals/page.tsx`, add a "Jobs" count/link in `PortalRow` or `PortalMeta`:
```tsx
<Link href={`/jobs/portals/${portal.id}`} className="glass-button glass-button-secondary text-xs py-1 px-2">
  {portal.scan_results_count > 0 ? `${portal.scan_results_count} jobs` : "View"}
</Link>
```

## Files to Touch

| File | Change |
|------|--------|
| `backend/app/api/portals.py` | Add `GET /{portal_id}/jobs` endpoint |
| `frontend/src/app/jobs/portals/use-portals.ts` | Add `usePortalJobs(id, page)` and `usePortal(id)` hooks |
| `frontend/src/app/jobs/portals/[id]/page.tsx` | New file — portal detail page |
| `frontend/src/app/jobs/portals/page.tsx` | Add "View Jobs" link per portal row |

## Verification

1. Navigate to `/jobs/portals` → each portal row shows job count link
2. Click link → `/jobs/portals/{id}` loads with company name header
3. Jobs list shows paginated portal_jobs for that company
4. Save button on a job saves it to `/api/jobs/save` (existing endpoint)
5. Backend: `curl /api/portals/{id}/jobs` returns `{jobs, total, page, pages}`
