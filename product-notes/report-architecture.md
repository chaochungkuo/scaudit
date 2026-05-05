# HTML Report Architecture

This document defines the structure and design of scaudit's HTML reporting system.

## Current Implementation

scaudit generates **2 static HTML files**, no server required, no Quarto dependency.

```text
report/
├── report.html   # Annotation audit view
└── review.html   # Human review worksheet
```

Both files are fully self-contained (inline CSS + JS). The Plotly CDN is loaded
asynchronously; the chart degrades gracefully to a "Loading…" overlay when offline.

---

## report.html — Audit View

### Sections

**Hero**
- Dataset path.
- Decision pill summary (`Accepted`, `Ambiguous`, `Needs review`, `Artifact warning`).

**Metrics grid**
- Cells, Genes, Clusters, Needs attention.

**Cluster overview (Plotly UMAP)**
- One trace per cluster, colored by decision state.
- Hover: cluster ID, proposed label, decision, confidence, cell count.
- Uses real `adata.obsm['X_umap']` when available (sampled ≤500 pts/cluster).
- Falls back to deterministic Gaussian blobs (seeded, polar layout) when UMAP is absent.
- Async CDN load (`plotly-2.35.2.min.js`); loading overlay while pending.

**Attention panel**
- All clusters with decision ∈ {Ambiguous, Unknown, Needs review, Artifact warning}.
- Quick links to cluster card anchors.

**Warning list**
- Propagated from `diagnosis.warnings` (missing cluster key, unreadable file, etc.).

**Cluster cards** (one `<details>` per cluster)
- Decision-color left border.
- Summary row: badge + cluster label + proposed label + confidence + cell count.
- Confidence row: lineage / subtype / overall badges.
- Evidence block:
  - **Markers**: top gene names (comma-separated).
  - **Marker DB**: builtin marker DB matches with Jaccard scores.
  - **References**: external reference h5ad matches.
  - **Models**: CellTypist label + probability %.
  - **QC flags**: (when populated).
- Reasoning block:
  - Supports (green left border).
  - Contradictions (orange).
  - Uncertainties (grey).
  - Suggested validation (blue).
- Cards for `Needs attention` decisions are open by default.

**Methods section**
- Evidence sources used, software versions, dataset metadata.

---

## review.html — Review Worksheet

**Purpose**: human reviewers accept, change, or flag cluster labels without running code.

**Features**:
- One row per cluster: proposed label, scaudit decision badge, decision dropdown, new label input, note input.
- JavaScript `downloadCSV()` exports the filled table as `review_table.csv`.
- Import: `scaudit review import review_table.csv --run results/`

**Review table schema**:

```csv
cluster_id, proposed_label, decision, confidence, review_status, reviewed_label, reviewer_note
```

---

## Visual Design

**Color palette** (CSS variables):

```css
--green:   #2a9d5c   /* Accepted */
--orange:  #c9600a   /* Needs review */
--amber:   #d97706   /* Ambiguous */
--muted:   #8899aa   /* Unknown */
--red:     #c0392b   /* Artifact warning */
--navy:    #1a2e4a   /* Primary text */
--border:  #dce4f0   /* Borders */
```

**Cluster card left borders** use `data-decision` attribute for CSS targeting:

```css
.cluster-card[data-decision="Accepted"]       { border-left-color: var(--green); }
.cluster-card[data-decision="Needs review"]   { border-left-color: var(--orange); }
.cluster-card[data-decision="Ambiguous"]      { border-left-color: var(--amber); }
.cluster-card[data-decision="Artifact warning"] { border-left-color: var(--red); }
```

**Confidence badges** use `.conf-high`, `.conf-medium`, `.conf-low`, `.conf-unknown` classes.

**Reasoning blocks** use `.rblock-support`, `.rblock-conflict`, `.rblock-uncertain`, `.rblock-suggest`.

---

## Generation

```python
from scaudit.report import render_draft_report, render_final_report

# Draft (after scaudit run)
render_draft_report(report_dir, diagnosis_path, annotation_cards_path)

# Final (after scaudit finalize)
render_final_report(report_dir)
```

`render_draft_report` writes both `report.html` and `review.html`.
`render_final_report` writes a summary `report.html` confirming final outputs.

---

## Planned Improvements (Post-MVP)

### Additional sections in report.html

- **Marker evidence heatmap**: Plotly heatmap of top marker scores across clusters.
- **Reference match matrix**: Jaccard similarity heatmap (clusters × known cell types).
- **Evidence completeness panel**: which clusters have all evidence sources vs. gaps.
- **UMAP color toggles**: switch between decision, confidence, proposed label.

### Additional pages

When the cluster count exceeds ~50, a second file may be introduced:

```text
report/
├── report.html          # Summary + UMAP + attention panel
├── review.html          # Review worksheet
├── clusters.html        # Searchable/filterable cluster table
└── methods.html         # Auto-generated methods text
```

### Click-through navigation

UMAP trace `customdata` → click → jump to cluster card anchor (already feasible with
`Plotly.react` click events and `location.hash`).

### Offline-first

Bundle Plotly inline when `--offline` is passed to avoid CDN dependency for
air-gapped compute environments.

---

## Design Principles

- One file = one purpose. `report.html` is for understanding; `review.html` is for deciding.
- All outputs are static. No server, no database, no build step.
- Graceful degradation: every section has a sensible fallback when data is absent.
- Evidence is always shown before the decision that derived from it.
- Uncertainty is surfaced prominently, not buried.
