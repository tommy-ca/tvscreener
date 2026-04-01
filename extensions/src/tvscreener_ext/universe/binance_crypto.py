from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pandas as pd

DEFAULT_EXCLUDE_BASES: tuple[str, ...] = (
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


@dataclass(frozen=True, slots=True)
class BinanceCryptoUniverseConstraints:
    instrument_type: str  # spot | perp
    top_n: int = 100
    quote_assets: tuple[str, ...] = ("USDT", "USDC")
    exclude_bases: tuple[str, ...] = DEFAULT_EXCLUDE_BASES
    min_quote_volume_usd: float = 10_000_000
    # Volatility is persisted for later analytics filtering/ranking; do not
    # use it as a hard selection constraint for base universes.
    min_volatility_24h_pct: float = 0.0


@dataclass(frozen=True, slots=True)
class BinanceCryptoMarketCapUniverseConstraints:
    instrument_type: str  # spot | perp
    top_n_market_cap: int = 100
    quote_assets: tuple[str, ...] = ("USDT", "USDC")
    # Raw universe selection is market-cap-driven; filtering is done later in analytics.
    min_volatility_24h_pct: float = 0.0


@dataclass(frozen=True, slots=True)
class BinanceCryptoCSMomentumUniverseConstraints:
    instrument_type: str  # spot | perp
    quote_assets: tuple[str, ...] = ("USDT", "USDC")
    seed_top_n_market_cap: int = 200
    min_quote_volume_usd: float = 10_000_000
    # Intentionally exclude these bases from the candidate universe
    # before momentum/ROC ranking.
    exclude_bases: tuple[str, ...] = DEFAULT_EXCLUDE_BASES


@dataclass(frozen=True, slots=True)
class BinanceCryptoTradeableBaseUniverseConstraints:
    instrument_type: str  # spot | perp
    top_n: int = 200
    quote_assets: tuple[str, ...] = ("USDT", "USDC")
    min_quote_volume_usd: float = 10_000_000
    # If a base is not in the market-cap top100 list and its TradingView history
    # is shorter than this threshold (in days), treat it as risky and exclude.
    min_history_days_non_mcap: int = 180
    # Exclude stablecoin bases and wrappers to focus on tradeable underlyings.
    exclude_bases: tuple[str, ...] = DEFAULT_EXCLUDE_BASES


@dataclass(frozen=True, slots=True)
class BinanceCryptoTradeableMcapOverlapUniverseConstraints:
    instrument_type: str  # spot | perp
    top_n_market_cap: int = 100
    top_n: int = 100
    quote_assets: tuple[str, ...] = ("USDT", "USDC")
    # Defaults aligned with tradeable base parity tuning.
    min_quote_volume_usd_spot: float = 2_500_000
    min_quote_volume_usd_perp: float = 20_000_000
    exclude_bases: tuple[str, ...] = DEFAULT_EXCLUDE_BASES


@dataclass(frozen=True, slots=True)
class BinanceCryptoMcapTierUniverseConstraints:
    instrument_type: str  # spot | perp
    # Pull this many bases from CoinScreener market-cap list.
    top_n_market_cap: int = 200
    # 1-indexed inclusive range within the market-cap list.
    mcap_rank_min: int = 1
    mcap_rank_max: int = 20
    quote_assets: tuple[str, ...] = ("USDT", "USDC")
    # Liquidity floors aligned with tradeable base parity tuning.
    min_quote_volume_usd_spot: float = 2_500_000
    min_quote_volume_usd_perp: float = 20_000_000
    # Require some history even for market-cap tiers.
    min_history_days: int = 180
    exclude_bases: tuple[str, ...] = DEFAULT_EXCLUDE_BASES


def _tv_type_for_instrument(instrument_type: str) -> str:
    it = (instrument_type or "").strip().lower()
    if it == "spot":
        return "spot"
    if it in {"perp", "swap"}:
        return "swap"
    raise ValueError(f"Unsupported crypto instrument_type: {instrument_type}")


def _compute_proxy_volatility_24h_pct(df: pd.DataFrame) -> pd.Series:
    """Deterministic proxy for 24h volatility, in percent."""

    n = len(df)
    import numpy as np

    nan_series = pd.Series([np.nan] * n, index=df.index, dtype="float64")
    high = pd.to_numeric(df["High"], errors="coerce") if "High" in df.columns else nan_series
    low = pd.to_numeric(df["Low"], errors="coerce") if "Low" in df.columns else nan_series
    price = pd.to_numeric(df["Price"], errors="coerce") if "Price" in df.columns else nan_series

    vol = (high - low) / price * 100.0
    if isinstance(vol, pd.Series):
        vol = vol.where(price != 0)
        return pd.Series(vol, index=df.index)
    return pd.Series([np.nan] * n, index=df.index)


def compute_volatility_24h_pct(df: pd.DataFrame) -> pd.Series:
    """Compute a per-row 24h volatility percent.

    Prefers TradingView's native volatility metric when present.
    Falls back per-row to a high/low/price proxy when native volatility is missing.
    """

    proxy = _compute_proxy_volatility_24h_pct(df)
    if "Volatility" not in df.columns:
        return proxy

    # `CryptoField.VOLATILITY` maps to `Volatility.D` and is returned as a percent.
    native = pd.to_numeric(df["Volatility"], errors="coerce")
    native_series = native if isinstance(native, pd.Series) else pd.Series(native, index=df.index)
    return native_series.fillna(proxy)


def compute_history_days(df: pd.DataFrame) -> pd.Series:
    """Compute an approximate available-history length in days.

    Prefers TradingView's `First Bar Time` and `Last Bar Update Time` when present.
    Values appear as Unix epoch timestamps (ms or s).
    """

    n = len(df)
    first_col = "First Bar Time" if "First Bar Time" in df.columns else None
    last_col = "Last Bar Update Time" if "Last Bar Update Time" in df.columns else None
    if not first_col or not last_col:
        return pd.Series([pd.NA] * n, index=df.index)

    first = pd.to_numeric(df[first_col], errors="coerce")
    last = pd.to_numeric(df[last_col], errors="coerce")

    # Heuristic: treat large values as milliseconds.
    first_num = pd.Series(first, index=df.index)
    last_num = pd.Series(last, index=df.index)
    scale = 1000.0 if (first_num.max(skipna=True) or 0) > 1e11 else 1.0

    seconds = (last_num / scale) - (first_num / scale)
    days = seconds / 86400.0
    return days


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

    quote_assets = tuple(
        (q or "").strip().upper() for q in constraints.quote_assets if (q or "").strip()
    )
    if not quote_assets:
        quote_assets = ("USDT",)

    sym = out["Symbol"].astype(str)
    sym_clean = sym.str.replace(".P", "", regex=False)
    sym_clean = sym_clean.str.split(":", n=1).str[-1]
    out["_symbol_clean"] = sym_clean

    def _match_quote(s: str) -> str | None:
        for q in quote_assets:
            if s.endswith(q):
                return q
        return None

    out["quote_asset"] = out["_symbol_clean"].map(_match_quote)
    out = out.dropna(subset=["quote_asset"]).copy()
    out["base"] = pd.NA
    for q in quote_assets:
        mask = out["quote_asset"] == q
        if mask.any():
            out.loc[mask, "base"] = out.loc[mask, "_symbol_clean"].astype(str).str[: -len(q)]

    # Base universes should focus on liquidity + tradability. Persist volatility
    # for downstream analytics, but do not hard-filter on it at selection time.
    out = out.dropna(subset=["Symbol", "quote_volume_usd", "base", "volatility_24h_pct"]).copy()

    exclude_bases = {b.strip().upper() for b in constraints.exclude_bases}
    out = out.loc[~out["base"].astype(str).str.upper().isin(exclude_bases)].copy()

    # Liquidity floor is a tradeable-universe concern. For top-by-volume snapshot universes
    # (`*_top100`) we treat `min_quote_volume_usd` as a soft hint: filter when possible, but
    # if it underfills `top_n` we fall back to ranking without the floor.
    out_all = out
    min_volume_floor = float(constraints.min_quote_volume_usd)
    if min_volume_floor > 0:
        out = out.loc[out["quote_volume_usd"] >= min_volume_floor].copy()

    # Dedup: pick one ticker per base, prefer the first quote asset.
    quote_preference = {q: i for i, q in enumerate(quote_assets)}
    out["_quote_pref"] = out["quote_asset"].astype(str).map(lambda q: quote_preference.get(q, 999))
    out = out.sort_values(
        ["_quote_pref", "quote_volume_usd"],
        ascending=[True, False],
    )  # type: ignore[call-arg]
    out = out.drop_duplicates(subset=["base"], keep="first").copy()

    if min_volume_floor > 0 and len(out) < int(constraints.top_n):
        out = out_all.copy()
        out["_quote_pref"] = (
            out["quote_asset"].astype(str).map(lambda q: quote_preference.get(q, 999))
        )
        out = out.sort_values(
            ["_quote_pref", "quote_volume_usd"],
            ascending=[True, False],
        )  # type: ignore[call-arg]
        out = out.drop_duplicates(subset=["base"], keep="first").copy()

    # Final ranking: highest USD quote volume.
    out = out.sort_values(["quote_volume_usd"], ascending=[False])  # type: ignore[call-arg]
    out = out.head(int(constraints.top_n))
    out = out.reset_index(drop=True)
    out["rank"] = out.index + 1

    out["instrument_type"] = (constraints.instrument_type or "").strip().lower()
    out["venue"] = "binance"
    return out


def build_binance_crypto_universe_tradeable_base(
    *, constraints: BinanceCryptoTradeableBaseUniverseConstraints
) -> tuple[list[str], dict]:
    """Tradeable-first base universe.

    Goal: produce a liquid, strategy-ready ticker set with minimal surprises.
    - Binance only
    - Spot or perp
    - Quote assets limited to a small allowlist (default USDT/USDC)
    - Exclude stable/wrapped bases
    - Liquidity gate only
    """

    candidates = fetch_tradingview_binance_crypto_candidates(
        instrument_type=constraints.instrument_type
    )
    if candidates.empty:
        snapshot = {
            "generated_at_utc": datetime.now(tz=UTC).isoformat(),
            "constraints": {
                "venue": "binance",
                "selection": "tradeable_base",
                "instrument_type": constraints.instrument_type,
                "top_n": constraints.top_n,
                "quote_assets": list(constraints.quote_assets),
                "min_quote_volume_usd": constraints.min_quote_volume_usd,
                "exclude_bases": list(constraints.exclude_bases),
            },
            "count": 0,
            "requested_tickers": [],
            "missing_tickers": [],
            "included_bases": [],
            "missing_bases": [],
            "rows": [],
        }
        return [], snapshot

    df = candidates.copy()

    # Restrict to quote assets. Compute base and drop excluded bases.
    quote_assets = tuple(
        (q or "").strip().upper() for q in constraints.quote_assets if (q or "").strip()
    )
    if not quote_assets:
        quote_assets = ("USDT",)

    sym = df["Symbol"].astype(str)
    sym_clean = sym.str.replace(".P", "", regex=False)
    sym_clean = sym_clean.str.split(":", n=1).str[-1]
    df["_symbol_clean"] = sym_clean

    def _match_quote(s: str) -> str | None:
        for q in quote_assets:
            if s.endswith(q):
                return q
        return None

    df["quote_asset"] = df["_symbol_clean"].map(_match_quote)
    df = df.dropna(subset=["quote_asset"]).copy()

    symbols = df["_symbol_clean"].astype(str).tolist()
    quotes = df["quote_asset"].astype(str).tolist()
    df["base"] = [
        base_from_symbol(symbol=s, quote_asset=q) for s, q in zip(symbols, quotes, strict=True)
    ]
    df = df.dropna(subset=["base"]).copy()

    excluded_bases = {b.strip().upper() for b in constraints.exclude_bases}
    df = df.loc[~df["base"].astype(str).str.upper().isin(excluded_bases)].copy()

    df["quote_volume_usd"] = pd.to_numeric(df.get("Volume 24h in USD"), errors="coerce")
    df["volatility_24h_pct"] = compute_volatility_24h_pct(df)
    df["history_days"] = compute_history_days(df)
    df = df.dropna(subset=["Symbol", "quote_volume_usd"]).copy()
    df = df.loc[df["quote_volume_usd"] >= float(constraints.min_quote_volume_usd)].copy()

    # Risk filter: exclude short-history bases that are not in market-cap top100.
    excluded_risky: list[dict[str, Any]] = []
    min_hist = int(constraints.min_history_days_non_mcap or 0)
    if min_hist > 0:
        try:
            coins = fetch_tradingview_top_coins_by_market_cap(top_n=100)
            mcap_bases: set[str] = set()
            if not coins.empty and "Name" in coins.columns:
                for n in coins["Name"].dropna().astype(str).tolist():
                    b = _base_from_coin_name(n)
                    if b:
                        mcap_bases.add(b)
        except Exception:
            mcap_bases = set()

        if mcap_bases:
            import numpy as np

            hist_arr = pd.to_numeric(df["history_days"], errors="coerce").to_numpy(dtype="float64")
            hist_lt = pd.Series(np.less(hist_arr, float(min_hist)), index=df.index)
            risky_mask = (~df["base"].astype(str).str.upper().isin(mcap_bases)) & (hist_lt)
            if risky_mask.any():
                excluded_risky = (
                    df.loc[
                        risky_mask,
                        [
                            "Symbol",
                            "base",
                            "quote_asset",
                            "quote_volume_usd",
                            "volatility_24h_pct",
                            "history_days",
                        ],
                    ]
                    .sort_values(["quote_volume_usd"], ascending=[False])
                    .head(250)
                    .to_dict(orient="records")
                )
                df = df.loc[~risky_mask].copy()

    returned_set = set(df["Symbol"].dropna().astype(str).tolist())

    # Pick one ticker per base, preferring first quote asset.
    picked: list[str] = []
    included_bases: list[str] = []
    missing_bases: list[str] = []
    prefer_q = quote_assets[0] if quote_assets else None

    for base in df["base"].astype(str).str.upper().drop_duplicates().tolist():
        ticker = _pick_ticker_for_base(
            base=base,
            instrument_type=constraints.instrument_type,
            quote_assets=quote_assets,
            returned=returned_set,
            prefer_quote_asset=prefer_q,
        )
        if ticker:
            picked.append(ticker)
            included_bases.append(base)
        else:
            missing_bases.append(base)

    df = df.loc[df["Symbol"].astype(str).isin(picked)].copy()
    df = df.sort_values(["quote_volume_usd"], ascending=[False]).head(int(constraints.top_n))

    tickers = df["Symbol"].astype(str).tolist()
    instrument_type = (constraints.instrument_type or "").strip().lower()

    snapshot = {
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "constraints": {
            "venue": "binance",
            "selection": "tradeable_base",
            "instrument_type": instrument_type,
            "top_n": constraints.top_n,
            "quote_assets": list(quote_assets),
            "min_quote_volume_usd": constraints.min_quote_volume_usd,
            "min_history_days_non_mcap": constraints.min_history_days_non_mcap,
            "exclude_bases": list(constraints.exclude_bases),
            "sort": "quote_volume_usd_desc",
        },
        "requested_tickers": sorted(returned_set),
        "missing_tickers": [],
        "included_bases": included_bases,
        "missing_bases": missing_bases,
        "count": len(tickers),
        "excluded_risky": excluded_risky,
        "rows": (
            [
                {
                    "ticker": str(row.get("Symbol")),
                    "symbol": symbol_from_ticker(str(row.get("Symbol"))),
                    "base": str(row.get("base")),
                    "quote_asset": str(row.get("quote_asset")),
                    "venue": "binance",
                    "instrument_type": instrument_type,
                    "entity_id": entity_id_for(
                        ticker=str(row.get("Symbol")), instrument_type=instrument_type
                    ),
                    "quote_volume_usd": row.get("quote_volume_usd"),
                    "volatility_24h_pct": row.get("volatility_24h_pct"),
                    "history_days": row.get("history_days"),
                }
                for row in cast(list[dict[str, Any]], df.to_dict(orient="records"))
            ]
            if not df.empty
            else []
        ),
    }

    return tickers, snapshot


def build_binance_crypto_universe_tradeable_mcap_overlap(
    *, constraints: BinanceCryptoTradeableMcapOverlapUniverseConstraints
) -> tuple[list[str], dict]:
    """Tradeable base restricted to market-cap top-N bases.

    This yields a cross-sectional universe that is:
    - market-cap anchored (via CoinScreener)
    - Binance-listed and liquid (via tradeable-base gates)
    """

    # 1) Get market-cap bases (broad) and keep order.
    coins = fetch_tradingview_top_coins_by_market_cap(top_n=constraints.top_n_market_cap)
    bases: list[str] = []
    if not coins.empty and "Name" in coins.columns:
        for n in coins["Name"].dropna().astype(str).tolist():
            b = _base_from_coin_name(n)
            if b:
                bases.append(b)
    bases = list(dict.fromkeys(bases))

    excluded_bases = {b.strip().upper() for b in constraints.exclude_bases}
    bases = [b for b in bases if b.strip().upper() not in excluded_bases]

    # 2) Fetch Binance candidates via TradingView crypto /scan (already filtered to BINANCE+type).
    candidates = fetch_tradingview_binance_crypto_candidates(
        instrument_type=constraints.instrument_type
    )
    if candidates.empty:
        snapshot = {
            "generated_at_utc": datetime.now(tz=UTC).isoformat(),
            "constraints": {
                "venue": "binance",
                "selection": "tradeable_mcap_overlap",
                "instrument_type": constraints.instrument_type,
                "top_n_market_cap": constraints.top_n_market_cap,
                "top_n": constraints.top_n,
                "quote_assets": list(constraints.quote_assets),
                "exclude_bases": list(constraints.exclude_bases),
            },
            "market_cap_bases": bases,
            "included_bases": [],
            "missing_bases": bases,
            "requested_tickers": [],
            "missing_tickers": [],
            "count": 0,
            "rows": [],
        }
        return [], snapshot

    df = candidates.copy()

    quote_assets = tuple(
        (q or "").strip().upper() for q in constraints.quote_assets if (q or "").strip()
    )
    if not quote_assets:
        quote_assets = ("USDT",)

    sym = df["Symbol"].astype(str)
    sym_clean = sym.str.replace(".P", "", regex=False)
    sym_clean = sym_clean.str.split(":", n=1).str[-1]
    df["_symbol_clean"] = sym_clean

    def _match_quote(s: str) -> str | None:
        for q in quote_assets:
            if s.endswith(q):
                return q
        return None

    df["quote_asset"] = df["_symbol_clean"].map(_match_quote)
    df = df.dropna(subset=["quote_asset"]).copy()
    symbols = df["_symbol_clean"].astype(str).tolist()
    quotes = df["quote_asset"].astype(str).tolist()
    df["base"] = [
        base_from_symbol(symbol=s, quote_asset=q) for s, q in zip(symbols, quotes, strict=True)
    ]
    df = df.dropna(subset=["base"]).copy()

    # Restrict to market-cap bases.
    mcap_set = {b.strip().upper() for b in bases}
    df = df.loc[df["base"].astype(str).str.upper().isin(mcap_set)].copy()

    # Liquidity gate.
    df["quote_volume_usd"] = pd.to_numeric(df.get("Volume 24h in USD"), errors="coerce")
    df["volatility_24h_pct"] = compute_volatility_24h_pct(df)
    df = df.dropna(subset=["Symbol", "quote_volume_usd"]).copy()
    floor = (
        float(constraints.min_quote_volume_usd_spot)
        if (constraints.instrument_type or "").strip().lower() == "spot"
        else float(constraints.min_quote_volume_usd_perp)
    )
    df = df.loc[df["quote_volume_usd"] >= floor].copy()

    returned_set = set(df["Symbol"].dropna().astype(str).tolist())

    # Pick one per base, preserving market-cap base order.
    picked: list[str] = []
    included_bases: list[str] = []
    missing_bases: list[str] = []
    prefer_q = quote_assets[0] if quote_assets else None

    for b in bases:
        ticker = _pick_ticker_for_base(
            base=b,
            instrument_type=constraints.instrument_type,
            quote_assets=quote_assets,
            returned=returned_set,
            prefer_quote_asset=prefer_q,
        )
        if ticker:
            picked.append(ticker)
            included_bases.append(b)
        else:
            missing_bases.append(b)

    df = df.loc[df["Symbol"].astype(str).isin(picked)].copy()
    df = df.sort_values(["quote_volume_usd"], ascending=[False]).head(int(constraints.top_n))

    tickers = df["Symbol"].astype(str).tolist()
    instrument_type = (constraints.instrument_type or "").strip().lower()
    snapshot = {
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "constraints": {
            "venue": "binance",
            "selection": "tradeable_mcap_overlap",
            "instrument_type": instrument_type,
            "top_n_market_cap": constraints.top_n_market_cap,
            "top_n": constraints.top_n,
            "quote_assets": list(quote_assets),
            "min_quote_volume_usd": floor,
            "exclude_bases": list(constraints.exclude_bases),
            "sort": "quote_volume_usd_desc",
        },
        "market_cap_bases": bases,
        "included_bases": included_bases,
        "missing_bases": missing_bases,
        "requested_tickers": sorted(returned_set),
        "missing_tickers": [],
        "count": len(tickers),
        "rows": (
            [
                {
                    "ticker": str(row.get("Symbol")),
                    "symbol": symbol_from_ticker(str(row.get("Symbol"))),
                    "base": str(row.get("base")),
                    "quote_asset": str(row.get("quote_asset")),
                    "venue": "binance",
                    "instrument_type": instrument_type,
                    "entity_id": entity_id_for(
                        ticker=str(row.get("Symbol")), instrument_type=instrument_type
                    ),
                    "quote_volume_usd": row.get("quote_volume_usd"),
                    "volatility_24h_pct": row.get("volatility_24h_pct"),
                }
                for row in cast(list[dict[str, Any]], df.to_dict(orient="records"))
            ]
            if not df.empty
            else []
        ),
    }

    return tickers, snapshot


def build_binance_crypto_universe_mcap_tier(
    *, constraints: BinanceCryptoMcapTierUniverseConstraints
) -> tuple[list[str], dict]:
    """Market-cap tier universe intersected with tradeable gates.

    This is the building block for "majors" / "minors" style selectors.
    """

    coins = fetch_tradingview_top_coins_by_market_cap(top_n=constraints.top_n_market_cap)
    bases_all: list[str] = []
    if not coins.empty and "Name" in coins.columns:
        for n in coins["Name"].dropna().astype(str).tolist():
            b = _base_from_coin_name(n)
            if b:
                bases_all.append(b)
    bases_all = list(dict.fromkeys(bases_all))

    excluded_bases = {b.strip().upper() for b in constraints.exclude_bases}
    bases_all = [b for b in bases_all if b.strip().upper() not in excluded_bases]

    rmin = max(1, int(constraints.mcap_rank_min))
    rmax = max(rmin, int(constraints.mcap_rank_max))
    bases = bases_all[rmin - 1 : rmax]

    candidates = fetch_tradingview_binance_crypto_candidates(
        instrument_type=constraints.instrument_type
    )
    if candidates.empty:
        snapshot = {
            "generated_at_utc": datetime.now(tz=UTC).isoformat(),
            "constraints": {
                "venue": "binance",
                "selection": "tradeable_mcap_tier",
                "tier": "custom",
                "instrument_type": constraints.instrument_type,
                "top_n_market_cap": constraints.top_n_market_cap,
                "mcap_rank_min": rmin,
                "mcap_rank_max": rmax,
                "quote_assets": list(constraints.quote_assets),
                "exclude_bases": list(constraints.exclude_bases),
                "min_history_days": constraints.min_history_days,
            },
            "market_cap_bases": bases,
            "included_bases": [],
            "missing_bases": bases,
            "requested_tickers": [],
            "missing_tickers": [],
            "count": 0,
            "rows": [],
        }
        return [], snapshot

    df = candidates.copy()

    quote_assets = tuple(
        (q or "").strip().upper() for q in constraints.quote_assets if (q or "").strip()
    )
    if not quote_assets:
        quote_assets = ("USDT",)

    sym = df["Symbol"].astype(str)
    sym_clean = sym.str.replace(".P", "", regex=False)
    sym_clean = sym_clean.str.split(":", n=1).str[-1]
    df["_symbol_clean"] = sym_clean

    def _match_quote(s: str) -> str | None:
        for q in quote_assets:
            if s.endswith(q):
                return q
        return None

    df["quote_asset"] = df["_symbol_clean"].map(_match_quote)
    df = df.dropna(subset=["quote_asset"]).copy()
    symbols = df["_symbol_clean"].astype(str).tolist()
    quotes = df["quote_asset"].astype(str).tolist()
    df["base"] = [
        base_from_symbol(symbol=s, quote_asset=q) for s, q in zip(symbols, quotes, strict=True)
    ]
    df = df.dropna(subset=["base"]).copy()

    mcap_set = {b.strip().upper() for b in bases}
    df = df.loc[df["base"].astype(str).str.upper().isin(mcap_set)].copy()

    df["quote_volume_usd"] = pd.to_numeric(df.get("Volume 24h in USD"), errors="coerce")
    df["volatility_24h_pct"] = compute_volatility_24h_pct(df)
    df["history_days"] = compute_history_days(df)

    df = df.dropna(subset=["Symbol", "quote_volume_usd"]).copy()
    floor = (
        float(constraints.min_quote_volume_usd_spot)
        if (constraints.instrument_type or "").strip().lower() == "spot"
        else float(constraints.min_quote_volume_usd_perp)
    )
    df = df.loc[df["quote_volume_usd"] >= floor].copy()

    min_hist = int(constraints.min_history_days or 0)
    if min_hist > 0:
        hist = pd.to_numeric(df["history_days"], errors="coerce")
        df = df.loc[hist.isna() | (hist >= float(min_hist))].copy()

    returned_set = set(df["Symbol"].dropna().astype(str).tolist())
    prefer_q = quote_assets[0] if quote_assets else None

    picked: list[str] = []
    included_bases: list[str] = []
    missing_bases: list[str] = []
    for b in bases:
        ticker = _pick_ticker_for_base(
            base=b,
            instrument_type=constraints.instrument_type,
            quote_assets=quote_assets,
            returned=returned_set,
            prefer_quote_asset=prefer_q,
        )
        if ticker:
            picked.append(ticker)
            included_bases.append(b)
        else:
            missing_bases.append(b)

    df = df.loc[df["Symbol"].astype(str).isin(picked)].copy()
    df = df.sort_values(["quote_volume_usd"], ascending=[False])

    tickers = df["Symbol"].astype(str).tolist()
    instrument_type = (constraints.instrument_type or "").strip().lower()
    snapshot = {
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "constraints": {
            "venue": "binance",
            "selection": "tradeable_mcap_tier",
            "tier": "custom",
            "instrument_type": instrument_type,
            "top_n_market_cap": constraints.top_n_market_cap,
            "mcap_rank_min": rmin,
            "mcap_rank_max": rmax,
            "quote_assets": list(quote_assets),
            "min_quote_volume_usd": floor,
            "min_history_days": constraints.min_history_days,
            "exclude_bases": list(constraints.exclude_bases),
            "sort": "quote_volume_usd_desc",
        },
        "market_cap_bases": bases,
        "included_bases": included_bases,
        "missing_bases": missing_bases,
        "requested_tickers": sorted(returned_set),
        "missing_tickers": [],
        "count": len(tickers),
        "rows": (
            [
                {
                    "ticker": str(row.get("Symbol")),
                    "symbol": symbol_from_ticker(str(row.get("Symbol"))),
                    "base": str(row.get("base")),
                    "quote_asset": str(row.get("quote_asset")),
                    "venue": "binance",
                    "instrument_type": instrument_type,
                    "entity_id": entity_id_for(
                        ticker=str(row.get("Symbol")), instrument_type=instrument_type
                    ),
                    "quote_volume_usd": row.get("quote_volume_usd"),
                    "volatility_24h_pct": row.get("volatility_24h_pct"),
                    "history_days": row.get("history_days"),
                }
                for row in cast(list[dict[str, Any]], df.to_dict(orient="records"))
            ]
            if not df.empty
            else []
        ),
    }

    return tickers, snapshot


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
        CryptoField.FIRST_BAR_TIME,
        CryptoField.LAST_BAR_UPDATE_TIME,
        CryptoField.BARS_COUNT,
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
    ss.set_tickers(*tickers)  # ty: ignore
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


def _pick_ticker_for_base(
    *,
    base: str,
    instrument_type: str,
    quote_assets: tuple[str, ...],
    returned: set[str],
    prefer_quote_asset: str | None = None,
) -> str | None:
    quote_assets_norm = tuple((q or "").strip().upper() for q in quote_assets if (q or "").strip())
    if not quote_assets_norm:
        return None

    prefer = (prefer_quote_asset or "").strip().upper() or None
    ordered = (
        (prefer,) + tuple(q for q in quote_assets_norm if q != prefer)
        if prefer
        else quote_assets_norm
    )

    for q in ordered:
        t = _ticker_for_base(base=base, quote_asset=q, instrument_type=instrument_type)
        if t in returned:
            return t
    return None


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

    included_bases: list[str] = []
    missing_bases: list[str] = []

    requested_tickers: list[str] = []
    for b in bases:
        for q in constraints.quote_assets:
            requested_tickers.append(
                _ticker_for_base(
                    base=b,
                    quote_asset=q,
                    instrument_type=constraints.instrument_type,
                )
            )

    candidates = fetch_tradingview_crypto_tickers(requested_tickers)
    if candidates.empty:
        out_tickers: list[str] = []
        ordered = candidates
        missing = requested_tickers
        missing_bases = bases
    else:
        returned = (
            candidates["Symbol"].dropna().astype(str).tolist()
            if "Symbol" in candidates.columns
            else []
        )
        returned_set = set(returned)
        missing = [t for t in requested_tickers if t not in returned_set]

        # Preserve market-cap rank order by picking one ticker per base.
        out_tickers = []
        prefer_q = constraints.quote_assets[0] if constraints.quote_assets else None
        for b in bases:
            picked = _pick_ticker_for_base(
                base=b,
                instrument_type=constraints.instrument_type,
                quote_assets=constraints.quote_assets,
                returned=returned_set,
                prefer_quote_asset=prefer_q,
            )
            if picked:
                out_tickers.append(picked)
                included_bases.append(b)
            else:
                missing_bases.append(b)

        ordered = candidates.copy()
        if "Symbol" in ordered.columns:
            ordered = ordered.loc[ordered["Symbol"].astype(str).isin(out_tickers)].copy()  # type: ignore[assignment]
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
            "quote_assets": list(constraints.quote_assets),
            "top_n_market_cap": constraints.top_n_market_cap,
            "min_volatility_24h_pct": constraints.min_volatility_24h_pct,
            "filters_applied": False,
            "sort": "market_cap_rank",
        },
        "market_cap_bases": bases,
        "included_bases": included_bases,
        "missing_bases": missing_bases,
        "requested_tickers": requested_tickers,
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

    requested: list[str] = []
    for b in bases_filtered:
        for q in constraints.quote_assets:
            requested.append(
                _ticker_for_base(
                    base=b,
                    quote_asset=q,
                    instrument_type=constraints.instrument_type,
                )
            )

    candidates = fetch_tradingview_crypto_tickers(requested)
    included_bases: list[str] = []
    missing_bases: list[str] = []
    if candidates.empty:
        tickers: list[str] = []
        missing = requested
        ordered = candidates
        missing_bases = bases_filtered
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

        available_set = set(
            ordered["Symbol"].dropna().astype(str).tolist() if "Symbol" in ordered.columns else []
        )

        # Pick one ticker per base (prefer primary quote asset), then order by volume.
        chosen: list[str] = []
        prefer_q = constraints.quote_assets[0] if constraints.quote_assets else None
        for b in bases_filtered:
            picked = _pick_ticker_for_base(
                base=b,
                instrument_type=constraints.instrument_type,
                quote_assets=constraints.quote_assets,
                returned=available_set,
                prefer_quote_asset=prefer_q,
            )
            if picked:
                chosen.append(picked)
                included_bases.append(b)
            else:
                missing_bases.append(b)

        ordered = ordered.loc[ordered["Symbol"].astype(str).isin(chosen)].copy()  # type: ignore[assignment]
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
            "quote_assets": list(constraints.quote_assets),
            "seed_top_n_market_cap": constraints.seed_top_n_market_cap,
            "min_quote_volume_usd": constraints.min_quote_volume_usd,
            "exclude_bases": list(constraints.exclude_bases),
            "sort": "quote_volume_usd_desc",
        },
        "market_cap_bases": bases,
        "bases_after_exclusions": bases_filtered,
        "included_bases": included_bases,
        "missing_bases": missing_bases,
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
                        quote_asset=(
                            constraints.quote_assets[0] if constraints.quote_assets else "USDT"
                        ),
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


def compute_top100_diagnostics(
    candidates: pd.DataFrame, *, constraints: BinanceCryptoUniverseConstraints
) -> dict[str, Any]:
    diag: dict[str, Any] = {
        "candidates_total": int(len(candidates)) if candidates is not None else 0,
        "quote_assets": list(constraints.quote_assets),
        "exclude_bases": list(constraints.exclude_bases),
        "min_quote_volume_usd": float(constraints.min_quote_volume_usd),
        "top_n": int(constraints.top_n),
    }

    if candidates is None or candidates.empty:
        return diag

    df = candidates.copy()
    df["quote_volume_usd"] = pd.to_numeric(df.get("Volume 24h in USD"), errors="coerce")

    proxy = _compute_proxy_volatility_24h_pct(df)
    if "Volatility" in df.columns:
        native = pd.to_numeric(df["Volatility"], errors="coerce")
        native_series = (
            native if isinstance(native, pd.Series) else pd.Series(native, index=df.index)
        )
        diag["volatility_native_nonnull"] = int(native_series.notna().sum())
        diag["volatility_proxy_used"] = int((native_series.isna() & proxy.notna()).sum())
    else:
        diag["volatility_native_nonnull"] = 0
        diag["volatility_proxy_used"] = int(proxy.notna().sum())

    df["volatility_24h_pct"] = compute_volatility_24h_pct(df)

    quote_assets = tuple(
        (q or "").strip().upper() for q in constraints.quote_assets if (q or "").strip()
    )
    if not quote_assets:
        quote_assets = ("USDT",)

    sym_clean = df["Symbol"].astype(str).str.replace(".P", "", regex=False)
    sym_clean = sym_clean.str.split(":", n=1).str[-1]
    df["_symbol_clean"] = sym_clean

    def _match_quote(s: str) -> str | None:
        for q in quote_assets:
            if s.endswith(q):
                return q
        return None

    df["quote_asset"] = df["_symbol_clean"].map(_match_quote)
    df = df.dropna(subset=["quote_asset"]).copy()
    diag["candidates_quote_asset_matched"] = int(len(df))

    df["base"] = pd.NA
    for q in quote_assets:
        mask = df["quote_asset"] == q
        if mask.any():
            df.loc[mask, "base"] = df.loc[mask, "_symbol_clean"].astype(str).str[: -len(q)]

    df = df.dropna(subset=["Symbol", "quote_volume_usd", "volatility_24h_pct", "base"]).copy()
    diag["candidates_nonnull_volume_and_volatility"] = int(len(df))

    df = df.loc[df["quote_volume_usd"] >= float(constraints.min_quote_volume_usd)].copy()
    diag["candidates_pass_min_volume"] = int(len(df))

    exclude_bases = {b.strip().upper() for b in constraints.exclude_bases}
    df = df.loc[~df["base"].astype(str).str.upper().isin(exclude_bases)].copy()
    diag["candidates_after_exclusions"] = int(len(df))

    quote_preference = {q: i for i, q in enumerate(quote_assets)}
    df["_quote_pref"] = df["quote_asset"].astype(str).map(lambda q: quote_preference.get(q, 999))
    df = df.sort_values(["_quote_pref", "quote_volume_usd"], ascending=[True, False])
    df = df.drop_duplicates(subset=["base"], keep="first").copy()
    diag["candidates_after_dedup_bases"] = int(len(df))

    # Selection behavior mirrors filter_and_rank_candidates.
    selected = filter_and_rank_candidates(candidates, constraints=constraints)
    diag["selected_count"] = int(len(selected))

    return diag


def build_binance_crypto_universe(
    *, constraints: BinanceCryptoUniverseConstraints
) -> tuple[list[str], dict]:
    candidates = fetch_tradingview_binance_crypto_candidates(
        instrument_type=constraints.instrument_type
    )
    diagnostics = compute_top100_diagnostics(candidates, constraints=constraints)
    ranked = filter_and_rank_candidates(candidates, constraints=constraints)

    tickers = ranked["Symbol"].astype(str).tolist() if not ranked.empty else []

    instrument_type = (constraints.instrument_type or "").strip().lower()

    snapshot = {
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "constraints": {
            "venue": "binance",
            "selection": "top_by_volume_filtered",
            "instrument_type": constraints.instrument_type,
            "top_n": constraints.top_n,
            "quote_assets": list(constraints.quote_assets),
            "exclude_bases": list(constraints.exclude_bases),
            "min_quote_volume_usd": constraints.min_quote_volume_usd,
        },
        "diagnostics": diagnostics,
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
                    "base": row.get("base"),
                    "quote_asset": row.get("quote_asset"),
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)
