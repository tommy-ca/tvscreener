---
status: complete
priority: p2
issue_id: "155"
tags: [agentic, lakehouse, mcp, iceberg]
dependencies: []
---

# Implement Lakehouse Discovery & Maintenance Tools

Agents are currently blind to the Iceberg catalog and lack maintenance tools in MCP.

## Problem Statement

The current MCP (Model Context Protocol) implementation does not provide agents with visibility into the Iceberg lakehouse catalog. Agents cannot list tables, inspect schemas, or perform necessary maintenance tasks (like vacuuming or snapshot management). This limits their ability to autonomously manage and query the data lake.

## Findings

- `server.py` and `tools.py` in the MCP directory lack Iceberg-specific tools.
- Agents cannot discover existing tables in the lakehouse.
- No automated maintenance operations are exposed via MCP.

## Proposed Solutions

### Option 1: Add specific Lakehouse Tools to MCP

**Approach:** Implement `lakehouse_list_tables`, `lakehouse_get_schema`, and `lakehouse_maintenance` tools in `server.py` and `tools.py`. These tools will wrap the underlying Iceberg/Catalog API calls.

**Pros:**
- Empowers agents to understand the data structure.
- Enables autonomous maintenance (e.g., after large writes).
- Improves agentic capabilities for data discovery.

**Cons:**
- Requires careful handling of catalog credentials and permissions.
- Maintenance tools need guardrails to prevent destructive actions.

**Effort:** 3-4 hours

**Risk:** Medium

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `tvscreener/mcp/server.py`: Register the new tools.
- `tvscreener/mcp/tools.py`: Implement the tool logic using the Iceberg catalog.

## Acceptance Criteria

- [ ] `lakehouse_list_tables` tool implemented and returns a list of tables in the catalog.
- [ ] `lakehouse_get_schema` tool implemented and returns the schema for a given table.
- [ ] `lakehouse_maintenance` tool implemented for basic tasks (e.g., listing snapshots, potentially vacuuming).
- [ ] Tools are documented and accessible via the MCP server.
- [ ] Agents can successfully use these tools to discover and describe tables.

## Work Log

### 2026-03-02 - Initial Entry

**By:** Antigravity

**Actions:**
- Created todo for implementing lakehouse discovery and maintenance tools.
- Identified the lack of catalog visibility for agents as a key limitation.
- Outlined the necessary tools to be added to the MCP layer.

## Notes

- This is essential for the "Agentic" goal of the project.
