## Design: Fix TradingView scan batching (range must cover tickers)

### Background
TradingView `/scan` uses a request payload shape like:
- `symbols: { tickers: [...] }` for explicit symbol lists
- `range: [from,to]` to control how many rows are returned

Observed behavior:
- even with `symbols.tickers`, TradingView returns only the requested `range` slice (default is 150 rows).

### Design

#### Rule: auto-range for explicit tickers
When `symbols.tickers` is non-empty and the range is still the **default**, the client should set:
- `payload["range"] = [0, len(tickers)]`

This ensures the response contains one row per ticker (subject to TradingView availability).

#### Preserve explicit range overrides
If a user calls `set_range(...)`, we assume they are intentionally paginating or sampling and we do not override.

Implementation detail:
- Track whether `set_range(...)` was called by the user vs the constructor default.

### Verification
- Unit test: with 200 tickers and default range, the outgoing payload must have `range=[0,200]`.
- Optional probe (manual): confirm TradingView returns all rows when range is sized to tickers length.

