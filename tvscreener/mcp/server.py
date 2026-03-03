"""
MCP server for tvscreener.

Exposes market screener functionality via the Model Context Protocol.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from . import tools
from .tools import (
    custom_screen,
    get_field_categories,
    inspect_file,
    load_mcp_config,
    save_mcp_config,
    scan_opportunities,
    scan_strategies,
    screen_crypto,
    screen_forex,
    screen_stocks,
    search_fields,
)

mcp = FastMCP(
    "tvscreener",
    instructions=(
        "Query market screener for stocks, crypto, and forex via tvscreener library. "
        "Use discover_fields to find available fields, then use custom_query for flexible filtering."
    ),
)


# =============================================================================
# SCANNER TOOLS
# =============================================================================


@mcp.tool()
def scanner_opportunities(
    asset_type: str = "forex",
    universe: str | None = None,
    pairs: str | None = None,
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
) -> str:
    """
    Run high-confluence opportunity scanner across multiple timeframes.

    Args:
        asset_type: "forex", "stocks", "crypto", "commodity"
        universe: "majors", "minors", "all" (for forex)
        pairs: Comma-separated list of symbols (e.g., "EURUSD,GBPUSD")
        timeframes: Comma-separated list of timeframes (e.g., "15,60,240")
        min_volume: Minimum average volume
        max_atr: Maximum ATR (volatility filter)
        min_ma_score: Minimum Moving Average score (-2.0 to 2.0)
        min_roc: Minimum Rate of Change
        contract_type: "spot", "cfd", "spreadbet", "all"
        include_atr: Include ATR values in results
        include_rsi: Include RSI values in results
        trend_weight: Scoring weight for trend (0.0 to 1.0)
        ma_weight: Scoring weight for MAs (0.0 to 1.0)
        osc_weight: Scoring weight for oscillators (0.0 to 1.0)
        roc_weight: Scoring weight for ROC (0.0 to 1.0)
        timeframe_weights: Per-TF scoring weights (e.g., "240:0.5,60:0.3,15:0.2")
        confluence_grade: Filter by grade ("A+", "A", "B", "C", "D", "F")
        min_confluence: Minimum total confluence score
        min_rvol: Minimum relative volume (1.0 = normal)
        risk_per_trade: Risk % per trade (e.g., 1.0)
        atr_multiplier: ATR multiplier for stop loss (e.g., 2.0)
        min_risk_reward: Minimum risk:reward ratio (e.g., 1.5)
        account_balance: Balance for position sizing (e.g., 10000.0)
        pip_value: Pip value for position sizing (default 10.0)
        detailed: Show detailed per-pair breakdown with TF analysis
        matrix: Show confluence matrix view for all pairs
        limit: Number of results to return
        show_risk: Include risk management fields (SL/TP/RR/Size)
        output: File path to save results (csv, json, parquet, xml)
        sql: DuckDB SQL string to filter results
        filters: List of DuckDB/Python expression filters
    """
    pair_list = [p.strip() for p in pairs.split(",")] if pairs else None

    try:
        results = scan_opportunities(
            asset_type=asset_type,
            universe=universe,
            pairs=pair_list,
            timeframes=timeframes,
            min_volume=min_volume,
            max_atr=max_atr,
            min_ma_score=min_ma_score,
            min_roc=min_roc,
            contract_type=contract_type,
            include_atr=include_atr,
            include_rsi=include_rsi,
            trend_weight=trend_weight,
            ma_weight=ma_weight,
            osc_weight=osc_weight,
            roc_weight=roc_weight,
            timeframe_weights=timeframe_weights,
            confluence_grade=confluence_grade,
            min_confluence=min_confluence,
            min_rvol=min_rvol,
            risk_per_trade=risk_per_trade,
            atr_multiplier=atr_multiplier,
            min_risk_reward=min_risk_reward,
            account_balance=account_balance,
            pip_value=pip_value,
            detailed=detailed,
            matrix=matrix,
            limit=limit,
            show_risk=show_risk,
            output=output,
            sql=sql,
            filters=filters,
        )

        if isinstance(results, str):
            return results

        df = results
        if df.empty:
            return "No opportunities found."

        return df.to_markdown(index=False)
    except Exception as e:
        return f"Error running opportunity scanner: {e}"


@mcp.tool()
def scanner_strategies(
    asset_type: str = "forex",
    universe: str | None = None,
    pairs: str | None = None,
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
    mr_signals: str | None = None,
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
) -> str:
    """
    Run strategy-specific scanner (Trend, Mean Reversion, etc).

    Args:
        asset_type: "forex", "stocks", "crypto", "commodity"
        universe: "majors", "minors", "all"
        pairs: Comma-separated symbols
        timeframes: Comma-separated timeframes (e.g., "15,60,240")
        strategy: "all", "trend", "mean_reversion", "hybrid", "breakout", "confluence"
        direction: "long", "short", "all"
        min_confluence: Minimum confluence score
        trend_threshold: Trend score threshold
        mr_threshold: Mean reversion score threshold
        min_roc: Minimum Rate of Change
        min_volume: Minimum average volume
        max_atr: Maximum ATR
        min_ma_score: Minimum MA score
        mr_signals: Comma-separated signals (e.g., "rsi_oversold,rsi_overbought")
        contract_type: "spot", "cfd", "spreadbet", "all"
        include_atr: Include ATR fields
        include_rsi: Include RSI fields
        min_tf_alignment: Required alignment across timeframes (1, 2, or 3)
        require_momentum: Require ROC to align with direction
        min_rvol: Minimum relative volume (1.0 = normal)
        require_volume_spike: Require volume > 1.5x average
        risk_per_trade: Risk % per trade
        atr_multiplier: ATR multiplier for stop loss
        min_risk_reward: Minimum risk:reward ratio
        account_balance: Balance for position sizing
        pip_value: Pip value for position sizing (default 10.0)
        trend_weight: Scoring weight for trend (0.0 to 1.0)
        ma_weight: Scoring weight for MAs (0.0 to 1.0)
        osc_weight: Scoring weight for oscillators (0.0 to 1.0)
        roc_weight: Scoring weight for ROC (0.0 to 1.0)
        timeframe_weights: Per-TF scoring weights (e.g., "240:0.5,60:0.3,15:0.2")
        rsi_lower: Lower RSI threshold for oversold signals
        rsi_upper: Upper RSI threshold for overbought signals
        detailed: Show detailed per-pair breakdown with TF analysis
        matrix: Show confluence matrix view for all pairs
        limit: Number of results to return
        show_risk: Include risk management fields (SL/TP/RR/Size)
        output: File path to save results
        sql: DuckDB SQL string to filter results
        filters: List of DuckDB/Python expression filters
    """
    pair_list = [p.strip() for p in pairs.split(",")] if pairs else None
    signal_list = [s.strip() for s in mr_signals.split(",")] if mr_signals else None

    try:
        results = scan_strategies(
            asset_type=asset_type,
            universe=universe,
            pairs=pair_list,
            timeframes=timeframes,
            strategy=strategy,
            direction=direction,
            min_confluence=min_confluence,
            trend_threshold=trend_threshold,
            mr_threshold=mr_threshold,
            min_roc=min_roc,
            min_volume=min_volume,
            max_atr=max_atr,
            min_ma_score=min_ma_score,
            mr_signals=signal_list,
            contract_type=contract_type,
            include_atr=include_atr,
            include_rsi=include_rsi,
            min_tf_alignment=min_tf_alignment,
            require_momentum=require_momentum,
            min_rvol=min_rvol,
            require_volume_spike=require_volume_spike,
            risk_per_trade=risk_per_trade,
            atr_multiplier=atr_multiplier,
            min_risk_reward=min_risk_reward,
            account_balance=account_balance,
            pip_value=pip_value,
            trend_weight=trend_weight,
            ma_weight=ma_weight,
            osc_weight=osc_weight,
            roc_weight=roc_weight,
            timeframe_weights=timeframe_weights,
            rsi_lower=rsi_lower,
            rsi_upper=rsi_upper,
            detailed=detailed,
            matrix=matrix,
            limit=limit,
            show_risk=show_risk,
            output=output,
            sql=sql,
            filters=filters,
        )

        if isinstance(results, str):
            return results

        df = results
        if df.empty:
            return "No signals found."

        return df.to_markdown(index=False)
    except Exception as e:
        return f"Error running strategy scanner: {e}"


@mcp.tool()
def scanner_inspect(
    path: str, head: int = 10, metadata_only: bool = False, sql: str | None = None
) -> str:
    """
    Inspect a Parquet file or Iceberg table with embedded metadata.

    Args:
        path: Path to the parquet file (e.g., 'exports/scan.parquet') or Iceberg table identifier (e.g., 'tvscreener.gold')
        head: Number of rows to show (default 10)
        metadata_only: Only show metadata, skip data table
        sql: DuckDB SQL string to query the file/table

    Examples:
        - scanner_inspect(path="exports/my_scan.parquet")
        - scanner_inspect(path="tvscreener.gold", head=20)
        - scanner_inspect(path="tvscreener.bronze", sql="SELECT * FROM df WHERE CHANGE > 5")
    """
    try:
        return inspect_file(path, head=head, metadata_only=metadata_only, sql=sql)
    except Exception as e:
        return f"Error inspecting file: {e}"


@mcp.tool()
def config_save(path: str, data_json: str) -> str:
    """
    Save scanner configuration to a YAML file.

    Args:
        path: Path to save (e.g., "my_config.yaml")
        data_json: JSON string of configuration parameters
    """
    try:
        data = json.loads(data_json)
        return save_mcp_config(path, data)
    except Exception as e:
        return f"Error saving config: {e}"


@mcp.tool()
def config_load(path: str) -> str:
    """
    Load scanner configuration from a YAML file.

    Args:
        path: Path to load from
    """
    try:
        data = load_mcp_config(path)
        return json.dumps(data, indent=2)
    except Exception as e:
        return f"Error loading config: {e}"


@mcp.tool()
def list_scanner_options() -> str:
    """
    List valid values for scanner parameters (asset types, strategies, etc).
    Use this to discover valid inputs for scanner_opportunities and scanner_strategies.
    """
    options = {
        "asset_types": ["forex", "stocks", "crypto", "commodity", "bond", "futures", "coin"],
        "universes": {
            "forex": ["majors", "minors", "all"],
            "crypto": ["all"],
            "stocks": ["all"],
        },
        "strategies": [
            "all",
            "trend_following",
            "mean_reversion",
            "hybrid",
            "breakout",
            "confluence",
        ],
        "contract_types": ["spot", "cfd", "spreadbet", "all"],
        "directions": ["long", "short", "all"],
        "confluence_grades": ["A+", "A", "B", "C", "D", "F"],
        "timeframes": ["1", "5", "15", "60", "240", "1D", "1W", "1M"],
    }
    return json.dumps(options, indent=2)


# =============================================================================
# FIELD DISCOVERY TOOLS
# =============================================================================


@mcp.tool()
def discover_fields(search_term: str, asset_type: str = "stock", limit: int = 20) -> str:
    """
    Search for available fields/indicators by keyword.

    Use this to find field names for custom_query. There are 3500+ fields available.

    Args:
        search_term: Keyword to search (e.g., "rsi", "volume", "earnings", "dividend", "macd", "moving_average")
        asset_type: "stock", "crypto", "forex", "bond", "futures", or "coin"
        limit: Maximum results (default 20)

    Returns:
        List of matching field names and descriptions

    Examples:
        - discover_fields("rsi") -> finds RSI indicator fields
        - discover_fields("earnings") -> finds earnings-related fields
        - discover_fields("dividend") -> finds dividend fields
    """
    fields = search_fields(search_term, asset_type, limit)

    if not fields:
        return f"No fields found matching '{search_term}'"

    result = f"Found {len(fields)} fields matching '{search_term}':\n\n"
    for f in fields:
        tech_marker = " [Technical]" if f.get("is_technical") else ""
        result += f"- **{f['name']}**: {f['display_name']}{tech_marker}\n"

    return result


@mcp.tool()
def list_field_types(asset_type: str = "stock") -> str:
    """
    List available field categories with sample fields.

    Use this to explore what types of data are available before using discover_fields.

    Args:
        asset_type: "stock", "crypto", "forex", "bond", "futures", or "coin"

    Returns:
        Categories and sample field names
    """
    categories = get_field_categories(asset_type)

    result = f"Field categories for {asset_type}:\n\n"
    for category, fields in categories.items():
        result += f"**{category}**:\n"
        for f in fields:
            result += f"  - {f}\n"
        result += "\n"

    result += "\nUse discover_fields('keyword') to find more fields in each category."
    return result


# =============================================================================
# FLEXIBLE QUERY TOOL
# =============================================================================


@mcp.tool()
def custom_query(
    asset_type: str = "stock",
    fields: str | None = None,
    filters: str | None = None,
    sort_by: str | None = None,
    ascending: bool = False,
    limit: int = 25,
    sql: str | None = None,
) -> str:
    """
    Flexible query with any fields and filters.

    Use discover_fields first to find available field names.

    Args:
        asset_type: "stock", "crypto", "forex", "bond", "futures", or "coin"
        fields: Comma-separated field names to return (e.g., "NAME,PRICE,RSI,MACD_LEVEL_12_26")
                If not specified, returns default fields.
        filters: JSON array of filter conditions. Each filter has:
                 - field: Field name (use discover_fields to find names)
                 - op: Operator (">=", ">", "<=", "<", "==", "!=", "match", "in_range")
                 - value: Value to compare (use [min, max] array for in_range)

                 Example: '[{"field": "PRICE", "op": ">=", "value": 100}, {"field": "RSI", "op": "in_range", "value": [30, 70]}]'
        sort_by: Field name to sort by
        ascending: Sort direction (default False = descending)
        limit: Maximum results (default 25, max 100)
        sql: Optional DuckDB SQL query to apply to the results (e.g. 'SELECT * FROM df WHERE RSI > 70')
    """
    # Parse fields
    select_fields = None
    if fields:
        select_fields = [f.strip() for f in fields.split(",")]

    # Parse filters
    filter_list = None
    if filters:
        try:
            filter_list = json.loads(filters)
        except json.JSONDecodeError as e:
            return f"Error parsing filters JSON: {e}"

    limit = min(limit, 100)

    try:
        df = custom_screen(
            asset_type=asset_type,
            select_fields=select_fields,
            filters=filter_list,
            sort_by=sort_by,
            ascending=ascending,
            limit=limit,
            sql=sql,
        )

        if df.empty:
            return "No results found matching the criteria."

        return df.to_markdown(index=False)
    except Exception as e:
        return f"Error executing query: {e}"


# =============================================================================
# PRESET QUERY TOOLS
# =============================================================================


@mcp.tool()
def search_stocks(
    min_price: float | None = None,
    max_price: float | None = None,
    min_market_cap_billions: float | None = None,
    max_market_cap_billions: float | None = None,
    sectors: str | None = None,
    sort_by: str = "market_cap",
    limit: int = 25,
) -> str:
    """
    Screen stocks with common filters (simplified interface).

    For advanced filtering, use custom_query with discover_fields.

    Args:
        min_price: Minimum stock price in USD
        max_price: Maximum stock price in USD
        min_market_cap_billions: Minimum market cap in billions USD
        max_market_cap_billions: Maximum market cap in billions USD
        sectors: Comma-separated sectors (Technology, Healthcare, Financial, etc.)
        sort_by: Sort by 'market_cap', 'price', 'volume', or 'change'
        limit: Maximum results (default 25, max 100)
    """
    min_cap = min_market_cap_billions * 1e9 if min_market_cap_billions else None
    max_cap = max_market_cap_billions * 1e9 if max_market_cap_billions else None
    sector_list = [s.strip() for s in sectors.split(",")] if sectors else None
    limit = min(limit, 100)

    df = screen_stocks(
        min_price=min_price,
        max_price=max_price,
        min_market_cap=min_cap,
        max_market_cap=max_cap,
        sectors=sector_list,
        sort_by=sort_by,
        limit=limit,
    )

    if df.empty:
        return "No stocks found matching the criteria."

    return df.to_markdown(index=False)


@mcp.tool()
def search_crypto(
    min_volume_millions: float | None = None,
    min_market_cap_billions: float | None = None,
    limit: int = 25,
) -> str:
    """
    Screen cryptocurrencies (simplified interface).

    For advanced filtering, use custom_query with discover_fields.

    Args:
        min_volume_millions: Minimum 24h trading volume in millions USD
        min_market_cap_billions: Minimum market cap in billions USD
        limit: Maximum results (default 25, max 100)
    """
    min_vol = min_volume_millions * 1e6 if min_volume_millions else None
    min_cap = min_market_cap_billions * 1e9 if min_market_cap_billions else None
    limit = min(limit, 100)

    df = screen_crypto(min_volume_24h=min_vol, min_market_cap=min_cap, limit=limit)

    if df.empty:
        return "No cryptocurrencies found matching the criteria."

    return df.to_markdown(index=False)


@mcp.tool()
def search_forex(min_volume_millions: float | None = None, limit: int = 25) -> str:
    """
    Screen forex currency pairs.

    Args:
        min_volume_millions: Minimum trading volume in millions
        limit: Maximum results (default 25, max 100)
    """
    min_vol = min_volume_millions * 1e6 if min_volume_millions else None
    limit = min(limit, 100)

    df = screen_forex(min_volume=min_vol, limit=limit)

    if df.empty:
        return "No forex pairs found matching the criteria."

    return df.to_markdown(index=False)


@mcp.tool()
def get_top_movers(asset_type: str = "stock", direction: str = "gainers", limit: int = 10) -> str:
    """
    Get top gaining or losing assets.

    Args:
        asset_type: "stock" or "crypto"
        direction: "gainers" or "losers"
        limit: Number of results (default 10, max 50)
    """
    limit = min(limit, 50)
    ascending = direction.lower() == "losers"

    if asset_type.lower() == "crypto":
        df = screen_crypto(sort_by="change", ascending=ascending, limit=limit)
    else:
        df = screen_stocks(sort_by="change", ascending=ascending, limit=limit)

    direction_label = "Losers" if ascending else "Gainers"

    if df.empty:
        return f"No {asset_type} data available."

    return f"Top {direction_label}:\n\n" + df.to_markdown(index=False)


@mcp.tool()
def list_sectors() -> str:
    """List available stock sectors for filtering."""
    sectors = [
        "Technology",
        "Healthcare",
        "Financial",
        "Consumer Cyclical",
        "Communication Services",
        "Industrials",
        "Consumer Defensive",
        "Energy",
        "Basic Materials",
        "Real Estate",
        "Utilities",
        "Electronic Technology",
        "Technology Services",
        "Producer Manufacturing",
    ]
    return "Available sectors:\n" + "\n".join(f"  - {s}" for s in sectors)


@mcp.tool()
def list_filter_operators() -> str:
    """List available filter operators for custom_query."""
    operators = {
        ">=": "Greater than or equal",
        ">": "Greater than",
        "<=": "Less than or equal",
        "<": "Less than",
        "==": "Equal to",
        "!=": "Not equal to",
        "match": "Text contains (for text fields like SECTOR)",
        "in_range": "Value between [min, max] (e.g., RSI between 30-70)",
        "not_in_range": "Value outside [min, max]",
        "crosses": "Value crosses another",
        "crosses_up": "Value crosses above another",
        "crosses_down": "Value crosses below another",
    }

    result = "Available filter operators for custom_query:\n\n"
    for op, desc in operators.items():
        result += f"- **{op}**: {desc}\n"

    result += "\nExample filters JSON:\n"
    result += "```json\n[\n"
    result += '  {"field": "PRICE", "op": ">=", "value": 100},\n'
    result += '  {"field": "RSI", "op": "in_range", "value": [30, 70]},\n'
    result += '  {"field": "SECTOR", "op": "match", "value": "Technology"}\n'
    result += "]\n```"

    return result


@mcp.tool()
def query_historical_scan(sql: str, file_path: str) -> str:
    """
    Execute a DuckDB SQL query against a previously exported Parquet file or Iceberg table.

    Use this to analyze data you have already exported or stored in the lakehouse
    without re-running the TradingView API.

    The table name in your query should be 'df' (e.g., 'SELECT PAIR, TREND FROM df WHERE GRADE = 'A+'').

    Args:
        sql: DuckDB SQL query string
        file_path: Path to parquet file (e.g. 'exports/scan.parquet') or Iceberg identifier (e.g. 'tvscreener.gold')

    Examples:
        - query_historical_scan(sql="SELECT * FROM df LIMIT 5", file_path="tvscreener.gold")
        - query_historical_scan(sql="SELECT PAIR, CHANGE FROM df WHERE CHANGE > 2", file_path="exports/scan.parquet")
    """
    return tools.query_historical_scan(sql, file_path)


# =============================================================================
# LAKEHOUSE TOOLS
# =============================================================================


@mcp.tool()
def list_tables() -> str:
    """
    List all tables in the Iceberg lakehouse catalog.
    Use this to discover available datasets (bronze, silver, gold, etc).
    """
    return tools.lakehouse_list_tables()


@mcp.tool()
def get_schema(table_name: str) -> str:
    """
    Get the schema (fields and types) of a specific lakehouse table.

    Args:
        table_name: Full identifier of the table (e.g., 'tvscreener.bronze', 'tvscreener.silver')
    """
    return tools.lakehouse_get_schema(table_name)


@mcp.tool()
def lakehouse_maintenance(table_name: str, operation: str, older_than_days: int = 7) -> str:
    """
    Perform maintenance on a lakehouse table (snapshot expiration, orphan file removal).

    Args:
        table_name: Full identifier of the table
        operation: 'expire_snapshots' (reclaim space) or 'remove_orphan_files' (cleanup)
        older_than_days: For expire_snapshots, how many days of history to keep (default 7)
    """
    return tools.lakehouse_maintenance(table_name, operation, older_than_days=older_than_days)


def run():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    run()
