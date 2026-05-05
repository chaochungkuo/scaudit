<p align="center">
  <img src="docs/assets/scaudit-logo.svg" alt="scaudit logo" width="560">
</p>

<p align="center">
  <a href="https://github.com/chaochungkuo/scaudit"><img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white"></a>
  <a href="https://github.com/chaochungkuo/scaudit/blob/main/LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-2FB344"></a>
  <a href="https://github.com/chaochungkuo/scaudit"><img alt="Version: 0.1.0" src="https://img.shields.io/badge/version-0.1.0-6D5DF6"></a>
  <a href="https://github.com/chaochungkuo/scaudit"><img alt="Status: early MVP" src="https://img.shields.io/badge/status-early%20MVP-12B5CB"></a>
</p>

# scaudit

Transparent annotation audit framework for single-cell RNA-seq.

scaudit turns cluster annotation into structured evidence records, confidence calls, human-review tables, and static HTML reports — so every label is traceable, auditable, and reproducible.

**Core thesis**: annotation = Evidence + Reasoning + Decision.

---

## Quickstart

```bash
# One-command annotation audit
scaudit annotate input.h5ad \
  --cluster-key leiden \
  --species mouse \
  --tissue heart \
  --out results/

# Open the report
open results/report/report.html
```

## Install

```bash
# Development (pixi)
pixi run scaudit --help

# Or directly
pip install -e .
```

## What scaudit produces

```text
results/
├── config.resolved.toml      # Exact parameters used
├── diagnosis.json            # Dataset structure + UMAP coords
├── annotation_cards.json     # Per-cluster evidence + decisions
├── annotation_summary.csv    # Summary table
├── review_table.csv          # Editable human-review worksheet
├── reproducibility.json      # Versions, hashes, environment
└── report/
    ├── report.html           # Interactive audit report (Plotly UMAP)
    └── review.html           # In-browser review table with CSV download
```

## Evidence sources (per cluster)

| Source | Method | Status |
|---|---|---|
| Marker genes | Scanpy Wilcoxon DE, top 20 per cluster | ✅ implemented |
| Builtin marker DB | Jaccard against ~60 curated cell-type gene sets | ✅ implemented |
| CellTypist | Majority-vote per cluster | ✅ optional (auto-skipped if not installed) |
| Local reference h5ad | Jaccard between DE marker sets | ✅ implemented |
| LLM summaries | Claude Haiku (requires `ANTHROPIC_API_KEY`) | ✅ optional |
| scVI / scANVI | Latent-space embedding | 🔲 planned |
| Ontology | CL / UBERON term hierarchy | 🔲 planned |

## Decision states

| Decision | Meaning |
|---|---|
| **Accepted** | High confidence, all evidence layers agree |
| **Ambiguous** | Evidence sources disagree |
| **Needs review** | Moderate or incomplete evidence |
| **Unknown** | No usable evidence |
| **Artifact warning** | Very small cluster or QC signal |

## Full workflow

```bash
# 1. Config-based workflow (more control)
scaudit init-config input.h5ad --out config.toml
scaudit validate config.toml
scaudit plan config.toml
scaudit run config.toml

# 2. Import human review
scaudit review import results/review_table.csv --run results/

# 3. Finalize
scaudit finalize results/ --out final/

# Reference management
scaudit reference add ref.h5ad \
  --id mouse_heart_v1 \
  --species mouse --tissue heart \
  --label-key cell_type
scaudit reference use mouse_heart_v1 --config config.toml

# Dataset inspection only
scaudit diagnose input.h5ad --cluster-key leiden
```

## Environment check

```bash
scaudit doctor
```

## Development

```bash
pixi run test
pixi run scaudit --help
```

## Design principles

- Evidence is always explicit and traceable.
- The LLM explains but never decides.
- Confidence levels are conservative (low by default, high only with multi-source agreement).
- All outputs are static files — no server required.
- Graceful fallback when optional dependencies are absent.

## Project notes

See [`product-notes/`](product-notes/) for architecture decisions, roadmap, methods, and design philosophy.
