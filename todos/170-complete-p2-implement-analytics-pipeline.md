---
status: complete
...
- [x] `AnalyticsPipeline` supports `.sql(template, params, **kwargs)`.
- [x] `AnalyticsPipeline` supports `.transform(func)` where `func` is narwhalified.
- [x] Uses MiniJinja for all SQL templating.
- [x] Interleaving SQL -> Python -> SQL works without explicit materialization.
- [x] Final output can be materialized as Pandas or Polars DataFrames.
- [x] Unit tests demonstrate a 3+ step pipeline via `uv run pytest`.


## Work Log

### 2026-03-02 - Initial Creation

**By:** Antigravity

**Actions:**
- Created todo based on architectural research for unified pipelines.
