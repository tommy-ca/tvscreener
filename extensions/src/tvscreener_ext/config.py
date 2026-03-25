from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class LakehouseLocalConfig:
    base_dir: Path
    catalog_db: str
    warehouse_dir: str


@dataclass(frozen=True, slots=True)
class LakehouseRemoteConfig:
    uri: str
    warehouse: str


@dataclass(frozen=True, slots=True)
class LakehouseCatalogConfig:
    mode: str
    name: str
    type: str
    local: LakehouseLocalConfig
    remote: LakehouseRemoteConfig | None
    properties: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Settings:
    lakehouse: LakehouseCatalogConfig


def _default_base_dir() -> Path:
    env = (os.getenv("TVSCREENER_LAKEHOUSE_BASE_DIR") or "").strip()
    if env:
        return Path(env).expanduser()
    return Path.cwd() / ".tvscreener" / "lakehouse"


def load_settings(config_path: str | None = None) -> Settings:
    cfg_path = Path(config_path) if config_path else Path("tvscreener.yaml")
    payload: dict[str, Any] = {}
    if cfg_path.exists():
        payload = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    lakehouse = payload.get("lakehouse") or {}
    catalog = lakehouse.get("catalog") or {}
    mode = str(catalog.get("mode") or "local").strip().lower()
    name = str(catalog.get("name") or "local").strip()
    cat_type = str(catalog.get("type") or "sql").strip()
    properties = dict(catalog.get("properties") or {})

    local_cfg = catalog.get("local") or {}
    base_dir = Path(local_cfg.get("base_dir") or _default_base_dir()).expanduser()
    catalog_db = str(local_cfg.get("catalog_db") or "catalog.db")
    warehouse_dir = str(local_cfg.get("warehouse_dir") or "warehouse")
    local = LakehouseLocalConfig(
        base_dir=base_dir,
        catalog_db=catalog_db,
        warehouse_dir=warehouse_dir,
    )

    remote: LakehouseRemoteConfig | None = None
    remote_cfg = catalog.get("remote")
    if remote_cfg:
        remote = LakehouseRemoteConfig(
            uri=str(remote_cfg.get("uri") or "").strip(),
            warehouse=str(remote_cfg.get("warehouse") or "").strip(),
        )

    return Settings(
        lakehouse=LakehouseCatalogConfig(
            mode=mode,
            name=name,
            type=cat_type,
            local=local,
            remote=remote,
            properties=properties,
        )
    )
