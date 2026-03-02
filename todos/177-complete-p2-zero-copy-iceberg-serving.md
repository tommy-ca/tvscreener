---
status: complete
priority: p2
issue_id: "177"
tags: [performance, duckdb, iceberg]
dependencies: ["148"]
---

# Optimize Edge Querying with Native Iceberg Scanning

## Problem Statement
Currently, `EdgeQueryClient` might materialize Arrow tables before handing them to DuckDB. For large datasets, this increases memory pressure and latency.

## Findings
- DuckDB's `iceberg_scan()` is a C++ native engine that reads Iceberg manifests directly.
- Passing the `metadata_location` JSON path is significantly faster than passing memory pointers.

## Proposed Solutions
1. **Direct Path Binding**: Update `EdgeQueryClient` to resolve the absolute path to the latest `metadata.json` for a table.
2. **Native Scan**: Use `SELECT * FROM iceberg_scan(?)` as the default source for all edge queries.

## Recommended Action
Refactor the edge client to prefer native DuckDB Iceberg scanning for maximum performance.

## Acceptance Criteria
- [ ] `EdgeQueryClient` avoids `to_arrow()` for local Iceberg tables.
- [ ] DuckDB utilizes predicate pushdown on Iceberg tables.
- [ ] Performance verified on a "Large" (1,000+ row) signal history.

## Work Log
### 2026-03-02 - Initial Creation
- Part of "Edge Analytics" audit.
