# lakehouse-auditor

## Description
Inspection and auditing of the Medallion lakehouse (Iceberg tables) using `tvscreener-ext-audit` and DuckDB-based Edge SQL queries.

## Instructions
When this skill is activated, you MUST help the user audit their market data lakehouse:

1.  **Table Inventory**:
    - Offer to list all active Iceberg tables.
    - Provide row counts and last-updated timestamps for `tvscreener.bronze`, `silver`, `gold`, and `signals_latest`.

2.  **Universe Health Audit**:
    - Offer to run a full universe audit: `uv run --project extensions tvscreener-ext-audit --groups 50`.
    - Report on group counts and potential data gaps.

3.  **Natural Language SQL**:
    - Allow the user to ask questions about the data in natural language.
    - Translate the user's request into an SQL query using `tvscreener-ext-scan query`.
    - Example: "Show me the top 10 most volatile crypto assets from the latest scan."
    - Command: `uv run --project extensions tvscreener-ext-scan query --table tvscreener.signals_latest --sql "SELECT PAIR, volatility_24h_pct FROM df ORDER BY volatility_24h_pct DESC LIMIT 10"`.

4.  **Data Freshness**:
    - Check the `tvscreener.runs` table to identify the last successful data and analytics runs.
    - Command: `uv run --project extensions tvscreener-ext-scan query --table tvscreener.runs --sql "SELECT * FROM df ORDER BY started_at_utc DESC LIMIT 5"`.

5.  **Summary**:
    - Provide a summary of the lakehouse health.
    - Suggest maintenance tasks if the data is stale: `tvscreener-ext-scan maintenance --compact`.

## Available Resources
- `tvscreener-ext-audit`: Tool for auditing Iceberg table groupings.
- `tvscreener-ext-scan query`: Command for running DuckDB SQL against the lakehouse.
- `docs/architecture/LAKEHOUSE.md`: Documentation on table schemas and the Medallion architecture.
