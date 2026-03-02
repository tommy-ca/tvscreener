"""
Helper functions for MCP tools.

These functions provide a clean interface between MCP tools and the tvscreener library.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
import yaml

import tvscreener as tvs
from tvscreener import (
    BondField,
    CoinField,
    CryptoField,
    FilterOperator,
    ForexField,
    FuturesField,
    StockField,
)
from tvscreener.lib.lakehouse import get_catalog
from tvscreener.lib.orchestrator import (
    AssetSelection,
    OutputConfig,
    RiskConfig,
    ScanRequest,
    ScoringConfig,
    ScreenerController,
)
from tvscreener.util import validate_path

if TYPE_CHECKING:
    from typing import Any


# Mapping from string operators to FilterOperator enum
FILTER_OP_MAP = {
    ">=": FilterOperator.ABOVE_OR_EQUAL,
    ">": FilterOperator.ABOVE,
    "<=": FilterOperator.BELOW_OR_EQUAL,
    "<": FilterOperator.BELOW,
    "==": FilterOperator.EQUAL,
    "!=": FilterOperator.NOT_EQUAL,
    "in_range": FilterOperator.IN_RANGE,
    "not_in_range": FilterOperator.NOT_IN_RANGE,
    "match": FilterOperator.MATCH,
    "crosses": FilterOperator.CROSSES,
    "crosses_up": FilterOperator.CROSSES_UP,
    "crosses_down": FilterOperator.CROSSES_DOWN,
}

# Mapping from asset type to field class and screener class
ASSET_CONFIG = {
    "stock": {"field_class": StockField, "screener_class": tvs.StockScreener},
    "crypto": {"field_class": CryptoField, "screener_class": tvs.CryptoScreener},
    "forex": {"field_class": ForexField, "screener_class": tvs.ForexScreener},
    "bond": {"field_class": BondField, "screener_class": tvs.BondScreener},
    "futures": {"field_class": FuturesField, "screener_class": tvs.FuturesScreener},
    "coin": {"field_class": CoinField, "screener_class": tvs.CoinScreener},
}


def get_field_enum(field_name: str, asset_type: str = "stock"):
    """
    Get the field enum from a field name string.

    Args:
        field_name: Name of the field (e.g., "PRICE", "RSI", "VOLUME")
        asset_type: Asset type ("stock", "crypto", "forex", "bond", "futures", "coin")

    Returns:
        Field enum or None if not found
    """
    field_name = field_name.upper().replace(" ", "_")
    config = ASSET_CONFIG.get(asset_type, ASSET_CONFIG["stock"])
    field_class = config["field_class"]

    # Try direct attribute access first
    if hasattr(field_class, field_name):
        return getattr(field_class, field_name)

    # Fall back to search
    results = field_class.search(field_name)
    if results:
        return results[0]

    return None


def search_fields(query: str, asset_type: str = "stock", limit: int = 20) -> list[dict[str, Any]]:
    """
    Search for available fields by keyword.

    Args:
        query: Search keyword (e.g., "rsi", "volume", "earnings")
        asset_type: Asset type
        limit: Maximum results to return

    Returns:
        List of matching field info dicts with 'name', 'display_name', 'is_technical'
    """
    config = ASSET_CONFIG.get(asset_type, ASSET_CONFIG["stock"])
    field_class = config["field_class"]

    results = field_class.search(query)[:limit]

    fields = []
    for f in results:
        # Field value tuple: (display_name, api_field, format, is_technical, is_recommendation)
        value = f.value
        fields.append(
            {
                "name": f.name,
                "display_name": value[0] if len(value) > 0 else f.name,
                "is_technical": value[3] if len(value) > 3 else False,
            }
        )

    return fields


def get_field_categories(asset_type: str = "stock") -> dict[str, list[str]]:
    """
    Get field categories with sample fields.

    Args:
        asset_type: Asset type

    Returns:
        Dict mapping category names to lists of field names
    """
    config = ASSET_CONFIG.get(asset_type, ASSET_CONFIG["stock"])
    field_class = config["field_class"]

    category_keywords = [
        "price",
        "volume",
        "moving_average",
        "rsi",
        "macd",
        "bollinger",
        "earnings",
        "dividend",
        "market_cap",
        "sector",
        "recommend",
    ]

    categories = {}
    for keyword in category_keywords:
        fields = [f.name for f in field_class.search(keyword)[:5]]
        if fields:
            categories[keyword] = fields

    return categories


def custom_screen(
    asset_type: str = "stock",
    select_fields: list[str] | None = None,
    filters: list[dict[str, Any]] | None = None,
    sort_by: str | None = None,
    ascending: bool = False,
    limit: int = 25,
    sql: str | None = None,
) -> pd.DataFrame:
    """
    Flexible screener with custom fields and filters.

    Args:
        asset_type: Asset type
        select_fields: List of field names to return
        filters: List of filter dicts: {"field": str, "op": str, "value": any}
        sort_by: Field name to sort by
        ascending: Sort direction
        limit: Maximum results
        sql: Optional SQL query to apply to results
    """
    config = ASSET_CONFIG.get(asset_type, ASSET_CONFIG["stock"])
    screener = config["screener_class"]()

    # Select fields
    if select_fields:
        fields_to_select = []
        for fname in select_fields:
            field = get_field_enum(fname, asset_type)
            if field:
                fields_to_select.append(field)
        if fields_to_select:
            screener.select(*fields_to_select)

    # Apply filters
    if filters:
        for f in filters:
            field_name = f.get("field")
            op = f.get("op", ">=")
            value = f.get("value")

            field = get_field_enum(field_name, asset_type)
            if not field:
                continue

            filter_op = FILTER_OP_MAP.get(op)
            if not filter_op:
                continue

            screener.where(field, filter_op, value)

    # Apply sorting
    if sort_by:
        sort_field = get_field_enum(sort_by, asset_type)
        if sort_field:
            screener.sort_by(sort_field, ascending=ascending)

    df = screener.get()

    if sql:
        from tvscreener.lib.query import EdgeQueryClient

        with EdgeQueryClient() as client:
            df = client.query_sql(df, sql)

    return df.head(limit)


def screen_stocks(
    min_price: float | None = None,
    max_price: float | None = None,
    min_market_cap: float | None = None,
    max_market_cap: float | None = None,
    sectors: list[str] | None = None,
    sort_by: str = "market_cap",
    ascending: bool = False,
    limit: int = 25,
) -> pd.DataFrame:
    """
    Screen stocks with common filters.

    Args:
        min_price: Minimum stock price
        max_price: Maximum stock price
        min_market_cap: Minimum market cap
        max_market_cap: Maximum market cap
        sectors: List of sectors to filter
        sort_by: Sort field ('market_cap', 'price', 'volume', 'change')
        ascending: Sort direction
        limit: Maximum results

    Returns:
        DataFrame with matching stocks
    """
    ss = tvs.StockScreener()

    ss.select(
        StockField.NAME,
        StockField.PRICE,
        StockField.CHANGE_PERCENT,
        StockField.VOLUME,
        StockField.MARKET_CAPITALIZATION,
        StockField.PRICE_TO_EARNINGS_RATIO_TTM,
        StockField.SECTOR,
    )

    if min_price is not None:
        ss.where(StockField.PRICE, FilterOperator.ABOVE_OR_EQUAL, min_price)
    if max_price is not None:
        ss.where(StockField.PRICE, FilterOperator.BELOW_OR_EQUAL, max_price)
    if min_market_cap is not None:
        ss.where(StockField.MARKET_CAPITALIZATION, FilterOperator.ABOVE_OR_EQUAL, min_market_cap)
    if max_market_cap is not None:
        ss.where(StockField.MARKET_CAPITALIZATION, FilterOperator.BELOW_OR_EQUAL, max_market_cap)
    if sectors:
        for s in sectors:
            ss.where(StockField.SECTOR, FilterOperator.MATCH, s)

    sort_field_map = {
        "market_cap": StockField.MARKET_CAPITALIZATION,
        "price": StockField.PRICE,
        "volume": StockField.VOLUME,
        "change": StockField.CHANGE_PERCENT,
    }
    if sort_by in sort_field_map:
        ss.sort_by(sort_field_map[sort_by], ascending=ascending)

    return ss.get().head(limit)


def screen_crypto(
    min_volume_24h: float | None = None,
    min_market_cap: float | None = None,
    sort_by: str = "market_cap",
    ascending: bool = False,
    limit: int = 25,
) -> pd.DataFrame:
    """
    Screen cryptocurrencies with common filters.

    Args:
        min_volume_24h: Minimum 24h trading volume
        min_market_cap: Minimum market cap
        sort_by: Sort field ('market_cap', 'volume', 'change')
        ascending: Sort direction
        limit: Maximum results

    Returns:
        DataFrame with matching cryptocurrencies
    """
    cs = tvs.CryptoScreener()

    cs.select(
        CryptoField.NAME,
        CryptoField.PRICE,
        CryptoField.CHANGE_PERCENT,
        CryptoField.VOLUME_24H_IN_USD,
        CryptoField.MARKET_CAPITALIZATION,
    )

    if min_volume_24h is not None:
        cs.where(CryptoField.VOLUME_24H_IN_USD, FilterOperator.ABOVE_OR_EQUAL, min_volume_24h)
    if min_market_cap is not None:
        cs.where(CryptoField.MARKET_CAPITALIZATION, FilterOperator.ABOVE_OR_EQUAL, min_market_cap)

    sort_field_map = {
        "market_cap": CryptoField.MARKET_CAPITALIZATION,
        "volume": CryptoField.VOLUME_24H_IN_USD,
        "change": CryptoField.CHANGE_PERCENT,
    }
    if sort_by in sort_field_map:
        cs.sort_by(sort_field_map[sort_by], ascending=ascending)

    return cs.get().head(limit)


def screen_forex(min_volume: float | None = None, limit: int = 25) -> pd.DataFrame:
    """
    Screen forex currency pairs.

    Args:
        min_volume: Minimum trading volume
        limit: Maximum results

    Returns:
        DataFrame with matching forex pairs
    """
    fs = tvs.ForexScreener()

    fs.select(ForexField.NAME, ForexField.PRICE, ForexField.CHANGE_PERCENT, ForexField.VOLUME)

    if min_volume is not None:
        fs.where(ForexField.VOLUME, FilterOperator.ABOVE_OR_EQUAL, min_volume)

    return fs.get().head(limit)


def scan_opportunities(
    asset_type: str = "forex",
    universe: str | None = None,
    pairs: list[str] | None = None,
    timeframes: str | None = None,
    min_volume: float | None = None,
    max_atr: float | None = None,
    min_ma_score: float | None = None,
    min_roc: float | None = None,
    contract_type: str | None = None,
    include_atr: bool = False,
    include_rsi: bool = False,
    trend_weight: float | None = None,
    ma_weight: float | None = None,
    osc_weight: float | None = None,
    roc_weight: float | None = None,
    timeframe_weights: str | None = None,
    confluence_grade: str | None = None,
    min_confluence: int | None = None,
    min_rvol: float | None = None,
    require_volume_spike: bool = False,
    risk_per_trade: float | None = None,
    atr_multiplier: float | None = None,
    min_risk_reward: float | None = None,
    account_balance: float | None = None,
    pip_value: float | None = None,
    detailed: bool = False,
    matrix: bool = False,
    limit: int | None = None,
    show_risk: bool = False,
    output: str | None = None,
    sql: str | None = None,
    filters: list[str] | None = None,
) -> pd.DataFrame | str:
    """
    Run the opportunity scanner for high-confluence setups across multiple timeframes.
    """
    from io import StringIO

    from rich.console import Console

    output_stream = StringIO()
    console = Console(file=output_stream, force_terminal=False, width=100)
    controller = ScreenerController(console=console)

    request = ScanRequest(
        assets=AssetSelection(
            scanner="opportunity",
            asset_type=asset_type,
            universe=universe,
            pairs=pairs,
            timeframes=timeframes,
            min_volume=min_volume,
            max_atr=max_atr,
            min_ma_score=min_ma_score,
            min_roc=min_roc,
            contract_type=contract_type,
            include_atr=include_atr,
            include_rsi=include_rsi,
            min_rvol=min_rvol,
            require_volume_spike=require_volume_spike,
        ),
        scoring=ScoringConfig(
            opportunity_trend_weight=trend_weight,
            opportunity_ma_weight=ma_weight,
            opportunity_osc_weight=osc_weight,
            opportunity_roc_weight=roc_weight,
            opportunity_timeframe_weights=timeframe_weights,
        ),
        risk=RiskConfig(
            risk_per_trade_pct=risk_per_trade,
            atr_multiplier=atr_multiplier,
            min_risk_reward_ratio=min_risk_reward,
            account_balance=account_balance,
            pip_value=pip_value,
        ),
        output=OutputConfig(
            detailed=detailed,
            matrix=matrix,
            limit=limit,
            show_risk=show_risk,
            output=output,
            sql=sql,
            filters=filters or [],
            confluence_grade=confluence_grade,
            min_opportunity_confluence=min_confluence,
        ),
    )
    results, screener = controller.get_opportunity_results(request)

    if output:
        metadata = controller._build_opportunity_metadata(request)
        controller._export_results(screener, output, metadata)

    if detailed or matrix:
        screener.print_summary(
            detailed=detailed,
            matrix=matrix,
            limit=limit,
            show_risk=show_risk,
        )
        return output_stream.getvalue()

    if output:
        display_df = results.head(limit) if limit is not None else results
        return output_stream.getvalue() + "\n\n" + display_df.to_markdown(index=False)

    return results.head(limit) if limit is not None else results


def scan_strategies(
    asset_type: str = "forex",
    universe: str | None = None,
    pairs: list[str] | None = None,
    timeframes: str | None = None,
    strategy: str = "all",
    direction: str = "all",
    min_confluence: int | None = None,
    trend_threshold: float | None = None,
    mr_threshold: float | None = None,
    min_roc: float | None = None,
    min_volume: float | None = None,
    max_atr: float | None = None,
    min_ma_score: float | None = None,
    mr_signals: list[str] | None = None,
    contract_type: str | None = None,
    include_atr: bool = False,
    include_rsi: bool = False,
    min_tf_alignment: int | None = None,
    require_momentum: bool = False,
    min_rvol: float | None = None,
    require_volume_spike: bool = False,
    risk_per_trade: float | None = None,
    atr_multiplier: float | None = None,
    min_risk_reward: float | None = None,
    account_balance: float | None = None,
    pip_value: float | None = None,
    trend_weight: float | None = None,
    ma_weight: float | None = None,
    osc_weight: float | None = None,
    roc_weight: float | None = None,
    timeframe_weights: str | None = None,
    rsi_lower: float | None = None,
    rsi_upper: float | None = None,
    detailed: bool = False,
    matrix: bool = False,
    limit: int | None = None,
    show_risk: bool = False,
    output: str | None = None,
    sql: str | None = None,
    filters: list[str] | None = None,
) -> pd.DataFrame | str:
    """
    Run the strategy scanner to find specific trade setups (Trend, Mean Reversion, etc).
    """
    from io import StringIO

    from rich.console import Console

    output_stream = StringIO()
    console = Console(file=output_stream, force_terminal=False, width=100)
    controller = ScreenerController(console=console)

    request = ScanRequest(
        assets=AssetSelection(
            scanner="strategy",
            asset_type=asset_type,
            universe=universe,
            pairs=pairs,
            timeframes=timeframes,
            strategy=strategy,
            contract_type=contract_type,
            min_volume=min_volume,
            max_atr=max_atr,
            min_ma_score=min_ma_score,
            min_roc=min_roc,
            include_atr=include_atr,
            include_rsi=include_rsi,
            min_rvol=min_rvol,
            require_volume_spike=require_volume_spike,
        ),
        scoring=ScoringConfig(
            filter_direction=direction,
            min_confluence=min_confluence,
            trend_threshold=trend_threshold,
            mr_threshold=mr_threshold,
            rsi_lower=rsi_lower,
            rsi_upper=rsi_upper,
            mr_signal=mr_signals or [],
            min_tf_alignment=min_tf_alignment,
            require_momentum=require_momentum,
            opportunity_trend_weight=trend_weight,
            opportunity_ma_weight=ma_weight,
            opportunity_osc_weight=osc_weight,
            opportunity_roc_weight=roc_weight,
            opportunity_timeframe_weights=timeframe_weights,
        ),
        risk=RiskConfig(
            risk_per_trade_pct=risk_per_trade,
            atr_multiplier=atr_multiplier,
            min_risk_reward_ratio=min_risk_reward,
            account_balance=account_balance,
            pip_value=pip_value,
        ),
        output=OutputConfig(
            detailed=detailed,
            matrix=matrix,
            limit=limit,
            show_risk=show_risk,
            output=output,
            sql=sql,
            filters=filters or [],
        ),
    )
    results, scanner = controller.get_strategy_results(request)

    if output:
        metadata = controller._build_strategy_metadata(request)
        controller._export_results(scanner, output, metadata)

    if detailed or matrix:
        scanner.print_summary(
            detailed=detailed,
            matrix=matrix,
            limit=limit,
            show_risk=show_risk,
        )
        return output_stream.getvalue()

    if output:
        display_df = results.head(limit) if limit is not None else results
        return output_stream.getvalue() + "\n\n" + display_df.to_markdown(index=False)

    return results.head(limit) if limit is not None else results


def save_mcp_config(path: str, config_data: dict[str, Any]) -> str:
    """Save configuration to a YAML file."""
    try:
        validated_path = validate_path(path, allow_tmp=True)
    except ValueError as e:
        return f"Error: {e}"

    if not validated_path.parent.exists():
        validated_path.parent.mkdir(parents=True, exist_ok=True)
    with open(validated_path, "w") as f:
        yaml.safe_dump(config_data, f)
    return f"Configuration saved to {path}"


def load_mcp_config(path: str) -> dict[str, Any]:
    """Load configuration from a YAML file."""
    try:
        validated_path = validate_path(path, allow_tmp=True)
    except ValueError:
        return {}

    if not validated_path.exists():
        return {}

    with open(validated_path) as f:
        return yaml.safe_load(f) or {}


def inspect_file(
    path: str, head: int = 10, metadata_only: bool = False, sql: str | None = None
) -> str:
    """
    Inspect a Parquet file with embedded metadata.
    """
    from io import StringIO

    from rich.console import Console

    from tvscreener.lib.inspect_utils import inspect_parquet
    from tvscreener.lib.orchestrator import OutputConfig, ScanRequest, ScreenerController

    try:
        validated_path = validate_path(path, allow_tmp=True)
    except ValueError as e:
        return f"Error: {e}"

    output = StringIO()
    console = Console(file=output, force_terminal=False, width=100)

    if sql:
        controller = ScreenerController(console=console)
        request = ScanRequest(
            output=OutputConfig(
                output=str(validated_path),
                sql=sql,
                head=head,
                metadata_only=metadata_only,
            )
        )
        controller.run_inspect_parquet(request)
    else:
        inspect_parquet(
            str(validated_path), head=head, metadata_only=metadata_only, console=console
        )

    return output.getvalue()


def query_historical_scan(sql: str, file_path: str) -> str:
    """
    Execute a DuckDB SQL query against a previously exported Parquet file.
    Use this instead of running a new scan when you already have the data.

    Args:
        sql: The DuckDB SQL query to execute. The table name is 'df' (e.g. 'SELECT * FROM df').
        file_path: The path to the parquet file (e.g. 'exports/gold/my_scan.parquet').
    """
    from tvscreener.lib.query import EdgeQueryClient

    try:
        # Query the file
        with EdgeQueryClient() as client:
            df = client.query_sql(file_path, sql)

        if df.empty:
            return "Query returned no results."

        return f"Query successful ({len(df)} rows):\n\n" + df.to_markdown(index=False)
    except Exception as e:
        return f"Query failed: {e}"


def lakehouse_list_tables() -> str:
    """
    List all tables in the Iceberg catalog.
    """
    try:
        catalog = get_catalog()

        # Try to list namespaces first to find all tables
        all_tables = []
        try:
            namespaces = catalog.list_namespaces()
            for ns in namespaces:
                # ns is a tuple like ('tvscreener',)
                all_tables.extend(catalog.list_tables(ns))
        except Exception:
            # Fallback to default tvscreener namespace if list_namespaces fails
            all_tables = catalog.list_tables("tvscreener")

        if not all_tables:
            return "No tables found in the lakehouse catalog."

        result = "Available lakehouse tables:\n"
        for identifier in all_tables:
            # identifier is a tuple like ('tvscreener', 'bronze')
            table_name = ".".join(identifier)
            result += f"- {table_name}\n"
        return result
    except Exception as e:
        return f"Error listing tables: {e}"


def lakehouse_get_schema(table_name: str) -> str:
    """
    Get the schema of a specific lakehouse table.

    Args:
        table_name: Full identifier of the table (e.g., 'tvscreener.bronze')
    """
    from pyiceberg.exceptions import NoSuchTableError

    try:
        catalog = get_catalog()
        table = catalog.load_table(table_name)
        schema = table.schema()

        result = f"Schema for {table_name}:\n\n"
        result += "| Field | Type | Required |\n"
        result += "|-------|------|----------|\n"
        for field in schema.fields:
            result += f"| {field.name} | {field.field_type} | {field.required} |\n"
        return result
    except NoSuchTableError:
        return f"Error: Table '{table_name}' not found."
    except Exception as e:
        return f"Error getting schema for {table_name}: {e}"


def lakehouse_maintenance(table_name: str, operation: str, **kwargs) -> str:
    """
    Perform maintenance operations on a lakehouse table.

    Args:
        table_name: Full identifier of the table
        operation: 'expire_snapshots' or 'remove_orphan_files'
        **kwargs: Additional arguments for the operation
    """
    from pyiceberg.table.maintenance import MaintenanceTable

    try:
        catalog = get_catalog()
        table = catalog.load_table(table_name)
        maintenance = MaintenanceTable(table)

        if operation == "expire_snapshots":
            older_than_days = kwargs.get("older_than_days", 7)
            from datetime import datetime, timedelta, timezone

            expire_timestamp = datetime.now(timezone.utc) - timedelta(days=older_than_days)
            maintenance.expire_snapshots().older_than(expire_timestamp).commit()
            return f"Successfully executed expire_snapshots on {table_name} (older than {older_than_days} days)."

        elif operation == "remove_orphan_files":
            maintenance.remove_orphan_files().commit()
            return f"Successfully executed remove_orphan_files on {table_name}."

        else:
            return f"Error: Unsupported maintenance operation '{operation}'."

    except Exception as e:
        return f"Error performing maintenance on {table_name}: {e}"
