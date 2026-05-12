# Provider Dependency Management

scaudit uses `pixi` as the source of truth for reproducible development and provider execution environments.

## Dependency Boundaries

Keep dependencies grouped by provider execution style:

| Provider family | Examples | Pixi location | Notes |
| --- | --- | --- | --- |
| Core Python reports | `marker_based`, `reference_mapping`, future comparison reports | default environment | Uses `scanpy`, `anndata`, `scikit-learn`, `quarto`, `pandas`, `matplotlib`, `seaborn`, and notebook rendering packages. |
| R-backed marker tools | `sctype`, `sccatch` | `provider-r` environment | R runtime and common table/JSON packages are isolated from the default Python environment. Tool-specific R packages or scripts should be added here when implementation starts. |
| Python-backed external tools | `scsa` if used through a Python CLI/package | provider-specific pixi feature, to be added with implementation | Add only after the exact maintained package or CLI entry point is selected and tested. |
| Database-backed marker evidence | `cellmarker`, `panglaodb` | default environment plus data-cache tasks | Treat database files as versioned data artifacts, not package dependencies. Store database name, version/date, URL, checksum, and local cache path in the provider JSON. |

## Current Pixi Environments

```bash
pixi run test
pixi run scaudit --help
pixi run --environment provider-r R --version
```

The default environment should remain usable for the normal Python CLI and report rendering. The `provider-r` environment exists for R-backed annotation providers and should not be required for default runs unless those providers are enabled.

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
| `sctype` | Use `provider-r`. Prefer vendoring or caching the exact ScType marker DB/script version used by the report. Record script/database provenance in `sctype.evidence.json`. |
| `sccatch` | Use `provider-r`. Add exact R package installation once the maintained source is selected. Record tissue parameter, database version, and all scoring thresholds. |
| `scsa` | Do not add blindly. First choose a maintained SCSA package/CLI source, then create a dedicated pixi feature if it requires extra Python dependencies. |
| `cellmarker` | Database provider. Add a data download/cache task with checksum and database release date. No separate runtime package should be required beyond core Python table processing. |
| `panglaodb` | Database provider. Same pattern as `cellmarker`: cache the marker table with provenance and checksum, then score through scaudit code. |

Provider reports should remain self-contained and runnable, but the dependency layer should stay explicit: the report tells readers which pixi environment, tool/package, command/function, parameters, and database version produced the results.
