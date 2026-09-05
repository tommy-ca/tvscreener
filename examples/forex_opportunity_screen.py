#!/usr/bin/env python3
"""
Forex Opportunity Screener Example

This example demonstrates how to use the ForexOpportunityScreener to find
trading opportunities across multiple forex pairs and timeframes.

Usage:
    python examples/forex_opportunity_screen.py

Requirements:
    pip install tvscreener tvscreener-ext
"""

from tvscreener_ext.screeners.filters import RocFilter, ScoreFilter
from tvscreener_ext.screeners.forex_opportunity import (
    ForexOpportunityScreener,
    ForexScreenerConfig,
)


def main():
    config = ForexScreenerConfig(
        score_filters=(
            ScoreFilter("all", 0.1),
            ScoreFilter("ma", 0.1),
            ScoreFilter("oscillator", 0.1),
        ),
        roc_filter=RocFilter(min_roc=0),
    )

    scanner = ForexOpportunityScreener(
        pairs=["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD"],
        timeframes=["15", "60", "240"],
        config=config,
    )

    print("Scanning forex opportunities...")
    print(f"Configuration: {scanner}")
    print()

    scanner.print_summary()

    print("\nExporting to files...")
    scanner.export("forex_opportunities.csv", "csv")
    scanner.export("forex_opportunities.json", "json")
    print("Done!")


if __name__ == "__main__":
    main()
