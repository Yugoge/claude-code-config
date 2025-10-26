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

### Automatic Fallback Strategy

All deep search commands now follow this hierarchy:

1. **First try**: WebFetch (fast, works for static HTML)
2. **If blocked**: Automatically use Playwright MCP
3. **If still fails**: Use alternative search strategies

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
1. Try WebFetch first (fast)
2. If fails, automatically switch to Playwright
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

1. **WebFetch first**: Always let commands try WebFetch first (it's 10x faster)
2. **Playwright when needed**: Only use for dynamic sites
3. **No manual specification**: Commands auto-detect when to use Playwright
4. **Trust the strategy**: Built-in fallback logic optimizes for speed

## 🔍 When Playwright Activates Automatically

Commands automatically use Playwright when:
- WebFetch returns `<script>` heavy content
- Response contains "403 Forbidden" or "Cloudflare"
- Site requires authentication/cookies
- Content is loaded via AJAX/fetch

## 🛠️ Troubleshooting

**Issue**: Playwright seems slow
**Solution**: This is normal - it's launching a real browser. WebFetch is tried first for speed.

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

No additional configuration needed. All 5 deep search commands now have Playwright as an automatic fallback for complex sites.

Try it:
```
/deep-search example.com "find API documentation"
```

Claude will intelligently choose the best tool for the job!
