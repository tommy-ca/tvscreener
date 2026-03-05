## ADDED Requirements

### Requirement: Configurable Iceberg catalog mode
The system SHALL support configuring the Iceberg SQL catalog and warehouse via layered settings.

#### Scenario: Local catalog default
- **WHEN** no lakehouse configuration is provided
- **THEN** the system uses a local SQLite SQL catalog
- **AND** uses a local file warehouse under `~/.tvscreener/lakehouse`

#### Scenario: Remote catalog configuration
- **WHEN** `lakehouse.catalog.mode=remote` is configured
- **THEN** the system uses the configured SQL catalog URI
- **AND** uses the configured warehouse URI

### Requirement: Layered configuration precedence
The system SHALL apply configuration precedence as ENV/.env overrides YAML, which overrides defaults.

#### Scenario: ENV overrides YAML
- **WHEN** a lakehouse value is set in YAML and also set via environment variable
- **THEN** the environment value is used

### Requirement: CLI config path influences lakehouse initialization
The system SHALL apply the CLI-provided YAML config path to lakehouse initialization for the current process.

#### Scenario: CLI initializes manager with YAML config
- **WHEN** the CLI is invoked with `--config <path>`
- **THEN** the lakehouse manager is initialized using that YAML file (unless already initialized)

### Requirement: Pass-through catalog properties
The system SHALL allow arbitrary catalog properties to be configured and passed to the Iceberg catalog loader.

#### Scenario: Properties are forwarded
- **WHEN** `lakehouse.catalog.properties` is configured
- **THEN** those key/value pairs are passed to `pyiceberg.load_catalog`

