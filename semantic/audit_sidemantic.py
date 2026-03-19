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
        con.close()

        layer = SemanticLayer(connection=f"duckdb:///{db_path}")
        load_from_directory(layer, Path.cwd() / "semantic" / "models")

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
