from __future__ import annotations

import contextlib
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from tvscreener.lib.pipeline_runner import PipelineRunSpec
from tvscreener.lib.query import EdgeQueryClient

logger = logging.getLogger(__name__)


def semantic_runtime() -> str:
    """Select semantic runtime.

    Policy:
    - `TVSCREENER_SEMANTIC_RUNTIME=sql` forces built-in SQL.
    - `TVSCREENER_SEMANTIC_RUNTIME=sidemantic` forces Sidemantic (falls back if not installed).
    - unset/`auto`: use Sidemantic if installed, else SQL.
    """

    override = (os.getenv("TVSCREENER_SEMANTIC_RUNTIME") or "").strip().lower()
    if override in {"sql", "duckdb"}:
        return "sql"

    if override in {"sidemantic"}:
        try:
            import sidemantic  # noqa: F401

            return "sidemantic"
        except Exception:
            return "sql"

    # auto
    try:
        import sidemantic  # noqa: F401

        return "sidemantic"
    except Exception:
        return "sql"


def _coerce_cell(value: Any) -> Any:
    # Keep Prefect artifact payloads JSON-friendly.
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    # Numpy scalars
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return value

    # Datetime-like objects
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)

    return value


def _df_to_rows(df: pd.DataFrame, *, limit: int) -> list[dict[str, Any]]:
    subset = df.head(limit)
    rows: list[dict[str, Any]] = []
    for _, row in subset.iterrows():
        rows.append({col: _coerce_cell(row[col]) for col in subset.columns})
    return rows


def semantic_opportunity_top_rows(
    *, data_params_hash: str, limit: int = 30
) -> list[dict[str, Any]] | None:
    """Top-N rows for results table artifacts.

    Prefer reading from the Iceberg per-run product table (`tvscreener.signals_batch`) so
    the table reflects the same inputs the matrix view is rendered from.
    """

    sql = f"""
    WITH ranked AS (
      SELECT
        *,
        row_number() OVER (
          PARTITION BY PAIR
          ORDER BY
            TOTAL_CONFLUENCE DESC NULLS LAST,
            abs(ENSEMBLE_SCORE) DESC NULLS LAST,
            fetched_at_utc DESC NULLS LAST
        ) AS rn
      FROM df
      WHERE params_hash = $params_hash
    )
    SELECT
      PAIR,
      Name,
      Price,
      RVOL,
      Volume,
      ENSEMBLE_SCORE,
      GRADE,
      DIRECTION,
      GRID_ALIGNED,
      GRID_TOTAL,
      CONFLUENCE_LEVEL,
      TOTAL_CONFLUENCE,
      TF_CONFLUENCE,
      TREND_SCORE,
      MA_SCORE,
      OSC_SCORE,
      ROC_SCORE,
      ROC_AVG,
      ROC_15,
      ROC_60,
      ROC_240,
      TREND_DIR,
      MA_DIR,
      OSC_DIR,
      ROC_DIR,
      RATING_SCORE,
      fetched_at_utc
    FROM ranked
    WHERE rn = 1
    ORDER BY
      TOTAL_CONFLUENCE DESC NULLS LAST,
      abs(ENSEMBLE_SCORE) DESC NULLS LAST,
      fetched_at_utc DESC NULLS LAST
    LIMIT {int(limit)}
    """

    try:
        with EdgeQueryClient(db_path=":memory:") as q:
            df = q.query_sql(
                "tvscreener.signals_batch", sql, params={"params_hash": data_params_hash}
            )
    except Exception as exc:
        logger.debug("Semantic top-rows query failed: %s", exc)
        return None

    if df.empty:
        return None

    return _df_to_rows(df, limit=limit)


def semantic_opportunity_health(*, data_params_hash: str) -> dict[str, Any] | None:
    """Health and lineage checks for table artifacts.

    This is intended to catch:
    - duplicated PAIR rows (and directional conflicts)
    - `ROC_SCORE=0` while raw ROC_* values are non-zero
    """

    sql = """
    WITH base AS (
      SELECT
        PAIR,
        DIRECTION,
        ROC_SCORE,
        ROC_15,
        ROC_60,
        ROC_240
      FROM df
      WHERE params_hash = $params_hash
    ),
    per_pair AS (
      SELECT
        PAIR,
        count(*) AS row_count,
        count(DISTINCT DIRECTION) AS direction_count
      FROM base
      GROUP BY 1
    )
    SELECT
      count(*) AS total_rows,
      (SELECT count(*) FROM per_pair) AS unique_pairs,
      (SELECT count(*) FROM per_pair WHERE row_count > 1) AS duplicate_pairs,
      (SELECT count(*) FROM per_pair WHERE direction_count > 1) AS conflict_pairs,
      sum(CASE WHEN ROC_SCORE = 0 AND (ROC_15 <> 0 OR ROC_60 <> 0 OR ROC_240 <> 0) THEN 1 ELSE 0 END)
        AS roc_score_zero_but_raw_nonzero
    FROM base
    """

    try:
        with EdgeQueryClient(db_path=":memory:") as q:
            df = q.query_sql(
                "tvscreener.signals_batch", sql, params={"params_hash": data_params_hash}
            )
    except Exception as exc:
        logger.debug("Semantic health query failed: %s", exc)
        return None

    if df.empty:
        return None

    out = {k: _coerce_cell(df.iloc[0][k]) for k in df.columns}
    out["source_table"] = "tvscreener.signals_batch"
    out["data_params_hash"] = data_params_hash
    out["dedup_partition"] = "PAIR"
    out["dedup_order"] = "TOTAL_CONFLUENCE desc, abs(ENSEMBLE_SCORE) desc, fetched_at_utc desc"
    return out


def resolve_latest_successful_data_params_hash(spec: PipelineRunSpec) -> str | None:
    """Resolve the latest successful data params_hash for this analytics spec."""

    sql = """
    SELECT params_hash
    FROM df
    WHERE pipeline_mode_executed = 'data'
      AND success = true
      AND asset_type = $asset_type
      AND scanner_family = $scanner_family
    """

    params: dict[str, Any] = {
        "asset_type": spec.asset_type,
        "scanner_family": spec.scanner_family,
    }

    if spec.universe:
        sql += " AND universe = $universe"
        params["universe"] = spec.universe

    if spec.instrument_type:
        sql += " AND instrument_type = $instrument_type"
        params["instrument_type"] = spec.instrument_type

    if spec.timeframe_set_id:
        sql += " AND timeframe_set_id = $timeframe_set_id"
        params["timeframe_set_id"] = spec.timeframe_set_id

    sql += " ORDER BY started_at_utc DESC LIMIT 1"

    try:
        with EdgeQueryClient(db_path=":memory:") as q:
            df = q.query_sql("tvscreener.runs", sql, params=params)
    except Exception as exc:
        logger.debug("Resolve latest data params_hash failed: %s", exc)
        return None

    if df.empty:
        return None

    val = df.iloc[0]["params_hash"]
    return str(val) if val is not None else None


def semantic_opportunity_grade_summary(
    *, data_params_hash: str, limit: int = 50
) -> list[dict[str, Any]] | None:
    """Grade/direction summary for a run (matrix-friendly)."""

    if semantic_runtime() == "sidemantic":
        sidemantic_rows = sidemantic_opportunity_grade_summary(
            data_params_hash=data_params_hash, limit=limit
        )
        if sidemantic_rows is not None:
            return sidemantic_rows

    sql = f"""
    WITH ranked AS (
      SELECT
        *,
        row_number() OVER (
          PARTITION BY PAIR
          ORDER BY
            TOTAL_CONFLUENCE DESC NULLS LAST,
            abs(ENSEMBLE_SCORE) DESC NULLS LAST,
            fetched_at_utc DESC NULLS LAST
        ) AS rn
      FROM df
      WHERE params_hash = $params_hash
    )
    SELECT
      GRADE,
      DIRECTION,
      count(*) AS opportunity_count,
      avg(ENSEMBLE_SCORE) AS avg_ensemble_score,
      avg(TOTAL_CONFLUENCE) AS avg_total_confluence,
      avg(TREND_SCORE) AS avg_trend_score,
      avg(MA_SCORE) AS avg_ma_score,
      avg(OSC_SCORE) AS avg_osc_score,
      avg(ROC_SCORE) AS avg_roc_score
    FROM ranked
    WHERE rn = 1
    GROUP BY 1, 2
    ORDER BY opportunity_count DESC
    LIMIT {int(limit)}
    """

    try:
        with EdgeQueryClient(db_path=":memory:") as q:
            df = q.query_sql(
                "tvscreener.signals_batch", sql, params={"params_hash": data_params_hash}
            )
    except Exception as exc:
        logger.debug("Semantic grade summary query failed: %s", exc)
        return None

    if df.empty:
        return None

    return _df_to_rows(df, limit=limit)


def _sidemantic_enabled() -> bool:
    return semantic_runtime() == "sidemantic"


def sidemantic_opportunity_grade_summary(
    *, data_params_hash: str, limit: int = 50
) -> list[dict[str, Any]] | None:
    """Compute grade/direction summary via Sidemantic, if enabled."""

    if not _sidemantic_enabled():
        return None

    try:
        import duckdb
        from sidemantic import SemanticLayer, load_from_directory
    except Exception as exc:
        logger.debug("Sidemantic not available: %s", exc)
        return None

    slice_sql = """
    SELECT
      entity_id,
      params_hash,
      GRADE,
      DIRECTION,
      ENSEMBLE_SCORE,
      TOTAL_CONFLUENCE,
      TREND_SCORE,
      MA_SCORE,
      OSC_SCORE,
      ROC_SCORE
    FROM df
    WHERE params_hash = $params_hash
    """

    try:
        with EdgeQueryClient(db_path=":memory:") as q:
            df = q.query_sql(
                "tvscreener.signals_batch", slice_sql, params={"params_hash": data_params_hash}
            )
    except Exception as exc:
        logger.debug("Sidemantic slice query failed: %s", exc)
        return None

    if df.empty:
        return None

    tmpdir = tempfile.mkdtemp(prefix="tvscreener_sidemantic_")
    try:
        db_path = str(Path(tmpdir) / "semantic.duckdb")
        con = duckdb.connect(db_path)
        con.execute("CREATE SCHEMA IF NOT EXISTS tvscreener")
        con.register("signals_batch_df", df)
        con.execute(
            "CREATE OR REPLACE TABLE tvscreener.signals_batch AS SELECT * FROM signals_batch_df"
        )
        con.close()

        layer = SemanticLayer(connection=f"duckdb:///{db_path}")
        models_dir = Path.cwd() / "semantic" / "models"
        load_from_directory(layer, models_dir)

        query = (
            "SELECT grade, direction, opportunity_count, avg_ensemble_score, avg_total_confluence, "
            "avg_trend_score, avg_ma_score, avg_osc_score, avg_roc_score "
            "FROM opportunity_matrix "
            f"WHERE opportunity_matrix.params_hash = '{data_params_hash}' "
            "ORDER BY opportunity_count DESC "
            f"LIMIT {int(limit)}"
        )
        res = layer.sql(query)
        rows = res.fetchall()
        cols = [d[0] for d in res.description]
        return [dict(zip(cols, r, strict=False)) for r in rows]
    except Exception as exc:
        logger.debug("Sidemantic semantic query failed: %s", exc)
        return None
    finally:
        with contextlib.suppress(Exception):
            import shutil

            shutil.rmtree(tmpdir)
