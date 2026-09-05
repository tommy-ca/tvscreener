from __future__ import annotations

import argparse
import logging


def setup_logging(verbose: bool = False) -> None:
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add common arguments to a parser."""
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--config", help="Path to YAML config")
