from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from tvscreener.core.base import Screener
from tvscreener.lib.screeners.base import BaseOpportunityScreener, ScreenerConfig


class MultiAssetMockScreener(BaseOpportunityScreener):
    def _get_screener_instance(self):
        return MagicMock(spec=Screener)

    def _get_field_class(self):
        return MagicMock()

    def _fetch_all_data(self):
        return pd.DataFrame({"Name": ["TEST"], "Price": [1.0]})


@pytest.mark.parametrize(
    ("asset_type", "raw"),
    [
        ("forex", pd.DataFrame({"PAIR": ["EURUSD"], "Price": [1.0]})),
        ("stock", pd.DataFrame({"Symbol": ["NASDAQ:AAPL"], "Price": [180.0]})),
        ("crypto", pd.DataFrame({"Symbol": ["BINANCE:BTCUSDT"], "Price": [60000.0]})),
    ],
)
def test_multi_asset_standardize_populates_entity_id(asset_type, raw):
    screener = MultiAssetMockScreener(symbols=["X"], asset_type=asset_type, config=ScreenerConfig())

    with patch("tvscreener.lib.screeners.base.write_iceberg"):
        out = screener._standardize(raw)

    assert not out.empty
    assert "entity_id" in out.columns
    assert out["entity_id"].notna().all()


def test_overwrite_scope_uses_asset_type_and_entity_id():
    screener = MultiAssetMockScreener(symbols=["AAPL"], asset_type="stock", config=ScreenerConfig())
    raw = pd.DataFrame({"Symbol": ["NASDAQ:AAPL"], "Price": [180.0]})

    with patch("tvscreener.lib.screeners.base.write_iceberg") as mock_write:
        _ = screener._standardize(raw)

    silver_calls = [c for c in mock_write.call_args_list if c.args[1] == "tvscreener.silver"]
    assert silver_calls
    kwargs = silver_calls[0].kwargs
    assert kwargs["mode"] == "overwrite"
    assert kwargs["partition_by"] == ["asset_type", "timeframe_set_id"]

    overwrite_filter = kwargs["overwrite_filter"]
    filter_text = str(overwrite_filter)
    assert "asset_type" in filter_text
    assert "entity_id" in filter_text


def test_coverage_gating_blocks_partial_silver_publish():
    config = ScreenerConfig(extra_options={"min_ingest_coverage": 0.95})
    screener = MultiAssetMockScreener(symbols=["BTCUSDT"], asset_type="crypto", config=config)
    screener.metadata.update_config(
        {"ingest_stats": {"requested_tickers_count": 10, "returned_unique": 5, "coverage": 0.5}}
    )
    raw = pd.DataFrame({"Symbol": ["BINANCE:BTCUSDT"], "Price": [60000.0]})

    with patch("tvscreener.lib.screeners.base.write_iceberg") as mock_write:
        out = screener._standardize(raw)

    assert not out.empty
    mock_write.assert_not_called()
