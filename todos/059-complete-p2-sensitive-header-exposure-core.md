---
status: complete
priority: p2
issue_id: "059"
tags: [security, audit, code-review]
dependencies: []
---

# Problem Statement
The core `Screener.get()` method in `tvscreener/core/base.py` captures the **entire** dictionary of HTTP response headers from TradingView and attaches it to the DataFrame. These headers are subsequently exported into JSON/Parquet metadata, potentially leaking sensitive session tokens or internal server information.

# Findings
- **File**: `tvscreener/core/base.py`
- **Line**: 18244 (approx)
- **Evidence**:
  ```python
  df.attrs["api_context"] = {
      "url": self.url,
      "status_code": response.status_code,
      "headers": dict(response.headers), # EXPOSURE
      "method": "POST"
  }
  ```

# Proposed Solutions
1. **Whitelist in Core**: Apply the same `HEADER_WHITELIST` logic from `MetadataCollector` inside `Screener.get()`.
2. **Omit Headers**: Only capture non-header context (URL/Status) and specific known-safe fields (Request ID).

# Recommended Action
Implement a header whitelist in the core `Screener` class to prevent sensitive data from ever reaching the DataFrame attributes.

# Acceptance Criteria
- [x] Exported files do not contain `Cookie`, `Authorization`, or sensitive server headers.
- [x] Only explicitly whitelisted headers are persisted.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code (Security Sentinel)
- Identified sensitive header exposure in core library data capture.

### 2026-02-28 - Implemented Header Whitelist
**By:** Antigravity (pr-comment-resolver)
- Implemented `safe_headers` whitelist in `Screener.get()` to filter response headers.
- Restricted headers to: `Content-Type`, `Date`, `Server`, `User-Agent`, `X-Request-Id`.
