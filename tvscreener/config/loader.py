from typing import Any

import yaml
from pydantic import ValidationError

from tvscreener.config.settings import ScreenerSettings
from tvscreener.util import validate_path

DEFAULT_CONFIG_PATH = "tvscreener.yaml"


def load_yaml_config(config_path: str | None = None) -> dict[str, Any]:
    """Load configuration from YAML file."""
    path = config_path or DEFAULT_CONFIG_PATH

    # Security: Validate path before reading
    try:
        validated_path = validate_path(path)
    except ValueError as e:
        # If the path is invalid or outside allowed directory, we ignore it
        # but only if it's the default path. If specific path was provided,
        # it might be better to log a warning.
        if config_path:
            import logging

            logging.warning(f"Invalid config path: {path} - {e}")
        return {}

    if not validated_path.exists():
        return {}

    with open(validated_path) as f:
        return yaml.safe_load(f) or {}


def load_settings(config_path: str | None = None) -> ScreenerSettings:
    """Load settings with precedence: ENV > .env > YAML > Defaults."""
    yaml_config = load_yaml_config(config_path) or {}
    # Filter out None values to allow defaults/ENV to take precedence
    yaml_config = {k: v for k, v in yaml_config.items() if v is not None}

    # Backward compatibility: handle flat YAML for nested models
    if any(k.startswith("opportunity_") for k in yaml_config):
        opportunity_data = {}
        for k in list(yaml_config.keys()):
            if k.startswith("opportunity_"):
                sub_key = k[len("opportunity_") :]
                # Remove redundant "opportunity_" prefix
                opportunity_data[sub_key] = yaml_config.pop(k)
        if opportunity_data:
            yaml_config["opportunity"] = opportunity_data

    # Risk settings are also now in a nested model
    risk_keys = {
        "min_tf_alignment",
        "require_momentum",
        "min_rvol",
        "require_volume_spike",
        "volume_spike_threshold",
        "risk_per_trade_pct",
        "min_risk_reward_ratio",
        "atr_multiplier",
        "account_balance",
        "pip_value",
    }
    risk_data = {}
    for k in list(yaml_config.keys()):
        if k in risk_keys:
            risk_data[k] = yaml_config.pop(k)
    if risk_data:
        yaml_config["risk"] = risk_data

    try:
        # Load from ENV/dotenv first to get explicit overrides
        env_settings = ScreenerSettings()

        # Merge YAML into final config
        merged: dict[str, Any] = dict(yaml_config)

        # Explicitly override YAML with any fields set by ENV/dotenv
        # Note: In Pydantic V2, if an ENV var for a nested model is set,
        # the parent field is included in model_fields_set.
        for field_name in env_settings.model_fields_set:
            merged[field_name] = getattr(env_settings, field_name)

        return ScreenerSettings(**merged)
    except ValidationError as e:
        import logging

        logging.warning(f"Settings validation error: {e}. Using defaults.")
        return ScreenerSettings()
