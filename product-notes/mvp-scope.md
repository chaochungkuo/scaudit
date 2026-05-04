# MVP Scope and Development Gate

This document defines the recommended first build of scaudit and the design decisions that should be locked before implementation starts.

## MVP Goal

Build the smallest useful version of scaudit that proves the core thesis:

```text
single-cell annotation can be represented as evidence + reasoning + decision
```

The MVP should produce an auditable annotation report, not a comprehensive single-cell platform.

## MVP User Story

A computational biologist has a clustered `.h5ad` file and wants to annotate clusters for a collaborator or paper.

They run:

```bash
scaudit annotate input.h5ad \
  --species mouse \
  --tissue heart \
  --cluster-key leiden \
  --out results/
```

scaudit outputs:

```text
results/
- report.html
- report.qmd
- annotation_cards.json
- annotation_summary.csv
- marker_evidence.csv
- model_predictions.csv
- reference_audit.json
- reproducibility.json
```

## MVP Inputs

Required:

- `.h5ad` AnnData input.
- Species.
- Tissue.
- Cluster key or permission to compute clusters.
- Output directory.

Optional:

- Condition key.
- Sample key.
- Batch key.
- Reference path.
- LLM enabled flag.
- Config YAML.

## MVP Annotation Unit

Recommended rule:

```text
Compute evidence at cell level when useful.
Make final decisions at cluster level.
```

Rationale:

- Cell-level predictions are useful for model evidence and heterogeneity checks.
- Cluster-level decisions are more stable and easier for users to review.
- Cluster-level annotation cards match how many labs discuss scRNA-seq results.

## MVP Evidence Sources

Required:

- Marker evidence using Scanpy differential expression.
- Model evidence using CellTypist or another lightweight default model.
- Basic reference audit metadata if a reference is provided.

Optional but useful:

- scVI/scANVI feature.
- LLM explanation.
- Condition comparison.

Deferred:

- scGPT.
- Geneformer.
- SingleR/R integration.
- Full ontology reasoning beyond simple label hierarchy placeholders.

## MVP Decision Categories

Use clear decision states:

```text
Accepted
Ambiguous
Unknown
Needs review
Artifact warning
```

`Artifact warning` should be allowed when QC signals suggest doublets, dying cells, ambient RNA, or low-quality clusters.

## MVP Output Units

## Annotation Card

Each cluster should have one annotation card:

```json
{
  "cluster_id": "4",
  "proposed_label": "Cardiomyocyte",
  "decision": "Accepted",
  "confidence_level": "high_lineage_medium_subtype",
  "marker_evidence": [],
  "model_evidence": [],
  "reference_evidence": [],
  "uncertainty": {},
  "warnings": [],
  "recommended_validation": [],
  "llm_explanation": null
}
```

## Reproducibility Record

Each run should save:

```json
{
  "scaudit_version": null,
  "input_file": "input.h5ad",
  "input_hash": null,
  "parameters": {},
  "references": [],
  "models": [],
  "environment": {},
  "created_at": null
}
```

## Quarto Report

MVP report sections:

- Dataset overview.
- QC and dataset diagnosis.
- Reference audit.
- Annotation summary.
- Cluster annotation cards.
- Marker evidence.
- Model agreement and disagreement.
- Ambiguous and unknown clusters.
- Reproducibility appendix.

## Excel Workbook

Excel is useful, but can be second priority if CSV tables are easier for MVP.

Recommended approach:

```text
MVP: CSV files
Next: Excel workbook
```

## LLM Boundary for MVP

LLM is optional and explain-only.

Allowed:

- Summarize evidence.
- Explain contradiction.
- Suggest validation markers based on provided evidence and known biology.
- State uncertainty.

Forbidden:

- Create the final label.
- Override decision category.
- Invent marker evidence.
- Invent reference evidence.
- Hide uncertainty.

## Dependency Boundary

Default MVP:

- Python 3.11.
- AnnData.
- Scanpy.
- pandas.
- numpy.
- Plotly.
- Quarto check or external requirement.
- CellTypist if dependency resolution is manageable.

Feature-gated:

- scvi-tools.
- OpenAI or other LLM API client.
- decoupler.

Deferred:

- scGPT.
- Geneformer.
- R-based methods.

## Development Gate

Do not start implementation until these contracts are written:

## 1. Evidence Schema

Define exact JSON shape for:

- Marker evidence.
- Model prediction evidence.
- Reference evidence.
- Ontology evidence.
- Uncertainty.
- Warnings.
- Decision trace.

## 2. Gene Harmonization Policy

Define:

- Accepted input gene identifiers.
- Gene symbol normalization.
- Ensembl-to-symbol behavior.
- Mouse-human ortholog behavior.
- Missing gene reporting.

## 3. Reference Schema and Scoring

Define:

- Reference metadata fields.
- Version fields.
- Gene overlap scoring.
- Metadata matching.
- Reference bias warnings.

## 4. Ensemble Decision Rule

Define:

- How marker, model, and reference evidence are combined.
- How disagreement is represented.
- When a decision becomes Accepted, Ambiguous, Unknown, or Needs review.

## 5. LLM Contract

Define:

- Structured input schema.
- Output schema.
- Forbidden claims.
- Citation/evidence grounding behavior.
- Failure fallback when LLM is unavailable.

## Recommended First Vertical Slice

The first implemented slice should be:

```text
Input .h5ad
-> read cluster key
-> compute marker evidence
-> run one lightweight model or accept mock model evidence adapter
-> build annotation_cards.json
-> render minimal Quarto report
-> write reproducibility.json
```

This slice proves the product without committing to every advanced method.
