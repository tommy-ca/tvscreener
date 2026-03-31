from __future__ import annotations

import os


def lakehouse_layout() -> str:
    """Returns the lakehouse table naming layout.

    - `legacy`: shared tables like `tvscreener.bronze`
    - `scalable`: dimensioned namespaces like `tvscreener_crypto_spot_bronze.screener_snapshot`
    """

    return (os.getenv("TVSCREENER_LAKEHOUSE_LAYOUT") or "legacy").strip().lower()


def default_instrument_type(asset_type: str) -> str:
    at = (asset_type or "").strip().lower()
    if at == "forex":
        return (os.getenv("TVSCREENER_CONTRACT_TYPE") or "cfd").strip().lower()
    if at == "crypto":
        return "spot"
    if at == "futures":
        return "future"
    return "spot"


def normalize_instrument_type(*, asset_type: str, raw: str | None) -> str:
    at = (asset_type or "").strip().lower()
    v = (raw or "").strip().lower()

    if not v:
        return default_instrument_type(at)

    if at == "crypto":
        # TradingView uses `Type=spot` for spot and `Type=swap` for perps.
        if v == "swap":
            return "perp"
        if v == "spot":
            return "spot"

    return v


def stage_table_id(
    *,
    stage: str,
    dataset: str,
    asset_type: str,
    instrument_type: str,
    layout: str | None = None,
) -> str:
    layout = (layout or lakehouse_layout()).strip().lower()
    if layout != "scalable":
        return f"tvscreener.{stage}"

    namespace = f"tvscreener_{asset_type}_{instrument_type}_{stage}"
    return f"{namespace}.{dataset}"


def product_table_id(
    *,
    dataset: str,
    asset_type: str,
    instrument_type: str,
    layout: str | None = None,
) -> str:
    layout = (layout or lakehouse_layout()).strip().lower()
    if layout != "scalable":
        return f"tvscreener.{dataset}"

    namespace = f"tvscreener_{asset_type}_{instrument_type}_product"
    return f"{namespace}.{dataset}"
