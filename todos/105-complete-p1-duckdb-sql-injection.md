---
status: complete
priority: p1
issue_id: "105"
tags: [security, duckdb, code-review]
dependencies: []
---

# DuckDB SQL Injection / Remote Code Execution via Global Connection

## Problem Statement

`DuckDBFilter` in `filters.py` uses the **global default DuckDB connection** (`duckdb.execute()`, `duckdb.register()`, `duckdb.query()`) instead of a sandboxed in-memory connection. This allows arbitrary file read/write and potential code execution through `--sql` CLI flag or MCP `sql` parameter.

The project plan explicitly called for sandboxing with `enable_external_access=False`, but this was never implemented.

## Findings

- `tvscreener/lib/screeners/filters.py:54-62` — Uses global `duckdb.execute()` and `duckdb.query()` without any sandboxing
- `tvscreener/lib/orchestrator.py:323-327` — Raw user SQL from `--sql` flag passed directly to `DuckDBFilter`
- `tvscreener/lib/orchestrator.py:375-379` — Same pattern for strategy scanner
- `PRAGMA threads=1` and `PRAGMA max_expression_depth=50` provide zero security boundary
- `DuckDBEngine` in `duckdb_engine.py` creates proper isolated connections but is **never used** by `DuckDBFilter`
- Exploitable via CLI: `--sql "COPY (SELECT 'pwned') TO '/tmp/pwned.txt'"`
- Exploitable via MCP: `scanner_opportunities(sql="SELECT * FROM read_csv('/etc/passwd')")`

## Proposed Solutions

### Option 1: Sandboxed Per-Invocation Connection (Recommended)

**Approach:** Create a new `duckdb.connect(':memory:')` with `enable_external_access=False` inside each `DuckDBFilter.__call__()`.

**Pros:**
- Complete isolation per filter invocation
- No shared state between calls
- Matches the plan's security requirements exactly

**Cons:**
- Small overhead per call for connection creation
- DuckDB relations from one filter can't chain to the next without materialization

**Effort:** 30 minutes

**Risk:** Low

---

### Option 2: SQL Statement Allowlisting + Sandboxed Connection

**Approach:** Validate SQL against a forbidden-keyword regex (COPY, INSTALL, LOAD, CALL, CREATE, DROP, ALTER, ATTACH) AND use sandboxed connection.

**Pros:**
- Defense in depth (two layers)
- Catches even creative bypass attempts

**Cons:**
- Regex validation can have false positives on legitimate column names
- More maintenance

**Effort:** 1 hour

**Risk:** Low

## Recommended Action

**Option 2 — Sandbox + Allowlist (defense in depth).** Create sandboxed per-invocation `duckdb.connect(':memory:', config={'enable_external_access': False, 'allow_unsigned_extensions': False})` AND add a forbidden-keyword blocklist (COPY, INSTALL, LOAD, CALL, CREATE, DROP, ALTER, ATTACH) validated before execution. Raise `FilterExecutionError` on violations.

## Technical Details

**Affected files:**
- `tvscreener/lib/screeners/filters.py:46-66` — DuckDBFilter.__call__
- `tvscreener/lib/screeners/duckdb_engine.py` — Unused but has correct pattern

**Related components:**
- `orchestrator.py` — Constructs DuckDBFilter instances
- `mcp/server.py` — Exposes sql parameter to agents

## Resources

- **PR:** #49
- **Plan reference:** `docs/plans/2026-03-01-feat-duckdb-mtf-filter-pipeline-plan.md` (lines 117-127)

## Acceptance Criteria

- [ ] DuckDBFilter uses isolated in-memory connection with `enable_external_access=False`
- [ ] `allow_unsigned_extensions=False` set on connection
- [ ] PRAGMA settings applied once per connection, not per call
- [ ] `read_csv('/etc/passwd')` throws FilterExecutionError
- [ ] `COPY ... TO` throws FilterExecutionError
- [ ] Unit test verifies sandbox prevents file access
- [ ] Existing filter tests still pass

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (multi-agent review)

**Actions:**
- Security sentinel identified global DuckDB connection as critical vulnerability
- Confirmed via code analysis that `enable_external_access` is never set
- Verified `duckdb_engine.py` exists but is unused
- Cross-referenced with plan document which explicitly specified sandboxing

**Learnings:**
- The plan specified the fix but implementation was missed
- DuckDB's global default connection has full filesystem and network access
