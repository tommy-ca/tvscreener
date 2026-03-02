from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

import pandas as pd
from pyiceberg.exceptions import NoSuchTableError

from tvscreener.lib.lakehouse import get_catalog, write_iceberg

if TYPE_CHECKING:
    from tvscreener.lib.screeners.base import BaseOpportunityScreener

logger = logging.getLogger(__name__)


def resume_or_run(
    screener: BaseOpportunityScreener,
    stage: str,
    runner_func: Callable[[], pd.DataFrame],
    persist: bool = True,
    mode: str | None = None,
) -> pd.DataFrame:
    """Helper to either resume a stage from Iceberg or run its logic.

    Consolidated boilerplate for Medallion pipeline stages (Todo 157).
    """
    replay = screener.config.extra_options.get("replay")
    table_name = f"tvscreener.{stage}"

    if mode is None:
        # Default to overwrite for Gold and Silver to ensure idempotency
        mode = "overwrite" if stage in ["gold", "silver"] else "append"

    if replay:
        try:
            catalog = get_catalog()
            table = catalog.load_table(table_name)
            logger.info("Resuming from %s Iceberg table", stage.capitalize())
            return table.to_pandas()
        except NoSuchTableError:
            pass
        except Exception as e:
            logger.debug("Failed to load from %s: %s", stage.capitalize(), e)

    df = runner_func()

    # Write-Audit-Publish (WAP) pattern (Todo 174)
    # Block Iceberg commits if data health check fails
    if persist and not screener._validate_health(df, stage):
        logger.error("Health check failed for stage '%s'. Blocking Iceberg commit.", stage)
        return df

    if persist:
        try:
            partition_by = None
            # Add metadata columns and set partitioning based on medallion layer
            from datetime import datetime, timezone

            now_utc = datetime.now(timezone.utc)
            if stage == "bronze":
                if "ingest_date" not in df.columns:
                    df["ingest_date"] = now_utc.strftime("%Y-%m-%d")
                partition_by = ["ingest_date"]
            elif stage == "silver":
                # asset_type should ideally come from the screener
                if "asset_type" not in df.columns:
                    df["asset_type"] = screener.__class__.__name__.replace("Screener", "").lower()
                partition_by = ["asset_type"]
            elif stage == "gold":
                if "signal_date" not in df.columns:
                    df["signal_date"] = now_utc.strftime("%Y-%m-%d")
                partition_by = ["signal_date"]

            write_iceberg(df, table_name, mode=mode, partition_by=partition_by)
        except Exception as e:
            logger.debug("Iceberg %s persistence failed: %s", stage.capitalize(), e)

    return df


class PipelineStage(Protocol):
    """Protocol for a Medallion pipeline stage."""

    def run(
        self, screener: BaseOpportunityScreener, data: pd.DataFrame | None = None
    ) -> pd.DataFrame:
        """Execute the stage logic."""
        ...


class Ingestor:
    """Bronze Stage: Responsible for fetching raw data from the TV API."""

    def run(
        self, screener: BaseOpportunityScreener, data: pd.DataFrame | None = None
    ) -> pd.DataFrame:
        logger.debug("Running Ingestor (Bronze Stage)")
        return screener._fetch_all_data()


class Standardizer:
    """Silver Stage: Responsible for renaming, filtering, and canonicalizing data."""

    def run(
        self, screener: BaseOpportunityScreener, data: pd.DataFrame | None = None
    ) -> pd.DataFrame:
        if data is None or data.empty:
            return pd.DataFrame()
        logger.debug("Running Standardizer (Silver Stage)")
        return screener._apply_standardization(data)


class Scorer:
    """Gold Stage: Responsible for scoring, ranking, and risk management."""

    def run(
        self, screener: BaseOpportunityScreener, data: pd.DataFrame | None = None
    ) -> pd.DataFrame:
        if data is None or data.empty:
            return pd.DataFrame()
        logger.debug("Running Scorer (Gold Stage)")
        # Scoring logic using ScoringEngine
        scored_df = screener._engine.rank_opportunities(data, copy=False)
        if screener.config.show_risk:
            scored_df = screener._risk_engine.apply(scored_df, copy=False)
        return scored_df
