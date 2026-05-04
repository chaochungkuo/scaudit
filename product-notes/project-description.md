# scaudit Project Description

## Summary

**scaudit** is a transparent annotation audit framework for single-cell RNA-seq. It turns cell type annotation into structured evidence records, uncertainty calls, human-reviewable decisions, and publication-ready reports.

Instead of treating annotation as a black-box prediction problem, scaudit reframes it as an **auditable biological decision-making process**. It integrates marker evidence, reference evidence, model predictions, ontology context, and optional LLM-assisted explanations to produce annotations that are interpretable, traceable, and reproducible.

## What scaudit Does

Given a single-cell dataset, scaudit:

- Diagnoses dataset structure and available metadata.
- Selects or evaluates relevant reference datasets.
- Applies multiple annotation strategies, including marker-based, reference-based, and model-based methods.
- Aggregates outputs into a unified evidence schema.
- Identifies agreement, ambiguity, contradiction, and possible artifacts.
- Produces cluster-level annotation cards with explicit decision traces.
- Generates Quarto reports and machine-readable reproducibility records.
- Supports human review and correction.

The output is not just an annotated `.h5ad`. The core output is a **complete annotation audit trail**.

## Core Reframe

scaudit reframes single-cell annotation from:

```text
What is this cell type?
```

to:

```text
Why was this label assigned, what evidence supports it, and should it be trusted?
```

## Product Promise

```text
From labels to evidence.
```

Alternative tagline:

```text
Not just annotation — but annotation you can trust.
```
