from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .settings import ScreenerSettings


def load_settings(config_path: str | None = None) -> ScreenerSettings:
    """Load settings from YAML, ENV, and defaults."""
    from pydantic import ValidationError

    cfg_path = Path(config_path) if config_path else Path("tvscreener.yaml")
    payload: dict[str, Any] = {}
    if cfg_path.exists():
        try:
            payload = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            import logging

            logging.warning(f"Failed to load config from {cfg_path}: {e}")

    try:
        return ScreenerSettings(**payload)
    except ValidationError as e:
        import logging

        logging.warning(f"Settings validation error: {e}. Using defaults.")
        return ScreenerSettings()
