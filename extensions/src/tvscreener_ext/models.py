from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tvscreener_ext.enums import Direction


@dataclass
class AssetSelection:
    """Routing and asset selection parameters."""

    scanner: str = "strategy"
    pipeline: str = "both"  # data | analytics | both
    strategy: str = "all"
    asset_type: str = "forex"
    universe: str | None = None
    pairs: list[str] | None = None
    timeframes: str | None = None
    contract_type: str | None = None
    instrument_type: str | None = None
    min_volume: float | None = None
    max_atr: float | None = None
    min_ma_score: float | None = None
    min_roc: float | None = None
    min_rvol: float | None = None
    require_volume_spike: bool = False
    include_atr: bool = False
    include_rsi: bool = False


@dataclass
class ScoringConfig:
    """Scoring and signal configuration parameters."""

    # Opportunity Screener Weights
    opportunity_trend_weight: float | None = None
    opportunity_ma_weight: float | None = None
    opportunity_osc_weight: float | None = None
    opportunity_roc_weight: float | None = None
    opportunity_timeframe_weights: str | None = None

    # Strategy Scanner Parameters
    filter_direction: Direction | str | None = None  # Direction.LONG, Direction.SHORT
    min_confluence: int | None = None
    trend_threshold: float | None = None
    mr_threshold: float | None = None
    rsi_lower: float | None = None
    rsi_upper: float | None = None
    mr_signal: list[str] = field(default_factory=list)
    min_tf_alignment: int | None = None
    require_momentum: bool = False


@dataclass
class RiskConfig:
    """Risk management parameters."""

    risk_per_trade_pct: float | None = None
    atr_multiplier: float | None = None
    min_risk_reward_ratio: float | None = None
    account_balance: float | None = None
    pip_value: float | None = None


@dataclass
class OutputConfig:
    """Output formatting and control parameters."""

    output: str | None = None
    detailed: bool = False
    matrix: bool = False
    limit: int | None = None
    show_risk: bool = False
    head: int | None = None
    metadata_only: bool = False
    save_config: str | None = None
    config_path: str | None = None
    verbose: bool = False
    sql: str | None = None
    sql_params: dict[str, Any] = field(default_factory=dict)
    filters: list[str] = field(default_factory=list)
    confluence_grade: str | None = None
    min_opportunity_confluence: int | None = None


@dataclass
class ScanRequest:
    """Unified scan request parameters using nested components."""

    assets: AssetSelection = field(default_factory=AssetSelection)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    # Backward compatibility properties for most common fields
    @property
    def scanner(self) -> str:
        return self.assets.scanner

    @property
    def asset_type(self) -> str:
        return self.assets.asset_type

    @property
    def sql(self) -> str | None:
        return self.output.sql

    @property
    def strategy(self) -> str:
        return self.assets.strategy
