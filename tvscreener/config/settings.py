from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from tvscreener.lib.screeners.risk_utils import RISK_DEFAULTS


class LakehouseLocalCatalogSettings(BaseModel):
    """Local-dev Iceberg SQL catalog + file warehouse settings."""

    # Base directory for local lakehouse state (catalog + warehouse).
    # If unset, defaults to ~/.tvscreener/lakehouse
    base_dir: str | None = None

    # File names / subdirs (relative to base_dir).
    catalog_db: str = Field(default="catalog.db")
    warehouse_dir: str = Field(default="warehouse")

    @field_validator("catalog_db", "warehouse_dir", mode="before")
    @classmethod
    def strip_strings(cls, v: Any) -> Any:
        return v.strip() if isinstance(v, str) else v


class LakehouseRemoteCatalogSettings(BaseModel):
    """Remote/shared Iceberg SQL catalog settings (e.g., Postgres)."""

    # SQLAlchemy URI for the Iceberg SQL catalog (pyiceberg "sql" catalog).
    # Example: postgresql+psycopg://user:pass@host:5432/iceberg
    uri: str = Field(min_length=1)

    # Warehouse location for table data.
    # Examples: file:///mnt/warehouse, s3://bucket/prefix, abfs://...
    warehouse: str = Field(min_length=1)

    @field_validator("uri", "warehouse", mode="before")
    @classmethod
    def strip_strings(cls, v: Any) -> Any:
        return v.strip() if isinstance(v, str) else v


class LakehouseCatalogSettings(BaseModel):
    """Iceberg catalog configuration (local or remote SQL catalog)."""

    mode: Literal["local", "remote"] = Field(default="local")
    name: str = Field(default="local")

    # pyiceberg catalog type. For this project we only support SQL catalogs today.
    type: Literal["sql"] = Field(default="sql")

    # Local mode settings (sqlite catalog + file warehouse).
    local: LakehouseLocalCatalogSettings = Field(default_factory=LakehouseLocalCatalogSettings)

    # Remote mode settings (postgres catalog + shared warehouse).
    remote: LakehouseRemoteCatalogSettings | None = Field(default=None)

    # Extra catalog properties passed to pyiceberg load_catalog (e.g. object store auth/endpoints).
    properties: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_mode(self) -> LakehouseCatalogSettings:
        if self.mode == "remote" and self.remote is None:
            raise ValueError(
                "lakehouse.catalog.remote must be set when lakehouse.catalog.mode=remote"
            )
        return self


class LakehouseSettings(BaseModel):
    """Top-level lakehouse settings group."""

    catalog: LakehouseCatalogSettings = Field(default_factory=LakehouseCatalogSettings)


class OpportunitySettings(BaseModel):
    """Opportunity-specific scanner settings."""

    min_volume: float | None = Field(default=None, ge=0)
    max_atr: float | None = Field(default=None, ge=0)
    min_ma_score: float | None = Field(default=None, ge=-2, le=2)
    trend_weight: float = Field(default=0.4, ge=0, le=1)
    ma_weight: float = Field(default=0.3, ge=0, le=1)
    osc_weight: float = Field(default=0.2, ge=0, le=1)
    roc_weight: float = Field(default=0.1, ge=0, le=1)
    timeframe_weights: str = Field(default="240:0.2,60:0.3,15:0.5")

    @field_validator("min_ma_score", "max_atr", "min_volume", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        if v == "" or v == "null" or v == "None":
            return None
        return v

    def get_timeframe_weights(self) -> dict[str, float]:
        from tvscreener.util import parse_timeframe_weights

        return parse_timeframe_weights(self.timeframe_weights)


class RiskSettings(BaseModel):
    """Risk management and signal alignment settings."""

    min_tf_alignment: int = Field(default=2, ge=1, le=3)
    require_momentum: bool = Field(default=False)
    min_rvol: float = Field(default=1.0, ge=0.0)
    require_volume_spike: bool = Field(default=False)
    volume_spike_threshold: float = Field(default=1.5, ge=1.0)

    risk_per_trade_pct: float = Field(default=RISK_DEFAULTS.risk_per_trade_pct, ge=0.1, le=10.0)
    min_risk_reward_ratio: float = Field(
        default=RISK_DEFAULTS.min_risk_reward_ratio, ge=0.5, le=5.0
    )
    atr_multiplier: float = Field(default=RISK_DEFAULTS.atr_multiplier, ge=0.5, le=5.0)

    account_balance: float = Field(default=RISK_DEFAULTS.account_balance, ge=100)
    pip_value: float = Field(default=RISK_DEFAULTS.pip_value, ge=0.01)

    @field_validator("require_momentum", "require_volume_spike", mode="before")
    @classmethod
    def parse_bool(cls, v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return bool(v)


class ScreenerSettings(BaseSettings):
    """Layered settings: YAML → ENV → CLI (CLI handled separately)"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="TVSCREENER_",
        extra="ignore",
        env_nested_delimiter="_",
    )

    # General / Strategy Filter Defaults
    min_volume: float | None = Field(default=None, ge=0)
    max_atr: float | None = Field(default=None, ge=0)
    min_ma_score: float | None = Field(default=None, ge=-2, le=2)
    min_confluence: int = Field(default=1, ge=1)
    trend_threshold: float = Field(default=0.2, ge=-1, le=1)
    mr_threshold: float = Field(default=0.2, ge=0, le=1)
    rsi_lower: float = Field(default=30.0, ge=0.0, le=50.0)
    rsi_upper: float = Field(default=70.0, ge=50.0, le=100.0)
    min_roc: float | None = Field(default=None, ge=0)

    # Universal Defaults
    default_universe: str = Field(default="all")
    default_timeframes: str = Field(default="240,60,15")
    contract_type: Literal["spot", "cfd", "spreadbet", "all"] = Field(default="cfd")

    # Scoped Settings
    opportunity: OpportunitySettings = Field(default_factory=OpportunitySettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    lakehouse: LakehouseSettings = Field(default_factory=LakehouseSettings)

    @field_validator("min_ma_score", "max_atr", "min_volume", "min_roc", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        if v == "" or v == "null" or v == "None":
            return None
        return v

    @field_validator("default_timeframes", mode="before")
    @classmethod
    def parse_timeframes(cls, v):
        if isinstance(v, list):
            return ",".join(str(x) for x in v)
        return v

    def get_timeframes_list(self) -> list[str]:
        return self.default_timeframes.split(",")

    @field_validator("default_universe", mode="before")
    @classmethod
    def validate_universe(cls, v):
        if v and isinstance(v, str):
            return v.lower().strip()
        return v

    def lakehouse_local_base_dir(self) -> Path:
        """Resolved local base dir for lakehouse files."""
        base = self.lakehouse.catalog.local.base_dir
        return Path(base).expanduser() if base else (Path.home() / ".tvscreener" / "lakehouse")
