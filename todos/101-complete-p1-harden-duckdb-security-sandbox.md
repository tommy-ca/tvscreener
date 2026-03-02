---
status: complete
priority: p1
issue_id: "101"
tags: [security, reliability, duckdb]
dependencies: []
---

# Harden DuckDB Security Sandbox and Exception Handling

## Problem Statement
While `enable_external_access=False` is planned, the DuckDB sandbox is still vulnerable to CPU exhaustion (complex Cartesian joins) and C++ stack overflows (deeply nested ASTs). Additionally, catching only `BinderException` will cause the CLI to fatally crash if the user hits an Out-Of-Memory (OOM) or syntax error.

## Findings
- Security Sentinel identified missing limits for CPU threads and expression depth.
- Catching `duckdb.BinderException` is too narrow. `duckdb.OutOfMemoryException` and `duckdb.ParserException` must also be caught gracefully.

## Proposed Solutions

### Option 1: Implement Strict PRAGMAs and Generic Try/Except
**Approach:** 
1. Add `PRAGMA threads=1` and `PRAGMA max_expression_depth=50` to the DuckDB connection initialization.
2. Broaden the exception handler in `DuckDBFilter` to catch the base `duckdb.Error` and wrap it in a user-friendly `FilterExecutionError`.

## Acceptance Criteria
- [x] DuckDB connection initializes with thread and expression depth limits.
- [x] Malformed SQL or OOM queries result in a clean CLI error message, not a Python traceback.