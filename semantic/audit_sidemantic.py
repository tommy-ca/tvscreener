from __future__ import annotations

import tempfile
from pathlib import Path


def main() -> int:
    try:
        import duckdb
        from sidemantic import SemanticLayer, load_from_directory
    except Exception as exc:
        raise SystemExit(
            "Sidemantic is not installed; run `uv sync --extra semantic` first"
        ) from exc

    from tvscreener.lib.query import EdgeQueryClient

    repo_root = Path(__file__).resolve().parents[1]

    # Pick a recent data params_hash that has signals.
    with EdgeQueryClient(db_path=":memory:") as q:
        runs = q.query_sql(
            "tvscreener.runs",
            """
            SELECT params_hash
            FROM df
            WHERE pipeline_mode_executed='data'
              AND success=true
              AND scanner_family='opportunity'
            ORDER BY started_at_utc DESC
            LIMIT 1
            """,
            params={},
        )
        if runs.empty:
            raise SystemExit("No successful data runs found in tvscreener.runs")
        data_params_hash = str(runs.iloc[0]["params_hash"])

        signals = q.query_sql(
            "tvscreener.signals_batch",
            """
            SELECT *
            FROM df
            WHERE params_hash = $params_hash
            """,
            params={"params_hash": data_params_hash},
        )
        if signals.empty:
            raise SystemExit(f"No signals_batch rows for params_hash={data_params_hash}")

        # Also pull a small runs slice.
        runs_slice = q.query_sql(
            "tvscreener.runs",
            """
            SELECT *
            FROM df
            WHERE scanner_family='opportunity'
            ORDER BY started_at_utc DESC
            LIMIT 200
            """,
            params={},
        )

    tmpdir = tempfile.mkdtemp(prefix="tvscreener_sidemantic_audit_")
    try:
        db_path = str(Path(tmpdir) / "audit.duckdb")
        con = duckdb.connect(db_path)
        con.execute("CREATE SCHEMA IF NOT EXISTS tvscreener")
        con.register("signals_df", signals)
        con.register("runs_df", runs_slice)
        con.execute("CREATE OR REPLACE TABLE tvscreener.signals_batch AS SELECT * FROM signals_df")
        con.execute("CREATE OR REPLACE TABLE tvscreener.runs AS SELECT * FROM runs_df")

        # Prefect-artifact helper views (used by semantic models).
        con.execute(
            """
            CREATE OR REPLACE VIEW tvscreener.signals_batch_dedup AS
            WITH ranked AS (
              SELECT
                *,
                abs(ENSEMBLE_SCORE) AS ENSEMBLE_SCORE_ABS,
                row_number() OVER (
                  PARTITION BY PAIR
                  ORDER BY TOTAL_CONFLUENCE DESC NULLS LAST,
                           abs(ENSEMBLE_SCORE) DESC NULLS LAST,
                           fetched_at_utc DESC NULLS LAST
                ) AS rn
              FROM tvscreener.signals_batch
            )
            SELECT * FROM ranked WHERE rn = 1
            """
        )
        con.execute(
            """
            CREATE OR REPLACE VIEW tvscreener.signals_pair_stats AS
            WITH base AS (
              SELECT
                params_hash,
                PAIR AS pair,
                DIRECTION,
                ROC_SCORE,
                ROC_15,
                ROC_60,
                ROC_240
              FROM tvscreener.signals_batch
            ), per_pair AS (
              SELECT
                params_hash,
                pair,
                count(*) AS row_count,
                count(DISTINCT DIRECTION) AS direction_count,
                CASE WHEN max(ROC_SCORE) = 0 AND (max(ROC_15) <> 0 OR max(ROC_60) <> 0 OR max(ROC_240) <> 0)
                  THEN 1 ELSE 0 END AS roc_flag
              FROM base
              GROUP BY 1, 2
            )
            SELECT
              params_hash,
              pair,
              row_count,
              direction_count,
              CASE WHEN row_count > 1 THEN 1 ELSE 0 END AS duplicate_flag,
              CASE WHEN direction_count > 1 THEN 1 ELSE 0 END AS conflict_flag,
              roc_flag
            FROM per_pair
            """
        )
        con.close()

        layer = SemanticLayer(connection=f"duckdb:///{db_path}")
        load_from_directory(layer, repo_root / "semantic" / "models")

        # Basic model availability.
        for sql in [
            "SELECT run_count, success_count, failure_count FROM tvscreener_runs LIMIT 1",
            (
                "SELECT grade, direction, opportunity_count, avg_ensemble_score, avg_roc_score "
                "FROM opportunity_matrix "
                f"WHERE opportunity_matrix.params_hash = '{data_params_hash}' "
                "GROUP BY 1,2 "
                "ORDER BY opportunity_count DESC "
                "LIMIT 10"
            ),
            (
                "SELECT PAIR, Name, TOTAL_CONFLUENCE, ENSEMBLE_SCORE "
                "FROM opportunity_top_rows "
                f"WHERE opportunity_top_rows.params_hash = '{data_params_hash}' "
                "ORDER BY TOTAL_CONFLUENCE DESC NULLS LAST "
                "LIMIT 5"
            ),
            (
                "SELECT total_rows, unique_pairs, duplicate_pairs, conflict_pairs, roc_score_zero_but_raw_nonzero "
                "FROM opportunity_health "
                f"WHERE opportunity_health.params_hash = '{data_params_hash}'"
            ),
        ]:
            res = layer.sql(sql)
            _ = res.fetchall()

        print("OK sidemantic audit")
        print("data_params_hash", data_params_hash)
        return 0
    finally:
        import shutil

        shutil.rmtree(tmpdir)


if __name__ == "__main__":
    raise SystemExit(main())
