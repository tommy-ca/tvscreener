# Security Audit: `feat/forex-strategy-scanner`

I have performed a comprehensive security audit of the requested components. The findings expose critical vulnerabilities across SQL injection, path traversal, DuckDB configuration, and AWS credential exposure.

## 1. SQL Injection Risks in `tvscreener/lib/query.py`
While `EdgeQueryClient` attempts to use DuckDB's parameterized queries, its implementation introduces several severe SQL injection vulnerabilities:
*   **MiniJinja Template Interpolation Bypass:** The `AnalyticsPipeline.sql` method calls `render_sql(query, **template_context)` *before* passing the query to DuckDB. If an attacker controls a variable passed via `params` and the query contains `{{ my_variable }}`, MiniJinja will interpolate the string directly into the SQL payload, completely bypassing DuckDB's safe parameter binding and resulting in full SQL Injection.
*   **Fragile Parameter Filtering:** The `_filter_sql_params` method determines parameters by simply matching strings (`f"${k}" in query` or `query.count("?")`). If an attacker injects `?` or `$param` via a MiniJinja string, they can silently corrupt the positional or named parameters sent to DuckDB.
*   **Unquoted View Creation:** In `query_sql`, while the `DROP VIEW` statement safely quotes the `table_alias`, the initial creation `relation.create_view(table_alias)` accepts the unquoted string directly. An attacker controlling `table_alias` can inject SQL.

## 2. DuckDB Configuration Bypasses (`lock_configuration` / `read_only`)
The DuckDB initialization contains a hardcoded bypass that leaves in-memory databases completely unprotected.
*   **Memory DB Configuration Bypass:**
    ```python
    is_memory = str(db_path) == ":memory:"
    self.con = duckdb.connect(str(db_path), read_only=not is_memory)
    if not is_memory:
        self.con.execute("SET lock_configuration=True;")
    ```
    If an in-memory database is used (`:memory:`), it is neither `read_only` nor locked. An attacker running `query_sql` against an in-memory client can execute `INSTALL sqlite; LOAD sqlite;` to load malicious extensions or alter core configurations.
*   **Missing External Access Controls:** The `enable_external_access` setting is never disabled (`False`). Even when `lock_configuration=True` and `read_only=True` are set, an attacker executing SQL can still run `SELECT * FROM read_csv('/etc/passwd')` to read arbitrary local files, or `COPY ... TO '/tmp/malicious'` to overwrite files, as `read_only` only protects the DuckDB file itself, not external filesystem access.

## 3. Path Traversal Risks (`manager.py` and `validate_path`)
*   **Global `sys.modules` Backdoor (`util.py`): [FIXED]** The `validate_path` function previously used `sys.modules` for implicit environment detection. This has been removed and replaced with a strict, explicit check for the `TVSCREENER_TEST_MODE` environment variable.
*   **Missing Path Validation in Edge Query (`query.py`):** `EdgeQueryClient.get_relation(data)` directly passes the `data` string to DuckDB's `read_parquet(?)` *without* passing it through `validate_path()`. This creates a massive bypass where an attacker can supply an absolute path (e.g., `/etc/passwd`) or a traversal payload (`../../../`), and DuckDB will attempt to read it directly.
*   **SQLAlchemy URI Injection (`manager.py`):** `LakehouseManager` constructs its SQLite connection string as `sqlite:////{self.catalog_db_path.absolute()}`. If the user's `HOME` directory (which can be manipulated via the `$HOME` environment variable on POSIX systems) contains URL-special characters like `?` or `#`, SQLAlchemy will silently truncate the path at that character, leading to Denial of Service or writing the catalog database to an unexpected directory.

## 4. S3 Credential Exposure in `EdgeQueryClient._setup_remote_access`
*   **Plaintext Credential Leak:** The `_setup_remote_access` method configures AWS credentials using DuckDB's legacy `SET` commands (`SET s3_access_key_id=?`, etc.). DuckDB stores these connection settings in plaintext internally.
*   **Exploitation:** Any user or agent who can execute a SQL query (e.g., via the MCP tools or CLI `--sql`) can run `SELECT * FROM duckdb_settings() WHERE name LIKE 's3%'` to extract the `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN` in plaintext.
*   **Remediation:** DuckDB v0.10.0+ introduced a secure Secrets Manager. The client must be updated to use `CREATE SECRET (TYPE S3, KEY_ID '...', SECRET '...');` which obscures credentials from `duckdb_settings()` and securely isolates them.
