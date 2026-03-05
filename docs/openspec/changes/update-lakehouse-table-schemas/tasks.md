## 1. Document current schemas (source of truth = code)
- [ ] 1.1 Capture Bronze TradingView screener snapshot schema (required vs optional columns)
- [ ] 1.2 Capture Silver normalized schema (identity + canonical rename rules)
- [ ] 1.3 Capture Gold schema (scores + confluence + risk + UX columns)
- [ ] 1.4 Capture current partition specs + overwrite scoping logic

## 2. Define multi-dataset taxonomy + naming
- [ ] 2.1 Define `dataset_type` enum and how it maps to tables
- [ ] 2.2 Choose naming convention:
  - [ ] keep `tvscreener.{bronze,silver,gold}` as compatibility aliases, or
  - [ ] migrate to Iceberg-native `namespace.table` where **namespace encodes stage** (e.g. `tvscreener_bronze`) and **table name is dataset** (e.g. `screener_snapshot`)
- [ ] 2.3 Define shared envelope columns across all datasets
 - [ ] 2.4 Add Iceberg SQL DDL for each dataset table (schema registry)
- [ ] 2.5 Define “schema packs” for prebuilt dataset schemas:
  - [ ] DBN (Databento Binary Encoding) record families → **Silver** dataset tables
  - [ ] Cryptofeed dtype families → **Silver** dataset tables
  - [ ] TradingView `/scan` snapshot → dataset table (Bronze canonical; Silver normalized)

## 3. Schema evolution plan (implementation-ready)
- [ ] 3.1 Decide canonical column naming for key TradingView fields (`Symbol`, `Name`, `Price`, `Subtype`)
- [ ] 3.2 Resolve ROC naming mismatch (`Roc|{tf}` vs `ROC_{tf}`) and update scoring contract
- [ ] 3.3 Define per-dataset medallion schemas:
  - [ ] `screener_snapshot`
  - [ ] `market_klines` (OHLCV)
  - [ ] `market_trades`
  - [ ] `market_bbo`
  - [ ] `market_book_l2`
  - [ ] `market_book_l3`
  - [ ] `instrument_definitions`
  - [ ] `symbol_mappings`
  - [ ] derivatives-only:
    - [ ] `deriv_funding`
    - [ ] `deriv_open_interest`
    - [ ] `deriv_liquidations`
    - [ ] `deriv_greeks` (future)
- [ ] 3.4 Define analytics product schemas:
  - [ ] `signals_latest` (latest-per-entity)
  - [ ] `signals_batch` (matrix-ready rollups per run/date)

## 4. Verification plan (once implemented)
- [ ] 4.1 Schema validation: write and read each table and assert required columns exist
- [ ] 4.2 Backward compatibility: legacy queries to `tvscreener.gold` still work (if alias retained)
- [ ] 4.3 Multi-asset smoke: scan forex + stock + crypto and verify partitions/identity are correct
- [ ] 4.4 Multi-dataset smoke (once added): write trades + book + klines and confirm no schema collisions
- [ ] 4.5 Derivatives smoke (once added): write instrument defs + funding/OI and validate joins via `entity_id`

## 5. Canonical-source audit (design validation)
- [ ] 5.1 Validate Iceberg identifier semantics against PyIceberg SQL catalog docs (namespace required, dotted identifiers)
- [ ] 5.2 Validate DDL examples against Apache Iceberg Spark DDL docs (`USING iceberg`, `PARTITIONED BY`)
- [ ] 5.3 Validate TradingView `/scan` record model against a canonical reference implementation (`totalCount`, `data[]`, `s`, `d[]`)
- [ ] 5.4 Validate multi-timeframe semantics: timeframe-qualified fields (`|15`, `|60`, `|240`, …) map cleanly to our `timeframes` + `timeframe_set_id`
- [ ] 5.5 Produce an “Audit Findings” section (Confirmed / Mismatch / Follow-ups) inside `design.md`
- [ ] 5.6 Validate DBN schema pack mapping (records → dataset tables) against canonical structs/docs
- [ ] 5.7 Validate Cryptofeed dtype mapping (dtypes → dataset tables) against canonical dtype docs/types

