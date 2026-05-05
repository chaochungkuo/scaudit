# Product Design

This document consolidates the current product design for scaudit across CLI experience, evidence construction, reference management, LLM reasoning, Quarto reporting, and human review.

## Project Description

**scaudit** is a transparent, evidence-based framework for single-cell RNA-seq annotation that transforms annotation from a black-box prediction task into an **auditable, reproducible, and interpretable decision-making process**.

Given a single-cell dataset, scaudit does not simply assign cell type labels. Instead, it:

- Selects and evaluates relevant reference datasets.
- Integrates multiple annotation strategies, including marker-based, reference-based, and model-based methods.
- Constructs structured, multi-source evidence for each cluster.
- Identifies agreement, ambiguity, and contradiction across methods.
- Generates interpretable reasoning using LLM assistance.
- Produces **interactive, publication-grade reports via Quarto**.
- Enables human review and correction.
- Outputs fully reproducible annotation records.

The final output is not just an annotated dataset, but a **complete annotation audit trail**.

## Product Positioning

scaudit should be positioned as:

```text
a single-cell annotation audit and reporting framework
```

It should not be positioned as a new model that replaces CellTypist, scANVI, SingleR, Scanpy, or expert review. Its value is to integrate those kinds of evidence into a coherent decision record.

## Target Users

Primary users:

- Computational biologists who need to annotate datasets and explain the decision process.
- Bioinformatics core facilities that need standardized, reproducible client deliverables.
- Disease biology and translational labs that need to distinguish known cell types, altered states, artifacts, and novel candidates.

Secondary users:

- Methods developers comparing annotation strategies.
- Collaborators and reviewers inspecting annotation decisions.

## MVP Boundary

The first version should prove the audit workflow, not the full platform.

MVP should include:

- AnnData `.h5ad` input.
- Cluster-level annotation cards.
- Marker evidence.
- One lightweight model or reference evidence source.
- Reproducibility record.
- Quarto HTML report.
- Optional evidence-grounded LLM explanation.

MVP should defer:

- Web app.
- Foundation model integration.
- R-based methods.
- Complex ontology reasoning.
- Full Excel workbook if CSV outputs are sufficient initially.

## Design Philosophy

### 1. Annotation Is a Decision, Not a Prediction

```text
Annotation = Evidence + Reasoning + Decision
```

Every result must answer:

- Why is this label assigned?
- What evidence supports it?
- What is uncertain?
- What should be validated?

### 2. No Black Boxes

scaudit explicitly exposes:

- Reference datasets used.
- Model predictions and agreement.
- Marker gene support and contradictions.
- Ontology-level consistency.

Users can trace every annotation step.

### 3. Multiple Methods, Unified

```text
Marker-based evidence      -> biological interpretability
Reference-based mapping    -> biological grounding
Model-based prediction     -> statistical inference
Ontology reasoning         -> hierarchical consistency
LLM explanation            -> human-readable interpretation
```

### 4. Uncertainty Is First-Class

Instead of forcing labels, scaudit highlights:

- Ambiguous clusters.
- Conflicting evidence.
- Low-confidence assignments.
- Potential novel or disease-specific states.

### 5. LLM as Reasoning Layer

LLMs are used to:

- Summarize evidence.
- Explain decisions.
- Detect contradictions.
- Suggest validation.

LLMs **do not replace evidence** and never act as the sole decision-maker.

### 6. Reproducibility by Design

Each run records:

- Reference versions.
- Model versions.
- Parameters.
- Evidence structure.

Results are **auditable and publication-ready**.

## System Architecture

```text
Input dataset
-> Dataset diagnosis
-> Reference selection
-> Evidence construction
    ├─ Marker-based
    ├─ Reference-based
    ├─ Model-based
    └─ Ontology-based
-> Evidence fusion
-> Uncertainty estimation
-> Decision
-> LLM explanation
-> Report generation (Quarto)
-> Human review (optional)
-> Final outputs
```

## CLI User Experience

### Basic Usage

```bash
scaudit annotate heart.h5ad \
  --species mouse \
  --tissue heart \
  --out results/
```

The system automatically:

1. Diagnoses dataset structure.
2. Selects relevant references.
3. Runs annotation methods.
4. Builds evidence.
5. Generates report.

### Advanced Usage

```bash
scaudit run config.yaml
```

Example config:

```yaml
dataset:
  species: mouse
  tissue: heart
  condition_key: genotype

references:
  auto_select: true

methods:
  marker_based: true
  reference_based: true
  model_based:
    celltypist: true
    scanvi: true

llm:
  enabled: true
  mode: explain_only

output:
  quarto_report: true
  excel_workbook: true
```

### Reference Management

```bash
scaudit reference search --species mouse --tissue heart
scaudit reference add my_ref.h5ad
scaudit reference list
```

Reference selection is transparent and auditable.

## Output System

scaudit treats output as a **first-class component**.

## Quarto-Based Interactive HTML Report

```text
report.html
report.qmd
```

Features:

- Interactive Plotly UMAP.
- Dataset overview and QC.
- Reference audit.
- Annotation summary.
- Cluster-level annotation cards.
- Marker evidence.
- Model agreement / disagreement.
- Ambiguous / unknown clusters.
- WT vs mutant comparison.
- LLM explanations.
- Export-ready figures.

## Interactive Figures

Plotly figures include:

- UMAP by annotation.
- UMAP by sample / condition.
- Confidence map.
- Reference similarity map.
- Marker heatmaps.
- Model agreement plots.
- Abundance comparison plots.

## Excel Workbook

```text
scaudit_results.xlsx
```

Sheets:

```text
Summary
Cluster Annotation
Marker Evidence
Reference Audit
Model Predictions
Ambiguous Clusters
Unknown Candidates
Condition Comparison
Review Table
Reproducibility
```

## Additional Outputs

```text
annotated.h5ad
annotation_cards.json
reproducibility.json
CSV/TSV tables
interactive figure files
```

## Annotation Card

Each cluster is represented as a core output unit:

```text
Cluster 4 — Cardiomyocyte

Final decision:
Cardiomyocyte

Resolution:
- lineage: high confidence
- subtype: uncertain

Marker evidence:
Tnnt2, Myh6, Actc1

Reference evidence:
mouse heart atlas (similarity 0.91)

Model evidence:
scANVI: 0.89

LLM explanation:
Consistent with cardiomyocytes, but subtype unresolved.

Suggested validation:
Check Myl2, Nppa, Nppb
```

## Human Review Workflow

```bash
scaudit review export results/
scaudit review import reviewed.csv
scaudit finalize results/
```

The workflow supports manual correction and versioned annotation.

## Deployment Strategy

```text
CLI (core engine)        -> local, reproducible
Server (optional GPU)    -> heavy computation
Web app (future)         -> visualization + interaction
```

## Vision

scaudit redefines single-cell annotation as:

```text
a transparent, evidence-driven, and explainable process
```

It bridges:

- Computational models.
- Biological knowledge.
- Human reasoning.

## Tagline Candidates

```text
Not just annotation — but annotation you can trust.
```

```text
From labels to evidence.
```

## Core Question

scaudit is not only answering:

```text
What cell type is this?
```

It is answering:

```text
Why is this the cell type, and should I trust it?
```
