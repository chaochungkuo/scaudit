# Product Strategy Review

This document reassesses scaudit as a product: positioning, target users, market fit, solution fit, differentiation, and risks.

## Executive Assessment

scaudit is a reasonable and valuable product direction. The strongest positioning is not "another cell type annotation model", but:

```text
an annotation audit and reporting layer for single-cell analysis
```

The product is useful because current annotation workflows are fragmented, hard to reproduce, hard to explain, and difficult to review. Most researchers already use a mixture of marker genes, reference mapping, pretrained models, manual review, figures, and lab discussion. scaudit can package that messy process into a structured, auditable workflow.

The product should therefore compete less with individual tools like CellTypist, SingleR, scANVI, or Scanpy, and more with the manual reasoning layer that currently exists across notebooks, spreadsheets, screenshots, and informal expert judgment.

## Positioning

Recommended positioning:

```text
scaudit is a transparent annotation audit framework for single-cell RNA-seq.
It turns cell type annotation into evidence records, uncertainty calls, review tables,
and publication-ready reports.
```

What scaudit is:

- An evidence aggregation layer.
- A reproducible annotation workflow.
- A report generator for annotation decisions.
- A human-in-the-loop review system.
- A bridge between computational predictions and biological interpretation.

What scaudit is not:

- Not primarily a new classifier.
- Not an LLM-only annotation tool.
- Not a replacement for domain experts.
- Not a reference atlas by itself.
- Not a fully automated "trust me" black box.

## Target Users

## Primary Users

### Computational Biologists and Bioinformaticians

They need to annotate datasets, compare methods, explain choices, and produce reliable outputs for collaborators or papers.

Main value:

- Less manual evidence collection.
- Better reproducibility.
- Easier review and debugging.
- Stronger reports for publication or internal analysis.

### Single-Cell Core Facilities

They process datasets for many labs and need standardized deliverables.

Main value:

- Consistent annotation reports.
- Audit trails for client projects.
- Reviewable outputs instead of opaque labels.
- Faster report generation.

### Translational and Disease Biology Labs

They often need to know whether a cluster is a known cell type, disease state, artifact, or novel candidate.

Main value:

- Uncertainty and ambiguity surfaced explicitly.
- Condition comparison support.
- Marker and validation suggestions.

## Secondary Users

### Methods Developers

They may use scaudit as a benchmark or wrapper layer for comparing annotation strategies.

### Reviewers and Collaborators

They benefit from clear evidence records and reproducible annotation decisions, even if they do not run the tool themselves.

## Market Need

The market need is real because single-cell annotation is still a high-friction step:

- Annotation decisions are often scattered across notebooks and manual notes.
- Different methods disagree, but disagreement is not systematically documented.
- Confidence scores are not comparable across tools.
- Reference choice is often underreported.
- Reviewers and collaborators ask why labels were assigned.
- Publication methods sections frequently underdescribe annotation decisions.

scaudit addresses this by turning annotation from a final column in `.obs` into a documented decision process.

## Differentiation

## Existing Tools

Most existing tools focus on one of these:

- Assigning labels.
- Mapping to a reference.
- Training or applying a model.
- Ranking markers.
- Visualizing clusters.

scaudit's differentiated layer is:

```text
evidence + uncertainty + reasoning + audit trail + report
```

## Strongest Differentiators

- Treats annotation as a decision process, not direct classification.
- Integrates multiple evidence sources without making any one method the sole authority.
- Makes uncertainty visible instead of hiding it.
- Produces annotation cards and reports, not just labels.
- Supports human review and versioned correction.
- Uses LLMs only for grounded reasoning and explanation.

## Solution Fit

The proposed solution is helpful if it stays focused on the painful part of annotation:

```text
How did we decide this label, and should we trust it?
```

The product becomes less useful if it tries to become a universal single-cell platform too early. The first version should avoid broad workflow sprawl and concentrate on annotation audit.

## Recommended Product Thesis

```text
Single-cell annotation is already multi-method and human-in-the-loop.
scaudit makes that implicit workflow explicit, structured, reproducible, and reviewable.
```

## MVP Recommendation

The MVP should be a local CLI that takes an `.h5ad`, produces cluster-level annotation evidence, and generates a Quarto HTML report plus machine-readable records.

Recommended MVP boundaries:

- Input: AnnData `.h5ad`.
- Unit: compute cell-level evidence where useful, decide at cluster level.
- Required evidence: marker evidence and at least one model/reference evidence source.
- Required outputs: annotation cards JSON, reproducibility JSON, Quarto report, summary tables.
- LLM: optional, explain-only, evidence-grounded.
- Human review: export/import review table can be basic in MVP.

MVP should not include:

- Foundation models as primary annotation.
- Full web app.
- R-based methods as core dependencies.
- Fully automated novel cell discovery claims.
- Heavy GPU-only assumptions.

## Product Risks

## Risk 1: Scope Creep

The project could grow into a full single-cell platform. That would dilute the core value.

Mitigation:

- Keep MVP centered on audit records and report generation.
- Treat advanced methods as plugins or features.

## Risk 2: False Authority

Because the output looks polished, users may overtrust weak evidence.

Mitigation:

- Make uncertainty prominent.
- Use `Needs review`, `Ambiguous`, and `Unknown` decisions explicitly.
- Require evidence provenance in every annotation card.

## Risk 3: LLM Hallucination

LLM explanations can invent biology if not constrained.

Mitigation:

- LLM operates only on structured evidence.
- LLM cannot create labels or override decisions.
- Every generated claim must trace back to an evidence field or be phrased as a validation suggestion.

## Risk 4: Reference Bias

References can be mismatched by species, tissue, condition, platform, or disease state.

Mitigation:

- Score references transparently.
- Warn about metadata mismatch.
- Record reference version and source.

## Risk 5: Score Incomparability

Different models produce scores with different meanings.

Mitigation:

- Avoid naive averaging in early versions.
- Use calibrated or rank-based evidence categories.
- Show disagreement instead of pretending a single confidence score is absolute.

## Development Readiness

The product is conceptually ready, but implementation should wait until five design contracts are specified:

```text
1. Evidence schema
2. Gene ID harmonization policy
3. Reference metadata and scoring schema
4. Ensemble decision rule
5. LLM input/output contract and forbidden behavior
```

Once those are defined, development can begin with a narrow vertical slice.

## Final Judgment

The product is coherent and useful. Its best market entry is as:

```text
a reproducible annotation audit/reporting framework for single-cell projects
```

The product should lead with trust, reviewability, and publication readiness, not with automation speed or model novelty.
