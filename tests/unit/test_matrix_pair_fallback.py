import pandas as pd
from tvscreener_ext.screeners.base import ScreenerConfig
from tvscreener_ext.screeners.factory import GenericOpportunityScreener


def test_prepare_enriched_data_adds_pair_for_crypto_from_symbol():
    screener = GenericOpportunityScreener(
        asset_type="crypto",
        symbols=["BINANCE:BTCUSDT"],
        timeframes=["240"],
        config=ScreenerConfig(),
    )
    df = pd.DataFrame({"symbol": ["BINANCE:BTCUSDT"], "TREND_240": [0.5]})
    out = screener._prepare_enriched_data(df)
    assert "PAIR" in out.columns
    assert out["PAIR"].iloc[0] == "BTCUSDT"


def test_prepare_enriched_data_adds_pair_for_crypto_from_qualified_symbol():
    screener = GenericOpportunityScreener(
        asset_type="crypto",
        symbols=["BINANCE:BTCUSDT"],
        timeframes=["240"],
        config=ScreenerConfig(),
    )
    df = pd.DataFrame({"Symbol": ["BINANCE:BTCUSDT"], "TREND_240": [0.5]})
    out = screener._prepare_enriched_data(df)
    assert out["PAIR"].iloc[0] == "BTCUSDT"


def test_prepare_enriched_data_fills_pair_when_present_but_null():
    screener = GenericOpportunityScreener(
        asset_type="crypto",
        symbols=["BINANCE:BTCUSDT"],
        timeframes=["240"],
        config=ScreenerConfig(),
    )
    df = pd.DataFrame({"PAIR": [None], "Symbol": ["BINANCE:BTCUSDT"]})
    out = screener._prepare_enriched_data(df)
    assert out["PAIR"].iloc[0] == "BTCUSDT"
