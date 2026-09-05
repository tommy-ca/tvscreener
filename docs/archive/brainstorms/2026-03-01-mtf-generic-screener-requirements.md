# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

---
date: 2026-03-01
topic: mtf-generic-screener-requirements
---

# Multi-Timeframe (MTF) Generic Screener: Specs & Requirements (DuckDB Edition)

## What We're Building
A robust, flexible engine that allows users to define custom filtering logic across multiple timeframes simultaneously. Powering this is a high-performance **DuckDB** backend that enables complex relational querying on top of live TradingView data and historical Parquet/S3 caches.

## Why This Approach
Professional traders often use "Waterfall" or "Triple Screen" logic (e.g., Daily trend + Hourly momentum + 15m entry). Hardcoding these into Python classes is inflexible. 

**DuckDB** provides:
- **Relational Power**: Use SQL for complex joins and window functions.
- **Zero-Copy Ingestion**: Direct, high-speed querying of Pandas DataFrames in-memory.
- **Unified Analytics**: Seamlessly merge real-time API data with local/remote historical datasets.

## Core Requirements

### 1. Two-Tiered Query Interface
- **Simple Expression Mode**: Converts shorthand strings to SQL.
    - *Syntax*: `{TIMEFRAME}:{FIELD} {OP} {VALUE}`
    - *Example*: `1D:TREND > 0 AND 1H:RSI < 30` -> `SELECT * FROM signals WHERE TREND_1D > 0 AND RSI_1H < 30`
- **Expert SQL Mode**: Direct access to the full power of DuckDB.
    - *Example*: `SELECT *, (RSI_15 + RSI_60) / 2 AS RSI_AVG FROM signals WHERE TREND_240 > 0.5`

### 2. Standardized Data Schema (DuckDB View)
The ingestion layer will register a view named `signals` with a flattened schema:
- **Canonical Columns**: `PAIR`, `EXCHANGE`, `PRICE`.
- **Dynamic Columns**: `{FACTOR}_{TIMEFRAME}` (e.g., `TREND_240`, `MA_15`, `ATR_60`).
- **Metadata**: `TOTAL_CONFLUENCE`, `GRADE`.

### 3. Data Ingestion & Augmentation
- **TradingView Real-time**: Optimized batching (500 symbols/request) to fetch all required `(Field, Timeframe)` pairs.
- **Cache Augmentation**: DuckDB can scan local `.parquet` files or S3 buckets via the `httpfs` extension to provide historical context (e.g., "Show pairs where current price is > 20-day high").

### 4. Performance Strategy
- **Vectorized Evaluation**: DuckDB executes the boolean logic in C++, making filter evaluation near-instant even for thousands of symbols.
- **Batching**: Group all unique technical indicators required by the query to minimize TV API calls.

## Technical Specifications

### DuckDBEngine Utility
A centralized utility to manage the lifecycle of the in-memory database:
```python
class DuckDBEngine:
    def __init__(self):
        self.con = duckdb.connect(database=':memory:')
    
    def register_df(self, name: str, df: pd.DataFrame):
        self.con.register(name, df)
        
    def query(self, sql: str) -> pd.DataFrame:
        return self.con.execute(sql).df()
```

### Expression Parser
A simple regex-based translator to map CLI shorthand to valid SQL identifiers based on the standardized schema.

## Key Decisions
- **Default View**: The results will be returned as a Pandas DataFrame for compatibility with the existing `RichConsoleRenderer`.
- **CLI Flags**: 
    - `--filter`: Shorthand boolean expression.
    - `--sql`: Raw SQL query string.
- **Asset Scope**: Initially Forex, but schema-ready for Stocks/Crypto.

## Next Steps
1.  Add `duckdb` to `pyproject.toml`.
2.  Implement `DuckDBEngine` in `tvscreener/lib/screeners/duckdb_engine.py`.
3.  Implement `MTFScanner` and `SQLScanner`.
4.  Develop the `MTFExpressionParser` utility.
