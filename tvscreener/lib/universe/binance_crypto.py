from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pandas as pd


@dataclass(frozen=True, slots=True)
class BinanceCryptoUniverseConstraints:
    instrument_type: str  # spot | perp
    top_n: int = 100
    min_quote_volume_usd: float = 10_000_000
    min_volatility_24h_pct: float = 3.0


@dataclass(frozen=True, slots=True)
class BinanceCryptoMarketCapUniverseConstraints:
    instrument_type: str  # spot | perp
    top_n_market_cap: int = 100
    quote_asset: str = "USDT"
    # Raw universe selection is market-cap-driven; filtering is done later in analytics.
    min_volatility_24h_pct: float = 0.0


@dataclass(frozen=True, slots=True)
class BinanceCryptoCSMomentumUniverseConstraints:
    instrument_type: str  # spot | perp
    quote_asset: str = "USDT"
    seed_top_n_market_cap: int = 200
    min_quote_volume_usd: float = 10_000_000
    # Intentionally exclude these bases from the candidate universe
    # before momentum/ROC ranking.
    exclude_bases: tuple[str, ...] = (
        # Stablecoins
        "USDT",
        "USDC",
        "DAI",
        "FDUSD",
        "PYUSD",
        "TUSD",
        "USDP",
        "BUSD",
        "USDE",
        "SUSDE",
        "RLUSD",
        "PAX",
        "PAXG",
        # Wrapped / liquid staking / synthetic bases
        "WBTC",
        "WETH",
        "STETH",
        "WSTETH",
        "WEETH",
        "SDAI",
    )


def _tv_type_for_instrument(instrument_type: str) -> str:
    it = (instrument_type or "").strip().lower()
    if it == "spot":
        return "spot"
    if it in {"perp", "swap"}:
        return "swap"
    raise ValueError(f"Unsupported crypto instrument_type: {instrument_type}")


def compute_volatility_24h_pct(df: pd.DataFrame):
    # Prefer TradingView's native volatility metric when present.
    # `CryptoField.VOLATILITY` maps to `Volatility.D` and is returned as a percent.
    if "Volatility" in df.columns:
        vol = pd.to_numeric(df["Volatility"], errors="coerce")
        return vol if isinstance(vol, pd.Series) else pd.Series(vol, index=df.index)

    # Fallback: derive a deterministic 24h proxy from TradingView high/low/price.
    n = len(df)
    high = (
        pd.to_numeric(df["High"], errors="coerce")
        if "High" in df.columns
        else pd.Series([pd.NA] * n)
    )
    low = (
        pd.to_numeric(df["Low"], errors="coerce") if "Low" in df.columns else pd.Series([pd.NA] * n)
    )
    price = (
        pd.to_numeric(df["Price"], errors="coerce")
        if "Price" in df.columns
        else pd.Series([pd.NA] * n)
    )
    # Type checkers struggle with pandas' operator overloads.
    import numpy as np

    high_series = pd.Series(pd.to_numeric(high, errors="coerce"), index=df.index)
    low_series = pd.Series(pd.to_numeric(low, errors="coerce"), index=df.index)
    price_series = pd.Series(pd.to_numeric(price, errors="coerce"), index=df.index)

    high_arr = np.asarray(high_series, dtype="float64")
    low_arr = np.asarray(low_series, dtype="float64")
    price_arr = np.asarray(price_series, dtype="float64")
    vol_arr = np.where(price_arr != 0, (high_arr - low_arr) / price_arr * 100.0, np.nan)
    return pd.Series(vol_arr, index=df.index)


def filter_and_rank_candidates(
    df: pd.DataFrame, *, constraints: BinanceCryptoUniverseConstraints
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    if "Volume 24h in USD" in out.columns:
        out["quote_volume_usd"] = pd.to_numeric(out["Volume 24h in USD"], errors="coerce")
    else:
        out["quote_volume_usd"] = pd.NA
    out["volatility_24h_pct"] = compute_volatility_24h_pct(out)

    out = out.dropna(subset=["Symbol", "quote_volume_usd", "volatility_24h_pct"])
    out = out.loc[out["quote_volume_usd"] >= float(constraints.min_quote_volume_usd)].copy()
    out = out.loc[out["volatility_24h_pct"] >= float(constraints.min_volatility_24h_pct)].copy()

    out = out.sort_values(["quote_volume_usd", "volatility_24h_pct"], ascending=[False, False])  # type: ignore[call-arg]
    out = out.head(int(constraints.top_n))
    out = out.reset_index(drop=True)
    out["rank"] = out.index + 1

    out["instrument_type"] = (constraints.instrument_type or "").strip().lower()
    out["venue"] = "binance"
    return out


def fetch_tradingview_binance_crypto_candidates(
    *, instrument_type: str, max_rows: int = 5000
) -> pd.DataFrame:
    """Fetch candidate rows from TradingView crypto /scan.

    Uses public TradingView /scan via the existing tvscreener library.
    """

    import tvscreener as tvs
    from tvscreener import CryptoField
    from tvscreener.filter import FilterOperator

    tv_type = _tv_type_for_instrument(instrument_type)

    ss = tvs.CryptoScreener()
    ss.set_range(0, int(max_rows))
    ss.sort_by(CryptoField.VOLUME_24H_IN_USD, ascending=False)

    ss.where(CryptoField.EXCHANGE, FilterOperator.EQUAL, "BINANCE")
    ss.where(CryptoField.TYPE, FilterOperator.EQUAL, tv_type)

    ss.select(
        CryptoField.NAME,
        CryptoField.EXCHANGE,
        CryptoField.TYPE,
        CryptoField.SUBTYPE,
        CryptoField.VOLATILITY,
        CryptoField.PRICE,
        CryptoField.HIGH,
        CryptoField.LOW,
        CryptoField.VOLUME_24H_IN_USD,
    )

    df = ss.get()
    if df is None:
        return pd.DataFrame()
    return df


def fetch_tradingview_top_coins_by_market_cap(*, top_n: int = 100) -> pd.DataFrame:
    """Fetch top coins by market cap using TradingView coin /scan.

    Uses `CoinScreener` with `CoinField.MARKET_CAP_CALC` which is populated for
    major coins.
    """

    import tvscreener as tvs
    from tvscreener import CoinField

    ss = tvs.CoinScreener()
    ss.set_range(0, int(top_n))
    ss.sort_by(CoinField.MARKET_CAP_CALC, ascending=False)
    ss.select(CoinField.NAME, CoinField.MARKET_CAP_CALC)
    df = ss.get()
    return pd.DataFrame() if df is None else df


def _base_from_coin_name(name: str) -> str | None:
    raw = (name or "").strip().upper()
    # CoinScreener returns names like BTCUSD.
    if raw.endswith("USD") and len(raw) > 3:
        return raw[: -len("USD")]
    return None


def base_from_symbol(*, symbol: str, quote_asset: str) -> str | None:
    sym = (symbol or "").strip().upper()
    quote_asset = (quote_asset or "").strip().upper()
    if not sym or not quote_asset:
        return None
    if not sym.endswith(quote_asset):
        return None
    base = sym[: -len(quote_asset)]
    return base or None


def _ticker_for_base(*, base: str, quote_asset: str, instrument_type: str) -> str:
    base = (base or "").strip().upper()
    quote_asset = (quote_asset or "").strip().upper()
    if instrument_type == "spot":
        return f"BINANCE:{base}{quote_asset}"
    if instrument_type == "perp":
        return f"BINANCE:{base}{quote_asset}.P"
    raise ValueError(f"Unsupported instrument_type: {instrument_type}")


def fetch_tradingview_crypto_tickers(tickers: list[str]) -> pd.DataFrame:
    """Fetch TradingView crypto rows for an explicit ticker list."""

    if not tickers:
        return pd.DataFrame()

    import tvscreener as tvs
    from tvscreener import CryptoField

    ss = tvs.CryptoScreener()
    ss.set_tickers(*tickers)
    ss.set_range(0, len(tickers))
    ss.select(
        CryptoField.NAME,
        CryptoField.EXCHANGE,
        CryptoField.TYPE,
        CryptoField.SUBTYPE,
        CryptoField.MARKET_CAPITALIZATION,
        CryptoField.VOLATILITY,
        CryptoField.PRICE,
        CryptoField.HIGH,
        CryptoField.LOW,
        CryptoField.VOLUME_24H_IN_USD,
    )
    df = ss.get()
    return pd.DataFrame() if df is None else df


def symbol_from_ticker(ticker: str) -> str:
    raw = (ticker or "").strip()
    if ":" in raw:
        raw = raw.split(":", 1)[1]
    if raw.endswith(".P"):
        raw = raw[: -len(".P")]
    return raw


def entity_id_for(*, ticker: str, instrument_type: str) -> str:
    instrument_type = (instrument_type or "").strip().lower()
    return f"binance:{instrument_type}:{symbol_from_ticker(ticker)}"


def build_binance_crypto_universe_market_cap(
    *, constraints: BinanceCryptoMarketCapUniverseConstraints
) -> tuple[list[str], dict]:
    coins = fetch_tradingview_top_coins_by_market_cap(top_n=constraints.top_n_market_cap)
    bases: list[str] = []
    if not coins.empty and "Name" in coins.columns:
        for n in coins["Name"].dropna().astype(str).tolist():
            b = _base_from_coin_name(n)
            if b:
                bases.append(b)
    # Stable order (market cap rank order), de-duped.
    bases = list(dict.fromkeys(bases))

    tickers = [
        _ticker_for_base(
            base=b,
            quote_asset=constraints.quote_asset,
            instrument_type=constraints.instrument_type,
        )
        for b in bases
    ]

    candidates = fetch_tradingview_crypto_tickers(tickers)
    if candidates.empty:
        out_tickers: list[str] = []
        ordered = candidates
        missing = tickers
    else:
        returned = (
            candidates["Symbol"].dropna().astype(str).tolist()
            if "Symbol" in candidates.columns
            else []
        )
        returned_set = set(returned)
        out_tickers = [t for t in tickers if t in returned_set]
        missing = [t for t in tickers if t not in returned_set]

        # Preserve market-cap rank order; do not filter/sort here.
        ordered = candidates.copy()
        if "Symbol" in ordered.columns:
            ordered["_order"] = (
                ordered["Symbol"]
                .astype(str)
                .map(lambda s: out_tickers.index(s) if s in out_tickers else 10**9)
            )
            ordered = ordered.sort_values(["_order"]).drop(columns=["_order"])

    # Best-effort metrics for later analytics filtering.
    if "Volume 24h in USD" in ordered.columns:
        ordered["quote_volume_usd"] = pd.to_numeric(ordered["Volume 24h in USD"], errors="coerce")
    if "Volatility" in ordered.columns or "High" in ordered.columns:
        ordered["volatility_24h_pct"] = compute_volatility_24h_pct(ordered)
    snapshot = {
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "constraints": {
            "venue": "binance",
            "selection": "market_cap_top100",
            "instrument_type": constraints.instrument_type,
            "quote_asset": constraints.quote_asset,
            "top_n_market_cap": constraints.top_n_market_cap,
            "min_volatility_24h_pct": constraints.min_volatility_24h_pct,
            "filters_applied": False,
            "sort": "market_cap_rank",
        },
        "market_cap_bases": bases,
        "requested_tickers": tickers,
        "missing_tickers": missing,
        "count": len(out_tickers),
        "rows": (
            [
                {
                    "ticker": str(row.get("Symbol")),
                    "symbol": symbol_from_ticker(str(row.get("Symbol"))),
                    "venue": "binance",
                    "instrument_type": (constraints.instrument_type or "").strip().lower(),
                    "entity_id": entity_id_for(
                        ticker=str(row.get("Symbol")),
                        instrument_type=(constraints.instrument_type or "").strip().lower(),
                    ),
                    "market_cap_usd": row.get("Market Capitalization"),
                    "quote_volume_usd": row.get("quote_volume_usd"),
                    "volatility_24h_pct": row.get("volatility_24h_pct"),
                }
                for row in cast(list[dict[str, Any]], ordered.to_dict(orient="records"))
            ]
            if not ordered.empty
            else []
        ),
    }
    return out_tickers, snapshot


def build_binance_crypto_universe_cs_momentum(
    *, constraints: BinanceCryptoCSMomentumUniverseConstraints
) -> tuple[list[str], dict]:
    """Build a candidate universe for cross-sectional momentum trading.

    This universe is meant to be *tradeable* and *liquid* before applying
    momentum/ROC ranking in analytics.
    """

    coins = fetch_tradingview_top_coins_by_market_cap(top_n=constraints.seed_top_n_market_cap)
    bases: list[str] = []
    if not coins.empty and "Name" in coins.columns:
        for n in coins["Name"].dropna().astype(str).tolist():
            b = _base_from_coin_name(n)
            if b:
                bases.append(b)
    bases = list(dict.fromkeys(bases))

    # Exclude stable/wrapped bases early.
    excluded_bases = {b.strip().upper() for b in constraints.exclude_bases}
    bases_filtered = [b for b in bases if b not in excluded_bases]

    requested = [
        _ticker_for_base(
            base=b,
            quote_asset=constraints.quote_asset,
            instrument_type=constraints.instrument_type,
        )
        for b in bases_filtered
    ]

    candidates = fetch_tradingview_crypto_tickers(requested)
    if candidates.empty:
        tickers: list[str] = []
        missing = requested
        ordered = candidates
    else:
        returned = (
            candidates["Symbol"].dropna().astype(str).tolist()
            if "Symbol" in candidates.columns
            else []
        )
        returned_set = set(returned)
        missing = [t for t in requested if t not in returned_set]

        ordered = candidates.copy()
        if "Volume 24h in USD" in ordered.columns:
            ordered["quote_volume_usd"] = pd.to_numeric(
                ordered["Volume 24h in USD"], errors="coerce"
            )
        else:
            ordered["quote_volume_usd"] = pd.NA
        ordered["volatility_24h_pct"] = compute_volatility_24h_pct(ordered)

        # Liquidity gate only (not a momentum filter).
        ordered = ordered.dropna(subset=["Symbol", "quote_volume_usd"]).copy()
        ordered = ordered.loc[
            ordered["quote_volume_usd"] >= float(constraints.min_quote_volume_usd)
        ].copy()

        # Sort by trading value (USD) so downstream analytics starts from the most liquid.
        ordered = ordered.sort_values(["quote_volume_usd"], ascending=[False])
        tickers = (
            ordered["Symbol"].dropna().astype(str).tolist() if "Symbol" in ordered.columns else []
        )

    instrument_type = (constraints.instrument_type or "").strip().lower()
    snapshot = {
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "constraints": {
            "venue": "binance",
            "selection": "cs_momentum_candidates",
            "instrument_type": instrument_type,
            "quote_asset": constraints.quote_asset,
            "seed_top_n_market_cap": constraints.seed_top_n_market_cap,
            "min_quote_volume_usd": constraints.min_quote_volume_usd,
            "exclude_bases": list(constraints.exclude_bases),
            "sort": "quote_volume_usd_desc",
        },
        "market_cap_bases": bases,
        "bases_after_exclusions": bases_filtered,
        "requested_tickers": requested,
        "missing_tickers": missing,
        "count": len(tickers),
        "rows": (
            [
                {
                    "ticker": str(row.get("Symbol")),
                    "symbol": symbol_from_ticker(str(row.get("Symbol"))),
                    "base": base_from_symbol(
                        symbol=symbol_from_ticker(str(row.get("Symbol"))),
                        quote_asset=constraints.quote_asset,
                    ),
                    "venue": "binance",
                    "instrument_type": instrument_type,
                    "entity_id": entity_id_for(
                        ticker=str(row.get("Symbol")), instrument_type=instrument_type
                    ),
                    "quote_volume_usd": row.get("quote_volume_usd"),
                    "volatility_24h_pct": row.get("volatility_24h_pct"),
                }
                for row in cast(list[dict[str, Any]], ordered.to_dict(orient="records"))
            ]
            if not ordered.empty
            else []
        ),
    }
    return tickers, snapshot


def build_binance_crypto_universe(
    *, constraints: BinanceCryptoUniverseConstraints
) -> tuple[list[str], dict]:
    candidates = fetch_tradingview_binance_crypto_candidates(
        instrument_type=constraints.instrument_type
    )
    ranked = filter_and_rank_candidates(candidates, constraints=constraints)

    tickers = ranked["Symbol"].astype(str).tolist() if not ranked.empty else []

    instrument_type = (constraints.instrument_type or "").strip().lower()

    snapshot = {
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "constraints": {
            "venue": "binance",
            "instrument_type": constraints.instrument_type,
            "top_n": constraints.top_n,
            "min_quote_volume_usd": constraints.min_quote_volume_usd,
            "min_volatility_24h_pct": constraints.min_volatility_24h_pct,
        },
        "count": len(tickers),
        "rows": (
            [
                {
                    "rank": int(row.get("rank") or 0),
                    "ticker": str(row.get("Symbol")),
                    "symbol": symbol_from_ticker(str(row.get("Symbol"))),
                    "venue": "binance",
                    "instrument_type": instrument_type,
                    "entity_id": entity_id_for(
                        ticker=str(row.get("Symbol")), instrument_type=instrument_type
                    ),
                    "Name": row.get("Name"),
                    "Type": row.get("Type"),
                    "Subtype": row.get("Subtype"),
                    "quote_volume_usd": row.get("quote_volume_usd"),
                    "volatility_24h_pct": row.get("volatility_24h_pct"),
                }
                for row in cast(list[dict[str, Any]], ranked.to_dict(orient="records"))
            ]
            if not ranked.empty
            else []
        ),
    }
    return tickers, snapshot


def maybe_write_universe_json(snapshot: dict, *, run_dir: str | None) -> str | None:
    if not run_dir:
        return None
    path = Path(run_dir) / "universe.json"
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)
