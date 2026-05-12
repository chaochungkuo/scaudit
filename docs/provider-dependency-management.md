# Provider Dependency Management

scaudit uses `pixi` as the source of truth for reproducible development and provider execution environments.

## Dependency Boundaries

Keep dependencies grouped by provider execution style:

| Provider family | Examples | Pixi location | Notes |
| --- | --- | --- | --- |
| Core Python reports | `marker_based`, `reference_mapping`, `sctype`, `sccatch`, `scsa`, future comparison reports | default environment | Uses `scanpy`, `anndata`, `scikit-learn`, `quarto`, `pandas`, `matplotlib`, `seaborn`, and notebook rendering packages. ScType/scCATCH/SCSA currently run executable scaudit-native style adapters. |
| R-backed official tools | future exact `sctype` or `sccatch` execution | `provider-r` environment | R runtime and common table/JSON packages are isolated from the default Python environment. Use this only after the exact official package/script/database source is pinned. |
| Python-backed external tools | future exact `scsa` CLI/package execution | provider-specific pixi feature, to be added with implementation | Add only after the exact maintained package or CLI entry point is selected and tested. |
| Database-backed marker evidence | `cellmarker`, `panglaodb` | default environment plus data-cache tasks | Treat database files as versioned data artifacts, not package dependencies. Store database name, version/date, URL, checksum, and local cache path in the provider JSON. |

## Current Pixi Environments

```bash
pixi run test
pixi run scaudit --help
pixi run --environment provider-r R --version
```

The default environment should remain usable for the normal Python CLI and report rendering. The current ScType/scCATCH/SCSA reports execute in the default environment through transparent scaudit-native adapters. The `provider-r` environment exists for future exact R-backed execution and should not be required for default runs unless those official backends are enabled.

## Adding A New Provider Dependency

When adding a provider, update dependencies in this order:

1. Identify whether the provider is Python package, R package/script, external CLI, or database-only.
2. Add the minimal runtime packages to the matching pixi feature/environment.
3. Keep heavy or fragile dependencies out of `default` unless the default CLI always needs them.
4. Add a provider method record with exact package name, version, command/function, parameters, and database version.
5. Add a graceful skipped/warning state when a provider dependency or database file is unavailable.
6. Run `pixi lock`, `pixi run test`, and the PBMC3k example before committing.

## Provider-Specific Notes

| Provider | Dependency plan |
| --- | --- |
| `sctype` | Current backend is an executable scaudit-native ScType-style marker scoring adapter in the default environment. If exact ScType execution is added later, use `provider-r` and record the exact script/database provenance in `sctype.evidence.json`. |
| `sccatch` | Current backend is an executable scaudit-native scCATCH-style marker matching adapter in the default environment. If exact scCATCH execution is added later, use `provider-r` and record tissue parameter, database version, and thresholds. |
| `scsa` | Current backend is an executable scaudit-native SCSA-style weighted marker scoring adapter in the default environment. If exact SCSA execution is added later, first choose a maintained CLI/package source, then create a dedicated pixi feature if needed. |
| `cellmarker` | Database provider. Add a data download/cache task with checksum and database release date. No separate runtime package should be required beyond core Python table processing. |
| `panglaodb` | Database provider. Same pattern as `cellmarker`: cache the marker table with provenance and checksum, then score through scaudit code. |

Provider reports should remain self-contained and runnable, but the dependency layer should stay explicit: the report tells readers which pixi environment, tool/package, command/function, parameters, and database version produced the results.
