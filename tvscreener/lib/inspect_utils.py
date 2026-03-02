import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

logger = logging.getLogger(__name__)


def inspect_parquet(
    path: str, head: int = 10, metadata_only: bool = False, console: Console | None = None
) -> None:
    """Read and display a Parquet file with embedded metadata in a pretty format."""
    if console is None:
        console = Console()

    p = Path(path)
    if not p.exists():
        console.print(f"[red]Error: File not found: {path}[/red]")
        return

    # 1. Read Metadata
    metadata: dict[str, Any] = {}
    try:
        import pyarrow.parquet as pq

        meta = pq.read_metadata(path)
        embedded_json = meta.metadata.get(b"tvscreener_metadata")
        if embedded_json:
            # Security: Size limit for JSON metadata to prevent DoS (e.g. 10MB)
            if len(embedded_json) > 10 * 1024 * 1024:
                logger.warning(f"Metadata too large ({len(embedded_json)} bytes), skipping")
            else:
                metadata = json.loads(embedded_json)
    except Exception as e:
        logger.debug(f"Could not read embedded metadata: {e}")

    # 2. Display Header
    console.print(Panel(f"[bold cyan]Inspection: {p.name}[/bold cyan]", expand=False))

    if metadata:
        _display_metadata(metadata, console)
    else:
        console.print("[yellow]No embedded metadata found.[/yellow]")

    if metadata_only:
        return

    # 3. Read and Display Table
    try:
        df = pd.read_parquet(path)

        table_title = f"Data Table (showing top {min(head, len(df))} of {len(df)} rows)"
        table = Table(title=table_title, header_style="bold magenta", box=None)

        # Determine important columns to show (don't show everything if it's too wide)
        all_cols = list(df.columns)
        primary_cols = [
            "PAIR",
            "DIRECTION",
            "GRADE",
            "STRENGTH_SIGN",
            "STRATEGY",
            "ENSEMBLE_SCORE",
            "CONFLUENCE_SCORE",
        ]
        show_cols = [c for c in primary_cols if c in all_cols]

        # Add factor context if space allows (showing latest TF usually)
        factor_cols = [
            c
            for c in all_cols
            if any(c.startswith(f"{f}_") for f in ["TREND", "MA", "OSC", "ROC"]) and "_" in c
        ]
        show_cols.extend(factor_cols[:4])

        for col in show_cols:
            table.add_column(col)

        for _, row in df.head(head).iterrows():
            table.add_row(*[str(row.get(col, "")) for col in show_cols])

        console.print(table)

        if len(df) > head:
            console.print(f"[dim]... and {len(df) - head} more rows[/dim]")

    except Exception as e:
        console.print(f"[red]Error reading data: {e}[/red]")


def _display_metadata(metadata: dict[str, Any], console: Console) -> None:
    """Display embedded metadata in a tree structure."""
    tree = Tree("[bold green]Embedded Metadata[/bold green]")

    # Version
    tree.add(f"Version: {metadata.get('version', 'N/A')}")

    # Execution Stats
    stats = metadata.get("execution_stats", {})
    if stats:
        s_node = tree.add("Execution Stats")
        s_node.add(f"Start: {stats.get('start_time', 'N/A')}")
        s_node.add(f"Duration: {stats.get('duration_seconds', 'N/A')}s")

    # Config
    config = metadata.get("config", {})
    if config:
        c_node = tree.add("Scanner Config")
        for k, v in config.items():
            if k == "risk_management":
                r_node = c_node.add("Risk Management")
                for rk, rv in v.items():
                    r_node.add(f"{rk}: [yellow]{rv}[/yellow]")
            else:
                c_node.add(f"{k}: {v}")

    # Summary Stats
    summary = metadata.get("summary_stats", {})
    if summary:
        sum_node = tree.add("Summary Stats")
        for k, v in summary.items():
            sum_node.add(f"{k}: [bold green]{v}[/bold green]")

    # API Summary (just count)
    api = metadata.get("api_summary", [])
    api_stats = metadata.get("api_summary_stats", {})
    if api:
        count = len(api)
        dropped = api_stats.get("dropped_count", 0)
        if dropped > 0:
            tree.add(
                f"API Audit Trail: {count} calls recorded ([yellow]+{dropped} dropped[/yellow])"
            )
        else:
            tree.add(f"API Audit Trail: {count} calls recorded")
    elif api_stats.get("dropped_count", 0) > 0:
        # Cases where api_summary might be truncated (to_json fallback)
        tree.add(
            f"API Audit Trail: 0 recorded ([yellow]+{api_stats['dropped_count']} dropped[/yellow])"
        )

    console.print(tree)
    console.print()
