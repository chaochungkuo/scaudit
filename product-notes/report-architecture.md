# HTML Report Architecture

This document defines the proposed structure for scaudit's HTML reporting system. The report should feel like a polished scientific analysis portal, not a single long static notebook.

## Design Goal

The report should be:

- Clear in hierarchy.
- Easy to navigate.
- Beautiful but restrained.
- Scientific and publication-ready.
- Useful for both quick overview and deep inspection.
- Built around evidence, uncertainty, and reviewability.

The report should not feel like a raw notebook export. It should feel like a structured annotation audit dossier.

## Core Principle

Use a multi-page report structure:

```text
index.html
-> overview and navigation hub
-> links to focused subreports
-> each subreport answers one analysis question
```

This avoids making users scroll through an overwhelming single page and allows each level of detail to have its own layout.

## Proposed Report Folder

```text
report/
├── index.html
├── dataset.html
├── annotation.html
├── clusters/
│   ├── index.html
│   ├── cluster_0.html
│   ├── cluster_1.html
│   └── cluster_2.html
├── evidence.html
├── references.html
├── uncertainty.html
├── comparison.html
├── review.html
├── methods.html
├── reproducibility.html
├── figures/
├── tables/
└── assets/
```

## Page 1: `index.html`

## Purpose

The entry point and navigation hub.

It should answer:

```text
What dataset is this?
What did scaudit conclude?
What needs attention?
Where should I click next?
```

## Sections

### Hero Summary

Content:

- Project / dataset name.
- Species, tissue, condition, sample count, cell count.
- Run date and scaudit version.
- Overall annotation status.

Example:

```text
Mouse heart single-cell annotation audit
42,381 cells · 18 clusters · 4 samples · 2 conditions
Annotation status: 14 accepted, 3 ambiguous, 1 needs review
```

### Key Metrics

Use compact metric tiles:

```text
Cells
Clusters
Accepted labels
Ambiguous clusters
Unknown clusters
Reference match
Model agreement
```

### Main Navigation

Primary navigation cards:

```text
Dataset overview
Annotation summary
Cluster reports
Evidence audit
Reference audit
Uncertainty
Condition comparison
Review table
Methods
Reproducibility
```

### Executive Summary

A short human-readable summary:

- Main annotation findings.
- Strongest supported cell types.
- Ambiguous or suspicious clusters.
- Recommended review priorities.

### Attention Panel

A prioritized list:

```text
Needs review:
- Cluster 7: conflicting T cell / NK evidence
- Cluster 12: low gene overlap with selected reference
- Cluster 15: possible doublet or ambient RNA signal
```

### Global UMAP

Interactive Plotly UMAP:

- Color by final annotation.
- Toggle by cluster, sample, condition, confidence.
- Click cluster links to cluster-level pages if possible.

## Page 2: `dataset.html`

## Purpose

Dataset diagnosis and QC.

It should answer:

```text
What is the input dataset, and is it suitable for annotation?
```

## Sections

- Input file and metadata summary.
- Cell and gene counts.
- Sample / batch / condition distribution.
- QC metrics.
- Cluster size distribution.
- Detected metadata keys.
- Warnings about missing metadata.
- Batch effect diagnostic summary.

## Figures

- UMAP by sample.
- UMAP by condition.
- UMAP by batch.
- QC violin plots.
- Cluster size bar plot.

## Page 3: `annotation.html`

## Purpose

High-level annotation summary.

It should answer:

```text
What labels were assigned, and how confident are they?
```

## Sections

- Annotation summary table.
- Final label per cluster.
- Decision state per cluster.
- Confidence by lineage and subtype.
- Accepted / ambiguous / unknown / needs review counts.
- Link to each cluster detail page.

## Figures

- UMAP by final annotation.
- UMAP by decision status.
- Confidence heatmap.
- Cluster-label summary bar chart.

## Page 4: `clusters/index.html`

## Purpose

Cluster report directory.

It should answer:

```text
Which clusters exist, what are their labels, and which ones need attention?
```

## Sections

- Searchable cluster table.
- Filter by decision status.
- Filter by confidence.
- Filter by cell type lineage.
- Links to individual cluster pages.

## Cluster Table Columns

```text
Cluster
Final label
Decision
Lineage confidence
Subtype confidence
Top markers
Top model prediction
Top reference match
Warnings
Review priority
```

## Page 5: `clusters/cluster_<id>.html`

## Purpose

The most important detail page. Each cluster gets one annotation card page.

It should answer:

```text
Why was this cluster assigned this label, and should I trust it?
```

## Sections

### Cluster Header

- Cluster ID.
- Final label.
- Decision status.
- Confidence badges.
- Cell count and percentage.
- Review priority.

### Final Decision

Clear decision block:

```text
Final decision: Cardiomyocyte
Lineage confidence: high
Subtype confidence: medium
Decision: Accepted
```

### Evidence Summary

A compact summary of:

- Marker evidence.
- Reference evidence.
- Model evidence.
- Ontology / hierarchy evidence.
- QC warnings.

### Marker Evidence

Content:

- Top marker table.
- Known marker support.
- Contradictory markers.
- Suggested validation markers.

Figures:

- Marker dot plot.
- Marker heatmap.
- Violin plots for selected markers.

### Reference Evidence

Content:

- Best matching reference.
- Similarity score or category.
- Reference version.
- Metadata match.
- Gene overlap.
- Reference bias warnings.

### Model Evidence

Content:

- Model predictions.
- Scores / confidence.
- Agreement or disagreement.
- Per-cell prediction distribution within the cluster.

### Uncertainty

Content:

- What is known.
- What is unresolved.
- Why confidence is limited.
- Alternative hypotheses.

### LLM Explanation

Evidence-grounded explanation:

- Summary.
- Supports.
- Contradictions.
- Uncertainties.
- Suggested validation.

### Review Panel

Human review fields:

```text
Accept label
Change label
Mark ambiguous
Mark unknown
Add note
```

In static HTML, this can initially be represented as an exported review table rather than live editing.

## Page 6: `evidence.html`

## Purpose

Cross-cluster evidence audit.

It should answer:

```text
How consistent is the evidence across the whole dataset?
```

## Sections

- Marker evidence matrix.
- Model agreement matrix.
- Reference similarity matrix.
- Evidence completeness table.
- Contradiction table.

## Figures

- Marker heatmap.
- Model agreement heatmap.
- Reference similarity heatmap.
- Evidence radar or stacked score chart per cluster.

## Page 7: `references.html`

## Purpose

Reference selection and reference bias audit.

It should answer:

```text
Which references were used, why were they selected, and are they appropriate?
```

## Sections

- Reference list.
- Reference manifest.
- Reference scoring table.
- Metadata match.
- Gene overlap report.
- Label coverage.
- Reference bias warnings.

## Figures

- Reference score bar plot.
- Gene overlap plot.
- Label coverage chart.

## Page 8: `uncertainty.html`

## Purpose

Focused uncertainty and risk view.

It should answer:

```text
Where should the user be careful?
```

## Sections

- Ambiguous clusters.
- Unknown clusters.
- Needs-review clusters.
- Artifact warnings.
- Model disagreement.
- Low reference support.
- Weak marker support.

## Figures

- UMAP by uncertainty.
- Decision status map.
- Model disagreement heatmap.
- Review priority plot.

## Page 9: `comparison.html`

## Purpose

Condition or group comparison, if metadata exists.

It should answer:

```text
How do annotations, abundance, or states differ across conditions?
```

## Sections

- Condition metadata summary.
- Cell type abundance comparison.
- Cluster abundance comparison.
- State or marker program differences.
- WT vs mutant interpretation, if applicable.

## Figures

- Abundance bar plots.
- Stacked composition plots.
- UMAP split by condition.
- Marker or gene program comparison plots.

If no condition key exists, this page should gracefully state that condition comparison was not run.

## Page 10: `review.html`

## Purpose

Human review workflow.

It should answer:

```text
What should the expert review, and how can corrections be made?
```

## Sections

- Review priority table.
- Editable CSV instructions.
- Current accepted / changed / pending labels.
- Link to exported review file.

## Review Table Columns

```text
cluster_id
proposed_label
decision
confidence
review_status
reviewed_label
reviewer_note
```

## Page 11: `methods.html`

## Purpose

Paper-ready methods description.

It should answer:

```text
How was this annotation generated?
```

## Sections

- Input data.
- Preprocessing.
- Marker evidence.
- Reference selection.
- Model evidence.
- Evidence fusion.
- Decision rules.
- LLM explanation policy.
- Software versions.

This page should be suitable for copying into a manuscript or supplement after light editing.

## Page 12: `reproducibility.html`

## Purpose

Full reproducibility record.

It should answer:

```text
Can this annotation run be audited and reproduced?
```

## Sections

- scaudit version.
- Input file hash.
- Parameters.
- Reference versions.
- Model versions.
- Dependency environment.
- Runtime metadata.
- Output file manifest.

## Navigation Design

## Global Sidebar

Every page should include a persistent sidebar:

```text
Overview
Dataset
Annotation
Clusters
Evidence
References
Uncertainty
Comparison
Review
Methods
Reproducibility
```

## Breadcrumbs

Cluster pages should include breadcrumbs:

```text
Overview > Clusters > Cluster 4
```

## Status Badges

Use consistent badges:

```text
Accepted       green
Ambiguous      yellow
Unknown        gray
Needs review   orange
Artifact       red
```

## Visual Style

Recommended style:

- Clean scientific dashboard.
- White or very light background.
- Deep navy text and structure.
- Purple / blue / teal / green accents from the logo.
- Compact cards for metrics and cluster summaries.
- Tables that are searchable and sortable.
- Figures embedded near the interpretation they support.

Avoid:

- Raw notebook-style vertical dumps.
- Overly decorative landing pages.
- Hiding important warnings below long figures.
- Too many colors without semantic meaning.

## Report Generation Strategy

Quarto can generate this structure as a multi-page website rather than a single document.

Recommended source structure:

```text
report_src/
├── _quarto.yml
├── index.qmd
├── dataset.qmd
├── annotation.qmd
├── clusters/
│   ├── index.qmd
│   └── cluster_template.qmd
├── evidence.qmd
├── references.qmd
├── uncertainty.qmd
├── comparison.qmd
├── review.qmd
├── methods.qmd
└── reproducibility.qmd
```

The CLI can generate `.qmd` files from structured JSON outputs, then call Quarto to render HTML.

## MVP Report Scope

MVP should generate:

```text
index.html
annotation.html
clusters/index.html
clusters/cluster_<id>.html
methods.html
reproducibility.html
```

Can be deferred:

```text
comparison.html
review.html with live interactions
advanced evidence heatmaps
full Excel-linked navigation
```

## Final Report Promise

The report should make the user feel:

```text
I can understand the annotation.
I can see the evidence.
I know what to trust.
I know what needs review.
I can share this with collaborators or reviewers.
```
