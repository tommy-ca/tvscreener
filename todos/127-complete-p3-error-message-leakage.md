---
status: complete
priority: p3
issue_id: "127"
tags: [security, error-handling, code-review]
dependencies: []
---

# Error Messages Leak Internal Details

## Problem Statement

`MalformedRequestException` includes full API URL and request payload. MCP error handlers return raw exception messages to clients, potentially exposing internal API structure, filter logic, and stack traces.

## Findings

- `tvscreener/exceptions.py:1-8` — Exception includes URL + full payload in message
- `tvscreener/mcp/server.py:170-171,327-328,343-344` — `return f"Error: {e}"` exposes raw exception
- Combined: MCP client sees internal API URLs and payloads

## Proposed Solutions

### Option 1: Sanitize Exception Messages

**Approach:** Store details as exception attributes, expose generic message in `__str__`. Log details server-side.

**Effort:** 30 minutes
**Risk:** Low

## Recommended Action

**Sanitize exception messages.** Store details as exception attributes, expose generic message in `__str__`. Log full details server-side.

## Acceptance Criteria

- [ ] Exception messages don't include full request payloads
- [ ] MCP returns actionable but non-leaking error messages
- [ ] Full details logged server-side for debugging

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (security-sentinel)
