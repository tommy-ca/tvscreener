## 1. Settings model (grouped nested config)
- [x] 1.1 Add `LakehouseSettings` nested group to `tvscreener/config/settings.py`
  - [x] Local catalog model (base_dir/catalog_db/warehouse_dir)
  - [x] Remote catalog model (uri/warehouse)
  - [x] Mode validator to require remote config when `mode=remote`
- [x] 1.2 Update `tvscreener/config/loader.py` to support flat YAML keys like `lakehouse_catalog_mode`

## 2. Lakehouse manager (config-driven)
- [x] 2.1 Refactor `tvscreener/lib/lakehouse/manager.py` to load catalog settings from `load_settings()`
- [x] 2.2 Add `get_manager(config_path=...)` to initialize singleton from CLI YAML path
- [x] 2.3 Update `tvscreener/lib/lakehouse/__init__.py` to accept `get_catalog(config_path=...)`

## 3. CLI plumbing (layered config end-to-end)
- [x] 3.1 Initialize lakehouse manager early in `tvscreener/lib/orchestrator.py` using `args.config`
- [x] 3.2 Ensure maintenance uses the same config path

## 4. Defaults + documentation
- [x] 4.1 Update `tvscreener.yaml` with a `lakehouse` group and commented remote example
- [x] 4.2 Update `docs/plans/2026-03-03-multi-asset-iceberg-catalog-and-table-design-plan.md` with config examples

## 5. Verification
- [ ] 5.1 Add a unit test that `get_manager(config_path=...)` initializes local defaults and does not crash
- [ ] 5.2 Add a unit test that remote mode validates required fields (missing uri/warehouse fails)
- [ ] 5.3 Smoke test CLI:
  - [x] `uv run tvscreener-scan query tvscreener.gold --sql "SELECT 1" --head 1`

