## Design: Runner requirements and engine comparison

### What we need from a workflow engine

Minimum (must-have):
- Submit a single-run job that executes `tvscreener-scan` commands (or runs `PipelineRunSpec` directly)
- Cron / scheduled runs
- Retries + failure visibility
- Concurrency limits (at least global)
- Persist logs/artifacts to a predictable directory

Nice-to-have:
- Web UI (run history, logs, parameters)
- Multi-worker / distributed execution
- RBAC + auth
- Event triggers

### Candidate comparison (high-level)

#### Dagu (dagu-org/dagu)
- Model: declarative YAML DAGs; runs shell/scripts/containers; web UI
- Ops: single self-contained binary; file-based storage; optional distributed mode; “zero-ops” posture
- Scheduling: cron supported
- Security: RBAC / OIDC / API keys available per docs
- License: GPL-3.0 (copyleft)
- Fit for tvscreener: strong if we want *CLI-first orchestration* with minimal infra, but license constraints likely dominate

#### Hatchet (hatchet-dev/hatchet)
- Model: durable task queue + workflows (DAGs/durable orchestration) via SDKs (Python/TS/Go)
- Ops: requires Postgres; provides dashboard/observability/alerting
- Scheduling: cron + delayed runs supported
- Flow control: concurrency + rate limiting + worker affinity
- License: MIT
- Fit for tvscreener: good for embedding execution in an app/service; heavier than Dagu but permissive license

#### Windmill (windmill-labs/windmill)
- Model: platform for scripts->jobs/workflows/UIs; Postgres-backed queue; web IDE; strong UI layer
- Ops: larger surface area (API servers + workers + DB); supports many runtimes; sandboxing
- Scheduling/triggers: cron/webhooks/routes/Kafka/etc.
- License: AGPL for OSS build; “Community Edition” binaries include non-OSS components under additional terms
- Fit for tvscreener: powerful if we want internal tooling/UI around scans; likely overkill for pure scanning and has license considerations

### Recommended next experiments (no migration)

1) If we want “lightweight orchestration around `tvscreener-scan` CLI”:
   - Prototype with Dagu *only if license is acceptable*.

2) If we want “durable queue + strong flow control + permissive license”:
   - Prototype Hatchet with a minimal worker that executes `PipelineRunSpec` runs (call into existing `LocalRunner`/`PrefectRunner` logic or shell out).

3) If we want “UI-first internal platform”:
   - Prototype Windmill only after confirming license/compliance posture.
