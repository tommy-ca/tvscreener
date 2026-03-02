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

    def _setup_remote_access(self, path: str) -> None:
        """Detect remote protocols and configure DuckDB httpfs extension."""
        if any(path.startswith(proto) for proto in ["s3://", "http://", "https://"]):
            try:
                self.con.execute("INSTALL httpfs; LOAD httpfs;")

                if path.startswith("s3://"):
                    # Configure AWS credentials if they exist in environment
                    if "AWS_ACCESS_KEY_ID" in os.environ:
                        self.con.execute(
                            f"SET s3_access_key_id='{os.environ['AWS_ACCESS_KEY_ID']}';"
                        )
                    if "AWS_SECRET_ACCESS_KEY" in os.environ:
                        self.con.execute(
                            f"SET s3_secret_access_key='{os.environ['AWS_SECRET_ACCESS_KEY']}';"
                        )
                    if "AWS_REGION" in os.environ:
                        self.con.execute(f"SET s3_region='{os.environ['AWS_REGION']}';")
                    if "AWS_SESSION_TOKEN" in os.environ:
                        self.con.execute(
                            f"SET s3_session_token='{os.environ['AWS_SESSION_TOKEN']}';"
                        )
            except Exception as e:
                logger.warning(f"Failed to configure remote access for {path}: {e}")

    def __enter__(self) -> EdgeQueryClient:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.con:
            self.con.close()

    def query_sql(
        self, parquet_path: str | Path, sql_query: str, table_alias: str = "df"
    ) -> pd.DataFrame:
        """
        Execute a DuckDB SQL query against a specific parquet file.

        Args:
            parquet_path: The absolute or relative path to the .parquet file.
            sql_query: The SQL query to execute.
            table_alias: The virtual table name to register the parquet file as.
        """
        path_str = str(parquet_path)
        is_remote = any(path_str.startswith(proto) for proto in ["s3://", "http://", "https://"])

        if is_remote:
            self._setup_remote_access(path_str)
        elif not Path(path_str).exists():
            raise FileNotFoundError("The specified parquet file does not exist.")

        try:
            # Execute user query directly against the parquet file
            # We use a CTE/View approach to bind the alias 'df' to the parquet file.
            self.con.execute(
                f"CREATE OR REPLACE VIEW {table_alias} AS SELECT * FROM read_parquet('{path_str}')"
            )
            result = self.con.execute(sql_query).df()
            return result
        except Exception as e:
            logger.error(f"Edge SQL query failed: {e}")
            raise RuntimeError("Edge SQL query failed. Check logs for details.") from None
        finally:
            self.con.execute(f"DROP VIEW IF EXISTS {table_alias}")

    def query_expr(self, data: str | Path | Any, transform_func: Callable) -> Any:
        """
        Execute a narwhals-based expression or transformation function against data.
        If data is a file path, it is read into DuckDB. Otherwise, it is passed directly
        to the transform function using the DuckDB backend via narwhals.

        Args:
            data: Path to parquet file, or a DataFrame/Relation (Pandas/Polars/DuckDB/etc.)
            transform_func: A narwhals-compatible function to apply to the data.
                            This function should be decorated with `@nw.narwhalify`
                            or designed to accept and return narwhals DataFrames/LazyFrames.

        Returns:
            The transformed data, typically in the format expected by the transform_func.
        """
        # If it's a string or Path, load it into a DuckDB relation
        if isinstance(data, (str, Path)):
            path_str = str(data)
            is_remote = any(
                path_str.startswith(proto) for proto in ["s3://", "http://", "https://"]
            )

            if is_remote:
                self._setup_remote_access(path_str)
            elif not Path(path_str).exists():
                raise FileNotFoundError("The specified parquet file does not exist.")

            # Read parquet into a DuckDB relation
            relation = self.con.read_parquet(path_str)
        else:
            # Assume it's already a DuckDB relation or another supported DataFrame type
            relation = data

        try:
            # Apply the narwhals transform function
            result = transform_func(relation)
            return result
        except Exception as e:
            logger.error(f"Edge Expr query failed: {e}")
            raise RuntimeError("Edge Expr query failed. Check logs for details.") from None
