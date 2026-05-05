# Tooling and Dependency Strategy

This document captures the implementation-layer tool strategy for scaudit, including candidate tools, their roles, suggested citations, tradeoffs, and Pixi dependency design.

## Tool Matrix

scaudit integrates tools across six categories:

```text
1. Marker-based methods
2. Reference-based methods
3. Model-based methods
4. Foundation models
5. Gene-set / pathway inference
6. Utility / infrastructure
```

The core design principle is:

```text
Integrate multiple tools -> produce evidence -> make decisions
```

scaudit is not designed to solve annotation with a single model.

## 1. Marker-Based Methods

## Scanpy

**Suggested citation**

- Wolf et al., Genome Biology (2018)

**Uses**

- Differential expression.
- Marker gene ranking.

**Strengths**

- Core Python ecosystem package for single-cell analysis.
- Stable and widely adopted.
- Native integration with AnnData.

**Limitations**

- Not an annotation tool by itself.
- Marker interpretation still requires expert reasoning or LLM-assisted explanation.

**Role in scaudit**

```text
marker-based evidence backbone
```

Scanpy should be treated as required for MVP.

## decoupler

**Suggested citation**

- Badia-i-Mompel et al., Bioinformatics (2022)

**Uses**

- Gene set inference.
- Pathway activity inference.
- TF activity inference, for example DoRothEA and PROGENy.

**Strengths**

- Provides functional interpretation beyond marker genes.
- More robust than raw marker inspection for some biological questions.

**Limitations**

- Does not directly assign cell types.
- Requires gene set or regulatory network databases.

**Role in scaudit**

```text
functional evidence
```

decoupler is a useful add-on, not necessarily MVP-critical.

## 2. Reference-Based Methods

## SingleR

**Suggested citation**

- Aran et al., Nature Immunology (2019)

**Strengths**

- Intuitive correlation-based annotation.
- Stable baseline.

**Limitations**

- R-based, which makes Python integration more complex.
- Does not directly address batch effects.

**Role in scaudit**

```text
optional reference annotation plugin
```

SingleR should not be a core MVP dependency unless R integration becomes a specific goal.

## scmap

**Suggested citation**

- Kiselev et al., Nature Methods (2018)

**Strengths**

- Lightweight.
- kNN-based reference mapping.

**Limitations**

- Generally less competitive than newer methods.
- Scaling can be limited.

**Role in scaudit**

```text
lightweight reference baseline
```

scmap can be considered as an optional baseline rather than a primary engine.

## 3. Model-Based Methods

## CellTypist

**Suggested citation**

- Dominguez Conde et al., Nature Medicine (2022)

**Strengths**

- Fast.
- Includes pretrained models.
- Easy to use.

**Limitations**

- Stronger in immune contexts.
- Reference/model coverage is fixed by available pretrained models.

**Role in scaudit**

```text
default baseline model
```

CellTypist should be part of the MVP.

## scvi-tools

**Suggested citation**

- Gayoso et al., Nature Methods (2022)

**Uses**

- SCVI.
- SCANVI.
- Batch correction.
- Semi-supervised annotation.

**Strengths**

- State-of-the-art modeling framework.
- Supports batch correction and semi-supervised workflows.
- Strong fit for scalable annotation and uncertainty-aware modeling.

**Limitations**

- GPU is recommended.
- Setup is more complex than lightweight methods.

**Role in scaudit**

```text
core model engine
```

scvi-tools is one of the most important model-layer dependencies, but may be optional or feature-gated depending on MVP scope.

## scPred

**Suggested citation**

- Alquicira-Hernandez et al., Genome Biology (2019)

**Strengths**

- Supports custom training.
- More interpretable than some deep learning approaches.

**Limitations**

- Requires training data.
- Less powerful than modern deep models in many settings.

**Role in scaudit**

```text
optional advanced classifier
```

scPred is not recommended for MVP core.

## 4. Foundation Models

## scGPT

**Suggested citation**

- Cui et al., Nature Methods (2024)

**Strengths**

- Strong generalization potential.
- High-quality embeddings.

**Limitations**

- Complex setup.
- GPU-heavy.
- Annotation behavior may be unstable depending on task and reference context.

**Role in scaudit**

```text
embedding and secondary evidence
```

scGPT should not be used as the primary decision-maker, especially in MVP.

## Geneformer

**Suggested citation**

- Theodoris et al., Nature (2023)

**Strengths**

- Strong representation learning.
- Useful for perturbation modeling.

**Limitations**

- Does not directly provide annotation support.
- Computationally heavy.

**Role in scaudit**

```text
future extension
```

Geneformer should be excluded from MVP.

## 5. LLM-Based Methods

## GPT-Based Annotation and Reasoning

**Suggested citation**

- Hou & Ji, Nature Methods (2024)

**Strengths**

- Strong explanation and summarization capabilities.
- Can integrate biological knowledge into human-readable reasoning.

**Limitations**

- Hallucination risk.
- Must not be used as the sole source of truth.

**Role in scaudit**

```text
reasoning layer only
```

LLMs are important for explanation, contradiction detection, and validation suggestions, but they should be constrained by structured evidence.

## 6. Utility and Infrastructure

## Typer and Rich

**Uses**

- CLI command structure.
- Rich terminal output.
- Tables.
- Panels.
- Progress bars.
- Spinners.
- Colored warnings and errors.

**Role in scaudit**

```text
premium CLI experience
```

Recommended stack:

```text
typer + rich
```

These should be part of the default CLI dependency set.

## AnnData

**Suggested citation**

- Wolf et al., Genome Biology (2018)

**Role in scaudit**

```text
core data structure
```

AnnData is required.

## Plotly

**Uses**

- Interactive visualization.
- UMAP plots.
- Confidence maps.
- Model agreement plots.
- Report figures.

**Role in scaudit**

```text
interactive visualization layer
```

Plotly is required for the Quarto reporting experience.

## Quarto

**Uses**

- HTML report generation.
- Publication-grade reporting.
- Reproducible report source via `.qmd`.

**Role in scaudit**

```text
core report generation system
```

Quarto is a core output dependency, but its installation strategy may need special handling because it is not a normal Python package.

## Pixi Dependency Strategy

The goal is:

```text
Anyone with Pixi installed can run scaudit reproducibly.
```

Recommended strategy:

```text
Use a minimal default environment and feature-gated optional dependencies.
```

## Recommended Pixi Layout

Draft `pixi.toml` structure:

```toml
[project]
name = "scaudit"

[dependencies]
python = "3.11"
scanpy = "*"
anndata = "*"
plotly = "*"
pandas = "*"
numpy = "*"

[feature.celltypist.dependencies]
celltypist = "*"

[feature.scvi.dependencies]
scvi-tools = "*"
torch = "*"

[feature.scgpt.dependencies]
scgpt = "*"

[feature.llm.dependencies]
openai = "*"
```

## CLI Usage with Pixi

Default run:

```bash
pixi run scaudit annotate ...
```

Feature-enabled run:

```bash
pixi run --features scvi scaudit annotate ...
```

## Dependency Design Principles

## 1. Do Not Force All Dependencies

Recommended dependency tiers:

```text
Default:
- Scanpy
- AnnData
- pandas
- numpy
- Plotly

Feature-gated:
- CellTypist
- scvi-tools
- decoupler
- LLM API client

Future / experimental:
- scGPT
- Geneformer
- R-based methods
```

## 2. Lazy Load Optional Modules

Optional modules should be imported only when enabled:

```python
if config["scvi"]["enabled"]:
    import scvi
```

This keeps the default environment lightweight and avoids import failures for unused features.

## 3. Provide Clear Error Messages

When an optional module is unavailable, scaudit should explain how to enable it:

```text
scGPT is not installed.
Enable the scgpt feature or install the required dependency before running this module.
```

## 4. Add a Capability Check Command

CLI command:

```bash
scaudit doctor
```

Example output:

```text
Available modules:
✔ scanpy
✔ celltypist
✔ scvi
✘ scgpt
✔ llm
```

## Recommended MVP Tool Set

Required for first version:

```text
- Scanpy
- CellTypist
- scvi-tools
- AnnData
- Plotly
- Quarto
```

Useful add-ons:

```text
- decoupler
- LLM API integration
```

Not needed for MVP:

```text
- scGPT
- Geneformer
```

## Open Dependency Questions

- Should CellTypist be a default dependency or a feature-gated dependency?
- Should scvi-tools be installed by default, or only under a `scvi` feature because of GPU and PyTorch complexity?
- How should Quarto be installed and checked: Pixi system dependency, external requirement, or bundled runtime expectation?
- Should R-based tools such as SingleR be supported through optional R environments, or deferred entirely?
- What is the minimum supported Python version: 3.10, 3.11, or 3.12?
