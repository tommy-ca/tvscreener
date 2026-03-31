import pandas as pd
from tvscreener_ext.universe import binance_crypto as bc


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
            # Keep this unit test network-free.
            min_history_days_non_mcap=0,
        )
    )

    # USDC base is excluded; ABC prefers USDT over USDC.
    assert "BINANCE:USDCUSDT" not in tickers
    assert "BINANCE:ABCUSDT" in tickers
    assert "BINANCE:ABCUSDC" not in tickers
    assert snapshot["constraints"]["selection"] == "tradeable_base"


def test_tradeable_base_excludes_new_non_mcap_bases(monkeypatch):
    df = pd.DataFrame(
        {
            "Symbol": ["BINANCE:AAAUSDT", "BINANCE:NEWUSDT"],
            "Volume 24h in USD": [50_000_000, 60_000_000],
            "Volatility": [4.0, 4.0],
            # Provide history timestamps in seconds.
            "First Bar Time": [0, 0],
            "Last Bar Update Time": [86400 * 400, 86400 * 10],
        }
    )

    monkeypatch.setattr(
        bc,
        "fetch_tradingview_binance_crypto_candidates",
        lambda instrument_type, max_rows=5000: df,
    )
    monkeypatch.setattr(
        bc,
        "fetch_tradingview_top_coins_by_market_cap",
        lambda top_n=100: pd.DataFrame({"Name": ["AAAUSD"], "Market Cap Calc": [1]}),
    )

    tickers, snapshot = bc.build_binance_crypto_universe_tradeable_base(
        constraints=bc.BinanceCryptoTradeableBaseUniverseConstraints(
            instrument_type="spot",
            quote_assets=("USDT",),
            min_quote_volume_usd=10_000_000,
            min_history_days_non_mcap=180,
            top_n=200,
        )
    )

    assert "BINANCE:AAAUSDT" in tickers
    assert "BINANCE:NEWUSDT" not in tickers
    assert snapshot["excluded_risky"]
    assert any((r.get("base") or "").upper() == "NEW" for r in snapshot["excluded_risky"])
