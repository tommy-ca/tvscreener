from __future__ import annotations

from typing import Any, cast

from tvscreener_ext.constants.forex import DEFAULT_TIMEFRAME_WEIGHTS
from tvscreener_ext.enums import Direction
from tvscreener_ext.models import ScanRequest
from tvscreener_ext.scoring import ScoringConfig as ScoreWeights
from tvscreener_ext.screeners.filters import AtrFilter, RocFilter, ScoreFilter, VolumeFilter
from tvscreener_ext.screeners.forex_opportunity import ContractType, ForexScreenerConfig
from tvscreener_ext.screeners.forex_strategy import StrategyConfig, StrategyType
from tvscreener_ext.utils.logic import parse_timeframe_weights


class ConfigFactory:
    """Service for pure logic mapping between ScanRequest and engine configurations."""

    def build_opportunity_config(self, request: ScanRequest) -> ForexScreenerConfig:
        """Build configuration for the opportunity screener."""
        score_filters = (
            [ScoreFilter("ma", request.assets.min_ma_score)]
            if request.assets.min_ma_score is not None
            else []
        )

        scoring_config = ScoreWeights(
            trend_weight=request.scoring.opportunity_trend_weight
            if request.scoring.opportunity_trend_weight is not None
            else 0.4,
            ma_weight=request.scoring.opportunity_ma_weight
            if request.scoring.opportunity_ma_weight is not None
            else 0.3,
            osc_weight=request.scoring.opportunity_osc_weight
            if request.scoring.opportunity_osc_weight is not None
            else 0.2,
            roc_weight=request.scoring.opportunity_roc_weight
            if request.scoring.opportunity_roc_weight is not None
            else 0.1,
        )

        return ForexScreenerConfig(
            scoring_config=scoring_config,
            timeframe_weights=self._parse_timeframe_weights(
                request.scoring.opportunity_timeframe_weights
            ),
            score_filters=tuple(score_filters),
            roc_filter=RocFilter(min_roc=request.assets.min_roc)
            if request.assets.min_roc is not None
            else None,
            volume_filter=VolumeFilter(min_volume=request.assets.min_volume)
            if request.assets.min_volume is not None
            else None,
            include_atr=request.assets.include_atr
            or request.assets.max_atr is not None
            or request.output.show_risk,
            include_rsi=request.assets.include_rsi or bool(request.scoring.mr_signal),
            atr_filter=AtrFilter(max_atr=request.assets.max_atr)
            if request.assets.max_atr is not None
            else None,
            contract_type=cast(ContractType, request.assets.contract_type or "cfd"),
            min_rvol=request.assets.min_rvol,
            show_risk=request.output.show_risk,
            risk_per_trade_pct=request.risk.risk_per_trade_pct or 1.0,
            atr_multiplier=request.risk.atr_multiplier or 2.0,
            min_risk_reward_ratio=request.risk.min_risk_reward_ratio or 1.5,
            account_balance=request.risk.account_balance or 10000.0,
        )

    def build_strategy_config(self, request: ScanRequest) -> StrategyConfig:
        """Build configuration for the strategy scanner."""
        strategy_name = {
            "trend": "trend_following",
            "mean_reversion": "mean_reversion",
            "hybrid": "hybrid",
            "breakout": "breakout",
            "confluence": "confluence",
        }.get(request.assets.strategy, "all")

        strategy_tuple = cast(
            tuple[StrategyType, ...], ("all",) if strategy_name == "all" else (strategy_name,)
        )

        return StrategyConfig(
            include_strategies=strategy_tuple,
            direction=request.scoring.filter_direction or Direction.ALL,
            min_confluence=request.scoring.min_confluence or 1,
            trend_threshold=request.scoring.trend_threshold or 0.0,
            mr_threshold=request.scoring.mr_threshold or 0.2,
            rsi_lower=request.scoring.rsi_lower or 30.0,
            rsi_upper=request.scoring.rsi_upper or 70.0,
            min_roc=request.assets.min_roc,
            min_volume=request.assets.min_volume,
            max_atr=request.assets.max_atr,
            min_ma_score=request.assets.min_ma_score,
            mean_reversion_signals=tuple(request.scoring.mr_signal)
            if request.scoring.mr_signal
            else (),
            contract_type=cast(ContractType, request.assets.contract_type or "cfd"),
            include_atr_fields=request.assets.include_atr
            or request.assets.max_atr is not None
            or request.output.show_risk,
            include_rsi_fields=request.assets.include_rsi or bool(request.scoring.mr_signal),
            min_tf_alignment=request.scoring.min_tf_alignment or 1,
            require_momentum=request.scoring.require_momentum,
            min_rvol=request.assets.min_rvol,
            require_volume_spike=request.assets.require_volume_spike,
            risk_per_trade_pct=request.risk.risk_per_trade_pct or 1.0,
            atr_multiplier=request.risk.atr_multiplier or 2.0,
            min_risk_reward_ratio=request.risk.min_risk_reward_ratio or 1.5,
            account_balance=request.risk.account_balance or 10000.0,
            show_risk=request.output.show_risk,
        )

    def build_opportunity_metadata(self, request: ScanRequest) -> dict[str, Any]:
        """Build metadata for opportunity scan artifacts."""
        return {
            "scanner": "opportunity",
            "filters": {
                "min_volume": request.assets.min_volume,
                "max_atr": request.assets.max_atr,
                "min_ma_score": request.assets.min_ma_score,
                "contract_type": request.assets.contract_type,
            },
            "timeframes": request.assets.timeframes,
        }

    def build_strategy_metadata(self, request: ScanRequest) -> dict[str, Any]:
        """Build metadata for strategy scan artifacts."""
        return {
            "scanner": "strategy",
            "strategy": request.assets.strategy,
            "filters": {
                "min_volume": request.assets.min_volume,
                "max_atr": request.assets.max_atr,
                "min_ma_score": request.assets.min_ma_score,
            },
            "timeframes": request.assets.timeframes,
        }

    def _parse_timeframe_weights(self, spec: str | None) -> dict[str, float]:
        """Parse timeframe weights with defaults."""
        return parse_timeframe_weights(spec, default=dict(DEFAULT_TIMEFRAME_WEIGHTS))
