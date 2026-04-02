from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pandas as pd

from tvscreener_ext.models import ScanRequest
from tvscreener_ext.screeners.factory import AssetScreenerFactory
from tvscreener_ext.services.config import ConfigFactory
from tvscreener_ext.services.export import ExportService
from tvscreener_ext.services.universe import UniverseResolver

if TYPE_CHECKING:
    from rich.console import Console

logger = logging.getLogger(__name__)


class ScanWorkflow:
    """Coordinator service for the scan execution lifecycle."""

    def __init__(
        self,
        resolver: UniverseResolver,
        factory: ConfigFactory,
        exporter: ExportService,
        console: Console | None = None,
    ):
        self.resolver = resolver
        self.factory = factory
        self.exporter = exporter
        self.console = console

    def get_opportunity_results(self, request: ScanRequest) -> tuple[pd.DataFrame, Any]:
        """Run opportunity screener and return results + screener instance."""
        pairs = self.resolver.resolve_tickers(
            request.assets.asset_type,
            request.assets.universe,
            request.assets.pairs,
            instrument_type=getattr(request.assets, "instrument_type", None),
        )
        timeframes = (
            request.assets.timeframes.split(",")
            if request.assets.timeframes
            else ["15", "60", "240"]
        )

        if self.console:
            self.console.print(
                f"[cyan]Scanning {len(pairs)} {request.assets.asset_type} symbols...[/cyan]"
            )

        config = self.factory.build_opportunity_config(request)
        screener = AssetScreenerFactory.create_screener(
            asset_type=request.assets.asset_type,
            symbols=pairs,
            timeframes=timeframes,
            config=config,
        )

        results = self._fetch_data_with_progress(screener.get_opportunities)
        return results, screener

    def _fetch_data_with_progress(self, fetch_func: Any) -> Any:
        """Helper to run a fetch function with rich progress bar."""
        if self.console and not getattr(self.console, "record", False):
            from rich.progress import Progress, SpinnerColumn, TextColumn

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
            ) as progress:
                progress.add_task("Fetching data...", total=None)
                return fetch_func()
        return fetch_func()
