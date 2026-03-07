from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import duckdb

    DUCKDB_AVAILABLE = True
except ImportError:
    duckdb = None
    DUCKDB_AVAILABLE = False

try:
    import minijinja

    MINIJINJA_AVAILABLE = True
except ImportError:
    minijinja = None
    MINIJINJA_AVAILABLE = False

try:
    import narwhals as nw

    NARWHALS_AVAILABLE = True
except ImportError:
    nw = None
    NARWHALS_AVAILABLE = False

logger = logging.getLogger(__name__)


class EdgeQueryClient:
    """
    Edge OLAP Client for querying finalized Parquet datasets using DuckDB.
    This is part of the Medallion architecture, separating compute from serving.
    """

    def __init__(self, db_path: str | Path | None = None):
        if not DUCKDB_AVAILABLE:
            raise RuntimeError(
                "DuckDB is required for Edge querying. Install the `duckdb` dependency (in this repo: `uv sync`)."
            )

        if db_path is None:
            # Default to a persistent cache outside the repo working dir
            db_path = Path.home() / ".tvscreener" / "cache" / "edge.duckdb"

        db_path = Path(db_path)
        if str(db_path) != ":memory:":
            db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create connection. Persistent by default.
        # Harden DuckDB:
        # - For on-disk DBs, open read-write only if the file doesn't exist yet (first run),
        #   then read-only on subsequent runs.
        # - Always lock configuration and disable external access.
        is_memory = str(db_path) == ":memory:"
        read_only = False if is_memory else db_path.exists()
        self.con = duckdb.connect(
            str(db_path),
            read_only=read_only,
            config={"lock_configuration": "True", "enable_external_access": "False"},
        )

        # Catalog-aware
        from tvscreener.lib.lakehouse import get_catalog

        self.catalog = get_catalog()

        # Register TA macros
        self._setup_ta_macros()

    def _setup_ta_macros(self) -> None:
        """Register standard Technical Analysis macros using DuckDB window functions."""
        # Simple Moving Average
        self.con.execute(
            "CREATE OR REPLACE TEMP MACRO sma(v, p) AS avg(v) OVER (ROWS BETWEEN p - 1 PRECEDING AND CURRENT ROW)"
        )
        # Moving Minimum
        self.con.execute(
            "CREATE OR REPLACE TEMP MACRO min_p(v, p) AS min(v) OVER (ROWS BETWEEN p - 1 PRECEDING AND CURRENT ROW)"
        )
        # Moving Maximum
        self.con.execute(
            "CREATE OR REPLACE TEMP MACRO max_p(v, p) AS max(v) OVER (ROWS BETWEEN p - 1 PRECEDING AND CURRENT ROW)"
        )
        # Moving Sum
        self.con.execute(
            "CREATE OR REPLACE TEMP MACRO sum_p(v, p) AS sum(v) OVER (ROWS BETWEEN p - 1 PRECEDING AND CURRENT ROW)"
        )
        # Change (Current - Previous)
        self.con.execute(
            "CREATE OR REPLACE TEMP MACRO change(v) AS v - lag(v) OVER (ROWS BETWEEN 1 PRECEDING AND 1 PRECEDING)"
        )

        # Advanced TA Macros
        # Z-Score (This one works because it doesn't nest window functions)
        self.con.execute(
            "CREATE OR REPLACE TEMP MACRO z_score(v, p) AS (v - avg(v) OVER (ROWS BETWEEN p - 1 PRECEDING AND CURRENT ROW)) / "
            "NULLIF(stddev(v) OVER (ROWS BETWEEN p - 1 PRECEDING AND CURRENT ROW), 0)"
        )

    def render_sql(self, template_str: str, **kwargs: Any) -> str:
        """Render a SQL template using MiniJinja."""
        if not MINIJINJA_AVAILABLE:
            logger.warning("MiniJinja not installed, returning raw template string.")
            return template_str

        return minijinja.render_str(template_str, **kwargs)

    def _setup_remote_access(self, path: str) -> None:
        """Detect remote protocols and configure DuckDB httpfs extension.

        Note: Disabled in hardened mode (lock_configuration=True, enable_external_access=False).
        Remote access should be handled by Python (e.g. pyarrow) if needed.
        """
        if any(path.startswith(proto) for proto in ["s3://", "http://", "https://"]):
            logger.warning("Remote access disabled via DuckDB configuration hardening for %s", path)
            raise RuntimeError(f"Remote access disabled via DuckDB configuration hardening: {path}")

    def pipeline(self, data: str | Path | Any, snapshot_id: int | None = None) -> AnalyticsPipeline:
        """Create a new AnalyticsPipeline starting with the given data.

        Supports Iceberg time-travel via snapshot_id.
        """
        return AnalyticsPipeline(self, data, snapshot_id=snapshot_id)

    def __enter__(self) -> EdgeQueryClient:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.con:
            self.con.close()

    def query_sql(
        self,
        data: str | Path | Any,
        sql_query: str,
        table_alias: str = "df",
        params: dict[str, Any] | list[Any] | None = None,
        snapshot_id: int | None = None,
    ) -> pd.DataFrame:
        """
        Execute a DuckDB SQL query against a specific parquet file, Iceberg table, or DataFrame.

        Args:
            data: The absolute or relative path to the .parquet file, an Iceberg table identifier, or a pandas DataFrame.
            sql_query: The SQL query to execute (can be MiniJinja template).
            table_alias: The virtual table name to register the data as.
            params: Parameters for the SQL query (both MiniJinja and SQL parameters).
            snapshot_id: Optional Iceberg snapshot ID for time-travel queries.
        """
        params = params or {}

        # 1. Render MiniJinja template if it's a template
        if MINIJINJA_AVAILABLE and "{{" in sql_query:
            if isinstance(params, dict):
                sql_query = self.render_sql(sql_query, **params)
            else:
                logger.warning("Params must be a dict for MiniJinja rendering. Skipping.")

        # 2. Get relation and register it as a temp view
        try:
            relation = self.get_relation(data, snapshot_id=snapshot_id)
            # Use DuckDB's in-process register/unregister instead of CREATE VIEW to keep
            # compatibility with read-only database connections.
            self.con.register(table_alias, relation)
        except Exception as e:
            logger.error("Failed to register data for query: %s", e)
            raise RuntimeError(f"Failed to register data for query: {e}") from e

        try:
            # 3. Filter params to only include those present as placeholders in the query
            # to avoid DuckDB's "Parameter argument/count mismatch" error.
            sql_params = self._filter_sql_params(sql_query, params)

            # We use the relation API for better parameter handling if needed,
            # or just use execute with params.
            result = self.con.execute(sql_query, sql_params).df()
            return result
        except Exception as e:
            logger.error("Edge SQL query failed: %s", e)
            raise RuntimeError(f"Edge SQL query failed: {e}") from None
        finally:
            with contextlib.suppress(Exception):
                self.con.unregister(table_alias)

    def _filter_sql_params(
        self, query: str, params: dict[str, Any] | list[Any] | None
    ) -> dict[str, Any] | list[Any] | None:
        """Filter params to only those present as placeholders in the query."""
        if not params:
            return None

        if isinstance(params, dict):
            # DuckDB uses $name or :name for named parameters
            filtered = {k: v for k, v in params.items() if f"${k}" in query or f":{k}" in query}
            return filtered if filtered else None

        if isinstance(params, list):
            # Positional parameters ?
            count = query.count("?")
            return params[:count] if count > 0 else None

        return params

    def get_relation(self, data: str | Path | Any, snapshot_id: int | None = None) -> Any:
        """Get a DuckDB relation from a file path, Iceberg table, or existing data.

        Supports Iceberg time-travel via snapshot_id.
        """
        # Handle DataFrames directly for zero-copy efficiency (Todo 186)
        if isinstance(data, pd.DataFrame):
            return self.con.from_df(data)

        # Handle other common DataFrame-like objects (Polars, Arrow, etc)
        if NARWHALS_AVAILABLE and isinstance(data, (nw.DataFrame, nw.LazyFrame)):
            native_data = data.to_native() if hasattr(data, "to_native") else data
            if isinstance(native_data, pd.DataFrame):
                return self.con.from_df(native_data)
            return self.con.from_arrow(native_data)

        # Handle Arrow-compatible objects directly
        if hasattr(data, "__arrow_c_stream__") or hasattr(data, "__arrow_c_array__"):
            return self.con.from_arrow(data)

        if isinstance(data, (str, Path)):
            path_str = str(data)
            is_iceberg = "." in path_str and not any(
                path_str.endswith(ext) for ext in [".parquet", ".csv", ".json", ".xml"]
            )

            if is_iceberg:
                table = self.catalog.load_table(path_str)
                # Use Arrow fallback for Iceberg since extensions are disabled by configuration hardening
                # Use table.scan().to_arrow() - table.to_arrow() doesn't exist
                arrow_table = (
                    table.scan(snapshot_id=snapshot_id).to_arrow()
                    if snapshot_id
                    else table.scan().to_arrow()
                )
                return self.con.from_arrow(arrow_table)
            else:
                is_remote = any(
                    path_str.startswith(proto) for proto in ["s3://", "http://", "https://"]
                )
                if is_remote:
                    self._setup_remote_access(path_str)

                # Security: Validate path before reading
                from tvscreener.util import validate_path

                valid_path = validate_path(path_str)

                # Use PyArrow for reading local parquet files to bypass DuckDB's enable_external_access=False
                import pyarrow.parquet as pq

                arrow_table = pq.read_table(valid_path)
                return self.con.from_arrow(arrow_table)

        return data

    def query_expr(self, data: str | Path | Any, transform_func: Callable) -> Any:
        """
        Execute a narwhals-based expression or transformation function against data.
        """
        relation = self.get_relation(data)

        try:
            # Apply the narwhals transform function
            if NARWHALS_AVAILABLE:
                # Wrap DuckDB relation in Narwhals
                nw_rel = nw.from_native(relation)
                result = transform_func(nw_rel)
                # If it's still a Narwhals object, convert back to native or DF
                if hasattr(result, "to_native"):
                    return result.to_native()
                return result
            return transform_func(relation)
        except Exception as e:
            logger.error("Edge Expr query failed: %s", e)
            raise RuntimeError(f"Edge Expr query failed: {e}") from None


class AnalyticsPipeline:
    """
    Unified Pipeline pattern for interleaving SQL and Narwhals transformations.
    Lazy-evaluated: transformations are queued and executed only on .execute() or .collect().
    """

    def __init__(
        self,
        client: EdgeQueryClient,
        initial_data: str | Path | Any,
        snapshot_id: int | None = None,
    ):
        self.client = client
        self.current_relation = client.get_relation(initial_data, snapshot_id=snapshot_id)
        self._step_count = 0

    def sql(self, query: str, params: dict[str, Any] | None = None) -> AnalyticsPipeline:
        """
        Add a SQL transformation step.

        The current state of the pipeline is available as 'df' in the SQL query.
        MiniJinja templating is supported for dynamic queries.

        Args:
            query: SQL query (can contain MiniJinja templates).
            params: Parameters for MiniJinja and SQL query placeholders.
        """
        import uuid

        params = params or {}

        # 1. Register current state as a unique view to avoid collisions in the DAG
        view_name = f"view_{uuid.uuid4().hex[:8]}_{self._step_count}"
        self._step_count += 1
        # Use connection-level registration to avoid CREATE VIEW on read-only DBs.
        self.client.con.register(view_name, self.current_relation)

        # 2. Render MiniJinja with 'df' bound to the current view_name
        template_context = {**params, "df": view_name}
        rendered_query = self.client.render_sql(query, **template_context)

        # 3. Fallback: if 'df' is still in the query but wasn't templated, replace it.
        # This allows users to write 'SELECT * FROM df' without {{ df }}.
        import re

        if re.search(r"\bdf\b", rendered_query) and view_name not in rendered_query:
            rendered_query = re.sub(r"\bdf\b", view_name, rendered_query)

        # 4. Bind the new relation
        sql_params = self.client._filter_sql_params(rendered_query, params)
        self.current_relation = self.client.con.sql(rendered_query, params=sql_params)
        return self

    def transform(self, func: Callable[[Any], Any]) -> AnalyticsPipeline:
        """
        Add a Narwhals-based transformation step.

        Args:
            func: A function that takes a Narwhals Frame and returns one.
        """
        if not NARWHALS_AVAILABLE:
            raise RuntimeError("Narwhals is required for .transform()")

        # Wrap DuckDB relation in Narwhals (lazy) - Todo 178
        nw_df = nw.from_native(self.current_relation)
        result = func(nw_df)

        # Convert back to native DuckDB relation while maintaining laziness
        try:
            native_result = nw.to_native(result)
            # If it's still a DuckDB relation, keep it
            if hasattr(native_result, "create_view"):
                self.current_relation = native_result
            else:
                # If it materialized to pandas/polars/arrow, re-wrap it as a relation
                self.current_relation = self.client.get_relation(native_result)
        except Exception:
            # Fallback if nw.to_native fails
            if hasattr(result, "to_native"):
                self.current_relation = result.to_native()
            else:
                self.current_relation = self.client.get_relation(result)

        return self

    def collect(self) -> pd.DataFrame:
        """Execute the pipeline and return a pandas DataFrame (Alias for execute)."""
        return self.execute()

    def execute(self) -> pd.DataFrame:
        """Execute the pipeline and return a pandas DataFrame."""
        try:
            return self.current_relation.df()
        except Exception as e:
            logger.error("Pipeline execution failed: %s", e)
            raise RuntimeError(f"Pipeline execution failed: {e}") from e

    def to_polars(self) -> Any:
        """Execute and return a Polars DataFrame."""
        return self.current_relation.pl()

    def to_arrow(self) -> Any:
        """Execute and return an Arrow Table."""
        return self.current_relation.arrow()

    def to_parquet(self, path: str | Path) -> None:
        """Execute and save directly to a Parquet file."""
        self.current_relation.write_parquet(str(path))
