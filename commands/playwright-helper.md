---
description: Guide for using Playwright MCP with deep search commands
---

# Playwright MCP Integration Guide

## ✅ Playwright MCP is Installed!

Playwright MCP provides browser automation capabilities to handle:
- Dynamic JavaScript-heavy websites
- Sites with anti-scraping protection
- Complex form interactions
- Screenshot capture
- Real browser rendering

## 🔗 How It Integrates with Deep Search Commands

### ⚠️ CRITICAL CHANGE: WebFetch is DISABLED

**Why**: WebFetch causes 10-minute timeouts on slow/unresponsive websites, and Task tool cannot cancel it.

**New Strategy**:

1. **First try**: WebSearch (fast, reliable, no timeout risk)
2. **For specific pages**: Use Playwright MCP (dynamic content, reliable)
3. **If still fails**: Use alternative search strategies

**Playwright is now the PRIMARY tool for page content extraction** (not fallback).

### Using Playwright Explicitly

When you know a site requires JavaScript rendering:

```
"Use Playwright to navigate to https://example.com and extract navigation links"
```

## 🎯 Playwright-Enhanced Command Examples

### With `/deep-search`

```
/deep-search example.com "find documentation"

Claude will:
1. Use WebSearch for discovery (fast)
2. Use Playwright for page navigation and content extraction
3. Handle JavaScript rendering, wait for elements
4. Extract structured data
```

### With `/site-navigate`

```
/site-navigate https://app.example.com "find user settings"

Playwright benefits:
- Can interact with single-page applications (SPAs)
- Handles dynamic route changes
- Waits for elements to load
- Can click buttons and fill forms if needed
```

### With `/research-deep`

```
/research-deep "topic that requires accessing paywalled sites"

Playwright helps:
- Render JavaScript-generated content
- Handle cookie consent popups
- Navigate multi-step processes
```

## 📋 Available Playwright Actions

When Playwright is active, you can:

- **Navigate**: Visit URLs
- **Extract**: Get page text, HTML, or accessibility tree
- **Screenshot**: Capture page images
- **Evaluate**: Run JavaScript in the page context
- **Wait**: Wait for elements or network activity
- **Interact**: Click, type, select (use sparingly)

## ⚡ Performance Tips

1. **WebSearch first**: Always start with WebSearch for discovery (10-30 seconds)
2. **Playwright for extraction**: Use Playwright when you need specific page content
3. **Parallel operations**: Run multiple Playwright navigations in parallel when possible
4. **Be specific**: Use precise selectors and scripts to minimize page interaction time

## 🔍 When Playwright is Used

Playwright is now the PRIMARY tool for page content extraction in:
- `/deep-search` - All phases requiring page navigation
- `/research-deep` - Phase 4 source content extraction
- `/site-navigate` - All page navigation tasks
- Any command that needs to extract content from specific URLs

**No longer a fallback** - it's the main content extraction method.

## 🛠️ Troubleshooting

**Issue**: Playwright seems slow
**Solution**: This is normal - it's launching a real browser. Typically completes in 5-15 seconds per page.

**Issue**: "Browser not installed" error
**Solution**: Playwright auto-downloads browsers on first use. Wait for download to complete.

**Issue**: Want to disable Playwright temporarily
**Solution**: It only activates on fallback. To disable entirely, remove from MCP config.

## 📚 Technical Details

**Installed via**: `claude mcp add playwright @modelcontextprotocol/server-playwright`

**Configuration**: `/root/.claude.json` (project-level)

**Transport**: stdio (local process)

**Browsers**: Chromium (default), Firefox, WebKit available

## 🎉 Ready to Use!

No additional configuration needed. All deep search commands now use Playwright as the PRIMARY content extraction method (WebFetch disabled).

Try it:
```
/deep-search example.com "find API documentation"
```

Claude will intelligently choose the best tool for the job!
