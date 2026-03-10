import pandas as pd

from tvscreener.lib.universe import binance_crypto as bc


def test_tradeable_mcap_cs_restricts_to_market_cap_bases(monkeypatch):
    monkeypatch.setattr(
        bc,
        "fetch_tradingview_top_coins_by_market_cap",
        lambda top_n=100: pd.DataFrame({"Name": ["AUSD", "BUSD"], "Market Cap Calc": [2, 1]}),
    )

    # Candidates include A and C; only A should survive the mcap base restriction.
    df = pd.DataFrame(
        {
            "Symbol": ["BINANCE:AUSDT", "BINANCE:CUSDT"],
            "Volume 24h in USD": [50_000_000, 50_000_000],
            "Volatility": [4.0, 4.0],
        }
    )
    monkeypatch.setattr(
        bc,
        "fetch_tradingview_binance_crypto_candidates",
        lambda instrument_type, max_rows=5000: df,
    )

    tickers, snapshot = bc.build_binance_crypto_universe_tradeable_mcap_overlap(
        constraints=bc.BinanceCryptoTradeableMcapOverlapUniverseConstraints(
            instrument_type="spot",
            top_n_market_cap=100,
            top_n=100,
            quote_assets=("USDT",),
            min_quote_volume_usd_spot=1.0,
            min_quote_volume_usd_perp=1.0,
        )
    )
    assert tickers == ["BINANCE:AUSDT"]
    assert snapshot["constraints"]["selection"] == "tradeable_mcap_overlap"
