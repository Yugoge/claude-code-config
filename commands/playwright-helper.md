---
description: Guide for using Playwright MCP with deep search commands
disable-model-invocation: true
---

# Playwright MCP Integration Guide

Playwright MCP provides browser automation for dynamic JavaScript-heavy sites, anti-scraping protection, forms, screenshots, and real browser rendering.

## Strategy

WebFetch is DISABLED (causes 10-minute timeouts). Use this order:
1. **WebSearch** — fast discovery
2. **Playwright MCP** — primary tool for page content extraction
3. Alternative search strategies as fallback

Playwright is used as the PRIMARY content extraction method in `/deep-search`, `/research-deep`, and `/site-navigate`.

## Available Playwright Actions

Navigate, extract (text/HTML/accessibility tree), screenshot, evaluate JavaScript, wait for elements, interact (click/type/select).

## Technical Details

Installed via `claude mcp add playwright @modelcontextprotocol/server-playwright`. Config at `$HOME/.claude.json`. Transport: stdio. Browsers: Chromium (default), Firefox, WebKit.
