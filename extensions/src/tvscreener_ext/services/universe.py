from __future__ import annotations

import os
from typing import Any

from tvscreener_ext.config.universe import FOREX_UNIVERSE, AssetUniverse, ConfigurationError
from tvscreener_ext.constants.commodity import COMMODITY_UNIVERSE
from tvscreener_ext.constants.crypto import CRYPTO_UNIVERSE
from tvscreener_ext.constants.forex import (
    DEFAULT_FOREX_PAIRS,
    FOREX_MAJORS,
    FOREX_MINORS,
)
from tvscreener_ext.constants.market_risk import (
    MARKET_RISK_FUTURES_TICKERS,
    MARKET_RISK_PROXY_TICKERS,
)
from tvscreener_ext.constants.stocks import STOCK_UNIVERSE
from tvscreener_ext.utils.logic import canonicalize_asset_type

UNIVERSE_MAP: dict[str, AssetUniverse] = {
    "forex": FOREX_UNIVERSE,
    "stock": STOCK_UNIVERSE,
    "crypto": CRYPTO_UNIVERSE,
    "futures": COMMODITY_UNIVERSE,
    "stocks": STOCK_UNIVERSE,
    "commodity": COMMODITY_UNIVERSE,
}

UNIVERSE_ALIASES = {
    "binance_spot_base": "binance_spot_tradeable_base",
    "binance_perp_base": "binance_perp_tradeable_base",
    "binance_spot_largecap": "binance_spot_tradeable_mcap_cs",
    "binance_perp_largecap": "binance_perp_tradeable_mcap_cs",
    "binance_spot_snapshot": "binance_spot_top100",
    "binance_perp_snapshot": "binance_perp_top100",
}


class UniverseResolver:
    """Service for ticker and asset discovery."""

    def get_universe_config(self, asset_type: str) -> AssetUniverse:
        """Get universe config by asset type with validation."""
        asset_type = canonicalize_asset_type(asset_type)
        if asset_type not in UNIVERSE_MAP:
            raise ConfigurationError(
                f"Unknown asset type: {asset_type}. Valid options: {', '.join(UNIVERSE_MAP.keys())}"
            )
        return UNIVERSE_MAP[asset_type]

    def resolve_tickers(
        self,
        asset_type: str,
        universe: str | None = None,
        specific: list[str] | None = None,
        *,
        instrument_type: str | None = None,
    ) -> list[str]:
        """Resolve symbols based on asset type, universe selector, or explicit list."""
        if specific:
            return specific

        # Triage crypto specific aliases
        if asset_type == "crypto" and universe in {"majors", "minors"}:
            it = (instrument_type or "spot").strip().lower()
            venue = "perp" if it in {"perp", "swap"} else "spot"
            universe = f"binance_{venue}_{universe}"

        if universe:
            universe = UNIVERSE_ALIASES.get(universe, universe)

        asset_type = canonicalize_asset_type(asset_type)

        # Forex resolution
        if asset_type == "forex":
            if universe == "majors":
                return FOREX_MAJORS
            if universe == "minors":
                return FOREX_MINORS
            return DEFAULT_FOREX_PAIRS

        # Market risk resolution
        if universe in {"market_risk", "risk"}:
            if asset_type == "stock":
                return list(MARKET_RISK_PROXY_TICKERS)
            if asset_type == "futures":
                return list(MARKET_RISK_FUTURES_TICKERS)

        # Dynamic Binance universes
        if asset_type == "crypto":
            if universe in {"binance_spot_top100", "binance_perp_top100"}:
                return self._resolve_binance_top100(universe)
            if universe in {"binance_spot_mcap_top100", "binance_perp_mcap_top100"}:
                return self._resolve_binance_mcap_top100(universe)
            if universe in {"binance_spot_cs_momentum", "binance_perp_cs_momentum"}:
                return self._resolve_binance_cs_momentum(universe)

        # Default fallthrough
        return []

    def _resolve_binance_top100(self, universe: str) -> list[str]:
        from tvscreener_ext.universe.binance_crypto import (
            BinanceCryptoUniverseConstraints,
            build_binance_crypto_universe,
        )

        it = "spot" if universe == "binance_spot_top100" else "perp"
        tickers, snapshot = build_binance_crypto_universe(
            constraints=BinanceCryptoUniverseConstraints(
                instrument_type=it,
                quote_assets=("USDT", "USDC"),
                min_quote_volume_usd=(2_500_000 if it == "spot" else 10_000_000),
            )
        )
        self._write_snapshot(snapshot)
        return tickers

    def _resolve_binance_mcap_top100(self, universe: str) -> list[str]:
        from tvscreener_ext.universe.binance_crypto import (
            BinanceCryptoMarketCapUniverseConstraints,
            build_binance_crypto_universe_market_cap,
        )

        it = "spot" if universe == "binance_spot_mcap_top100" else "perp"
        tickers, snapshot = build_binance_crypto_universe_market_cap(
            constraints=BinanceCryptoMarketCapUniverseConstraints(
                instrument_type=it,
                min_volatility_24h_pct=0.0,
            )
        )
        self._write_snapshot(snapshot)
        return tickers

    def _resolve_binance_cs_momentum(self, universe: str) -> list[str]:
        from tvscreener_ext.universe.binance_crypto import (
            BinanceCryptoCSMomentumUniverseConstraints,
            build_binance_crypto_universe_cs_momentum,
        )

        it = "spot" if universe == "binance_spot_cs_momentum" else "perp"
        tickers, snapshot = build_binance_crypto_universe_cs_momentum(
            constraints=BinanceCryptoCSMomentumUniverseConstraints(
                instrument_type=it,
                min_quote_volume_usd=(1_700_000 if it == "spot" else 10_000_000),
            )
        )
        self._write_snapshot(snapshot)
        return tickers

    def _write_snapshot(self, snapshot: Any) -> None:
        from tvscreener_ext.universe.binance_crypto import maybe_write_universe_json

        run_dir = (os.getenv("TVSCREENER_RUN_DIR") or "").strip() or None
        _ = maybe_write_universe_json(snapshot, run_dir=run_dir)
