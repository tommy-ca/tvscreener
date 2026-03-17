from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd


def test_pipeline_spec_normalized_sets_code_version_from_env(monkeypatch):
    from tvscreener.lib.pipeline_runner import PipelineRunSpec

    monkeypatch.setenv("TVSCREENER_CODE_VERSION", "v-test-001")

    spec = PipelineRunSpec(
        scanner_family="opportunity",
        pipeline_mode="data",
        asset_type="forex",
        timeframes=["15", "60", "240"],
    ).normalized()

    assert spec.code_version == "v-test-001"
    assert spec.params_hash
    assert spec.timeframe_set_id


def test_local_runner_persists_runs_metadata(monkeypatch):
    from tvscreener.lib import pipeline_runner as pr

    class DummyController:
        def __init__(self, console=None):
            self._console = console

        def run_scan(self, _request):
            return 3

    captured: dict[str, object] = {}

    def fake_write_iceberg(df, table_name, mode="append", partition_by=None, overwrite_filter=None):
        captured["df"] = df
        captured["table_name"] = table_name
        captured["mode"] = mode
        captured["partition_by"] = partition_by
        captured["overwrite_filter"] = overwrite_filter

    monkeypatch.setattr(pr, "ScreenerController", DummyController)
    monkeypatch.setattr(pr, "_utc_now", lambda: datetime(2026, 3, 7, 12, 0, tzinfo=UTC))
    monkeypatch.setattr("tvscreener.lib.lakehouse.get_manager", lambda _config=None: object())
    monkeypatch.setattr("tvscreener.lib.lakehouse.write_iceberg", fake_write_iceberg)

    spec = pr.PipelineRunSpec(
        scanner_family="opportunity",
        pipeline_mode="data",
        asset_type="forex",
        universe="majors",
        timeframes=["15", "60", "240"],
    ).normalized()

    result = pr.LocalRunner(console=None).run(spec)

    assert result.success is True
    assert result.result_count == 3

    assert captured["table_name"] == "tvscreener.runs"
    assert captured["mode"] == "append"
    assert captured["partition_by"] == ["asset_type", "ingest_date"]

    persisted_df = captured["df"]
    assert isinstance(persisted_df, pd.DataFrame)
    assert persisted_df.iloc[0]["params_hash"] == spec.params_hash
    assert persisted_df.iloc[0]["run_id"] == spec.params_hash
    assert persisted_df.iloc[0]["code_version"] == spec.code_version
    assert persisted_df.iloc[0]["asset_type"] == "forex"
    assert bool(persisted_df.iloc[0]["success"]) is True


def test_local_runner_strict_persist_raises_on_run_metadata_failure(monkeypatch):
    from tvscreener.lib import pipeline_runner as pr

    class DummyController:
        def __init__(self, console=None):
            self._console = console

        def run_scan(self, _request):
            return 1

    def failing_write_iceberg(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setenv("TVSCREENER_STRICT_PERSIST", "1")
    monkeypatch.setattr(pr, "ScreenerController", DummyController)
    monkeypatch.setattr(pr, "_utc_now", lambda: datetime(2026, 3, 7, 12, 0, tzinfo=UTC))
    monkeypatch.setattr("tvscreener.lib.lakehouse.get_manager", lambda _config=None: object())
    monkeypatch.setattr("tvscreener.lib.lakehouse.write_iceberg", failing_write_iceberg)

    spec = pr.PipelineRunSpec(
        scanner_family="opportunity",
        pipeline_mode="data",
        asset_type="forex",
        universe="majors",
        timeframes=["15", "60", "240"],
    ).normalized()

    try:
        _ = pr.LocalRunner(console=None).run(spec)
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("Expected strict persistence to raise")
