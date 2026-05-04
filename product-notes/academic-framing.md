# Academic Framing

## Academic Project Description

Single-cell RNA sequencing (scRNA-seq) has become a central technology for resolving cellular heterogeneity across tissues, developmental stages, and disease conditions. A critical step in scRNA-seq analysis is **cell type annotation**, which translates transcriptional clusters into biological meaning. Despite extensive methodological development, annotation remains **semi-manual, context-dependent, and often non-reproducible**.

Existing approaches to cell type annotation can be broadly categorized into:

- **Marker-based methods**, which rely on canonical gene signatures and expert knowledge.
- **Reference-based methods**, which transfer labels from annotated datasets via similarity metrics.
- **Supervised or semi-supervised models**, including probabilistic frameworks such as scANVI and classifier-based tools such as CellTypist.
- **Foundation models**, such as scGPT and related architectures, which learn large-scale representations of cellular states.

These approaches have significantly improved scalability and automation, yet they share key limitations:

```text
1. Dependence on imperfect or incomplete reference datasets
2. Lack of transparency in model-driven predictions
3. Inconsistent annotation granularity across datasets
4. Limited ability to represent uncertainty and ambiguity
5. Absence of standardized, auditable annotation workflows
```

Recent studies highlight that even state-of-the-art methods can produce inconsistent annotations across datasets and experimental conditions [1-3]. Furthermore, emerging approaches using large language models (LLMs) demonstrate the potential for automated reasoning over marker genes, but also raise concerns regarding hallucination and lack of grounding [4,5].

## Conceptual Framework

**scaudit** proposes a shift in perspective:

> Cell type annotation should not be treated as a prediction problem, but as an **evidence-based, auditable decision process**.

Instead of producing a single label, scaudit constructs a structured representation of annotation as:

```text
Annotation = Evidence + Reasoning + Decision
```

Where:

- **Evidence** is derived from multiple orthogonal sources.
- **Reasoning** integrates and evaluates these sources.
- **Decision** is explicitly justified and qualified.

## Methodological Components

scaudit integrates four complementary layers of evidence.

### 1. Marker-Based Evidence

Gene-level signals derived from differential expression or predefined marker sets provide **biological interpretability** and remain essential for expert validation [1].

### 2. Reference-Based Evidence

Query datasets are mapped to curated reference atlases, such as Human Cell Atlas and Tabula Sapiens, providing **biological grounding through similarity-based label transfer** [2].

### 3. Model-Based Evidence

Predictions from computational models, such as CellTypist and scANVI, provide **statistical inference**, enabling scalable annotation across large datasets [3,6].

### 4. Ontology-Aware Reasoning

Cell type annotations are contextualized within hierarchical ontologies, addressing inconsistencies in label granularity and enabling **multi-resolution interpretation** [7].

## LLM-Assisted Reasoning

scaudit incorporates large language models as a **reasoning and interpretation layer**, rather than as a primary annotator.

LLMs are used to:

- Summarize multi-source evidence.
- Identify contradictions across signals.
- Generate human-readable explanations.
- Suggest alternative interpretations and validation strategies.

Importantly, LLMs operate on **structured evidence inputs**, mitigating risks of hallucination and ensuring traceability [4,5].

## Representation of Uncertainty

A central principle of scaudit is the explicit representation of uncertainty.

Rather than enforcing deterministic labels, scaudit characterizes:

```text
- Agreement vs disagreement across models
- Strength of marker support
- Distance to reference distributions
- Ontological consistency
```

This enables identification of:

- Ambiguous cell states.
- Transitional or activation states.
- Dataset-specific or disease-specific populations.
- Potential novel cell types.

## Auditable Annotation

Each annotation in scaudit is represented as a structured **annotation record**, including:

```text
- Selected reference datasets
- Model predictions and scores
- Marker gene support and contradictions
- Ontology mapping
- Confidence and uncertainty indicators
- Recommended validation steps
```

This transforms annotation into a **reproducible and inspectable process**, aligning with emerging standards for computational reproducibility in single-cell analysis [8].

## Academic Design Philosophy

### 1. Transparency Over Automation

Automation should not obscure biological reasoning. All intermediate steps must be visible and interpretable.

### 2. Integration Over Single-Method Reliance

No single method is sufficient. Robust annotation requires **multi-source evidence integration**.

### 3. Uncertainty as First-Class Output

Ambiguity is inherent in biological systems and should be explicitly represented rather than suppressed.

### 4. Human-in-the-Loop Interpretation

The goal is to **augment expert reasoning**, not replace it.

### 5. Reproducibility by Design

All annotation decisions must be traceable, versioned, and reproducible.

## Vision

scaudit aims to establish a new paradigm for single-cell annotation:

> From label assignment to **evidence-driven biological interpretation**.

By bridging computational models, reference knowledge, and explainable reasoning, scaudit provides a foundation for **transparent, auditable, and trustworthy annotation workflows**.

## Suggested References

These are citation placeholders to be replaced with formal references later:

```text
[1] Abdelaal et al., Nature Methods (2019) - Benchmarking scRNA-seq annotation methods
[2] Stuart et al., Cell (2019) - Integration and reference mapping
[3] Gayoso et al., Nature Methods (2022) - scVI / scANVI
[4] Hou & Ji, Nature Methods (2024) - GPT-based cell annotation
[5] Li et al., Cell Research / related LLM-based annotation work
[6] Dominguez Conde et al., Nature Medicine (2022) - CellTypist
[7] Cell Ontology Consortium
[8] Luecken & Theis, Molecular Systems Biology (2019) - Best practices
```

## Potential Uses

This version can serve as:

- GitHub README in academic style.
- Preprint introduction skeleton.
- Grant proposal framing.
