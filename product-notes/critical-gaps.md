# Critical Gaps and Design Blind Spots

This document captures important design gaps that should be resolved before implementation. These issues determine whether scaudit becomes a basic annotation tool or a robust single-cell annotation operating system.

## Summary

scaudit already has a strong architecture around CLI, evidence, references, LLM reasoning, Quarto reporting, and reproducible outputs. The remaining critical work is to define the hidden production layers:

- Feature and gene identifier harmonization.
- Reference bias and versioning.
- Calibration and ensemble decision logic.
- LLM boundaries and hallucination guards.
- Debugging, caching, and reproducibility infrastructure.
- Scientific interpretation layers such as novel cell detection and cell state separation.

## 1. Core Algorithm Layer

### 1.1 Gene ID / Feature Harmonization

Different datasets may use inconsistent gene identifiers:

```text
- Ensembl ID vs gene symbol
- Mouse vs human orthologs
- Inconsistent gene filtering
```

If this layer is missing, reference mapping can fail or become misleading.

scaudit needs a gene mapping layer:

```text
- Gene symbol normalization
- Ortholog mapping, especially mouse <-> human
- Missing gene handling
- Explicit record of gene matching statistics
```

This is one of the first major production pitfalls.

### 1.2 Cell-Level vs Cluster-Level Decisions

The annotation unit must be explicit:

```text
- Cell-level annotation is noisy.
- Cluster-level annotation is more stable.
```

Recommended principle:

```text
Compute at cell level, decide at cluster level.
```

Cell-level evidence can be aggregated into cluster-level decisions, reducing instability while preserving detailed signal.

### 1.3 Doublet / Low-Quality Cell Detection

Many unknown or ambiguous clusters may actually represent artifacts:

```text
- Doublets
- Dying cells
- Ambient RNA
- Low-quality cells
```

scaudit should integrate QC warnings and possibly doublet detection concepts such as Scrublet or DoubletFinder.

Without this layer, artifacts may be misinterpreted as biological novelty.

## 2. Reference System

### 2.1 Reference Bias Detection

Reference selection alone is not enough. scaudit also needs to detect whether a selected reference is biased relative to the query.

Example:

```text
Reference: healthy tissue
Query: tumor tissue
```

This can introduce systematic mismatch.

Expected output:

```text
Reference bias warning:
Query dataset differs from reference condition (tumor vs healthy).
```

### 2.2 Reference Versioning

Annotation must record reference identity and version.

Example:

```json
{
  "reference": "mouse_heart_atlas_v1",
  "version": "2026-05-01",
  "source": "cellxgene"
}
```

Without versioning, results cannot be reproduced.

## 3. Model Layer

### 3.1 Batch Effect Detection

scaudit should distinguish batch effect detection from batch correction.

Important question:

```text
When should batch correction be recommended?
```

Example UX:

```text
Batch detected: sample explains 35% variance.
Recommendation: run scVI-based correction or model-aware annotation.
```

### 3.2 Model Calibration

Scores from different models are not directly comparable:

```text
CellTypist 0.8 != scANVI 0.8
```

scaudit needs score normalization or calibration before evidence fusion.

Without calibration, model voting can become misleading.

### 3.3 Ensemble Strategy

Decision behavior must be defined when methods disagree.

Example:

```text
CellTypist = T cell
scANVI = NK cell
```

The system needs explicit rules:

```text
- Voting
- Weighted voting
- Evidence override
- Hierarchical fallback
- Ambiguous decision when conflict remains unresolved
```

## 4. LLM Layer

### 4.1 Prompt Design

LLM input should be structured evidence, not raw data.

Example:

```json
{
  "markers": [],
  "reference": {},
  "model_predictions": {},
  "uncertainty": {}
}
```

### 4.2 Hallucination Guard

The LLM must not invent evidence.

Explicit restrictions:

```text
LLM cannot:
- Invent marker genes
- Invent references
- Invent biological claims not present in the evidence
- Override evidence-based decisions
```

Allowed behavior:

```text
LLM can:
- Summarize provided evidence
- Explain contradictions
- Suggest validation based on explicit evidence
- State uncertainty clearly
```

### 4.3 Explain vs Decide Boundary

The LLM is an explanation layer, not a decision engine.

Enforcement rule:

```text
LLM cannot override evidence decision.
```

## 5. System Engineering Layer

### 5.1 Logging and Debug System

Users will need to inspect specific decisions.

Example command:

```bash
scaudit debug --cluster 7
```

Expected role:

```text
Explain why cluster 7 received its label, including evidence, scores, references, model outputs, uncertainty, and decision path.
```

### 5.2 Cache System

Reference mapping and model inference can be slow.

Likely cache targets:

```text
- Reference embeddings
- Query embeddings
- Model outputs
- Marker results
- LLM explanations
```

### 5.3 Parallelization

Many operations can be parallelized:

```text
- Per cluster
- Per reference
- Per model
- Per output figure
```

Without parallelization, large datasets may become too slow.

## 6. Scientific Interpretation Layer

### 6.1 Novel Cell Detection

Novel cell detection should be formalized.

Potential definition:

```text
Low reference similarity
+ High internal consistency
+ Distinct marker or gene program
= Novel candidate
```

This could become a paper-level differentiating feature.

### 6.2 State vs Cell Type Distinction

The system should separate cell type from cell state.

Example:

```text
Cell type: cardiomyocyte
State: stress_response
```

This distinction is one of the hardest problems in annotation and should be represented explicitly.

### 6.3 Cross-Condition Interpretation

WT vs mutant or condition comparisons should be formalized.

Potential outputs:

```text
- Delta abundance
- Delta gene program
- Delta cell state
```

## 7. Output Layer

### 7.1 Methods Auto-Generation

scaudit can generate a paper-ready Methods section using Quarto templates.

Expected output:

```text
Methods section for publication or supplement.
```

### 7.2 Publication-Ready Figure Export

Outputs should include static publication formats, not only interactive figures.

Formats:

```text
PNG
SVG
PDF
```

### 7.3 Data Package Export

scaudit should support a shareable export package.

Example package contents:

```text
- annotated.h5ad
- report.html
- report.qmd
- tables
- figures
- config
- reproducibility.json
```

## Top Five Definitions Needed Before Coding

Before implementation starts, the following five areas should be defined first:

```text
1. Gene ID harmonization
2. Reference scoring function
3. Evidence schema (JSON)
4. Ensemble decision rule
5. LLM boundary and forbidden behaviors
```

## Core Reframe

scaudit is no longer only:

```text
an annotation tool
```

It is becoming:

```text
a single-cell annotation operating system
```
