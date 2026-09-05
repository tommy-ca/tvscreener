from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from tvscreener_ext.data_sources.logic import (
    StubDataSource,
    TradingViewDataSource,
    build_data_source,
)


def test_build_data_source_defaults_to_tradingview():
    adapter = build_data_source(None)
    assert isinstance(adapter, TradingViewDataSource)
    assert adapter.source == "tradingview"


def test_build_data_source_stub_alias():
    adapter = build_data_source("mock")
    assert isinstance(adapter, StubDataSource)
    assert adapter.source == "stub"


def test_tradingview_adapter_adds_provenance_columns():
    screener = MagicMock()
    df = pd.DataFrame({"Symbol": ["FX:EURUSD"], "PRICE": [1.0]})
    screener.get.return_value = df

    adapter = TradingViewDataSource()
    out = adapter.fetch_batch(screener=screener, tickers=["FX:EURUSD"])

    assert "source" in out.columns
    assert "source_event_id" in out.columns
    assert out.iloc[0]["source"] == "tradingview"


def test_stub_adapter_returns_contract_columns():
    adapter = StubDataSource()
    out = adapter.fetch_batch(screener=MagicMock(), tickers=["A", "B"])

    assert list(out["Symbol"]) == ["A", "B"]
    assert "source" in out.columns
    assert "source_event_id" in out.columns
    assert set(out["source"].tolist()) == {"stub"}
