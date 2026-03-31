## ADDED Requirements

### Requirement: Extensions distribution depends on installed upstream
The system SHALL provide a separate extensions distribution that runs against an installed upstream `tvscreener`
package.

#### Scenario: Extensions run without repo checkout
- **GIVEN** an environment with only installed packages
- **WHEN** the operator installs `tvscreener` and the extensions distribution
- **THEN** workflows run without cloning this repository

#### Scenario: Upstream version includes required workflow surface area
- **GIVEN** the extensions workflows require a `tvscreener-scan`-equivalent CLI and/or pipeline runner modules
- **WHEN** an operator installs `tvscreener` from the package index
- **THEN** the installed upstream version MUST include the required entrypoints/modules
- **OR** the extensions distribution MUST provide those capabilities itself without importing repo-local sources

#### Scenario: Extensions prefer upstream when available
- **GIVEN** upstream `tvscreener` ships the pipeline runner + lakehouse + Prefect runner modules
- **WHEN** the operator installs upstream from the package index
- **THEN** extensions import and use upstream implementations
- **AND** extensions do not carry duplicate copies of core pipeline logic

#### Scenario: Extensions do not import repo-local `tvscreener`
- **GIVEN** an operator runs extensions from within a clone of this repo
- **WHEN** they execute `uv run --project extensions ...`
- **THEN** Python resolves `import tvscreener` from site-packages (the installed upstream distribution)
- **AND** extensions do not rely on repo-local paths (no `sys.path` insertion of the repo root)

#### Scenario: Extensions fail fast on repo-source import
- **GIVEN** the operator runs extensions from the repo root
- **WHEN** `import tvscreener` would resolve to `<repo>/tvscreener/...`
- **THEN** extensions raise a clear error instructing the operator to install upstream and re-run

#### Scenario: Repo-local upstream remains unchanged
- **GIVEN** this repository contains an in-tree copy of upstream `tvscreener/`
- **WHEN** orchestration, lakehouse, or analytics changes are required
- **THEN** the changes are implemented in `extensions/` (or upstream is updated at the source)

#### Scenario: Extensions do not rely on repo-local changes
- **GIVEN** an operator runs extensions from within a clone of this repo
- **WHEN** upstream `tvscreener` is installed from the package index
- **THEN** the behavior of `tvscreener-ext-*` does not depend on modifications to the repo-local `tvscreener/` tree
- **AND** extensions enforce this by failing fast if `import tvscreener` resolves to `<repo>/tvscreener/...`

### Requirement: Extensions keep workflow dependencies optional
The extensions distribution SHOULD group optional workflow dependencies as extras.

#### Scenario: Prefect is an optional extra
- **GIVEN** an operator installs the extensions distribution without extras
- **WHEN** they run non-Prefect commands
- **THEN** Prefect is not required

#### Scenario: Prefect is enabled via an extra
- **WHEN** an operator installs with the Prefect extra
- **THEN** Prefect orchestration CLIs and flows run successfully

### Requirement: Essential pipelines are reproducible under Prefect
Extensions SHALL provide a reproducible runset for essential universes.

#### Scenario: Full refresh writes Iceberg then analytics outputs
- **WHEN** an operator runs the essential runset with `pipeline_mode=both`
- **THEN** Iceberg tables are written deterministically
- **AND** analytics outputs are produced from Iceberg-backed inputs

#### Scenario: Worker deployments schedule Track B runs
- **GIVEN** operator uses Prefect worker engine
- **WHEN** extensions apply deployments for `mode=both`
- **THEN** the deployments reference bundled batch specs and stable `artifacts_dir`
- **AND** the system provides a Prefect-compatible code distribution strategy so deployments become `status=READY`

#### Scenario: Worker deployments require a packaging strategy
- **GIVEN** Prefect worker deployments run outside the authoring process
- **WHEN** the operator applies deployments
- **THEN** the system MUST provide one of:
   - a container image that contains the flow code, OR
   - a remote storage / pull-step strategy that fetches the flow code at runtime
- **AND** if neither is configured, the deployments MAY remain `status=NOT_READY` and the scheduler MAY produce
  `scheduled_runs=count 0` (for example, if the server scheduler is not running or SQLite is locked)

#### Scenario: Prefect helpers are idempotent
- **GIVEN** an operator is iterating locally
- **WHEN** they run `tvscreener-prefectctl pool` repeatedly
- **THEN** the command completes successfully and leaves the work pool + queues in a usable state

#### Scenario: Default work queue is stable across environments
- **GIVEN** an operator runs the same deployments locally and remotely
- **WHEN** they do not customize queue routing
- **THEN** deployments target `TVSCREENER_PREFECT_WORK_QUEUE` (default: `default`)
- **AND** a single worker can execute scheduled runs without requiring queue-specific env

#### Scenario: Split deployments exist for essential universes
- **GIVEN** an operator wants independent scheduling
- **WHEN** they deploy Track B essential pipelines
- **THEN** there are separate Prefect deployments for:
  - forex majors/minors data + analytics
  - crypto (binance) spot/perp majors/minors data + analytics

#### Scenario: Split deployments use the default work queue
- **GIVEN** an operator wants local/remote parity
- **WHEN** they deploy using `tvscreener-deploy-schedules --mode split-data|split-analytics`
- **THEN** the deployments target `TVSCREENER_PREFECT_WORK_QUEUE` (default: `default`) for all split deployments

#### Scenario: Lakehouse base dir is stable across environments
- **GIVEN** an operator runs pipelines locally and remotely
- **WHEN** they set `TVSCREENER_LAKEHOUSE_BASE_DIR` to the same relative path (and ensure the same working dir)
- **THEN** Iceberg catalog + warehouse paths resolve consistently

#### Scenario: Extensions CLIs load `.env` by default
- **GIVEN** an operator has created a local `.env` from `.env.example`
- **WHEN** they run extensions CLIs (`tvscreener-prefectctl`, `tvscreener-ext-scan`, `tvscreener-ext-validate`)
- **THEN** the CLIs load `.env` into `os.environ` (without overriding existing values)

#### Scenario: Local-only development uses in-process Prefect
- **GIVEN** an operator is running from a local repo checkout without remote storage
- **WHEN** they want a repeatable runset
- **THEN** they run `tvscreener-ext-validate --runner prefect` to create server-backed flow runs
- **AND** do not rely on Prefect worker scheduling until a packaging strategy is adopted

#### Scenario: Local worker can execute scheduled runs
- **GIVEN** a single-machine setup where the Prefect worker runs in the same environment as the extensions code
- **WHEN** the operator starts a `process` worker for the work pool
- **THEN** scheduled runs can execute end-to-end even if Prefect reports the deployment status as `NOT_READY`

### Requirement: Extensions support upstream surface-area mismatch
Extensions SHALL define how workflows behave when the installed upstream `tvscreener` package does not ship the
repo-local workflow/pipeline modules.

#### Scenario: Thin-wrapper mode requires upstream pipeline modules
- **GIVEN** extensions are implemented as a thin wrapper over upstream pipelines
- **WHEN** upstream `tvscreener` is installed
- **THEN** upstream MUST provide the required modules/entrypoints
- **AND** extensions MUST fail fast with a clear operator error if they are missing

#### Scenario: Extensions-owned pipeline mode does not import repo-local sources
- **GIVEN** upstream `tvscreener` is installed but does not ship pipeline modules
- **WHEN** an operator runs pipelines via extensions
- **THEN** extensions execute without importing from a repo checkout
- **AND** extensions rely on upstream only for TradingView API access (or other explicitly supported surfaces)

#### Scenario: Extensions provide a stable scan entrypoint
- **WHEN** an operator runs `tvscreener-ext-scan`
- **THEN** the command executes using the extensions-owned pipeline runner
- **AND** it accepts `--pipeline data|analytics|both` and writes artifacts under `artifacts/runs/<params_hash>/`
