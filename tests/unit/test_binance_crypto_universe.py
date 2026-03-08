import pandas as pd

from tvscreener.lib.universe.binance_crypto import (
    BinanceCryptoUniverseConstraints,
    filter_and_rank_candidates,
)


def test_filter_and_rank_candidates_applies_thresholds_and_sorts():
    df = pd.DataFrame(
        {
            "Symbol": ["BINANCE:A", "BINANCE:B", "BINANCE:C"],
            "Name": ["A", "B", "C"],
            "Type": ["spot", "spot", "spot"],
            "Subtype": ["crypto", "crypto", "crypto"],
            "Price": [100.0, 100.0, 100.0],
            "High": [104.0, 103.0, 120.0],
            "Low": [100.0, 101.0, 119.0],
            # When present, TradingView's volatility column should be used.
            "Volatility": [4.0, 2.0, 50.0],
            "Volume 24h in USD": [20_000_000, 50_000_000, 9_000_000],
        }
    )

    out = filter_and_rank_candidates(
        df,
        constraints=BinanceCryptoUniverseConstraints(
            instrument_type="spot",
            top_n=100,
            min_quote_volume_usd=10_000_000,
            min_volatility_24h_pct=3.0,
        ),
    )

    # C fails min volume; B fails min volatility; only A remains.
    assert out["Symbol"].tolist() == ["BINANCE:A"]
    assert out["rank"].tolist() == [1]
    assert out["instrument_type"].tolist() == ["spot"]
