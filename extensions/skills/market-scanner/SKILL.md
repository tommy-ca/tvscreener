# market-scanner

## Description
Guided configuration and execution of market scans for Forex, Crypto, and Stocks using the `tvscreener-ext-scan` tool.

## Instructions
When this skill is activated, you MUST guide the user through the scan configuration process:

1.  **Asset Identification**:
    - Ask the user which asset type they want to scan: `forex`, `crypto`, or `stock`.
    - If `crypto` is chosen, ask for the instrument type: `spot` or `perp`.

2.  **Universe Selection**:
    - Based on the asset type, suggest valid universes:
        - **Forex**: `majors`, `minors`.
        - **Crypto**: `majors`, `minors`, `top100`, `cs_momentum`.
        - **Stock**: `market_risk`.
    - Ask the user to select one or provide specific tickers.

3.  **Scan Configuration**:
    - Ask for the scanner type: `opportunity` (data + analytics) or `strategy` (analytics only).
    - If `strategy` is chosen, ask for the strategy name: `trend`, `mean_reversion`, `hybrid`, `confluence`.
    - Ask for timeframes (comma-separated, e.g., `240,60,15`).

4.  **Execution Mode**:
    - Ask whether to run `local` or via `prefect` orchestration.
    - If `prefect` is chosen, verify the server is running (`curl http://127.0.0.1:4200/api/health`).

5.  **Execution**:
    - Construct the `tvscreener-ext-scan` command.
    - Confirm the command with the user before executing.
    - Example: `uv run --project extensions tvscreener-ext-scan scan --runner local --scanner opportunity --asset-type forex --universe majors --timeframes 240,60,15 --matrix`.

6.  **Post-Scan**:
    - Inform the user of the output location (`artifacts/runs/<hash>/`).
    - Offer to display the result matrix if `--matrix` was used.

## Available Resources
- `tvscreener-ext-scan`: The primary CLI tool for executing scans.
- `docs/guide/extensions.md`: Documentation for advanced scan parameters.
- `extensions/src/tvscreener_ext/config/universes.py`: List of valid universe identifiers.
