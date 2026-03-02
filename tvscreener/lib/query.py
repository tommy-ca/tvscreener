from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import duckdb

    DUCKDB_AVAILABLE = True
except ImportError:
    duckdb = None  # type: ignore
    DUCKDB_AVAILABLE = False

try:
    import minijinja

    MINIJINJA_AVAILABLE = True
except ImportError:
    minijinja = None  # type: ignore
    MINIJINJA_AVAILABLE = False

try:
    import narwhals as nw

    NARWHALS_AVAILABLE = True
except ImportError:
    nw = None  # type: ignore
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
                "DuckDB is required for Edge querying. Install with `pip install duckdb`."
            )

        if db_path is None:
            # Default to a persistent cache in exports/
            db_path = Path("exports/.tvscreener_cache.duckdb")

        db_path = Path(db_path)
        if str(db_path) != ":memory:":
            db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create connection. Persistent by default.
        self.con = duckdb.connect(str(db_path))

        # Catalog-aware
        from tvscreener.lib.lakehouse import get_catalog

        self.catalog = get_catalog()

        # Register TA macros
        self._setup_ta_macros()

    def _setup_ta_macros(self) -> None:
        """Register standard Technical Analysis macros using DuckDB window functions."""
        # Simple Moving Average
        self.con.execute(
            "CREATE OR REPLACE MACRO sma(v, p) AS avg(v) OVER (ROWS BETWEEN p - 1 PRECEDING AND CURRENT ROW)"
        )
        # Moving Minimum
        self.con.execute(
            "CREATE OR REPLACE MACRO min_p(v, p) AS min(v) OVER (ROWS BETWEEN p - 1 PRECEDING AND CURRENT ROW)"
        )
        # Moving Maximum
        self.con.execute(
            "CREATE OR REPLACE MACRO max_p(v, p) AS max(v) OVER (ROWS BETWEEN p - 1 PRECEDING AND CURRENT ROW)"
        )
        # Moving Sum
        self.con.execute(
            "CREATE OR REPLACE MACRO sum_p(v, p) AS sum(v) OVER (ROWS BETWEEN p - 1 PRECEDING AND CURRENT ROW)"
        )
        # Change (Current - Previous)
        self.con.execute(
            "CREATE OR REPLACE MACRO change(v) AS v - lag(v) OVER (ROWS BETWEEN 1 PRECEDING AND 1 PRECEDING)"
        )

    def render_sql(self, template_str: str, **kwargs: Any) -> str:
        """Render a SQL template using MiniJinja."""
        if not MINIJINJA_AVAILABLE:
            logger.warning("MiniJinja not installed, returning raw template string.")
            return template_str

        return minijinja.render_str(template_str, **kwargs)

    def _setup_remote_access(self, path: str) -> None:
        """Detect remote protocols and configure DuckDB httpfs extension."""
        if any(path.startswith(proto) for proto in ["s3://", "http://", "https://"]):
            try:
                self.con.execute("INSTALL httpfs; LOAD httpfs;")

                if path.startswith("s3://"):
                    # Configure AWS credentials if they exist in environment using parameters
                    if "AWS_ACCESS_KEY_ID" in os.environ:
                        self.con.execute(
                            "SET s3_access_key_id=?;", [os.environ["AWS_ACCESS_KEY_ID"]]
                        )
                    if "AWS_SECRET_ACCESS_KEY" in os.environ:
                        self.con.execute(
                            "SET s3_secret_access_key=?;",
                            [os.environ["AWS_SECRET_ACCESS_KEY"]],
                        )
                    if "AWS_REGION" in os.environ:
                        self.con.execute("SET s3_region=?;", [os.environ["AWS_REGION"]])
                    if "AWS_SESSION_TOKEN" in os.environ:
                        self.con.execute(
                            "SET s3_session_token=?;", [os.environ["AWS_SESSION_TOKEN"]]
                        )
            except Exception as e:
                logger.warning("Failed to configure remote access for %s: %s", path, e)

    def pipeline(self, data: str | Path | Any) -> AnalyticsPipeline:
        """Create a new AnalyticsPipeline starting with the given data."""
        return AnalyticsPipeline(self, data)

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
    ) -> pd.DataFrame:
        """
        Execute a DuckDB SQL query against a specific parquet file, Iceberg table, or DataFrame.

        Args:
            data: The absolute or relative path to the .parquet file, an Iceberg table identifier, or a pandas DataFrame.
            sql_query: The SQL query to execute (can be MiniJinja template).
            table_alias: The virtual table name to register the data as.
            params: Parameters for the SQL query (both MiniJinja and SQL parameters).
        """
        params = params or {}

        # 1. Render MiniJinja template if it's a template
        if MINIJINJA_AVAILABLE and "{{" in sql_query:
            if isinstance(params, dict):
                sql_query = self.render_sql(sql_query, **params)
            else:
                logger.warning("Params must be a dict for MiniJinja rendering. Skipping.")

        # 2. Get relation and create view
        try:
            relation = self.get_relation(data)
            relation.create_view(table_alias)
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
            # Safely drop the view using an identifier-quoted name
            safe_alias = '"' + table_alias.replace('"', '""') + '"'
            self.con.execute(f"DROP VIEW IF EXISTS {safe_alias}")

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

    def get_relation(self, data: str | Path | Any) -> Any:
        """Get a DuckDB relation from a file path, Iceberg table, or existing data."""
        if isinstance(data, (str, Path)):
            path_str = str(data)
            is_iceberg = "." in path_str and not any(
                path_str.endswith(ext) for ext in [".parquet", ".csv", ".json", ".xml"]
            )

            if is_iceberg:
                table = self.catalog.load_table(path_str)
                try:
                    self.con.execute("INSTALL iceberg; LOAD iceberg;")
                    return self.con.sql(
                        "SELECT * FROM iceberg_scan(?)", params=[table.metadata_location]
                    )
                except Exception:
                    return self.con.from_arrow(table.to_arrow())
            else:
                is_remote = any(
                    path_str.startswith(proto) for proto in ["s3://", "http://", "https://"]
                )
                if is_remote:
                    self._setup_remote_access(path_str)
                return self.con.read_parquet(path_str)
        return self.con.from_df(data) if isinstance(data, pd.DataFrame) else data

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

    def __init__(self, client: EdgeQueryClient, initial_data: str | Path | Any):
        self.client = client
        self.current_relation = client.get_relation(initial_data)
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
        self.current_relation.create_view(view_name)

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

        # Wrap DuckDB relation in Narwhals (lazy)
        nw_df = nw.from_native(self.current_relation)
        result = func(nw_df)

        # Convert back to native DuckDB relation if possible (maintains laziness)
        if hasattr(result, "to_native"):
            self.current_relation = result.to_native()
        else:
            # If it materialized (e.g. returned pandas/polars), re-wrap it
            self.current_relation = self.client.con.from_df(result)
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
