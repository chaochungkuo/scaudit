# MVP Scope and Implementation Status

This document defines the first build of scaudit and tracks which pieces are complete.

## MVP Goal

Build the smallest useful version of scaudit that proves the core thesis:

```text
single-cell annotation can be represented as evidence + reasoning + decision
```

The MVP should produce an auditable annotation report, not a comprehensive single-cell platform.

## Status Key

```text
✅ Implemented
🔄 Partial / in progress
🔲 Planned
```

---

## MVP User Story — ✅ Implemented

A computational biologist has a clustered `.h5ad` file and wants to annotate clusters.

They run:

```bash
scaudit annotate input.h5ad \
  --cluster-key leiden \
  --species mouse \
  --tissue heart \
  --out results/
```

scaudit outputs:

```text
results/
├── config.resolved.toml
├── diagnosis.json
├── annotation_cards.json
├── annotation_summary.csv
├── review_table.csv
├── reproducibility.json
└── report/
    ├── report.html
    └── review.html
```

---

## MVP Inputs

Required (implemented):

- `.h5ad` AnnData input.
- Cluster key.
- Output directory.

Optional (implemented):

- `--species`
- `--tissue`
- `--no-llm`
- Config TOML (`scaudit run config.toml`).

Optional (planned):

- Condition key.
- Sample key.
- Batch key.
- Reference path (already works via registry).

---

## MVP Annotation Unit — ✅ Implemented

```text
Compute evidence at cell level when useful.
Make final decisions at cluster level.
```

CellTypist predictions are per-cell, aggregated to cluster level via majority voting.
Marker DE is cluster-level (one-vs-all Wilcoxon).

---

## MVP Evidence Sources

### Marker evidence — ✅ Implemented

- `scanpy.tl.rank_genes_groups` with Wilcoxon test.
- Top 20 genes per cluster.
- Stored per cluster: `gene`, `score`, `log2fc`, `pval_adj`.
- Strong markers: log2FC > 1.0, padj < 0.01.
- Moderate markers: log2FC > 0.5, padj < 0.05.

### Builtin marker DB — ✅ Implemented

- ~60 cell types across immune, epithelial, stromal, cardiac, neural lineages.
- Jaccard similarity between log2FC-filtered query markers and known gene sets.
- Provides label proposals offline, no model weights required.
- Stored as `{ref_id: "builtin", label, jaccard, n_shared}` in `evidence.references`.

### CellTypist model evidence — ✅ Implemented (optional)

- Per-cell predictions with majority voting per cluster.
- Stored as `{model: "CellTypist", label, probability}` in `evidence.models`.
- Gracefully skipped if `celltypist` not installed.

### Local reference h5ad matching — ✅ Implemented

- Wilcoxon DE computed for reference cell types.
- Jaccard between query cluster marker set and reference cell-type marker sets.
- Top 5 matches stored in `evidence.references` per cluster.
- Requires `scaudit reference add` before run.

### LLM reasoning summaries — ✅ Implemented (optional)

- `enrich_cards_with_llm()` calls Claude Haiku via `anthropic` SDK.
- Updates `reasoning.summary` with ≤60-word grounded narrative.
- System prompt enforces: no invented evidence, no decision override, uncertainty stated.
- Skipped silently if SDK absent or `ANTHROPIC_API_KEY` not set.
- Disable with `--no-llm`.

### Planned evidence sources

- scVI / scANVI latent-space embedding similarity — 🔲
- Ontology-aware label hierarchy (CL terms) — 🔲
- QC evidence: n_counts, n_genes, pct_mito per cluster — 🔲
- Doublet score integration (Scrublet) — 🔲

---

## MVP Decision Categories — ✅ Implemented

```text
Accepted          All evidence layers agree, high confidence
Ambiguous         Evidence sources disagree on label
Needs review      Default — incomplete or moderate evidence
Unknown           No evidence computed
Artifact warning  Cell count < 10 or QC flags
```

Decision logic in `_assign_annotation()`:

1. `Artifact warning` if cell_count < 10 (overrides everything).
2. `Needs review` if no evidence computed.
3. `Ambiguous` if CellTypist label conflicts with best reference match.
4. `Accepted` if overall confidence == "high" and proposed label is set.
5. `Needs review` if moderate confidence.
6. `Needs review` otherwise.

---

## MVP Confidence Levels — ✅ Implemented

Three axes, each independently assessed:

| Axis | Source | High | Medium | Low |
|---|---|---|---|---|
| Lineage | Marker DE | ≥5 strong markers | ≥3 moderate | <3 moderate |
| Subtype | Reference Jaccard | J ≥ 0.20 | J ≥ 0.08 | J < 0.08 |
| Overall | Min of axes | avg rank ≥ 2.5 | avg ≥ 1.5 | avg ≥ 0.5 |

CellTypist probability affects model confidence (>75% → high, >50% → medium).

---

## MVP Annotation Card Schema — ✅ Implemented

```json
{
  "cluster_id": "4",
  "proposed_label": "Cardiomyocyte",
  "decision": "Accepted",
  "confidence": {
    "lineage": "high",
    "subtype": "medium",
    "overall": "high"
  },
  "evidence": {
    "markers": [{"gene": "MYH7", "score": 12.3, "log2fc": 2.1, "pval_adj": 1e-8}],
    "models": [{"model": "CellTypist", "label": "Cardiomyocyte", "probability": 0.92}],
    "references": [{"ref_id": "builtin", "label": "Cardiomyocyte", "jaccard": 0.31, "n_shared": 4}],
    "ontology": [],
    "qc_warnings": []
  },
  "uncertainty": {
    "model_disagreement": "low",
    "reference_distance": "low",
    "marker_inconsistency": "low"
  },
  "reasoning": {
    "summary": "Cluster 4 shows strong cardiomyocyte identity with high-scoring sarcomere markers (MYH7, TNNT2) and consistent CellTypist prediction.",
    "supports": ["5 strongly enriched marker genes", "CellTypist: Cardiomyocyte (92%)"],
    "contradictions": [],
    "uncertainties": [],
    "validation_suggestions": ["Validate MYH7, TNNT2, ACTC1 using PMID literature."]
  },
  "provenance": {
    "parameters": {},
    "models": ["CellTypist"],
    "references": ["builtin"],
    "cell_count": 1842
  }
}
```

---

## MVP Reproducibility Record — ✅ Implemented

```json
{
  "scaudit_version": "0.1.0",
  "input_file": "input.h5ad",
  "input_hash": null,
  "parameters": {},
  "references": [],
  "models": [],
  "environment": {
    "python": "3.12.10",
    "platform": "macOS-15.4.1-arm64"
  },
  "created_at": "2026-05-05T10:00:00+00:00"
}
```

Planned additions: input file SHA-256 hash, CellTypist model version, reference checksums.

---

## MVP Report — ✅ Implemented

Two static HTML files. No Quarto, no server.

See [`report-architecture.md`](report-architecture.md) for full details.

---

## MVP Exit Criteria — ✅ Met

```bash
scaudit annotate input.h5ad --cluster-key leiden --out results/
scaudit review import results/review_table.csv --run results/
scaudit finalize results/ --out final/
```

Produces all required outputs. Tests pass (14/14).

---

## Immediate Next Priorities

1. **Gene harmonization** — Ensembl/symbol normalization before cross-dataset reference matching is reliable.
2. **QC evidence layer** — Per-cluster n_counts / n_genes / pct_mito as explicit evidence.
3. **Annotated h5ad output** — Write labels back to `adata.obs` in `finalize`.
4. **End-to-end test with real data** — Validate the full pipeline on a public dataset (e.g., Tabula Muris heart).

---

## Deferred from MVP

```text
- scGPT / Geneformer (foundation model embeddings)
- SingleR / R integration
- Full ontology reasoning
- scVI / scANVI
- Condition comparison
- Web app / live review UI
- Public reference download (CELLxGENE, HCA)
- Batch correction
- Doublet detection
```
