---
status: complete
priority: p2
issue_id: "164"
tags: [mcp, lakehouse, iceberg, agentic]
dependencies: []
---

# Implement Lakehouse Discovery Tools

Add tools to MCP for Iceberg catalog exploration and maintenance.

## Problem Statement

Agents currently lack visibility into the Iceberg catalog. There are no tools available in the MCP server to list tables, inspect schemas, or perform maintenance tasks (like expiring snapshots or removing orphan files), making it difficult for agents to manage the lakehouse autonomously.

## Findings

- `server.py` and `tools.py` in `tvscreener/mcp/` do not currently expose Iceberg-specific tools.
- Agents need `lakehouse_list_tables` to know what data is available.
- Agents need `lakehouse_get_schema` to understand the structure of specific tables.

## Proposed Solutions

### Option 1: Basic Discovery Tools

**Approach:** Implement `lakehouse_list_tables` and `lakehouse_get_schema` in `server.py` using the configured Iceberg catalog.

**Pros:**
- Enables agents to discover and query data.
- Low implementation effort.

**Cons:**
- Doesn't address maintenance needs.

**Effort:** 2-3 hours

**Risk:** Low

---

### Option 2: Full Discovery & Maintenance Suite

**Approach:** Implement discovery tools plus `lakehouse_maintenance` for tasks like compaction, snapshot expiration, and vacuuming.

**Pros:**
- Comprehensive lifecycle management for the lakehouse.
- Improves long-term system health.

**Cons:**
- Maintenance operations can be destructive if misused.
- Requires careful implementation of safety checks.

**Effort:** 5-8 hours

**Risk:** Medium

## Recommended Action

**Option 2 selected.**

## Technical Details

**Affected files:**
- `tvscreener/mcp/server.py`
- `tvscreener/mcp/tools.py`

**Related components:**
- Iceberg Catalog (PyIceberg)
- MCP Infrastructure

**Database changes (if any):**
- No (Lakehouse/Iceberg only)

## Resources

- [PyIceberg Documentation](https://pyiceberg.apache.org/api/)
- [MCP (Model Context Protocol) Specs](https://modelcontextprotocol.io/)

## Acceptance Criteria

- [x] `lakehouse_list_tables` tool added to `server.py`.
- [x] `lakehouse_get_schema` tool added to `server.py`.
- [x] `lakehouse_maintenance` tool added with support for `expire_snapshots` and `remove_orphan_files`.
- [x] Tools successfully discovered by MCP clients.
- [x] Error handling for missing catalog or invalid table names.

## Work Log

### 2026-03-02 - Initial Creation

**By:** Antigravity

**Actions:**
- Created todo for lakehouse discovery tools.
- Defined core tools needed for agentic autonomy in the lakehouse.

**Learnings:**
- Visibility into the data catalog is a prerequisite for effective agentic data analysis.

### 2026-03-02 - Implementation

**By:** Antigravity

**Actions:**
- Implemented `lakehouse_list_tables`, `lakehouse_get_schema`, and `lakehouse_maintenance` in `tvscreener/mcp/tools.py`.
- Exposed the new tools in `tvscreener/mcp/server.py`.
- Added `remove_orphan_files` to `IcebergCatalogManager`.
- Verified implementation with unit tests in `tests/unit/test_mcp_lakehouse.py`.

## Notes

- Safety is paramount for maintenance tools. Ensure agents cannot accidentally delete active data.
- `lakehouse_maintenance` defaults to 7 days for snapshot expiration.
