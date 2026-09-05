## tvscreener extensions

This directory is a standalone `uv` project that packages workflow/orchestration helpers and
extensions-owned pipelines as an extensions distribution (`tvscreener-ext`) that depends on an installed
upstream `tvscreener`.

### Run commands (uv-only)

From the repo root:

```bash
uv run --project extensions --help
uv run --project extensions tvscreener-ext-scan --help
```

Prefect support:

```bash
uv run --project extensions --extra prefect tvscreener-prefectctl --help
```

### Essential runset

```bash
uv run --project extensions --extra prefect tvscreener-ext-validate --runner prefect --mode both
```

### Upstream resolution

These CLIs force `import tvscreener` to resolve from site-packages so a repo checkout does not shadow the
installed upstream package.
