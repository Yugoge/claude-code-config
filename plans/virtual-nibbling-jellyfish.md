# Fix 5 UI Bugs in Applio

## Context

After deploying the auth + OAuth system, several UI bugs were reported across the generate, dashboard, and static pages.

## Root Cause Analysis

### Bug 1: PDF preview not rendering + tokens show 0
- **Preview**: The iframe preview loads HTML via `/api/generations/{id}/preview/resume` which goes through the Next.js proxy. The proxy at `route.ts:15-19` reads response as `resp.text()` which works for HTML, but the issue is likely the iframe `sandbox="allow-same-origin"` preventing CSS/resource loading. Need to verify on actual page.
- **Tokens 0**: DB confirms `total_input_tokens=0, total_output_tokens=0`. The generations were created in debug mode (mock files visible in work dir: `03_mock_resume_*`). This is correct behavior for debug mode - no AI calls = no tokens. The UI should show "Debug Mode" instead of misleading "Free" cost.

### Bug 2 & 3: Dashboard/Generate download gives JSON or blank PDF
- **Root cause**: `frontend/src/app/api/[...path]/route.ts:45` — `proxyResponse(await resp.text(), resp)` reads binary PDF as text, corrupting it. The `proxyResponse` function creates `new NextResponse(data)` from text string, destroying binary content.
- **Fix**: For binary content-types (application/pdf, application/octet-stream), stream the raw response body instead of reading as text.

### Bug 4: Terms/Privacy/Contact pages empty
- `frontend/src/app/terms/page.tsx` — shows "Coming Soon"
- `frontend/src/app/privacy/page.tsx` — shows "Coming Soon"
- Contact link is a `mailto:` — not a page (this is fine)

### Bug 5: Footer extends beyond viewport
- `frontend/src/components/Footer.tsx:3-4` — inner div has no `max-w` or `px` constraints
- NavBar uses `mx-auto max-w-5xl`, LayoutShell main uses `mx-auto max-w-5xl px-4 sm:px-6`
- Footer should match the same pattern

## Implementation Plan

### Fix 1: API Proxy — binary-safe response forwarding
**File**: `frontend/src/app/api/[...path]/route.ts`

Replace `proxyResponse` to handle binary content:
```typescript
async function proxyResponse(resp: Response): Promise<NextResponse> {
  const ct = resp.headers.get("content-type") || "application/json";
  // Binary content types: stream raw body
  if (ct.includes("application/pdf") || ct.includes("application/octet-stream") || ct.includes("image/")) {
    const buf = await resp.arrayBuffer();
    return new NextResponse(buf, {
      status: resp.status,
      headers: {
        "Content-Type": ct,
        ...(resp.headers.get("content-disposition") && {
          "Content-Disposition": resp.headers.get("content-disposition")!,
        }),
      },
    });
  }
  // Text content: read as text
  const data = await resp.text();
  return new NextResponse(data, {
    status: resp.status,
    headers: { "Content-Type": ct },
  });
}
```
Update all callers: `return proxyResponse(resp)` instead of `proxyResponse(await resp.text(), resp)`.

This fixes **bugs 2 and 3** (dashboard JSON download + generate blank download).

### Fix 2: GenerationStatsPanel — handle debug/zero tokens gracefully
**File**: `frontend/src/components/GenerationStatsPanel.tsx`

When `total_tokens === 0`, show "No API calls (debug mode)" instead of "0 in / 0 out" and "Free".

### Fix 3: Footer width constraint
**File**: `frontend/src/components/Footer.tsx`

Add `mx-auto max-w-5xl px-4 sm:px-6` to the inner `<div>` to match NavBar/LayoutShell pattern.

### Fix 4: Terms of Service page content
**File**: `frontend/src/app/terms/page.tsx`

Replace "Coming Soon" with standard Terms of Service content for an AI job application assistant SaaS.

### Fix 5: Privacy Policy page content
**File**: `frontend/src/app/privacy/page.tsx`

Replace "Coming Soon" with standard Privacy Policy content.

## Files to Modify

1. `frontend/src/app/api/[...path]/route.ts` — binary-safe proxy (bugs 2, 3)
2. `frontend/src/components/GenerationStatsPanel.tsx` — zero token display (bug 1)
3. `frontend/src/components/Footer.tsx` — max-width constraint (bug 5)
4. `frontend/src/app/terms/page.tsx` — real content (bug 4)
5. `frontend/src/app/privacy/page.tsx` — real content (bug 4)

## Verification

1. Rebuild frontend: `cd /root/applio/frontend && docker build -t applio-web:latest .`
2. Restart: `cd /root/deploy && docker compose up -d applio-web`
3. Test in browser:
   - Dashboard: click download button → should download PDF (not JSON)
   - Generate result page: PDF preview should render in iframe
   - Generate result page: download should produce valid PDF
   - Footer: should be centered with same width as navbar
   - /terms and /privacy: should show real content
