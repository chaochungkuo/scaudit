# Reference Management Workflow

This document defines how scaudit should help users discover, download, register, and use reference datasets without requiring them to manually write full reference metadata in `config.toml`.

## Core Decision

Users should not need to manually define public references in the config file.

Recommended model:

```text
config.toml stores reference policy and selected reference IDs.
local registry stores full reference metadata and file paths.
scaudit commands manage discovery, download, registration, and config updates.
```

Manual reference definition should remain available for custom/private references, but should not be the default UX.

## Why This Matters

Reference handling is one of the hardest parts of scRNA-seq annotation:

- Users may not know which atlas is appropriate.
- Public references need source/version tracking.
- Downloaded files need validation and caching.
- Config files become fragile if users manually write paths and metadata.
- Reproducibility requires exact reference IDs, versions, and checksums.

scaudit should make reference selection transparent, guided, and reproducible.

## Recommended Commands

## Search

```bash
scaudit reference search \
  --species mouse \
  --tissue heart
```

Purpose:

- Search supported public reference registries.
- Show candidate references.
- Display metadata and availability.

Example output:

```text
ID                       Species  Tissue  Source     Version      Cells   Status
mouse_heart_cellxgene    mouse    heart   cellxgene  2026-05-01   48521   remote
tabula_muris_heart       mouse    heart   cellxgene  2024-11-12   12344   remote
local_heart_ref          mouse    heart   local      custom       8021    local
```

## Recommend

```bash
scaudit reference recommend \
  --config config.toml
```

Purpose:

- Read dataset metadata from config.
- Score candidate references.
- Explain why each reference is recommended or rejected.

Example output:

```text
Recommended references:
1. mouse_heart_cellxgene
   score: 0.88
   reasons: species match, tissue match, strong label coverage
   warning: reference condition is healthy, query condition is mutant

2. tabula_muris_heart
   score: 0.74
   reasons: species match, tissue match
   warning: older reference, smaller cell count
```

## Recommend and Write Config

```bash
scaudit reference recommend \
  --config config.toml \
  --write
```

Expected config update:

```toml
[references]
auto_select = true
max_references = 3
registry = "default"
cache_dir = "references"
selected = ["mouse_heart_cellxgene"]
allow_condition_mismatch = true
require_species_match = true
```

## Download

```bash
scaudit reference download mouse_heart_cellxgene
```

Purpose:

- Download the reference dataset.
- Store it in the local cache.
- Validate the file.
- Create or update manifest.
- Register it in `registry.json`.

## Use

```bash
scaudit reference use mouse_heart_cellxgene \
  --config config.toml
```

Purpose:

- Add a registered reference ID to `config.toml`.
- Avoid manual metadata editing.

## Add Custom Reference

```bash
scaudit reference add my_ref.h5ad \
  --id my_mouse_heart_ref \
  --species mouse \
  --tissue heart \
  --condition healthy \
  --technology 10x \
  --label-key cell_type
```

Purpose:

- Register a user-created reference.
- Generate manifest metadata.
- Make it available for future configs.

## List

```bash
scaudit reference list
```

Purpose:

- Show locally registered references.
- Include source, version, path, and status.

## Update

```bash
scaudit reference update
```

Purpose:

- Refresh remote registry metadata.
- Check whether newer reference versions are available.
- Do not silently change a config without explicit user approval.

## Local Registry Layout

```text
references/
├── registry.json
├── mouse_heart_cellxgene/
│   ├── reference.h5ad
│   └── manifest.json
└── my_mouse_heart_ref/
    ├── reference.h5ad
    └── manifest.json
```

## Registry Entry

```json
{
  "id": "mouse_heart_cellxgene",
  "status": "local",
  "manifest_path": "references/mouse_heart_cellxgene/manifest.json",
  "data_path": "references/mouse_heart_cellxgene/reference.h5ad"
}
```

## Manifest Schema

```json
{
  "id": "mouse_heart_cellxgene",
  "version": "2026-05-01",
  "source": "cellxgene",
  "species": "mouse",
  "tissue": "heart",
  "condition": "healthy",
  "technology": "10x",
  "path": "references/mouse_heart_cellxgene/reference.h5ad",
  "label_key": "cell_type",
  "gene_id_type": "symbol",
  "downloaded_at": "2026-05-04",
  "checksum": null
}
```

## Config Relationship

User-facing config should stay simple:

```toml
[references]
auto_select = true
max_references = 3
registry = "default"
cache_dir = "references"
selected = ["mouse_heart_cellxgene"]
allow_condition_mismatch = true
require_species_match = true
```

The full manifest is resolved at runtime from the registry.

## Reference Selection in Reports

The report should include:

- Selected reference IDs.
- Source and version.
- Selection score.
- Gene overlap.
- Metadata match.
- Label coverage.
- Bias warnings.
- Download/checksum information.

## Safety Rules

- Never silently replace a selected reference with a new version.
- Always record the exact reference version in `reproducibility.json`.
- Warn when query and reference condition differ.
- Warn when gene overlap is low.
- Allow custom references, but validate required metadata.

## MVP Recommendation

Implement reference management in this order:

```text
1. reference add for local/custom references
2. reference list
3. reference use --config
4. reference search/recommend using a small built-in registry
5. reference download for supported public references
6. reference update
```

This order allows MVP development without depending immediately on complex public database integrations.
