from datetime import UTC, datetime

from tvscreener.lib.pipeline_runner import PipelineRunSpec, RunResult, _persist_run_record


def test_persist_run_record_uses_concrete_types(monkeypatch):
    captured = {}

    def _fake_write_iceberg(
        df, table_name, mode="append", partition_by=None, overwrite_filter=None
    ):
        captured["df"] = df
        captured["table"] = table_name

    monkeypatch.setattr("tvscreener.lib.lakehouse.write_iceberg", _fake_write_iceberg)

    spec = PipelineRunSpec(
        scanner_family="opportunity",
        pipeline_mode="analytics",
        asset_type="crypto",
        universe="majors",
        timeframes=["240", "60", "15"],
        instrument_type="spot",
        config_path=None,
    )
    now = datetime.now(tz=UTC)
    result = RunResult(
        params_hash=spec.compute_params_hash(),
        scanner_family="opportunity",
        pipeline_mode_executed="analytics",
        started_at_utc=now,
        finished_at_utc=now,
        success=True,
        result_count=0,
        exit_code=0,
        errors=[],
    )

    _persist_run_record(spec, result)
    df = captured["df"]
    assert "instrument_type" in df.columns
    assert df["instrument_type"].iloc[0] == "spot"
    assert df["config_path"].iloc[0] == ""
