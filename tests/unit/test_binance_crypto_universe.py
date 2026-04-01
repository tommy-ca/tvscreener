import pandas as pd

from tvscreener_ext.universe.binance_crypto import (
    BinanceCryptoMarketCapUniverseConstraints,
    BinanceCryptoUniverseConstraints,
    build_binance_crypto_universe_market_cap,
    compute_volatility_24h_pct,
    filter_and_rank_candidates,
)


def test_filter_and_rank_candidates_applies_thresholds_and_sorts():
    df = pd.DataFrame(
        {
            "Symbol": ["BINANCE:AAAUSDC", "BINANCE:AAAUSDT", "BINANCE:BBBUSD"],
            "Type": ["spot", "spot", "spot"],
            "Subtype": ["crypto", "crypto", "crypto"],
            "Price": [100.0, 100.0, 100.0],
            "High": [104.0, 104.0, 120.0],
            "Low": [100.0, 100.0, 119.0],
            "Volatility": [4.0, 4.0, 50.0],
            # USDC has higher volume but should lose to USDT for the same base.
            "Volume 24h in USD": [50_000_000, 20_000_000, 20_000_000],
        }
    )

    out = filter_and_rank_candidates(
        df,
        constraints=BinanceCryptoUniverseConstraints(
            instrument_type="spot",
            top_n=100,
            quote_assets=("USDT", "USDC"),
            min_quote_volume_usd=10_000_000,
        ),
    )

    # BBBUSD fails quote_assets; AAA is deduped and prefers USDT over USDC.
    assert out["Symbol"].tolist() == ["BINANCE:AAAUSDT"]
    assert out["rank"].tolist() == [1]
    assert out["instrument_type"].tolist() == ["spot"]


def test_filter_and_rank_candidates_fills_top_n_when_floor_underfills():
    # Build enough unique bases to satisfy top_n even if a liquidity floor is too strict.
    rows = []
    for i in range(150):
        base = f"COIN{i:03d}"
        rows.append(
            {
                "Symbol": f"BINANCE:{base}USDT",
                "Price": 1.0,
                "High": 1.1,
                "Low": 0.9,
                "Volatility": 10.0,
                "Volume 24h in USD": float(10_000_000 - i * 10_000),
            }
        )
    df = pd.DataFrame(rows)

    out = filter_and_rank_candidates(
        df,
        constraints=BinanceCryptoUniverseConstraints(
            instrument_type="spot",
            top_n=100,
            quote_assets=("USDT",),
            # This floor would underfill if treated as a hard filter.
            min_quote_volume_usd=9_900_000,
        ),
    )

    assert len(out) == 100
    assert out["Symbol"].str.endswith("USDT").all()


def test_compute_volatility_falls_back_to_proxy_when_native_missing():
    df = pd.DataFrame(
        {
            "Price": [100.0, 100.0],
            "High": [104.0, 110.0],
            "Low": [100.0, 100.0],
            "Volatility": [4.0, None],
        }
    )

    vol = compute_volatility_24h_pct(df)
    assert float(vol.iloc[0]) == 4.0
    assert float(vol.iloc[1]) == 10.0


def test_market_cap_universe_filters_volatility_and_sorts_by_volume(monkeypatch):
    # Mock top coins by market cap -> bases A, B
    import pandas as pd

    from tvscreener_ext.universe import binance_crypto as bc

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
                "Name": [t.split(":", 1)[1] for t in tickers],
                "Market Capitalization": [1000] * len(tickers),
                "Volume 24h in USD": [200_000_000] * len(tickers),
                "Volatility": [4.0] * len(tickers),
                "Price": [1.0] * len(tickers),
                "High": [1.0] * len(tickers),
                "Low": [1.0] * len(tickers),
            }
        ),
    )

    tickers, snapshot = build_binance_crypto_universe_market_cap(
        constraints=BinanceCryptoMarketCapUniverseConstraints(
            instrument_type="spot",
            top_n_market_cap=100,
            quote_assets=("USDT", "USDC"),
            min_volatility_24h_pct=0.0,
        )
    )
    assert tickers == ["BINANCE:AUSDT", "BINANCE:BUSDT"]
    assert snapshot["constraints"]["selection"] == "market_cap_top100"
    assert snapshot["market_cap_bases"] == ["A", "B"]


def test_market_cap_universe_falls_back_to_usdc(monkeypatch):
    import pandas as pd

    from tvscreener_ext.universe import binance_crypto as bc

    monkeypatch.setattr(
        bc,
        "fetch_tradingview_top_coins_by_market_cap",
        lambda top_n=100: pd.DataFrame({"Name": ["AUSD"], "Market Cap Calc": [1]}),
    )

    def _fetch(tickers: list[str]) -> pd.DataFrame:
        # Only the USDC market exists.
        present = [t for t in tickers if t.endswith("USDC")]
        return pd.DataFrame(
            {
                "Symbol": present,
                "Name": [t.split(":", 1)[1] for t in present],
                "Volume 24h in USD": [20_000_000],
                "Volatility": [5.0],
                "Price": [1.0],
                "High": [1.0],
                "Low": [1.0],
            }
        )

    monkeypatch.setattr(bc, "fetch_tradingview_crypto_tickers", _fetch)

    tickers, _snapshot = build_binance_crypto_universe_market_cap(
        constraints=BinanceCryptoMarketCapUniverseConstraints(
            instrument_type="spot",
            top_n_market_cap=100,
            quote_assets=("USDT", "USDC"),
        )
    )
    assert tickers == ["BINANCE:AUSDC"]
