## ADDED Requirements

### Requirement: Lakehouse table identifiers scale by dimensions
The system SHALL support a table identifier layout that scales with `asset_type`, `instrument_type`, `stage`, and `dataset`.

#### Scenario: Logical identifier includes asset and instrument type
- **WHEN** the system refers to a lakehouse table for a persisted dataset
- **THEN** the identifier model includes `asset_type` and `instrument_type` to prevent schema collisions

### Requirement: Nested namespace layout is supported logically
The system SHALL define a canonical logical layout using nested namespaces.

#### Scenario: Canonical logical layout
- **WHEN** a maintainer documents or reasons about a table id
- **THEN** it uses `tvscreener.<asset_type>.<instrument_type>.<stage>.<dataset>`

### Requirement: Flattened encoding is allowed for catalog compatibility
The system SHOULD support a flattened physical encoding when multi-level namespaces are not available.

#### Scenario: Flattened physical encoding
- **GIVEN** a target catalog backend prefers single-level namespaces
- **WHEN** the system maps logical ids to physical ids
- **THEN** it may encode the namespace as `tvscreener_<asset_type>_<instrument_type>_<stage>`
- **AND** the table name remains `<dataset>`

#### Scenario: Repo enforces single-level namespaces today
- **GIVEN** the current `LakehouseManager` validates identifiers as `namespace.table`
- **WHEN** the scalable layout is enabled
- **THEN** the system uses the flattened physical encoding for table identifiers

### Requirement: Asset/instrument schemas do not collide
The system SHALL isolate schemas by table or namespace so asset/instrument-specific fields do not force nullable growth.

#### Scenario: Crypto spot and perp snapshots are isolated
- **GIVEN** the system persists `screener_snapshot` for crypto spot and crypto perps
- **WHEN** the tables are created and written
- **THEN** they do not share a single Iceberg table that accumulates incompatible fields
