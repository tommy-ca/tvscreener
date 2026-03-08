import pandas as pd

from tvscreener.lib.universe.binance_crypto import (
    BinanceCryptoMarketCapUniverseConstraints,
    BinanceCryptoUniverseConstraints,
    build_binance_crypto_universe_market_cap,
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


def test_market_cap_universe_filters_volatility_and_sorts_by_volume(monkeypatch):
    # Mock top coins by market cap -> bases A, B
    import pandas as pd

    from tvscreener.lib.universe import binance_crypto as bc

    monkeypatch.setattr(
        bc,
        "fetch_tradingview_top_coins_by_market_cap",
        lambda top_n=100: pd.DataFrame({"Name": ["AUSD", "BUSD"], "Market Cap Calc": [2, 1]}),
    )

    # Mock ticker fetch: both markets are present, regardless of volatility.
    monkeypatch.setattr(
        bc,
        "fetch_tradingview_crypto_tickers",
        lambda tickers: pd.DataFrame(
            {
                "Symbol": tickers,
                "Name": ["AUSDT", "BUSDT"],
                "Market Capitalization": [1000, 900],
                "Volume 24h in USD": [200_000_000, 50_000_000],
                "Volatility": [2.0, 4.0],
                "Price": [1.0, 1.0],
                "High": [1.0, 1.0],
                "Low": [1.0, 1.0],
            }
        ),
    )

    tickers, snapshot = build_binance_crypto_universe_market_cap(
        constraints=BinanceCryptoMarketCapUniverseConstraints(
            instrument_type="spot",
            top_n_market_cap=100,
            quote_asset="USDT",
            min_volatility_24h_pct=0.0,
        )
    )
    assert tickers == ["BINANCE:AUSDT", "BINANCE:BUSDT"]
    assert snapshot["constraints"]["selection"] == "market_cap_top100"
    assert snapshot["market_cap_bases"] == ["A", "B"]
