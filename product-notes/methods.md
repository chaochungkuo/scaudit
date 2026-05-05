# Methods

Technical reference for scaudit's annotation pipeline. This doubles as a basis
for a paper Methods section or supplement after light editing.

---

## 1. Problem Formulation

Given a single-cell RNA-seq dataset with expression matrix:

```math
X ∈ ℝ^{n × p}
```

where `n` is cells and `p` is genes, with cluster labels:

```math
c(i) ∈ {1, …, K}
```

The goal is to assign a cell type label to each cluster `k`:

```math
ŷ_k ∈ Y
```

while also producing an interpretable evidence structure `E_k` and a final decision `D_k`.

Annotation is formally a tuple:

```math
A_k = (E_k, R_k, D_k)
```

- `E_k`: multi-source evidence (markers, model, reference, DB).
- `R_k`: reasoning trace (supports, contradictions, uncertainties).
- `D_k`: final decision state.

---

## 2. Dataset Diagnosis

Before annotation, scaudit inspects the input `.h5ad`:

- Cell count, gene count, available `.obs` keys.
- Cluster key validation (is it present in `.obs`?).
- Cluster sizes (per-cluster cell count).
- UMAP coordinates: if `adata.obsm['X_umap']` exists, up to 500 cells per cluster
  are sampled (seed=42) and stored in `diagnosis.json` for the interactive report.

Output: `diagnosis.json`.

---

## 3. Evidence Construction

For each cluster `k`, scaudit builds a multi-source evidence set:

```math
E_k = {E_k^marker, E_k^DB, E_k^model, E_k^ref}
```

### 3.1 Marker-Based Evidence

One-vs-all Wilcoxon rank-sum test via `scanpy.tl.rank_genes_groups`:

```math
Δ_{k,g} = log2FC(μ_{k,g} / μ_{¬k,g})
```

Top 20 genes ranked by Wilcoxon score. Strong markers: log2FC > 1.0, padj < 0.01.
Moderate markers: log2FC > 0.5, padj < 0.05.

Each marker stored as `{gene, score, log2fc, pval_adj}`.

### 3.2 Builtin Marker Database

A curated set of ~60 cell types with known marker genes (human symbols).
Jaccard similarity between the log2FC-filtered query gene set and each DB entry:

```math
J(Q_k, M_y) = |Q_k ∩ M_y| / |Q_k ∪ M_y|
```

Matches with J ≥ 0.05 are stored, top 5 reported per cluster.
Stored as `{ref_id: "builtin", label, jaccard, n_shared}`.

### 3.3 CellTypist Model Evidence

Per-cell probability predictions using `celltypist.annotate()` with majority voting.
Cluster-level aggregation:

```math
ŷ_k^model = argmax_{y} (|{i ∈ k : P_model(y|i) is top}| / |k|)
```

Top label and majority fraction stored as `{model: "CellTypist", label, probability}`.
Skipped gracefully if `celltypist` is not installed.

### 3.4 Local Reference h5ad Matching

For each registered reference h5ad with known `label_key`:

1. Wilcoxon DE computed per cell type in the reference.
2. Jaccard similarity between query cluster markers (log2FC > 0.5, padj < 0.05)
   and reference cell-type marker sets.

```math
J_ref(k, y) = |M_k ∩ M_y^ref| / |M_k ∪ M_y^ref|
```

Top 5 matches stored per cluster as `{ref_id, label, jaccard, n_shared}`.

---

## 4. Confidence Assessment

Confidence is assessed independently on three axes:

| Axis | Source | High | Medium | Low |
|---|---|---|---|---|
| Lineage | Marker DE | ≥5 strong markers | ≥3 moderate | <3 moderate |
| Subtype | Best reference Jaccard | J ≥ 0.20 | J ≥ 0.08 | J < 0.08 |

CellTypist probability also informs an independent model confidence channel:
probability ≥ 0.75 → high; ≥ 0.50 → medium; < 0.50 → low.

Overall confidence is derived from the rank-weighted average:

```math
overall_rank = mean({rank(lineage), rank(model), rank(subtype)})
```

where rank: high=3, medium=2, low=1, unknown=0.

---

## 5. Decision Rule

The final decision is assigned as:

```python
if cell_count < 10:
    decision = "Artifact warning"
elif no evidence computed:
    decision = "Needs review"
elif CellTypist label != best reference label and both are present:
    decision = "Ambiguous"
elif overall == "high" and proposed_label is set:
    decision = "Accepted"
elif overall in ("medium", "high") and proposed_label is set:
    decision = "Needs review"
else:
    decision = "Needs review"
```

The decision states are:

| Decision | Meaning |
|---|---|
| **Accepted** | Strong, consistent multi-source evidence |
| **Ambiguous** | Evidence sources disagree on label |
| **Needs review** | Default; incomplete or moderate evidence |
| **Unknown** | No evidence — placeholder clusters |
| **Artifact warning** | Too few cells or QC flags |

---

## 6. Uncertainty Quantification

Three axes of uncertainty stored per cluster:

- `model_disagreement`: low if CellTypist is available and uncontradicted; high if contradicted.
- `reference_distance`: low if best reference Jaccard ≥ 0.20; high otherwise.
- `marker_inconsistency`: low if ≥5 strong markers; medium if <5; high if no markers.

---

## 7. LLM-Assisted Reasoning

Given structured evidence `E_k`, construct a prompt:

```
Cluster k (N cells) · Decision: X · Confidence: lineage=Y subtype=Z overall=W
Marker genes: [top 8 with log2FC]
Model evidence: [CellTypist label + probability]
Reference matches: [top 3 builtin / external Jaccard]
Supports / Uncertainties / Contradictions
```

Claude Haiku generates a ≤60-word grounded summary, stored in `reasoning.summary`.

Hard constraints enforced in the system prompt:
- No invented marker genes, references, or biological claims.
- No override of the evidence-based decision or confidence level.
- Uncertainty is explicitly stated when evidence is weak.
- Output is plain text, not JSON.

The LLM is purely explanatory. No downstream code reads `reasoning.summary`
to make decisions. Skipped silently if `anthropic` SDK absent or `ANTHROPIC_API_KEY` unset.

---

## 8. Annotation Record

Each cluster's complete output:

```json
{
  "cluster_id": "k",
  "proposed_label": "ŷ_k",
  "decision": "Accepted / Ambiguous / Needs review / Unknown / Artifact warning",
  "confidence": {"lineage": "high/medium/low/unknown", "subtype": "...", "overall": "..."},
  "evidence": {
    "markers": [{"gene": "...", "score": ..., "log2fc": ..., "pval_adj": ...}],
    "models": [{"model": "CellTypist", "label": "...", "probability": ...}],
    "references": [{"ref_id": "builtin|<id>", "label": "...", "jaccard": ..., "n_shared": ...}],
    "ontology": [],
    "qc_warnings": []
  },
  "uncertainty": {
    "model_disagreement": "low/high/unknown",
    "reference_distance": "low/high/unknown",
    "marker_inconsistency": "low/medium/high"
  },
  "reasoning": {
    "summary": "...",
    "supports": ["..."],
    "contradictions": ["..."],
    "uncertainties": ["..."],
    "validation_suggestions": ["..."]
  },
  "provenance": {
    "cell_count": ...,
    "models": ["CellTypist"],
    "references": ["builtin", "my_ref"],
    "parameters": {}
  }
}
```

---

## 9. Reproducibility Record

Saved alongside every run:

```json
{
  "scaudit_version": "0.1.0",
  "input_file": "input.h5ad",
  "input_hash": null,
  "parameters": {"dataset": {...}, "output": {...}},
  "references": [],
  "models": [],
  "environment": {"python": "3.12.10", "platform": "..."},
  "created_at": "2026-05-05T10:00:00+00:00"
}
```

Planned: input file SHA-256 hash, CellTypist model version, reference checksums.

---

## 10. Pipeline Summary

```text
Input .h5ad
→ diagnose_dataset()        # Structure check, cluster sizes, UMAP coords
→ compute_cluster_evidence()
    → _fill_marker_evidence()    # Wilcoxon DE (scanpy)
    → _fill_marker_db_evidence() # Jaccard vs builtin DB
    → _fill_celltypist_evidence() # CellTypist majority vote (optional)
    → _fill_reference_evidence() # Jaccard vs registered reference h5ads (optional)
→ build_annotation_cards()
    → _assign_annotation()       # Rule-based decision + confidence
→ enrich_cards_with_llm()    # Claude Haiku narrative (optional)
→ render_draft_report()      # report.html + review.html
→ write outputs              # JSON, CSV, config.resolved.toml, reproducibility.json
```

---

## 11. Planned Method Additions

| Method | Phase |
|---|---|
| Gene symbol normalization | Phase 13 |
| Mouse ↔ human ortholog mapping | Phase 13 |
| Per-cluster QC metrics (n_counts, pct_mito) | Phase 14 |
| Annotated h5ad output | Phase 15 |
| Weighted evidence fusion / calibration | Phase 20 |
| scVI / scANVI latent similarity | Phase 20 |
| Cell state vs cell type separation | Phase 21 |
| Novel cell detection | Phase 20 |
