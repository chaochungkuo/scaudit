# Provider Dependency Management

scaudit uses `pixi` as the source of truth for reproducible development and provider execution environments.

Reusable provider data is stored under the global scaudit cache root. The default is `~/.cache/scaudit`, overridable with `[cache].dir` in config or the `SCAUDIT_CACHE_DIR` environment variable. Providers should download only when a required cache artifact is missing; second and later runs should reuse the existing file and record checksum/provenance in provider JSON.

## Dependency Boundaries

Keep dependencies grouped by provider execution style:

| Provider family | Examples | Pixi location | Notes |
| --- | --- | --- | --- |
| Core Python reports | `marker_based`, future marker comparison reports | default environment | Uses `scanpy`, `anndata`, `scikit-learn`, `quarto`, `pandas`, `matplotlib`, `seaborn`, and notebook rendering packages. |
| External marker tools | `sctype`, `sccatch`, `scsa` | out of scope | These providers are intentionally skipped for the marker-based final check. Simulated predictions are not allowed. |
| Database-backed marker evidence | `cellmarker`, `panglaodb`, `user_markers` | default environment plus data-cache tasks | Treat database files as versioned data artifacts, not package dependencies. Store database name, version/date, URL or local source, checksum, and local path in the provider JSON. |

## Current Pixi Environments

```bash
pixi run test
pixi run scaudit --help
```

The default environment should remain usable for the normal Python CLI and report rendering. ScType/scCATCH/SCSA are intentionally skipped and must not emit predictions unless official backend work is explicitly resumed later.

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
| `cellmarker` | Database provider. Reads an explicit local CellMarker table when configured; otherwise downloads the species-specific table to the global cache, records checksum/provenance, and scores marker overlap through the shared marker database provider engine. |
| `panglaodb` | Database provider. Reads an explicit local PanglaoDB marker table when configured; otherwise downloads the marker table to the global cache, records checksum/provenance, and scores marker overlap through the shared marker database provider engine. |
| `user_markers` | Database provider. Reads a user-supplied CSV/TSV marker list from an explicit local path, records checksum/provenance, and scores marker overlap through the shared marker database provider engine. |

Provider reports should remain self-contained and runnable, but the dependency layer should stay explicit: the report tells readers which pixi environment, tool/package, command/function, parameters, and database version produced the results.
