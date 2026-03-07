from unittest.mock import ANY, MagicMock, patch

import pandas as pd
import pytest
from pyiceberg.exceptions import NoSuchTableError

from tvscreener.core.base import Screener
from tvscreener.lib.screeners.base import BaseOpportunityScreener, ScreenerConfig


class MockScreener(BaseOpportunityScreener):
    def _get_screener_instance(self):
        return MagicMock(spec=Screener)

    def _get_field_class(self):
        return MagicMock()

    def _fetch_all_data(self):
        return pd.DataFrame({"Name": ["TEST"], "Price": [1.0]})


@pytest.fixture
def mock_catalog():
    with patch("tvscreener.lib.screeners.base.get_catalog") as mock:
        yield mock


@pytest.fixture
def mock_write_iceberg():
    with patch("tvscreener.lib.screeners.base.write_iceberg") as mock:
        yield mock


def test_ingest_no_replay(mock_catalog, mock_write_iceberg):
    config = ScreenerConfig()
    screener = MockScreener(symbols=["TEST"], config=config)

    df = screener._ingest()

    assert not df.empty
    assert df.iloc[0]["Name"] == "TEST"
    mock_catalog.assert_not_called()
    mock_write_iceberg.assert_called_with(
        ANY,
        "tvscreener.bronze",
        mode="append",
        partition_by=["asset_type", "ingest_date", "timeframe_set_id"],
        overwrite_filter=None,
    )


def test_ingest_replay_success(mock_catalog, mock_write_iceberg):
    config = ScreenerConfig(extra_options={"replay": True})
    screener = MockScreener(symbols=["TEST"], config=config)

    mock_table = MagicMock()
    replayed = pd.DataFrame({"Name": ["REPLAYED"], "Price": [2.0]})
    mock_table.scan.return_value.to_arrow.return_value.to_pandas.return_value = replayed
    mock_catalog.return_value.load_table.return_value = mock_table

    df = screener._ingest()

    assert df.iloc[0]["Name"] == "REPLAYED"
    mock_catalog.return_value.load_table.assert_called_with("tvscreener.bronze")


def test_ingest_replay_no_table(mock_catalog, mock_write_iceberg):
    config = ScreenerConfig(extra_options={"replay": True})
    screener = MockScreener(symbols=["TEST"], config=config)

    mock_catalog.return_value.load_table.side_effect = NoSuchTableError("No table")

    df = screener._ingest()

    assert df.iloc[0]["Name"] == "TEST"  # Fallback to fetch
    mock_catalog.return_value.load_table.assert_called_with("tvscreener.bronze")


def test_standardize_no_replay(mock_catalog, mock_write_iceberg):
    config = ScreenerConfig()
    screener = MockScreener(symbols=["TEST"], config=config)
    input_df = pd.DataFrame({"Name": ["TEST"], "Price": [1.0]})

    df = screener._standardize(input_df)

    assert not df.empty
    mock_write_iceberg.assert_called_with(
        ANY,
        "tvscreener.silver",
        mode="overwrite",
        partition_by=["asset_type", "timeframe_set_id"],
        overwrite_filter=ANY,
    )


def test_score_no_replay(mock_catalog, mock_write_iceberg):
    config = ScreenerConfig()
    screener = MockScreener(symbols=["TEST"], config=config)
    input_df = pd.DataFrame({"Name": ["TEST"], "Price": [1.0], "ENSEMBLE_SCORE": [0.5]})

    # Mock ScoringEngine class method instead of instance method
    with patch(
        "tvscreener.score.ScoringEngine.rank_opportunities", return_value=input_df
    ) as mock_rank:
        df = screener._score(input_df)
        assert not df.empty
        mock_rank.assert_called_once()

        calls = [(c.args, c.kwargs) for c in mock_write_iceberg.call_args_list]
        assert any(args[1] == "tvscreener.gold" for args, _ in calls)
        assert any(args[1] == "tvscreener.signals_batch" for args, _ in calls)
        assert any(args[1] == "tvscreener.signals_latest" for args, _ in calls)


def test_score_writes_long_form_when_enabled(mock_catalog, mock_write_iceberg):
    config = ScreenerConfig(extra_options={"long_form_output": True})
    screener = MockScreener(symbols=["TEST"], timeframes=["15", "60"], config=config)
    input_df = pd.DataFrame(
        {
            "entity_id": ["fx:eurusd"],
            "PAIR": ["EURUSD"],
            "TREND_15": [0.4],
            "TREND_60": [0.8],
            "ROC_15": [0.1],
            "ROC_60": [0.2],
            "ENSEMBLE_SCORE": [0.5],
        }
    )

    with patch("tvscreener.score.ScoringEngine.rank_opportunities", return_value=input_df):
        _ = screener._score(input_df)

    calls = [(c.args, c.kwargs) for c in mock_write_iceberg.call_args_list]
    assert any(args[1] == "tvscreener.signals_long" for args, _ in calls)

    long_call = next((args for args, _ in calls if args[1] == "tvscreener.signals_long"), None)
    assert long_call is not None
    long_df = long_call[0]
    assert list(long_df["timeframe"]) == ["15", "60"]
    assert "trend" in long_df.columns
    assert "roc" in long_df.columns


def test_ingest_persists_params_hash_and_code_version(
    mock_catalog, mock_write_iceberg, monkeypatch
):
    monkeypatch.setenv("TVSCREENER_PARAMS_HASH", "phash-123")
    monkeypatch.setenv("TVSCREENER_CODE_VERSION", "git-abc123")

    config = ScreenerConfig()
    screener = MockScreener(symbols=["TEST"], config=config)

    _ = screener._ingest()

    persisted_df = mock_write_iceberg.call_args.args[0]
    assert "params_hash" in persisted_df.columns
    assert "code_version" in persisted_df.columns
    assert persisted_df.iloc[0]["params_hash"] == "phash-123"
    assert persisted_df.iloc[0]["code_version"] == "git-abc123"


def test_fetch_all_data_retries_then_succeeds():
    config = ScreenerConfig(
        extra_options={
            "batch_size": 1,
            "source_policies": {
                "tradingview": {
                    "min_interval_seconds": 0,
                    "jitter_seconds": 0,
                    "fetch_max_retries": 2,
                    "fetch_retry_base_seconds": 0,
                    "fetch_retry_max_seconds": 0,
                }
            },
        }
    )
    screener = MockScreener(symbols=["TEST"], config=config)

    client = MagicMock()
    client.get.side_effect = [
        RuntimeError("transient"),
        pd.DataFrame({"Symbol": ["TEST"], "Name": ["TEST"], "Price": [1.0]}),
    ]
    screener._get_screener_instance = lambda: client

    df = BaseOpportunityScreener._fetch_all_data(screener)

    assert client.get.call_count == 2
    assert not df.empty
    assert "source" in df.columns
    assert "source_event_id" in df.columns
    stats = screener.metadata.config.get("ingest_stats") or {}
    assert stats.get("failed_batches") == 0


def test_fetch_all_data_retries_are_bounded_on_failure():
    config = ScreenerConfig(
        extra_options={
            "batch_size": 1,
            "source_policies": {
                "tradingview": {
                    "min_interval_seconds": 0,
                    "jitter_seconds": 0,
                    "fetch_max_retries": 1,
                    "fetch_retry_base_seconds": 0,
                    "fetch_retry_max_seconds": 0,
                }
            },
        }
    )
    screener = MockScreener(symbols=["TEST"], config=config)

    client = MagicMock()
    client.get.side_effect = RuntimeError("always-fail")
    screener._get_screener_instance = lambda: client

    df = BaseOpportunityScreener._fetch_all_data(screener)

    assert df.empty
    assert client.get.call_count == 2  # initial + one retry
    stats = screener.metadata.config.get("ingest_stats") or {}
    assert stats.get("failed_batches") == 1
    assert stats.get("coverage") == 0.0
