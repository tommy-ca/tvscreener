from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast

import narwhals as nw
import pandas as pd

from tvscreener.lib.screeners.metadata_utils import MetadataCollector
from tvscreener.lib.screeners.risk_utils import RISK_DEFAULTS, RiskConfig, RiskEngine
from tvscreener.score import DEFAULT_SCORING_CONFIG, ScoringConfig, ScoringEngine
from tvscreener.util import validate_path

if TYPE_CHECKING:
    from tvscreener.core.base import Screener
    from tvscreener.lib.screeners.filters import DataFrameFilter

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="Screener")


@dataclass(frozen=True, slots=True)
class ScreenerConfig:
    """Base configuration for all screeners."""

    scoring_config: ScoringConfig = field(default_factory=lambda: DEFAULT_SCORING_CONFIG)
    timeframe_weights: dict[str, float] = field(default_factory=dict)
    include_atr: bool = False
    include_rsi: bool = False
    min_rvol: float | None = None
    show_risk: bool = False

    # Risk management parameters (defaults)
    risk_per_trade_pct: float = RISK_DEFAULTS.risk_per_trade_pct
    atr_multiplier: float = RISK_DEFAULTS.atr_multiplier
    min_risk_reward_ratio: float = RISK_DEFAULTS.min_risk_reward_ratio
    account_balance: float = RISK_DEFAULTS.account_balance
    pip_value: float = RISK_DEFAULTS.pip_value

    extra_options: dict[str, Any] = field(default_factory=dict)

    def to_risk_config(self) -> RiskConfig:
        """Convert screener config to RiskConfig."""
        return RiskConfig(
            account_balance=self.account_balance,
            risk_per_trade_pct=self.risk_per_trade_pct,
            min_risk_reward_ratio=self.min_risk_reward_ratio,
            atr_multiplier=self.atr_multiplier,
            pip_value=self.pip_value,
        )


class ExportMixin(ABC):
    """Mixin to provide shared export and data enrichment logic to screeners."""

    # These are expected to be available in the class using the mixin
    timeframes: list[str]
    metadata: MetadataCollector
    post_filters: list[DataFrameFilter]

    @abstractmethod
    def _get_data(self) -> pd.DataFrame:
        """Get the underlying data for the scanner."""
        pass

    @nw.narwhalify
    def _prepare_enriched_data(self, df: Any) -> Any:
        """Prepare DataFrame with canonical names and human-readable factor columns."""
        if len(df) == 0:
            return df

        from tvscreener.lib.screeners.transformer import DataTransformer

        # Ensure PAIR is at the front
        if "PAIR" in df.columns:
            cols = [c for c in df.columns if c != "PAIR"]
            df = df.select(["PAIR"] + cols)

        # Standard technical factor and stat renames
        df = DataTransformer.rename_technical_columns(df, self.timeframes)
        df = DataTransformer.standardize_stat_columns(df)

        return df

    def export(self, path: str, format_name: str, label: str = "results", **kwargs) -> None:
        """Export results to various formats."""
        from tvscreener.lib.screeners.export_helpers import get_export_function

        # Security: Validate path before exporting
        try:
            validated_path = validate_path(path)
        except ValueError as e:
            logger.error("Cannot export results: %s", e)
            return

        # Merge manual metadata with collector metadata
        cli_metadata = kwargs.pop("metadata", {})
        merged_metadata = {**cli_metadata, **self.metadata.to_dict()}

        get_export_function(format_name)(
            lambda: self._prepare_enriched_data(self._get_data()),
            str(validated_path),
            **kwargs,
            metadata=merged_metadata,
            logger=logging.getLogger(self.__class__.__module__),
            label=label,
        )

    def _direction_emoji(self, value: float) -> str:
        """Direction indicator that always shows 🟢 or 🔴 (never ⚪)."""
        if value >= 0.5:
            return "🟢🟢"
        if value > 0:
            return "🟢"
        if value <= -0.5:
            return "🔴🔴"
        return "🔴"

    def _matrix_sign(self, value: float) -> str:
        """Single emoji for matrix cells (no doubles — prevents column truncation)."""
        if value > 0:
            return "🟢"
        if value < 0:
            return "🔴"
        return "⚪"

    def print_summary(self, results_df: pd.DataFrame | None = None, **kwargs) -> None:
        """Print a summary of the results to the console using the default renderer.

        Args:
            results_df: Optional DataFrame to render instead of the screener's internal data.
            **kwargs: Additional rendering options (limit, detailed, matrix, etc.)
        """
        from tvscreener.lib.screeners.renderers.rich_console import RichConsoleRenderer

        renderer = RichConsoleRenderer()
        renderer.render(self, results_df=results_df, **kwargs)


@dataclass
class BaseOpportunityScreener(ExportMixin, ABC, Generic[T]):
    """Abstract base for high-level asset-specific opportunity screeners."""

    symbols: list[str] = field(default_factory=list)
    timeframes: list[str] = field(default_factory=lambda: ["15", "60", "240"])
    config: ScreenerConfig = field(default_factory=ScreenerConfig)
    metadata: MetadataCollector = field(default_factory=MetadataCollector)
    post_filters: list[DataFrameFilter] = field(default_factory=list)
    _cached_data: pd.DataFrame | None = field(init=False, default=None)
    _risk_engine: RiskEngine = field(init=False)

    def __post_init__(self) -> None:
        self._validate_inputs()
        self._engine = ScoringEngine(
            config=self.config.scoring_config,
            timeframes=self.timeframes,
            tf_weights=self.config.timeframe_weights,
        )
        self._risk_engine = RiskEngine(self.config.to_risk_config())

        # Force include_atr if show_risk is True
        if self.config.show_risk and not self.config.include_atr:
            # We can't modify self.config because it's frozen,
            # but we can check both in the methods.
            pass

        self.metadata.set_config(
            {
                "symbols_count": len(self.symbols),
                "timeframes": self.timeframes,
                "include_atr": self.config.include_atr or self.config.show_risk,
                "include_rsi": self.config.include_rsi,
                "min_rvol": self.config.min_rvol,
                "show_risk": self.config.show_risk,
                **self.config.extra_options,
            }
        )

    def _get_data(self) -> pd.DataFrame:
        """Implementation of ExportMixin's _get_data."""
        if self._cached_data is not None:
            return self._cached_data
        return self.get_opportunities(use_cache=True)

    def _validate_inputs(self) -> None:
        """Validate symbols and timeframes. Can be overridden by subclasses."""
        pass

    @abstractmethod
    def _get_screener_instance(self) -> T:
        """Return an instance of the underlying library Screener (e.g., ForexScreener)."""
        pass

    @abstractmethod
    def _get_field_class(self) -> Any:
        """Return the field class for this asset (e.g., ForexField)."""
        pass

    def get_opportunities(self, use_cache: bool = False) -> pd.DataFrame:
        if use_cache and self._cached_data is not None:
            return self._cached_data

        logger.info(
            "Scanning %s symbols across %s timeframes",
            len(self.symbols),
            len(self.timeframes),
        )

        df = self._fetch_all_data()

        if df.empty:
            self.metadata.finish(results_count=0)
            return df

        df = self._apply_asset_filters(df)
        df = self._merge_duplicates(df)
        df = self._rank_opportunities(df)

        # Apply post_filters so all consumers (CLI, MCP, API) get filtered data
        if self.post_filters:
            for pf in self.post_filters:
                df = pf(df)
                if df.empty:
                    break

        self._cached_data = df
        self.metadata.finish(
            results_count=len(df),
            total_scanned=len(self.symbols),
            average_ensemble=float(df["ENSEMBLE_SCORE"].mean()) if not df.empty else 0.0,  # type: ignore
        )
        return df

    def _get_tickers(self) -> list[str]:
        """Return the list of tickers to fetch. Subclasses can override for prefixing/formatting."""
        return self.symbols

    def _prepare_screener(self, screener: T, field_class: Any) -> None:
        """Hook for subclasses to add extra fields or filters to the screener before fetching."""
        pass

    def _fetch_all_data(self) -> pd.DataFrame:
        """Fetch data for all symbols in batches."""
        tickers = self._get_tickers()
        if not tickers:
            return pd.DataFrame()

        screener = self._get_screener_instance()
        field_class = self._get_field_class()

        # Prepare fields
        select_fields = self._get_base_fields(field_class)
        for tf in self.timeframes:
            select_fields.extend(self._get_timeframe_fields(field_class, tf))

        screener.select(*select_fields)
        self._prepare_screener(screener, field_class)

        # Batching (TV API usually supports ~500 symbols per request)
        batch_size = self.config.extra_options.get("batch_size", 500)
        all_dfs = []

        for i in range(0, len(tickers), batch_size):
            batch_tickers = tickers[i : i + batch_size]
            screener.set_tickers(*batch_tickers)

            try:
                df = screener.get()
                if "api_context" in df.attrs:
                    ctx = df.attrs["api_context"]
                    self.metadata.add_api_call(
                        url=ctx.get("url", ""),
                        status_code=ctx.get("status_code", 0),
                        method=ctx.get("method", "GET"),
                        headers=ctx.get("headers", {}),
                    )
                if not df.empty:
                    all_dfs.append(df)
            except Exception as e:
                logger.error("Error fetching batch %s: %s", i // batch_size + 1, e)

        if not all_dfs:
            return pd.DataFrame()

        combined_df = pd.concat(all_dfs, ignore_index=True)
        # Enforce PyArrow backend at the Silver boundary for zero-copy efficiency
        if not combined_df.empty:
            combined_df = cast(pd.DataFrame, combined_df.convert_dtypes(dtype_backend="pyarrow"))
        return combined_df

    def _get_base_fields(self, field_class: Any) -> list[Any]:
        """Get base fields for the asset type."""
        fields = [
            getattr(field_class, "NAME", None),
            getattr(field_class, "PRICE", None),
            getattr(field_class, "SUBTYPE", None),
        ]
        # Try to find a volume field
        volume_fields = [
            "AVERAGE_VOLUME_10D_CALC",
            "RELATIVE_VOLUME_10D_CALC",
            "VOLUME",
        ]
        for vf in volume_fields:
            field = getattr(field_class, vf, None)
            if field:
                fields.append(field)

        return [f for f in fields if f is not None]

    def _get_timeframe_fields(self, field_class: Any, tf: str) -> list[Any]:
        """Get technical fields for a specific timeframe."""
        fields = []
        # Support both dot and underscore patterns
        patterns = [
            f"RECOMMEND_ALL_{tf}",
            f"RECOMMEND_MA_{tf}",
            f"RECOMMEND_OTHER_{tf}",
            f"ROC_{tf}",
        ]

        if self.config.include_atr or self.config.show_risk:
            patterns.append(f"ATR_{tf}")
        if self.config.include_rsi:
            patterns.append(f"RSI_{tf}")

        for p in patterns:
            f = getattr(field_class, p, None)
            if f:
                fields.append(f)

        return fields

    def _apply_asset_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply asset-specific filters. Default implementation does nothing."""
        return df

    def _merge_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle duplicate results (e.g. from different exchanges)."""
        if df.empty:
            return df
        # Default implementation: just keep first by name
        if "Name" in df.columns:
            return df.drop_duplicates(subset=["Name"])
        return df

    def _rank_opportunities(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply scoring and ranking."""
        if df.empty:
            return df
        df = self._engine.rank_opportunities(df)

        if self.config.show_risk:
            df = self._risk_engine.apply(df)

        return df
