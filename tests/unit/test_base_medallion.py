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
    with patch("tvscreener.lib.screeners.pipeline.get_catalog") as mock:
        yield mock


@pytest.fixture
def mock_write_iceberg():
    with patch("tvscreener.lib.screeners.pipeline.write_iceberg") as mock:
        yield mock


def test_ingest_no_replay(mock_catalog, mock_write_iceberg):
    config = ScreenerConfig()
    screener = MockScreener(symbols=["TEST"], config=config)

    df = screener._ingest()

    assert not df.empty
    assert df.iloc[0]["Name"] == "TEST"
    mock_catalog.assert_not_called()
    mock_write_iceberg.assert_called_with(
        ANY, "tvscreener.bronze", mode="append", partition_by=["ingest_date"]
    )


def test_ingest_replay_success(mock_catalog, mock_write_iceberg):
    config = ScreenerConfig(extra_options={"replay": True})
    screener = MockScreener(symbols=["TEST"], config=config)

    mock_table = MagicMock()
    mock_table.to_pandas.return_value = pd.DataFrame({"Name": ["REPLAYED"], "Price": [2.0]})
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
        ANY, "tvscreener.silver", mode="overwrite", partition_by=["asset_type"]
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
        mock_write_iceberg.assert_called_with(
            ANY, "tvscreener.gold", mode="overwrite", partition_by=["signal_date"]
        )
