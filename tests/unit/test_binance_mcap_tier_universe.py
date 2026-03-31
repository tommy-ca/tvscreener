import pandas as pd
from tvscreener_ext.universe import binance_crypto as bc


def test_mcap_tier_universe_selects_rank_slice_and_applies_liquidity_and_history(monkeypatch):
    # Market-cap list: A (rank1), B (rank2), C (rank3)
    monkeypatch.setattr(
        bc,
        "fetch_tradingview_top_coins_by_market_cap",
        lambda top_n=200: pd.DataFrame(
            {"Name": ["AUSD", "BUSD", "CUSD"], "Market Cap Calc": [3, 2, 1]}
        ),
    )

    # Candidates returned from /scan.
    df = pd.DataFrame(
        {
            "Symbol": [
                "BINANCE:AUSDC",
                "BINANCE:AUSDT",
                "BINANCE:BUSDT",
                "BINANCE:CUSDT",
            ],
            "Volume 24h in USD": [50_000_000, 20_000_000, 30_000_000, 30_000_000],
            "Volatility": [4.0, 4.0, 4.0, 4.0],
            # History in seconds.
            "First Bar Time": [0, 0, 0, 0],
            "Last Bar Update Time": [86400 * 400, 86400 * 400, 86400 * 400, 86400 * 10],
        }
    )
    monkeypatch.setattr(
        bc,
        "fetch_tradingview_binance_crypto_candidates",
        lambda instrument_type, max_rows=5000: df,
    )

    # Majors: ranks 1-2 => A, B. Prefer USDT for A.
    tickers, snapshot = bc.build_binance_crypto_universe_mcap_tier(
        constraints=bc.BinanceCryptoMcapTierUniverseConstraints(
            instrument_type="spot",
            top_n_market_cap=200,
            mcap_rank_min=1,
            mcap_rank_max=2,
            quote_assets=("USDT", "USDC"),
            min_quote_volume_usd_spot=10_000_000,
            min_history_days=180,
        )
    )

    assert tickers == ["BINANCE:BUSDT", "BINANCE:AUSDT"]
    assert snapshot["constraints"]["selection"] == "tradeable_mcap_tier"
    assert snapshot["market_cap_bases"] == ["A", "B"]
    assert snapshot["missing_bases"] == []

    # Minors: ranks 3-3 => C, but it fails history and gets excluded.
    tickers2, snapshot2 = bc.build_binance_crypto_universe_mcap_tier(
        constraints=bc.BinanceCryptoMcapTierUniverseConstraints(
            instrument_type="spot",
            top_n_market_cap=200,
            mcap_rank_min=3,
            mcap_rank_max=3,
            quote_assets=("USDT",),
            min_quote_volume_usd_spot=10_000_000,
            min_history_days=180,
        )
    )
    assert tickers2 == []
    assert snapshot2["market_cap_bases"] == ["C"]
    assert snapshot2["missing_bases"] == ["C"]
