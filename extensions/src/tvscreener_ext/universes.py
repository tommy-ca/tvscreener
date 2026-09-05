from __future__ import annotations

from dataclasses import dataclass

FOREX_MAJORS = [
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "USDCHF",
    "USDCAD",
    "AUDUSD",
    "NZDUSD",
]

FOREX_MINORS = [
    "EURGBP",
    "EURJPY",
    "GBPJPY",
    "EURCHF",
    "AUDJPY",
    "EURCAD",
    "CADJPY",
    "CHFJPY",
    "NZDJPY",
    "GBPAUD",
    "EURAUD",
    "AUDNZD",
    "EURNZD",
    "GBPCAD",
    "AUDCAD",
    "GBPNZD",
    "GBPCHF",
    "AUDCHF",
    "CADCHF",
    "NZDCHF",
    "NZDCAD",
]


BINANCE_MAJORS_BASES = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "SOLUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "LINKUSDT",
    "XLMUSDT",
    "BCHUSDT",
    "TRXUSDT",
]

# Snapshot-based minors list aligned to the essential validation runset.
BINANCE_MINORS_BASES = [
    "FETUSDT",
    "ZECUSDT",
    "PEPEUSDT",
    "BONKUSDT",
    "VIRTUALUSDT",
    "AVAXUSDT",
    "LTCUSDT",
    "AAVEUSDT",
    "FLOKIUSDT",
    "HBARUSDT",
    "SHIBUSDT",
    "DASHUSDT",
    "RENDERUSDT",
    "CRVUSDT",
    "SUIUSDT",
    "INJUSDT",
    "ONDOUSDT",
    "UNIUSDT",
    "FILUSDT",
    "ENAUSDT",
    "SEIUSDT",
    "TONUSDT",
    "ICPUSDT",
    "OPUSDT",
    "ETHFIUSDT",
    "DOTUSDT",
    "BFUSDUSDT",
    "DEXEUSDT",
    "NEARUSDT",
    "JSTUSDT",
    "SUNUSDT",
]


MARKET_RISK_TICKERS = [
    "AMEX:SPY",
    "NASDAQ:QQQ",
    "TVC:VIX",
    "TVC:DXY",
]


@dataclass(frozen=True, slots=True)
class Universe:
    name: str
    tickers: list[str]


def resolve_universe(
    *, asset_type: str, universe: str, instrument_type: str | None = None
) -> Universe:
    at = (asset_type or "").strip().lower()
    u = (universe or "").strip().lower()
    it = (instrument_type or "").strip().lower() if instrument_type else None

    if at == "forex":
        if u == "majors":
            return Universe(name="majors", tickers=[f"FX_IDC:{p}" for p in FOREX_MAJORS])
        if u == "minors":
            return Universe(name="minors", tickers=[f"FX_IDC:{p}" for p in FOREX_MINORS])
        raise ValueError(f"Unsupported forex universe: {universe}")

    if at == "crypto":
        if it not in {"spot", "perp"}:
            raise ValueError(f"Unsupported crypto instrument_type: {instrument_type}")
        suffix = ".P" if it == "perp" else ""
        if u == "majors":
            return Universe(
                name="majors", tickers=[f"BINANCE:{b}{suffix}" for b in BINANCE_MAJORS_BASES]
            )
        if u == "minors":
            return Universe(
                name="minors", tickers=[f"BINANCE:{b}{suffix}" for b in BINANCE_MINORS_BASES]
            )
        raise ValueError(f"Unsupported crypto universe: {universe}")

    if at == "stock":
        if u == "market_risk":
            return Universe(name="market_risk", tickers=list(MARKET_RISK_TICKERS))
        raise ValueError(f"Unsupported stock universe: {universe}")

    raise ValueError(f"Unsupported asset_type: {asset_type}")
