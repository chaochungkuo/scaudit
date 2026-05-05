# Product Roadmap

scaudit grows from a narrow, trustworthy vertical slice:

```text
input.h5ad -> evidence -> draft report -> review -> final annotated.h5ad
```

into a broader system only after the audit workflow is reliable.

The product proves that annotation can be represented as:

```text
Evidence + Reasoning + Decision + Report + Review
```

---

## Implementation Status Key

```text
✅ Complete
🔄 In progress / partial
🔲 Planned
⏸  Deferred
```

---

## Phase 0: Product Contract Freeze — ✅ Complete

Decisions made and locked:

- MVP input format: `.h5ad`.
- Annotation unit: cluster-level decisions.
- Evidence sources: markers + CellTypist + local reference + builtin DB.
- Report format: 2-file static HTML (`report.html` + `review.html`).
- Finalization: draft run → human review → `finalize`.
- LLM: explain-only, never decides.

---

## Phase 1: Repository and Runtime Foundation — ✅ Complete

```bash
scaudit --help
scaudit version
scaudit doctor
```

Pixi-based environment, typed models, lazy optional imports, test framework.

---

## Phase 2: Config and Dataset Diagnosis — ✅ Complete

```bash
scaudit init-config input.h5ad --out config.toml
scaudit validate config.toml
scaudit plan config.toml
scaudit diagnose input.h5ad --cluster-key leiden
```

Outputs: `config.resolved.toml`, `diagnosis.json` (includes UMAP coords when available).

---

## Phase 3: Evidence Schema and Marker Evidence — ✅ Complete

- `ClusterEvidence` dataclass with `markers`, `celltypist_label`, `reference_matches`.
- `MarkerGene` with `gene`, `score`, `log2fc`, `pval_adj`.
- Scanpy Wilcoxon DE via `rank_genes_groups`, top 20 per cluster.
- `compute_cluster_evidence()` pipeline.

Outputs: `annotation_cards.json`, `annotation_summary.csv`, `review_table.csv`.

---

## Phase 4: Reference Registry MVP — ✅ Complete

```bash
scaudit reference add ref.h5ad --id my_ref --species mouse --tissue heart --label-key cell_type
scaudit reference list
scaudit reference use my_ref --config config.toml
```

Outputs: `references/registry.json`, `references/<id>/manifest.json`.

---

## Phase 5: Builtin Marker DB — ✅ Complete

~60 curated cell-type gene sets across immune, epithelial, stromal, cardiac, neural lineages.
Jaccard-based label proposal. Works offline, no model weights.

`lookup_cell_type(query_genes)` → sorted matches with `{ref_id, label, jaccard, n_shared}`.

---

## Phase 6: Model Evidence (CellTypist) — ✅ Complete

Majority-vote per cluster. Auto-skipped if `celltypist` not installed.
Result stored as `{model: "CellTypist", label: ..., probability: ...}` in each card's `evidence.models`.

---

## Phase 7: Reference h5ad Matching — ✅ Complete

For each registered reference, Wilcoxon DE is computed and Jaccard similarity is measured
between query cluster marker sets and reference cell-type marker sets.
Top 5 matches stored per cluster.

---

## Phase 8: Decision Engine — ✅ Complete

Rule-based engine in `_assign_annotation()`:

```text
Artifact warning  → cell_count < 10
Accepted          → overall==high, proposed_label set, no contradictions
Ambiguous         → evidence sources disagree on label
Needs review      → default when evidence is incomplete or moderate
```

Confidence levels `{lineage, subtype, overall}` derived from marker strength,
CellTypist probability, and reference Jaccard.

---

## Phase 9: LLM Reasoning Layer — ✅ Complete (optional)

`scaudit.llm.enrich_cards_with_llm()` calls Claude Haiku with structured evidence
to produce a ≤60-word grounded narrative per cluster.

Rules enforced in system prompt:
- No invented genes, references, or biological claims.
- No override of evidence-based decision or confidence.
- Uncertainty is stated explicitly.

Requires `anthropic` SDK and `ANTHROPIC_API_KEY`. Silently skipped otherwise.
Pass `--no-llm` to disable on the CLI.

---

## Phase 10: 2-File Static HTML Report — ✅ Complete

Replaced Quarto with pure-Python HTML generation. No Quarto dependency.

```text
report/
├── report.html   # Audit view: hero, metrics, Plotly UMAP, attention panel, cluster cards
└── review.html   # Review worksheet: editable dropdowns + CSV download
```

Each cluster card includes:
- Decision badge + confidence row (lineage / subtype / overall).
- Evidence block: marker gene list, marker DB matches, external references, model predictions.
- Reasoning block: supports (green), contradictions (orange), uncertainties (grey), suggestions (blue).
- Uses real `adata.obsm['X_umap']` when available; deterministic placeholder layout otherwise.

---

## Phase 11: Annotate Command — ✅ Complete

Single-command workflow matching the MVP user story:

```bash
scaudit annotate input.h5ad \
  --cluster-key leiden \
  --species mouse \
  --tissue heart \
  --out results/ \
  [--no-llm]
```

Internally creates a temporary config and delegates to `prepare_run()`.

---

## Phase 12: Review and Finalize — ✅ Complete

```bash
scaudit review import results/review_table.csv --run results/
scaudit finalize results/ --out final/
```

Outputs: `final_annotation_cards.json`, `final_annotation_summary.csv`, `review_audit.json`.

---

## MVP Exit Criteria — ✅ Met

The full path works end-to-end:

```bash
scaudit annotate input.h5ad --cluster-key leiden --out results/
# or
scaudit run config.toml

scaudit review import results/review_table.csv --run results/
scaudit finalize results/ --out final/
```

---

# Post-MVP Roadmap

## Phase 13: Gene Harmonization — 🔲 Planned

Critical production layer. Required before cross-dataset references are reliable.

- Gene symbol normalization (case, aliases).
- Ensembl-to-symbol mapping.
- Mouse ↔ human ortholog mapping (one-to-one only by default).
- Missing gene fraction reporting per cluster.
- Gene overlap diagnostic in `diagnosis.json` and report.

```text
WARNING: 22% of query genes not found in reference mouse_heart_v1.
Fix: check gene_id_type in reference manifest (currently 'ensembl', query is 'symbol').
```

---

## Phase 14: QC Evidence Layer — 🔲 Planned

Integrate per-cluster QC metrics as an explicit evidence type.

- `n_counts`, `n_genes`, `pct_counts_mt` per cluster (mean ± std).
- Flags: low gene count, high MT fraction, low total counts.
- Populate `evidence.qc_warnings` in each annotation card.
- Artifact-warning logic should use QC flags, not only cell count.
- Optional integration with Scrublet scores.

---

## Phase 15: Annotated h5ad Output — 🔲 Planned

Write final labels back to `.h5ad`:

```python
adata.obs["scaudit_label"] = ...
adata.obs["scaudit_decision"] = ...
adata.obs["scaudit_confidence"] = ...
adata.uns["scaudit"] = reproducibility_record
```

```bash
scaudit finalize results/ --out final/ --write-h5ad
```

Output: `final/annotated.h5ad`.

---

## Phase 16: Public Reference Ecosystem — 🔲 Planned

Reduce friction for reference discovery and download.

```bash
scaudit reference search --species mouse --tissue heart
scaudit reference download tabula_muris_heart --version 2024
scaudit reference update mouse_heart_v1
```

Potential sources: CELLxGENE, Human Cell Atlas, Tabula Sapiens, Tabula Muris.

Requires: version pinning, checksums, cache management.

---

## Phase 17: Richer Report — 🔲 Planned

Improvements to the existing 2-file HTML report:

- Per-cluster marker dot plots (Plotly heatmap).
- Reference match visualization (Jaccard heatmap across clusters × cell types).
- Evidence completeness summary (which clusters have all evidence sources vs. gaps).
- `methods.html` auto-generated from actual run config.
- `reproducibility.html` rendering `reproducibility.json`.
- UMAP color toggles: by decision, by confidence, by proposed label.
- Click on UMAP cluster → jump to card.

---

## Phase 18: `scaudit debug` Command — 🔲 Planned

Focused per-cluster evidence panel in the terminal:

```bash
scaudit debug --run results/ --cluster 7
```

Shows: decision path, evidence table, top markers, model predictions, reference matches, uncertainty scores.

---

## Phase 19: Batch Effect Detection — 🔲 Planned

- Detect whether `sample` or `batch` key explains significant variance.
- Warn when reference condition (healthy) differs from query condition (disease/tumor).
- Recommend scVI-based correction when batch effect is strong.

---

## Phase 20: Better Ensemble Logic — 🔲 Planned

Current decision engine uses simple rank-based averaging. Future improvements:

- Calibration layer: normalize CellTypist and reference scores to comparable ranges.
- Weighted voting with configurable source weights.
- Hierarchical fallback: if subtype disagrees, fall back to lineage-level label.
- Novel cell detection: low reference similarity + high internal consistency + distinct markers.

---

## Phase 21: Cell State Separation — 🔲 Planned

Separate cell type (identity) from cell state (activity/condition).

```json
{
  "cell_type": "Cardiomyocyte",
  "cell_state": "stress_response",
  "state_evidence": ["NPPA", "NPPB", "HSPA1A"]
}
```

Potential method: NMF or gene program scoring (decoupler).

---

## Phase 22: Condition Comparison — 🔲 Planned

When `condition_key` is provided:

- Cell type abundance differences across conditions.
- Marker program differences per condition.
- UMAP split by condition.
- `comparison.html` in the report.

---

## Phase 23: Scale and Performance — 🔲 Planned (Post-MVP)

- Per-cluster parallelization for marker evidence.
- Cached reference marker sets (skip re-computing DE for unchanged references).
- Resume failed runs.
- Structured logs to `results/logs/scaudit.log`.
- Memory-aware h5ad loading for datasets >500k cells.

---

## Phase 24: Web App and Team Mode — ⏸ Deferred

- Browser-based review UI (no CSV editing).
- Shared reference registry.
- Team review state.
- Run provenance database.
- API.

---

## Risk Register

| Risk | Mitigation |
|---|---|
| Scope creep before MVP is stable | Phase gate: don't add post-MVP features until annotate → review → finalize is solid on real datasets |
| Gene ID mismatch silently corrupts reference matching | Phase 13 gene harmonization — flag and report mismatches explicitly |
| LLM explanations overstate confidence | System prompt enforces evidence grounding; LLM output never touches `decision` field |
| Report becomes unreadable with many clusters | Add filtering/search to cluster card list; paginate beyond ~50 clusters |
| CellTypist model drift between versions | Pin model version in `reproducibility.json` |
