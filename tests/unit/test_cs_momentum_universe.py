import pandas as pd

from tvscreener_ext.universe import binance_crypto as bc


def test_cs_momentum_universe_excludes_stables_and_sorts_by_volume(monkeypatch):
    monkeypatch.setattr(
        bc,
        "fetch_tradingview_top_coins_by_market_cap",
        lambda top_n=200: pd.DataFrame(
            {"Name": ["BTCUSD", "USDCUSD", "ETHUSD"], "Market Cap Calc": [3, 2, 1]}
        ),
    )

    def _fetch(tickers: list[str]) -> pd.DataFrame:
        # USDC should never be requested (excluded); BTC volume < ETH volume.
        assert "BINANCE:USDCUSDT" not in tickers
        volumes = []
        for t in tickers:
            if t.startswith("BINANCE:ETH"):
                volumes.append(120_000_000)
            else:
                volumes.append(50_000_000)
        return pd.DataFrame(
            {
                "Symbol": tickers,
                "Volume 24h in USD": volumes,
                "Volatility": [5.0] * len(tickers),
                "Price": [1.0] * len(tickers),
                "High": [1.0] * len(tickers),
                "Low": [1.0] * len(tickers),
            }
        )

    monkeypatch.setattr(bc, "fetch_tradingview_crypto_tickers", _fetch)

    tickers, snapshot = bc.build_binance_crypto_universe_cs_momentum(
        constraints=bc.BinanceCryptoCSMomentumUniverseConstraints(
            instrument_type="spot",
            seed_top_n_market_cap=200,
            min_quote_volume_usd=10_000_000,
        )
    )

    # Sorted by volume desc
    assert tickers == ["BINANCE:ETHUSDT", "BINANCE:BTCUSDT"]
    assert snapshot["constraints"]["selection"] == "cs_momentum_candidates"
