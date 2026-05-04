# Configuration File Design

This document defines how scaudit should support file-based configuration, especially `config.toml`, so users can manually edit all options and run the workflow reproducibly.

## Core Decision

Configuration should not require command-line flags.

scaudit should support:

```text
1. CLI flags for quick runs
2. config.toml for reproducible full runs
```

Recommended default:

```text
config.toml
```

Rationale:

- TOML is readable and explicit.
- It works well for reproducible computational workflows.
- It is easier to review than long command-line commands.
- It can be saved with the final results for provenance.
- Pixi itself uses TOML, so the ecosystem feels consistent.

## Recommended Workflow

## Step 1: Create Template Config

```bash
scaudit init-config input.h5ad \
  --format toml \
  --out config.toml
```

## Step 2: Edit `config.toml`

The user manually edits:

```text
dataset metadata
cluster key
sample key
condition key
reference behavior
methods
LLM behavior
output options
review/finalization behavior
```

## Step 3: Validate Config

```bash
scaudit validate config.toml
```

This should check:

- File exists.
- Input `.h5ad` exists.
- Required fields exist.
- Cluster key exists in `.obs`.
- Optional methods are installed.
- Reference paths are valid.
- LLM settings are valid.
- Output directory is writable.

## Step 4: Preview Execution Plan

```bash
scaudit plan config.toml
```

This should show:

- Dataset summary.
- Methods to run.
- References to use.
- Report pages to generate.
- Expected outputs.
- Warnings before expensive computation.

## Step 5: Run

```bash
scaudit run config.toml
```

or:

```bash
scaudit run config.toml --out results/
```

## Minimal `config.toml`

```toml
[dataset]
path = "input.h5ad"
species = "mouse"
tissue = "heart"
cluster_key = "leiden"

[output]
dir = "results"
report = true
draft_h5ad = true
review_table = true
```

## Full `config.toml` Draft

```toml
[project]
name = "mouse_heart_annotation"
description = "Mouse heart single-cell annotation audit"

[dataset]
path = "input.h5ad"
species = "mouse"
tissue = "heart"
organism = "Mus musculus"
cluster_key = "leiden"
sample_key = "sample"
condition_key = "genotype"
batch_key = "sample"

[gene_harmonization]
input_gene_id_type = "auto"
reference_gene_id_type = "auto"
normalize_symbols = true
ortholog_map = "none"
min_gene_overlap_warning = 0.70
min_gene_overlap_strong_warning = 0.50

[references]
auto_select = true
max_references = 3
allow_condition_mismatch = true
require_species_match = true
registry = "default"
cache_dir = "references"

selected = []

[methods]
marker_based = true
reference_based = true
ontology_based = false

[methods.model_based]
celltypist = true
scanvi = false
scvi = false

[methods.qc]
enabled = true
doublet_warning = true
ambient_rna_warning = true
low_quality_warning = true

[decision]
unit = "cluster"
confidence_mode = "categorical"
prefer_lineage_over_subtype = true
allow_unknown = true
allow_ambiguous = true

[llm]
enabled = false
provider = "openai"
mode = "explain_only"
model = ""
temperature = 0

[report]
enabled = true
format = "html"
multi_page = true
theme = "scaudit"
include_methods = true
include_reproducibility = true
include_cluster_pages = true
include_condition_comparison = true

[output]
dir = "results"
draft_h5ad = true
final_h5ad = true
annotation_cards = true
summary_tables = true
review_table = true
reproducibility = true
figures = true
```

## Reference Configuration Strategy

Users should not be required to manually write reference metadata for public references.

Recommended model:

```text
Public/database references:
  discovered, downloaded, cached, and registered by scaudit

User-created references:
  added manually or through scaudit reference add
```

This means `[references]` in `config.toml` should usually describe policy, not full manifest details.

## Public Reference Workflow

## Search References

```bash
scaudit reference search \
  --species mouse \
  --tissue heart
```

Example output:

```text
ID                       Species  Tissue  Source     Version      Cells
mouse_heart_cellxgene    mouse    heart   cellxgene  2026-05-01   48521
tabula_muris_heart       mouse    heart   cellxgene  2024-11-12   12344
```

## Download Reference

```bash
scaudit reference download mouse_heart_cellxgene
```

Expected behavior:

```text
- Download reference into local reference cache
- Validate file
- Generate or retrieve manifest
- Register reference locally
```

## Add Downloaded Reference to Config

```bash
scaudit reference use mouse_heart_cellxgene \
  --config config.toml
```

This should update:

```toml
[references]
auto_select = true
max_references = 3
registry = "default"
cache_dir = "references"
selected = ["mouse_heart_cellxgene"]
```

The full reference metadata should live in the local reference registry, not be manually duplicated in every config file.

## Auto-Select and Update Config

For convenience:

```bash
scaudit reference recommend \
  --config config.toml \
  --write
```

Expected behavior:

```text
- Read dataset species/tissue/condition from config
- Search known registries
- Score candidate references
- Recommend top references
- Optionally write selected reference IDs into config.toml
```

## User-Created Reference Workflow

For private or custom references:

```bash
scaudit reference add my_ref.h5ad \
  --id my_mouse_heart_ref \
  --species mouse \
  --tissue heart \
  --condition healthy \
  --technology 10x \
  --label-key cell_type
```

Then:

```bash
scaudit reference use my_mouse_heart_ref \
  --config config.toml
```

## Reference Registry

Downloaded and custom references should be tracked in a local registry:

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

The config stores reference IDs and policy. The registry stores full metadata.

## Reference Manifest

Each registered reference should have a manifest:

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

## Revised Reference Section

Recommended user-facing config:

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

Advanced users may still provide inline local references, but this should not be the normal path.

## CLI Override Behavior

CLI flags can override config values for convenience:

```bash
scaudit run config.toml --out new_results/
```

Recommended rule:

```text
config.toml is the source of truth,
CLI flags are explicit overrides.
```

Overrides must be recorded in `reproducibility.json`.

## Config Saved With Outputs

Every run should copy the final resolved config to:

```text
results/config.resolved.toml
```

This file should include:

- Values from the user config.
- CLI overrides.
- Auto-detected fields.
- Selected references.
- Effective method settings.

## Recommended Commands

```bash
scaudit init-config input.h5ad --format toml --out config.toml
scaudit reference recommend --config config.toml --write
scaudit validate config.toml
scaudit plan config.toml
scaudit run config.toml
scaudit finalize results/
```

## Product Recommendation

`config.toml` should be the recommended mode for serious usage.

CLI-only usage should remain available:

```bash
scaudit annotate input.h5ad --species mouse --tissue heart --out results/
```

But the report and reproducibility records should encourage users to keep and share the resolved config.
