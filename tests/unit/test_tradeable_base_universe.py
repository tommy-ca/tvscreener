import pandas as pd

from tvscreener.lib.universe import binance_crypto as bc


def test_tradeable_base_picks_one_per_base_and_prefers_usdt(monkeypatch):
    # Mock candidates as if returned from TradingView crypto /scan.
    df = pd.DataFrame(
        {
            "Symbol": [
                "BINANCE:ABCUSDC",
                "BINANCE:ABCUSDT",
                "BINANCE:XYZUSDT",
                "BINANCE:USDCUSDT",
            ],
            "Volume 24h in USD": [50_000_000, 60_000_000, 40_000_000, 500_000_000],
            "Volatility": [4.0, 4.0, 4.0, 1.0],
        }
    )

    monkeypatch.setattr(
        bc,
        "fetch_tradingview_binance_crypto_candidates",
        lambda instrument_type, max_rows=5000: df,
    )

    tickers, snapshot = bc.build_binance_crypto_universe_tradeable_base(
        constraints=bc.BinanceCryptoTradeableBaseUniverseConstraints(
            instrument_type="spot",
            top_n=200,
            quote_assets=("USDT", "USDC"),
            min_quote_volume_usd=10_000_000,
        )
    )

    # USDC base is excluded; ABC prefers USDT over USDC.
    assert "BINANCE:USDCUSDT" not in tickers
    assert "BINANCE:ABCUSDT" in tickers
    assert "BINANCE:ABCUSDC" not in tickers
    assert snapshot["constraints"]["selection"] == "tradeable_base"
