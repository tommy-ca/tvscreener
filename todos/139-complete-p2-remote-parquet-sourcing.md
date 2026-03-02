---
status: complete
priority: p2
issue_id: "139"
tags: [architecture, duckdb, remote, cloud]
dependencies: ["137"]
---

# Implement Remote Parquet Sourcing (Zero-ETL)

## Problem Statement
Currently, `EdgeQueryClient` only supports local file paths. To support modern cloud-native workflows, we should allow agents and users to query Parquet files directly from remote URLs (S3, HTTPS).

## Findings
- DuckDB's `httpfs` extension allows direct querying of remote Parquet files.
- We need to handle AWS/Cloud credentials for private buckets.

## Proposed Solutions
1. **Protocol Detection**: Detect if a path starts with `s3://` or `https://`.
2. **Extension Management**: Auto-run `INSTALL httpfs; LOAD httpfs;` when remote paths are detected.
3. **Credential Sync**: Map environment variables (`AWS_ACCESS_KEY_ID`, etc.) to DuckDB settings.

## Recommended Action
Integrate `httpfs` support into `query_sql` and `query_expr`.

## Acceptance Criteria
- [ ] Queries against public HTTPS Parquet URLs work without downloading.
- [ ] S3 bucket queries work when credentials are provided in environment variables.
- [ ] Extensions are lazy-loaded only when needed.

## Work Log
### 2026-03-02 - Task Created
- Part of Phase 2 architecture modernization.
