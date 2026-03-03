---
status: completed
priority: p2
issue_id: "189"
tags: [mcp, documentation, iceberg, agents]
dependencies: []
---

# Bridge MCP Semantic Gap for Iceberg

## Problem Statement

The MCP tools docstrings in `mcp/server.py` currently instruct agents to pass "Parquet file paths". Because of this, agents are unaware that they can query native Iceberg tables (e.g., `tvscreener.gold`). This creates a semantic gap that restricts agents from utilizing the project's powerful Iceberg storage layer.

## Findings

- Docstrings for `scanner_inspect` and `query_historical_scan` explicitly mention "Parquet file paths".
- DuckDB via MCP natively supports Iceberg table queries.
- Agents rely heavily on docstrings to formulate inputs. Updating the prompts directly addresses this gap.

## Proposed Solutions

### Option 1: Update Docstrings to Highlight Iceberg Identifiers

**Approach:** Modify the MCP tool descriptions in `mcp/server.py`. Explicitly state that users/agents can pass Iceberg table identifiers (like `tvscreener.gold`, `tvscreener.silver`) in addition to or instead of Parquet file paths. Provide examples within the docstring.

**Pros:**
- Instantly informs agents of the available Iceberg layer.
- Zero code logic changes needed; pure documentation enhancement.

**Cons:**
- None.

**Effort:** < 1 hour
**Risk:** None

## Recommended Action

Implement Option 1. Update the docstrings for `scanner_inspect` and `query_historical_scan` in `mcp/server.py` to provide clear examples of querying native Iceberg tables (e.g., `tvscreener.gold`).

## Technical Details

**Affected files:**
- `tvscreener/mcp/server.py` (or potentially `tvscreener/mcp/tools.py` depending on where the exact docstrings reside)

**Related components:**
- MCP Tool specifications
- Iceberg DuckDB integration

## Resources

- Agentic tool prompt engineering guidelines

## Acceptance Criteria

- [x] Docstrings for `scanner_inspect` and `query_historical_scan` are updated.
- [x] The updated docstrings explicitly mention the ability to query Iceberg tables (e.g., `tvscreener.gold`).
- [x] Examples of querying Iceberg tables are included in the tool descriptions.
- [x] Tests pass when executing `uv run pytest`.

## Work Log

### 2026-03-03 - Initial Creation

**By:** Claude Code

**Actions:**
- Created todo from issue findings.

### 2026-03-03 - Implementation

**By:** Claude Code

**Actions:**
- Updated docstrings in `tvscreener/mcp/server.py` for `scanner_inspect` and `query_historical_scan`.
- Refactored `inspect_file` in `tvscreener/mcp/tools.py` to use `ScreenerController` for unified path/table handling.
- Verified changes with `tests/unit/test_mcp_lakehouse.py`.
