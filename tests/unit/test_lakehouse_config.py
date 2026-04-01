from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
import yaml

from tvscreener_ext.lakehouse import get_manager
from tvscreener_ext.lakehouse.manager import LakehouseManager


@pytest.fixture(autouse=True)
def reset_manager_singleton():
    """Reset the LakehouseManager singleton before and after each test."""
    import tvscreener_ext.lakehouse.manager as manager_mod

    manager_mod._MANAGER_INSTANCE = None
    yield
    manager_mod._MANAGER_INSTANCE = None


def test_lakehouse_initializes_with_default_config():
    with patch("tvscreener_ext.config.load_settings") as mock_load:
        mock_settings = MagicMock()
        mock_settings.lakehouse.catalog.mode = "local"
        mock_settings.lakehouse.catalog.local.catalog_db = "catalog.db"
        mock_settings.lakehouse.catalog.local.warehouse_dir = "warehouse"
        mock_settings.lakehouse.catalog.local.base_dir = None
        mock_settings.lakehouse_local_base_dir.return_value = Path("/tmp/tvscreener/lakehouse")
        mock_load.return_value = mock_settings

        manager = get_manager()
        assert isinstance(manager, LakehouseManager)
        mock_load.assert_called_once_with(None)


def test_lakehouse_initializes_with_custom_config(tmp_path):
    config_file = tmp_path / "custom_config.yaml"
    config_data = {
        "lakehouse": {
            "catalog": {"mode": "local", "local": {"base_dir": str(tmp_path / "custom_lakehouse")}}
        }
    }
    config_file.write_text(yaml.dump(config_data))

    # Note: load_settings will actually load the file if we don't mock it,
    # but we want to test that get_manager passes the path correctly.
    with patch("tvscreener_ext.config.load_settings") as mock_load:
        mock_settings = MagicMock()
        mock_settings.lakehouse.catalog.mode = "local"
        mock_settings.lakehouse.catalog.local.catalog_db = "catalog.db"
        mock_settings.lakehouse.catalog.local.warehouse_dir = "warehouse"
        mock_settings.lakehouse.catalog.local.base_dir = str(tmp_path / "custom_lakehouse")
        mock_settings.lakehouse_local_base_dir.return_value = Path(tmp_path / "custom_lakehouse")
        mock_load.return_value = mock_settings

        manager = get_manager(str(config_file))
        assert manager._config_path == str(config_file)
        mock_load.assert_called_once_with(str(config_file))


def test_lakehouse_singleton_ignores_subsequent_config():
    with patch("tvscreener_ext.config.load_settings") as mock_load:
        mock_settings = MagicMock()
        mock_settings.lakehouse.catalog.mode = "local"
        mock_load.return_value = mock_settings

        mgr1 = get_manager("config1.yaml")
        mgr2 = get_manager("config2.yaml")

        assert mgr1 is mgr2
        assert mgr1._config_path == "config1.yaml"
        # load_settings should only be called once during first initialization
        mock_load.assert_called_once_with("config1.yaml")


def test_lakehouse_remote_config_validation():
    from pydantic import ValidationError

    from tvscreener_ext.config.settings import ScreenerSettings

    # Valid remote config
    valid_remote = {
        "lakehouse": {
            "catalog": {
                "mode": "remote",
                "remote": {
                    "uri": "postgresql://localhost/iceberg",
                    "warehouse": "s3://bucket/warehouse",
                },
            }
        }
    }
    settings = ScreenerSettings(**cast(Any, valid_remote))
    assert settings.lakehouse.catalog.mode == "remote"
    assert settings.lakehouse.catalog.remote is not None
    assert settings.lakehouse.catalog.remote.uri == "postgresql://localhost/iceberg"

    # Invalid: mode=remote but no remote block
    invalid_remote_missing = {"lakehouse": {"catalog": {"mode": "remote"}}}
    with pytest.raises(ValidationError) as exc:
        ScreenerSettings(**cast(Any, invalid_remote_missing))
    assert "lakehouse.catalog.remote must be set" in str(exc.value)

    # Invalid: remote block missing required fields
    invalid_remote_fields = {
        "lakehouse": {
            "catalog": {
                "mode": "remote",
                "remote": {
                    "uri": " "  # Should fail due to min_length=1 after strip
                },
            }
        }
    }
    with pytest.raises(ValidationError):
        ScreenerSettings(**cast(Any, invalid_remote_fields))


def test_lakehouse_env_override(monkeypatch):
    from tvscreener_ext.config.settings import ScreenerSettings

    # Mock environment variables
    monkeypatch.setenv("TVSCREENER_LAKEHOUSE_CATALOG_MODE", "remote")
    monkeypatch.setenv("TVSCREENER_LAKEHOUSE_CATALOG_REMOTE_URI", "postgresql://env_host/db")
    monkeypatch.setenv(
        "TVSCREENER_LAKEHOUSE_CATALOG_REMOTE_WAREHOUSE", "s3://env_bucket/env_warehouse"
    )

    # ScreenerSettings should pick these up
    settings = ScreenerSettings()
    assert settings.lakehouse.catalog.mode == "remote"
    assert settings.lakehouse.catalog.remote is not None
    assert settings.lakehouse.catalog.remote.uri == "postgresql://env_host/db"
    assert settings.lakehouse.catalog.remote.warehouse == "s3://env_bucket/env_warehouse"
