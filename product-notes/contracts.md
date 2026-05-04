# Development Contracts

This document defines the five core contracts that must be locked before scaudit implementation begins. These contracts describe the interfaces between evidence generation, reference handling, decision logic, LLM reasoning, reports, and future tests.

## Contract 1: Evidence Schema

## Purpose

The evidence schema is the core data structure of scaudit. It defines how annotation evidence, uncertainty, decisions, reasoning, and provenance are represented.

The MVP should use cluster-level annotation cards as the primary output unit.

## Annotation Unit

Recommended rule:

```text
Compute evidence at cell level when useful.
Make final decisions at cluster level.
```

## Annotation Card Schema

Draft cluster-level schema:

```json
{
  "cluster_id": "4",
  "proposed_label": "Cardiomyocyte",
  "decision": "Accepted",
  "confidence": {
    "lineage": "high",
    "subtype": "medium",
    "overall": "medium"
  },
  "evidence": {
    "markers": [],
    "models": [],
    "references": [],
    "ontology": [],
    "qc_warnings": []
  },
  "uncertainty": {
    "model_disagreement": "low",
    "reference_distance": "low",
    "marker_inconsistency": "medium"
  },
  "reasoning": {
    "summary": null,
    "supports": [],
    "contradictions": [],
    "uncertainties": [],
    "validation_suggestions": []
  },
  "provenance": {
    "parameters": {},
    "models": [],
    "references": []
  }
}
```

## Confidence Representation

MVP should prefer categorical confidence:

```text
high
medium
low
unknown
```

Rationale:

- Different tools produce non-comparable numeric scores.
- Categorical confidence is easier to explain and review.
- Numeric scores can still be stored inside specific evidence entries.

## Required Evidence Categories

```text
markers
models
references
ontology
qc_warnings
```

MVP may leave `ontology` empty if ontology reasoning is not yet implemented, but the field should exist for forward compatibility.

## Decision Values

Allowed decision values:

```text
Accepted
Ambiguous
Unknown
Needs review
Artifact warning
```

## Contract 2: Gene ID Harmonization Policy

## Purpose

Gene identifier harmonization prevents reference mapping, marker comparison, and model input from silently failing due to incompatible feature names.

## MVP Policy

MVP support:

```text
Primary: gene symbols
Optional: Ensembl IDs converted to gene symbols
Cross-species ortholog mapping: explicit opt-in only
```

## Detection Rules

The system should infer input gene ID type where possible:

```text
ENSG...    -> human Ensembl ID
ENSMUSG... -> mouse Ensembl ID
otherwise -> likely gene symbol
```

## Required Behavior

scaudit must:

- Detect or record input gene ID type.
- Detect or record reference gene ID type.
- Normalize symbols where possible.
- Report matched and missing genes.
- Report gene overlap ratio.
- Warn when overlap is low.

## Gene Overlap Report Schema

```json
{
  "input_gene_id_type": "symbol",
  "reference_gene_id_type": "symbol",
  "n_input_genes": 18000,
  "n_reference_genes": 22000,
  "n_matched_genes": 14500,
  "overlap_ratio": 0.81,
  "ortholog_mapping_used": false,
  "warnings": []
}
```

## Low Overlap Behavior

Recommended MVP thresholds:

```text
overlap_ratio >= 0.70 -> acceptable
0.50 <= overlap_ratio < 0.70 -> warning, downweight reference evidence
overlap_ratio < 0.50 -> strong warning, reference evidence should not drive Accepted decisions
```

Thresholds can be tuned later.

## Cross-Species Mapping

Mouse-human ortholog mapping should not run by default.

It should require an explicit option such as:

```bash
--ortholog-map mouse-human
```

Cross-species mapping must be recorded in provenance.

## Contract 3: Reference Metadata and Scoring Schema

## Purpose

Reference evidence is only useful if the reference identity, version, metadata, and selection logic are transparent.

## Reference Manifest Schema

Each reference should have a manifest:

```json
{
  "id": "mouse_heart_atlas",
  "version": "2026-05-01",
  "source": "cellxgene",
  "species": "mouse",
  "tissue": "heart",
  "condition": "healthy",
  "technology": "10x",
  "path": "references/mouse_heart_atlas.h5ad",
  "label_key": "cell_type",
  "gene_id_type": "symbol"
}
```

## Reference Scoring

MVP should use an interpretable weighted scoring function:

```text
score = 0.4 metadata_match
      + 0.3 gene_overlap
      + 0.2 label_coverage
      + 0.1 technology_match
```

## Scoring Components

```text
metadata_match:
  species, tissue, condition/disease relevance

gene_overlap:
  overlap between query genes and reference genes after harmonization

label_coverage:
  whether the reference contains relevant or expected cell type labels

technology_match:
  match between technologies such as 10x, Smart-seq, single-nucleus, etc.
```

## Reference Audit Record

```json
{
  "reference_id": "mouse_heart_atlas",
  "version": "2026-05-01",
  "source": "cellxgene",
  "score": 0.86,
  "components": {
    "metadata_match": 0.9,
    "gene_overlap": 0.81,
    "label_coverage": 0.85,
    "technology_match": 0.7
  },
  "warnings": [
    "Reference condition is healthy while query condition is tumor."
  ]
}
```

## MVP Guidance

Do not start with complex embedding similarity as the primary reference selection criterion. It can be added later, but the first version should prioritize transparent metadata and gene-overlap scoring.

## Contract 4: Ensemble Decision Rule

## Purpose

The ensemble decision rule defines how marker evidence, model predictions, reference evidence, QC warnings, and uncertainty become a final decision.

## Core Principle

Do not use naive score averaging in MVP.

Different tools produce scores with different meanings:

```text
CellTypist 0.8 != scANVI 0.8 != reference similarity 0.8
```

MVP should use categorical evidence rules and expose disagreement.

## Decision Categories

## Accepted

Use when:

- Marker evidence supports the proposed label.
- At least one model or reference agrees.
- No strong lineage-level contradiction exists.
- No major QC or artifact warning exists.

## Ambiguous

Use when:

- Top candidates are biologically close.
- Methods disagree within the same lineage.
- Lineage is clear but subtype is unresolved.

Example:

```text
Macrophage / myeloid lineage accepted, subtype unresolved.
```

## Unknown

Use when:

- Marker support is weak.
- Reference similarity is low.
- Model confidence is weak or inconsistent.
- No known label is sufficiently supported.

## Needs Review

Use when:

- Evidence conflicts at lineage level.
- Reference metadata mismatch is substantial.
- Gene overlap is low.
- Decision depends on weak or incomplete evidence.
- LLM or rule-based checks detect contradictions.

## Artifact Warning

Use when:

- Doublet-like signals are present.
- Low-quality or dying-cell signals dominate.
- Ambient RNA contamination is likely.
- Cluster appears technical rather than biological.

## Priority Rules

Recommended MVP priority:

```text
1. Major QC/artifact warning -> Artifact warning or Needs review
2. Lineage-level contradiction -> Needs review
3. Strong marker + model/reference agreement -> Accepted
4. Same-lineage disagreement or subtype uncertainty -> Ambiguous
5. Weak evidence across sources -> Unknown
```

## Label Resolution Principle

Prefer lineage-level correctness over subtype overreach.

The system should prefer:

```text
Cell type: macrophage / myeloid lineage
Subtype: unresolved
```

over an unsupported precise subtype.

## Contract 5: LLM Input/Output Contract

## Purpose

The LLM is a reasoning and explanation layer. It must not become an oracle, classifier, or hidden decision-maker.

## LLM Role

Allowed:

- Summarize structured evidence.
- Explain why evidence supports or contradicts a label.
- Identify uncertainty.
- Suggest validation checks.
- Produce human-readable report text.

Forbidden:

- Create the final label.
- Override the decision category.
- Invent marker genes.
- Invent references.
- Invent model results.
- Hide uncertainty.
- Present unsupported biological claims as evidence.

## LLM Input Schema

The LLM receives structured evidence, not raw expression data.

```json
{
  "cluster_id": "4",
  "candidate_label": "Cardiomyocyte",
  "decision": "Accepted",
  "marker_evidence": [
    {
      "gene": "Tnnt2",
      "direction": "up",
      "support": "positive"
    }
  ],
  "model_evidence": [
    {
      "model": "scANVI",
      "label": "Cardiomyocyte",
      "score": 0.89,
      "calibrated_confidence": "high"
    }
  ],
  "reference_evidence": [
    {
      "reference": "mouse_heart_atlas",
      "version": "2026-05-01",
      "label": "Cardiomyocyte",
      "similarity": 0.91,
      "confidence": "high"
    }
  ],
  "uncertainty": {
    "lineage": "low",
    "subtype": "medium"
  },
  "warnings": [],
  "forbidden": [
    "do not assign a new label",
    "do not override the decision",
    "do not invent marker genes",
    "do not invent references",
    "do not hide uncertainty"
  ]
}
```

## LLM Output Schema

```json
{
  "summary": "Evidence supports cardiomyocyte identity at lineage level.",
  "supports": [
    "Marker genes support contractile cardiomyocyte identity."
  ],
  "contradictions": [],
  "uncertainties": [
    "Subtype is not resolved."
  ],
  "validation_suggestions": [
    "Check Myl2, Nppa, Nppb."
  ],
  "decision_override": null
}
```

## Grounding Rule

Every explanation should be grounded in the structured input.

If the LLM suggests additional validation markers, they must be clearly labeled as suggestions rather than evidence already observed.

## Failure Behavior

If LLM execution fails or is disabled:

- Annotation decisions remain valid.
- Reports should omit LLM text or show `LLM explanation unavailable`.
- No evidence or decision should depend exclusively on LLM output.

## Development Implications

These contracts should become:

- JSON schema files.
- Unit tests.
- CLI validation checks.
- Report rendering assumptions.
- LLM prompt and parser constraints.

Implementation should begin only after these contracts are accepted or revised.
