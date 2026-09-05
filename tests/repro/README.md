## Repro scripts (not pytest)

This directory contains **manual repro** scripts that are useful for investigating engine behavior or security
edge-cases. These files are intentionally **not** collected by pytest.

Run them explicitly with `uv`:

```bash
uv run python tests/repro/<area>/repro_*.py
```

