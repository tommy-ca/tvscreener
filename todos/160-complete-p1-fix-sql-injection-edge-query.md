---
status: complete
priority: p1
issue_id: "160"
tags: [security, sql-injection, duckdb]
dependencies: []
---

# Fix SQL Injection in Edge Querying & Inspect

## Problem Statement

The `inspect --output` functionality and S3 credential settings in `query.py` currently use f-strings to construct SQL queries. This exposes the application to SQL injection vulnerabilities where user-supplied input (like output paths or credential names) could be used to execute arbitrary SQL.

## Findings

- `query.py`: Identified use of f-strings for building SQL queries in `inspect` and S3 configuration sections.
- `inspect --output`: The output path is likely being interpolated directly into a `COPY TO` or similar statement.
- S3 Credentials: S3 settings are being interpolated into `SET` or `CREATE SECRET` statements.

## Proposed Solutions

### Option 1: Parameterized Queries and MiniJinja Templating (Recommended)

**Approach:** 
1. Use DuckDB's native parameter binding (`?` or `$`) for all data values and file paths.
2. Integrate **MiniJinja** (Rust-based, zero-dependency Python wrapper) for structural dynamic SQL (e.g., conditional filters or dynamic table aliases).
3. Use `read_parquet(?)` with parameter binding for all file paths.

**Pros:**
- Complete mitigation of SQL injection for data values.
- Powerful, sandboxed templating for dynamic queries.
- Lightweight: Single binary wheel, no extra dependencies.

**Cons:**
- Adds `minijinja` as a dependency.

**Effort:** 2-3 hours

**Risk:** Low

---

### Option 2: Whitelisting and Identifier Quoting

**Approach:** Use `duckdb.sql()` which automatically handles some quoting, and manually escape identifiers using double quotes.

**Pros:** No new dependencies.

**Cons:** Harder to maintain and more prone to developer error.

**Effort:** 2 hours

**Risk:** Medium

## Recommended Action

Implement **Option 1**. Integrate MiniJinja and strictly enforce parameter binding for all inputs in `EdgeQueryClient`.

## Technical Details

**Affected files:**
- `query.py` - Refactor `query_sql` and credential setup.
- `orchestrator.py` - Pass `sql_params` and `template_context`.
- `pyproject.toml` - Managed via `uv add minijinja`.

## Acceptance Criteria

- [x] `read_parquet()` and `iceberg_scan()` calls in `query.py` use `?` placeholders.
- [x] User-provided SQL strings are rendered via MiniJinja before execution.
- [x] CLI supports `--sql-params` as a JSON string via `uv run tvscreener-scan`.
- [x] No f-strings are used to construct SQL statements in `query.py`.
- [x] Credentials from environment variables are set using parameterized `SET` commands.

## Work Log

### 2026-03-02 - Initial Creation

**By:** Antigravity

**Actions:**
- Created todo based on security finding.
- Identified affected areas in `query.py`.

### 2026-03-02 - Implementation

**By:** Antigravity

**Actions:**
- Installed `minijinja` and removed `jinja2`.
- Refactored `EdgeQueryClient` in `query.py` to use `minijinja` and DuckDB parameter binding.
- Fixed S3 credential injection by using parameterized `SET` commands.
- Updated `orchestrator.py` to pass `sql_params` to `query_sql`.
- Verified fix with TDD-style security tests in `tests/security/test_sql_injection.py`.
