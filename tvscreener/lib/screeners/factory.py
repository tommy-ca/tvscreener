from __future__ import annotations

from typing import Any

import tvscreener as tvs
from tvscreener import (
    BondField,
    CoinField,
    CryptoField,
    ForexField,
    FuturesField,
    StockField,
)
from tvscreener.lib.screeners.base import BaseOpportunityScreener, ScreenerConfig
from tvscreener.lib.screeners.forex_opportunity import ForexOpportunityScreener
from tvscreener.lib.screeners.risk_utils import RISK_DEFAULTS

ASSET_MAP = {
    "stock": {"field_class": StockField, "screener_class": tvs.StockScreener},
    "crypto": {"field_class": CryptoField, "screener_class": tvs.CryptoScreener},
    "forex": {"field_class": ForexField, "screener_class": tvs.ForexScreener},
    "bond": {"field_class": BondField, "screener_class": tvs.BondScreener},
    "futures": {"field_class": FuturesField, "screener_class": tvs.FuturesScreener},
    "coin": {"field_class": CoinField, "screener_class": tvs.CoinScreener},
}


class GenericOpportunityScreener(BaseOpportunityScreener):
    """A generic opportunity screener that works for any asset type supported by the library."""

    def __init__(
        self, asset_type: str, symbols: list[str], timeframes: list[str], config: ScreenerConfig
    ):
        self.asset_type = asset_type.lower()
        if self.asset_type not in ASSET_MAP:
            # Fallback to stock or raise error? Todo says clear error message.
            raise ValueError(
                f"Unsupported asset type: {asset_type}. Supported: {list(ASSET_MAP.keys())}"
            )
        super().__init__(symbols=symbols, timeframes=timeframes, config=config)

    def _get_screener_instance(self) -> Any:
        return ASSET_MAP[self.asset_type]["screener_class"]()

    def _get_field_class(self) -> Any:
        return ASSET_MAP[self.asset_type]["field_class"]


class AssetScreenerFactory:
    """Factory for creating the appropriate opportunity screener based on asset type."""

    @staticmethod
    def create_screener(
        asset_type: str,
        symbols: list[str],
        timeframes: list[str],
        config: Any,  # Can be ForexScreenerConfig or ScreenerConfig
    ) -> BaseOpportunityScreener:
        asset_type = asset_type.lower()

        # Use specialized implementation for forex if available and requested
        if asset_type == "forex":
            # Convert generic config to ForexScreenerConfig if necessary
            from tvscreener.lib.screeners.forex_opportunity import ForexScreenerConfig

            if not isinstance(config, ForexScreenerConfig):
                fx_config = ForexScreenerConfig(
                    scoring_config=config.scoring_config,
                    timeframe_weights=config.timeframe_weights,
                    include_atr=config.include_atr,
                    include_rsi=config.include_rsi,
                    min_rvol=config.min_rvol,
                    show_risk=config.show_risk,
                    risk_per_trade_pct=config.risk_per_trade_pct,
                    atr_multiplier=config.atr_multiplier,
                    min_risk_reward_ratio=config.min_risk_reward_ratio,
                    account_balance=config.account_balance,
                    pip_value=config.pip_value,
                )
            else:
                fx_config = config
            return ForexOpportunityScreener(pairs=symbols, timeframes=timeframes, config=fx_config)

        # Default to generic screener for other asset types
        # Note: if config is ForexScreenerConfig, we extract the base parts
        if hasattr(config, "scoring_config"):
            base_config = ScreenerConfig(
                scoring_config=config.scoring_config,
                timeframe_weights=config.timeframe_weights,
                include_atr=config.include_atr,
                include_rsi=config.include_rsi,
                min_rvol=config.min_rvol,
                show_risk=config.show_risk,
                risk_per_trade_pct=getattr(
                    config, "risk_per_trade_pct", RISK_DEFAULTS.risk_per_trade_pct
                ),
                atr_multiplier=getattr(config, "atr_multiplier", RISK_DEFAULTS.atr_multiplier),
                min_risk_reward_ratio=getattr(
                    config, "min_risk_reward_ratio", RISK_DEFAULTS.min_risk_reward_ratio
                ),
                account_balance=getattr(config, "account_balance", RISK_DEFAULTS.account_balance),
                pip_value=getattr(config, "pip_value", RISK_DEFAULTS.pip_value),
            )
        else:
            base_config = config

        return GenericOpportunityScreener(
            asset_type=asset_type, symbols=symbols, timeframes=timeframes, config=base_config
        )
