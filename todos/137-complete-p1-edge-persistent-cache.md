---
status: complete
priority: p1
issue_id: "137"
tags: [architecture, duckdb, persistence]
dependencies: ["134"]
---

# Implement Persistent Edge Cache for DuckDB

## Problem Statement
The current `EdgeQueryClient` uses an ephemeral `:memory:` database. Every time the CLI or an agent runs a query, the DuckDB state is lost. This prevents cross-session caching and forces redundant data registration.

## Findings
- `EdgeQueryClient` supports persistent DuckDB databases and a context manager interface.
- The default persistent cache location SHOULD NOT be a repository-local snapshots directory; it should
  live under `~/.tvscreener/` to keep “no snapshots by default” true.

## Proposed Solutions
1. **Persistent Default**: Default to `~/.tvscreener/cache/edge.duckdb`.
2. **Context Manager Support**: Keep `__enter__` and `__exit__` to handle connection lifecycle safely.
3. **Auto-Provisioning**: Ensure `~/.tvscreener/cache/` exists before connecting.

## Recommended Action
Implement the persistent cache with a context manager interface.

## Acceptance Criteria
- [ ] `EdgeQueryClient` defaults to `~/.tvscreener/cache/edge.duckdb`.
- [ ] No repository-local snapshot directory is created as a side effect of queries.
- [ ] `with EdgeQueryClient() as client:` pattern works correctly.
- [ ] Data persists between different CLI invocations.

## Work Log
### 2026-03-02 - Task Created
- Part of Phase 2 architecture modernization.
