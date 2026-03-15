## Proposal: Evaluate alternative workflow engines for `PipelineRunSpec`

We currently run scans via a Prefect-backed runner. This change package documents evaluation criteria and compares a few lightweight workflow engines that could also execute `PipelineRunSpec` runs.

Scope:
- Documentation-only evaluation
- No runtime/engine migration

Candidates (requested):
- Dagu (`dagu-org/dagu`)
- Hatchet (`hatchet-dev/hatchet`)
- Windmill (`windmill-labs/windmill`)
