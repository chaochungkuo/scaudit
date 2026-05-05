# Critical Gaps and Known Limitations

This document tracks important production gaps and design limitations.
Items marked ✅ have been addressed; items marked 🔲 are still open.

---

## 1. Core Algorithm Layer

### 1.1 Gene ID / Feature Harmonization — 🔲 Highest priority

Different datasets use inconsistent gene identifiers:

```text
- Ensembl ID vs gene symbol
- Mouse vs human orthologs
- Inconsistent filtering
```

**Current state**: scaudit assumes symbols throughout. If a reference uses Ensembl IDs
and the query uses symbols, Jaccard will be 0 and no reference matches will be found —
silently, with no warning.

**What's needed**:
- Gene symbol normalization (case, aliases).
- Ensembl-to-symbol mapping.
- Mouse ↔ human ortholog table (one-to-one only by default).
- Gene overlap fraction reported per reference pair.
- Warning when overlap < 50%: `"Only 31% of query genes found in reference; results may be unreliable."`

See roadmap Phase 13.

---

### 1.2 QC Evidence Layer — 🔲

Many `Artifact warning` and `Needs review` decisions involve QC signals, but scaudit
currently only flags clusters with < 10 cells. No per-cluster QC metrics are computed.

**What's needed**:
- Per-cluster mean ± std for `n_counts`, `n_genes_by_counts`, `pct_counts_mt`.
- Populate `evidence.qc_warnings` when values are outliers.
- Integrate Scrublet or DoubletFinder scores if present in `.obs`.

See roadmap Phase 14.

---

### 1.3 Annotated `.h5ad` Output — 🔲

`scaudit finalize` writes JSON and CSV outputs but does not write labels back to `.h5ad`.

**What's needed**:
```python
adata.obs["scaudit_label"] = ...
adata.obs["scaudit_decision"] = ...
adata.obs["scaudit_confidence"] = ...
adata.uns["scaudit"] = reproducibility_record
```

See roadmap Phase 15.

---

## 2. Reference System

### 2.1 Reference Bias Detection — 🔲

A selected reference may be systematically mismatched to the query.

Example: reference is healthy tissue, query is tumor tissue.

**What's needed**:
- Metadata comparison: species, tissue, condition, technology.
- Warning when query condition differs from reference condition.
- Gene overlap fraction as a proxy for compatibility.
- Report a reference bias warning in the report's attention panel.

---

### 2.2 Reproducibility: Input Hash and Reference Versions — 🔄 Partial

`reproducibility.json` currently records scaudit version, Python version, and timestamp.
`input_hash` is `null`. CellTypist model version is not recorded.

**What's needed**:
- SHA-256 hash of input `.h5ad`.
- CellTypist model name and version.
- Reference checksums (already in manifest schema, not yet computed).

---

### 2.3 Public Reference Discovery — 🔲

Users must supply reference `.h5ad` files manually via `scaudit reference add`.
There is no discovery, search, or download from public databases.

See roadmap Phase 16.

---

## 3. Model Layer

### 3.1 Model Calibration — 🔲

Scores from different models are not directly comparable:
```text
CellTypist 0.8 ≠ scANVI 0.8
```

**Current state**: CellTypist probability (majority-vote fraction) is used directly.
When additional models are added, calibration will be needed before evidence fusion.

---

### 3.2 Ensemble Strategy — 🔄 Rule-based only

Current decision logic is rule-based (single model, no weighted voting).
When multiple models produce conflicting signals, the decision is `Ambiguous`.

**What's needed for Phase 20**:
- Weighted voting across models.
- Hierarchical fallback to lineage when subtype disagrees.
- Configurable source weights in `config.toml`.

---

### 3.3 Batch Effect Detection — 🔲

scaudit does not detect whether batch/sample explains significant variance.

**What's needed**:
- Check whether `sample` or `batch` key (if present) correlates with UMAP structure.
- Warn when batch explains a large fraction of cluster separation.
- Recommend scVI-based correction when batch effect is strong.

---

## 4. LLM Layer

### 4.1 Prompt Robustness — 🔄 Basic guardrails in place

The current system prompt includes prohibitions against inventing evidence or overriding
decisions. However, there is no automated check that the LLM output complies.

**What's needed**:
- Post-processing check: does the output contain gene names not in the evidence?
- Confidence-hedging audit: does the summary overstate evidence strength?
- Fallback to rule-based summary when LLM is unavailable or output fails checks.

---

### 4.2 LLM Model Pinning — 🔲

The model ID (`claude-haiku-4-5-20251001`) is hardcoded. If the model is deprecated,
runs will fail silently or produce degraded output.

**What's needed**:
- Record LLM model ID in `reproducibility.json`.
- Allow override via config or environment variable.

---

## 5. System Engineering Layer

### 5.1 No Structured Logging — 🔲

No log file is written. Errors from optional evidence steps (CellTypist, reference matching)
are silently caught and discarded.

**What's needed**:
- Structured log file: `results/logs/scaudit.log`.
- Warning entries for every caught exception in evidence computation.
- `--verbose` flag for detailed terminal output.

---

### 5.2 No Caching — 🔲

Each run re-reads the input `.h5ad`, re-computes all DE tests, and re-runs CellTypist.
For large datasets (>100k cells) this is expensive.

**What's needed**:
- Cache reference DE results (skip if reference h5ad unchanged).
- Cache CellTypist predictions (skip if input cells unchanged).
- Cache marker results (skip if expression matrix unchanged).

---

### 5.3 No `scaudit debug` Command — 🔲

Users cannot inspect why a specific cluster received its decision from the terminal.

See roadmap Phase 18.

---

### 5.4 Performance on Large Datasets — 🔲

`ad.read_h5ad(path)` in `compute_cluster_evidence()` loads the entire expression matrix
into memory. For datasets >500k cells this may exceed available RAM.

**Mitigation**: use `backed="r"` + subsample for marker computation, or defer to
a chunked implementation.

---

## 6. Scientific Interpretation Layer

### 6.1 Novel Cell Detection — 🔲

Clusters with low reference similarity + high internal consistency + distinct markers
are likely biologically novel. scaudit does not currently flag these separately.

**Proposed definition**:
```text
best reference Jaccard < 0.05
+ ≥ 3 strong markers
+ no CellTypist match with probability > 0.6
= potential novel cell type candidate
```

Assign `decision = "Novel candidate"` and surface in attention panel.

---

### 6.2 Cell State vs Cell Type — 🔲

scaudit assigns a single `proposed_label` (cell type identity). Activated or stress states
are not distinguished from the cell type itself.

**What's needed**:
- Gene program scoring (decoupler / NMF) to separate state from type.
- Optional `cell_state` field in annotation card.

---

### 6.3 Condition Comparison — 🔲

When a `condition_key` is provided, scaudit currently ignores it.

**What's needed**:
- Cell type abundance per condition.
- Marker program differences between conditions.
- Optional `comparison.html` in the report.

---

## Top Priorities Before First Production Use

```text
1. Gene harmonization         — without it, reference matching is unreliable on real data
2. QC evidence layer          — artifact detection needs more than cell count
3. Annotated h5ad output      — users need labels written back to their dataset
4. End-to-end test on real data — validate pipeline on a public dataset (e.g., Tabula Muris)
5. Input file hash             — reproducibility requires it
```
