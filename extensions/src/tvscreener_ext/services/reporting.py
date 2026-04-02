from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

    from tvscreener_ext.services.universe import UniverseResolver

logger = logging.getLogger(__name__)


class ReportingService:
    """Service for audits, reporting, and reviews."""

    def __init__(self, resolver: UniverseResolver, console: Console | None = None):
        self.resolver = resolver
        self.console = console

    def run_audit(self, args: argparse.Namespace) -> int:
        """Run audits and write structured reports."""
        target = getattr(args, "target", None)
        out_dir = getattr(args, "out_dir", None)
        if not target:
            return 2

        if target != "binance-universes":
            if self.console:
                self.console.print(f"[red]Unknown audit target: {target}[/red]")
            return 2

        out_base = Path(out_dir or "artifacts/audits/binance-universes")
        out_base.mkdir(parents=True, exist_ok=True)

        include_all = bool(getattr(args, "include_all", False))
        universes = [
            "binance_spot_majors",
            "binance_perp_majors",
            "binance_spot_minors",
            "binance_perp_minors",
            "binance_spot_tradeable_base",
            "binance_perp_tradeable_base",
            "binance_spot_tradeable_mcap_cs",
            "binance_perp_tradeable_mcap_cs",
            "binance_spot_top100",
            "binance_perp_top100",
        ]
        if include_all:
            universes += [
                "binance_spot_mcap_top100",
                "binance_perp_mcap_top100",
                "binance_spot_cs_momentum",
                "binance_perp_cs_momentum",
            ]

        report: dict[str, dict] = {}
        sets: dict[str, set[str]] = {}

        previous_run_dir = os.environ.get("TVSCREENER_RUN_DIR")
        for u in universes:
            run_dir = out_base / u
            run_dir.mkdir(parents=True, exist_ok=True)
            os.environ["TVSCREENER_RUN_DIR"] = str(run_dir)
            pairs = self.resolver.resolve_tickers("crypto", u, specific=None)
            sets[u] = set(pairs)

            def _quote_asset(ticker: str) -> str:
                sym = ticker.split(":", 1)[-1]
                if sym.endswith(".P"):
                    sym = sym[: -len(".P")]
                for q in ("USDT", "USDC", "BTC", "ETH", "TRY", "BRL", "EUR", "JPY", "GBP"):
                    if sym.endswith(q):
                        return q
                return "OTHER"

            quote_dist: dict[str, int] = {}
            for p in pairs:
                q = _quote_asset(p)
                quote_dist[q] = quote_dist.get(q, 0) + 1

            uni_path = run_dir / "universe.json"
            uni = None
            if uni_path.exists():
                with contextlib.suppress(Exception):
                    uni = json.loads(uni_path.read_text(encoding="utf-8"))

            errors: list[str] = []
            if len(pairs) != len(set(pairs)):
                errors.append("duplicates")
            if u.startswith("binance_perp") and any(not p.endswith(".P") for p in pairs):
                errors.append("perp_missing_dotP")
            if u.startswith("binance_spot") and any(p.endswith(".P") for p in pairs):
                errors.append("spot_has_dotP")
            if any(not p.startswith("BINANCE:") for p in pairs):
                errors.append("non_binance_ticker")

            report[u] = {
                "count": len(pairs),
                "sample": pairs[:10],
                "quote_asset_dist": dict(
                    sorted(quote_dist.items(), key=lambda kv: (-kv[1], kv[0]))
                ),
                "universe_json": str(uni_path) if uni_path.exists() else None,
                "selection": (
                    uni.get("constraints", {}).get("selection") if isinstance(uni, dict) else None
                ),
                "missing_tickers": (
                    len(uni.get("missing_tickers", [])) if isinstance(uni, dict) else None
                ),
                "included_bases": (
                    len(uni.get("included_bases", [])) if isinstance(uni, dict) else None
                ),
                "errors": errors,
            }

        overlap: dict[str, dict[str, int]] = {
            a: {b: len(sets[a] & sets[b]) for b in universes} for a in universes
        }
        payload = {"universes": report, "overlap": overlap}
        report_path = out_base / "report.json"
        report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

        if self.console:
            self.console.print(f"[green]Wrote {report_path}[/green]")

        if previous_run_dir is None:
            os.environ.pop("TVSCREENER_RUN_DIR", None)
        else:
            os.environ["TVSCREENER_RUN_DIR"] = previous_run_dir
        return 0

    def run_report(self, args: argparse.Namespace) -> int:
        """Generate DuckDB reports."""
        target = getattr(args, "target", None)
        if target != "binance-universes":
            if self.console:
                self.console.print(f"[red]Unknown report target: {target}[/red]")
            return 2
        in_dir = getattr(args, "in_dir", "artifacts/audits/binance-universes")
        out_dir = getattr(args, "out_dir", "artifacts/reports/binance-universes")
        from tvscreener_ext.reports.binance_universes import generate_binance_universes_report

        paths = generate_binance_universes_report(in_dir=in_dir, out_dir=out_dir)
        if self.console:
            self.console.print(f"[green]Wrote {paths.report_json}[/green]")
            self.console.print(f"[green]Wrote {paths.report_md}[/green]")
        return 0

    def run_review(self, args: argparse.Namespace) -> int:
        """Run audit + report pipeline."""
        target = getattr(args, "target", None)
        if target != "binance-universes":
            if self.console:
                self.console.print(f"[red]Unknown review target: {target}[/red]")
            return 2
        audit_out_dir = getattr(args, "audit_out_dir", "artifacts/audits/binance-universes")
        report_out_dir = getattr(args, "report_out_dir", "artifacts/reports/binance-universes")
        strict = bool(getattr(args, "strict", False))

        audit_args = argparse.Namespace(
            command="audit",
            target=target,
            out_dir=audit_out_dir,
            include_all=bool(getattr(args, "include_all", False)),
            verbose=getattr(args, "verbose", False),
            config=getattr(args, "config", None),
        )
        rc = self.run_audit(audit_args)
        if rc != 0:
            return rc

        if strict:
            report_path = Path(audit_out_dir) / "report.json"
            try:
                payload = json.loads(report_path.read_text(encoding="utf-8"))
                universes = (payload or {}).get("universes", {})
                if any((v or {}).get("errors") for v in universes.values()):
                    if self.console:
                        self.console.print(
                            "[bold red]Review failed: audit errors present[/bold red]"
                        )
                    return 2
            except Exception:
                return 2

        report_args = argparse.Namespace(
            command="report",
            target=target,
            in_dir=audit_out_dir,
            out_dir=report_out_dir,
            verbose=getattr(args, "verbose", False),
            config=getattr(args, "config", None),
        )
        return self.run_report(report_args)
