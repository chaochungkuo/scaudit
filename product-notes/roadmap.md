# Product Roadmap

This roadmap describes how to build scaudit from zero to MVP, then into a mature scientific product, and finally into an industry-level platform.

## Roadmap Principle

scaudit should grow from a narrow, trustworthy vertical slice:

```text
input.h5ad -> evidence -> draft report -> review -> final annotated.h5ad
```

into a broader system only after the audit workflow is reliable.

The product should not start as a full single-cell platform. It should first prove that annotation can be represented as:

```text
Evidence + Reasoning + Decision + Report + Review
```

## Phase 0: Product Contract Freeze

## Goal

Convert the current product design into implementation-ready contracts.

## Deliverables

- Final `config.toml` schema.
- JSON Schema for annotation cards.
- JSON Schema for reference manifests.
- JSON Schema for reproducibility records.
- JSON Schema for review table import/export.
- LLM input/output contract.
- First demo dataset selected.
- First reference strategy selected.

## Key Decisions

- MVP input format: `.h5ad`.
- MVP annotation unit: cluster-level decisions.
- MVP evidence sources: markers plus one lightweight model/reference source.
- MVP report format: multi-page Quarto HTML.
- MVP finalization: draft run followed by human review and `finalize`.

## Exit Criteria

```text
We can describe every MVP output file before writing code.
```

## Phase 1: Repository and Runtime Foundation

## Goal

Set up a reproducible development and execution environment.

## Deliverables

- Pixi-based project setup.
- Python package skeleton.
- CLI entry point.
- Test framework.
- Basic logging.
- Version command.
- `scaudit doctor`.
- Project documentation skeleton.

## CLI Commands

```bash
scaudit --help
scaudit version
scaudit doctor
```

## Engineering Requirements

- Use typed internal models for contracts.
- Validate JSON outputs.
- Keep optional dependencies lazy-loaded.
- Keep Quarto and LLM optional at first.

## Exit Criteria

```text
Users can install the local package, run scaudit doctor, and see environment capability checks.
```

## Phase 2: Config and Dataset Diagnosis

## Goal

Allow users to create, validate, and inspect a run configuration before expensive computation.

## Deliverables

- `scaudit init-config`.
- `scaudit validate`.
- `scaudit plan`.
- `.h5ad` reader.
- Dataset metadata detection.
- Cluster key validation.
- Gene ID type detection.
- Basic QC metadata summary.
- Resolved config export.

## CLI Commands

```bash
scaudit init-config input.h5ad --format toml --out config.toml
scaudit validate config.toml
scaudit plan config.toml
```

## Outputs

```text
results/config.resolved.toml
results/diagnosis.json
```

## Exit Criteria

```text
A user can generate and validate config.toml for a real .h5ad without running annotation.
```

## Phase 3: Evidence Schema and Marker Evidence

## Goal

Build the first real evidence layer using marker genes.

## Deliverables

- Annotation card builder.
- Marker evidence adapter using Scanpy.
- Cluster marker ranking.
- Marker evidence tables.
- Basic confidence categories.
- Initial decision placeholder.

## Outputs

```text
annotation_cards.json
marker_evidence.csv
annotation_summary.csv
```

## Exit Criteria

```text
For every cluster, scaudit produces a valid annotation card with marker evidence.
```

## Phase 4: Reference Registry MVP

## Goal

Support reproducible reference metadata without requiring users to manually write full manifests.

## MVP Scope

Start with:

- Local custom references.
- Small built-in registry or fixture registry.
- Reference add/list/use.

Defer:

- Full public database download.
- Automatic CELLxGENE integration.
- Complex reference embedding search.

## CLI Commands

```bash
scaudit reference add my_ref.h5ad --id my_ref --species mouse --tissue heart --label-key cell_type
scaudit reference list
scaudit reference use my_ref --config config.toml
```

## Outputs

```text
references/registry.json
references/<id>/manifest.json
reference_audit.json
```

## Exit Criteria

```text
Users can register a local reference and have config.toml refer to it by ID.
```

## Phase 5: First Model or Reference Evidence

## Goal

Add a second evidence source so scaudit can compare marker evidence against model/reference evidence.

## Recommended MVP Path

Use CellTypist if dependency resolution is manageable. If not, define a model adapter interface and start with a simple reference or mock adapter for integration tests.

## Deliverables

- Model evidence adapter interface.
- CellTypist adapter or first lightweight model adapter.
- Per-cell predictions.
- Cluster-level aggregation.
- Model evidence table.
- Model-marker agreement summary.

## Outputs

```text
model_predictions.csv
model_evidence.json
```

## Exit Criteria

```text
Each cluster has marker evidence plus one independent model/reference evidence source.
```

## Phase 6: Decision Engine MVP

## Goal

Convert evidence into conservative decision states.

## Deliverables

- Rule-based decision engine.
- Accepted / Ambiguous / Unknown / Needs review / Artifact warning states.
- Lineage-over-subtype preference.
- Conflict detection.
- Warning propagation.
- Review priority scoring.

## Exit Criteria

```text
Every cluster receives a proposed label, decision state, confidence category, and review priority.
```

## Phase 7: Quarto Report MVP

## Goal

Generate the first polished multi-page HTML audit report.

## MVP Pages

```text
report/index.html
report/annotation.html
report/clusters/index.html
report/clusters/cluster_<id>.html
report/methods.html
report/reproducibility.html
```

## Deliverables

- Quarto source generator.
- Report theme.
- Summary metrics.
- Annotation summary table.
- Cluster detail pages.
- Marker/model evidence sections.
- Reproducibility appendix.

## Exit Criteria

```text
A collaborator can open report/index.html and understand what was assigned, why, and what needs review.
```

## Phase 8: Review and Finalize

## Goal

Separate draft annotation from final annotation.

## Deliverables

- `review_table.csv`.
- Review import validation.
- Final annotation card generation.
- Final `.h5ad` writer.
- Final report generation.
- Review audit record.

## CLI Commands

```bash
scaudit review import results/review_table.csv --run results/
scaudit finalize results/ --out final/
```

## Final Outputs

```text
final/annotated.h5ad
final/final_annotation_cards.json
final/final_annotation_summary.csv
final/review_audit.json
final/reproducibility.json
final/report/index.html
```

## MVP Exit Criteria

The MVP is complete when this full path works:

```bash
scaudit init-config input.h5ad --format toml --out config.toml
scaudit validate config.toml
scaudit plan config.toml
scaudit run config.toml
scaudit review import results/review_table.csv --run results/
scaudit finalize results/ --out final/
```

And produces:

```text
draft report
review table
final annotated.h5ad
final report
reproducibility record
```

# Post-MVP: Mature Scientific Product

## Phase 9: Better Evidence and Calibration

## Goals

- Improve evidence reliability.
- Reduce false confidence.
- Make disagreement more informative.

## Features

- Better gene harmonization.
- Reference gene overlap diagnostics.
- Reference bias detection.
- Score calibration and rank-based evidence categories.
- Model disagreement views.
- Batch effect detection.
- Artifact warnings.

## Exit Criteria

```text
The report clearly distinguishes strong evidence, weak evidence, and conflicting evidence.
```

## Phase 10: Public Reference Ecosystem

## Goals

- Make reference discovery useful and reproducible.
- Reduce setup burden for users.

## Features

- `reference search`.
- `reference recommend`.
- `reference download`.
- `reference update`.
- Public registry metadata.
- Version pinning.
- Checksums.
- Reference cache management.

## Supported Sources

Potential sources:

- CELLxGENE.
- Human Cell Atlas.
- Tabula Sapiens.
- Curated project-specific registries.

## Exit Criteria

```text
Users can discover, download, pin, and audit public references without manually editing manifests.
```

## Phase 11: LLM Reasoning Layer

## Goals

- Add high-quality explanation without making the LLM a decision-maker.

## Features

- Evidence-grounded LLM prompts.
- JSON output parsing.
- Hallucination guardrails.
- Explanation sections in cluster pages.
- Validation suggestions.
- Optional provider support.

## Exit Criteria

```text
LLM explanations improve readability but no decision depends exclusively on LLM output.
```

## Phase 12: Richer Reports

## Goals

- Make the report feel premium, navigable, and publication-ready.

## Features

- Full multi-page report architecture.
- Interactive Plotly UMAPs.
- Evidence heatmaps.
- Reference audit dashboard.
- Uncertainty dashboard.
- Condition comparison pages.
- Export-ready PNG/SVG/PDF figures.
- Methods auto-generation.
- Data package export.

## Exit Criteria

```text
The report can be shared with collaborators, reviewers, or core facility clients as a polished deliverable.
```

## Phase 13: Advanced Annotation Features

## Goals

- Support deeper biological interpretation.

## Features

- Cell state vs cell type separation.
- Novel cell candidate detection.
- Cross-condition interpretation.
- Functional evidence via decoupler.
- Ontology-aware label consistency.
- scVI/scANVI feature support.
- Optional foundation model embeddings.

## Exit Criteria

```text
scaudit can support serious biological interpretation beyond first-pass labels.
```

# Industry-Level Product

## Phase 14: Robust Engineering and Scale

## Goals

- Make scaudit reliable on larger datasets and team workflows.

## Features

- Caching.
- Parallel execution.
- Resume failed runs.
- Structured logs.
- Debug command.
- Run manifest.
- Output validation.
- Performance benchmarks.
- Large dataset memory strategy.

## CLI Commands

```bash
scaudit debug --run results/ --cluster 7
scaudit cache list
scaudit cache clean
scaudit report results/
```

## Exit Criteria

```text
Large runs are debuggable, resumable, and reproducible.
```

## Phase 15: Quality System

## Goals

- Make the product reliable enough for teams and regulated-ish environments.

## Features

- Schema validation everywhere.
- Golden demo datasets.
- Snapshot tests for reports.
- End-to-end workflow tests.
- Reproducibility tests.
- Dependency lock validation.
- CI test matrix.
- Clear error taxonomy.
- Backward-compatible schema versions.

## Exit Criteria

```text
Every release can prove that outputs remain valid and reproducible across supported demo datasets.
```

## Phase 16: Team and Server Mode

## Goals

- Support shared compute and team review workflows.

## Features

- Optional server execution.
- GPU worker support.
- Job queue.
- Shared reference registry.
- Shared run storage.
- Team review state.
- Authentication if needed.
- Audit logs.

## Exit Criteria

```text
A lab or core facility can run scaudit for multiple projects with shared references and review workflows.
```

## Phase 17: Web App

## Goals

- Provide a polished interactive interface for review, exploration, and collaboration.

## Features

- Upload/select run.
- Browse report pages.
- Interactive cluster review.
- Edit labels.
- Compare versions.
- Export final `.h5ad`.
- Manage references.
- Manage configs.

## Exit Criteria

```text
Non-command-line users can review and finalize annotations without editing CSV files.
```

## Phase 18: Enterprise and Platform Capabilities

## Goals

- Make scaudit suitable for institutional or commercial deployment.

## Features

- Project workspace model.
- Role-based access.
- Run provenance database.
- API.
- Batch processing.
- Integration with object storage.
- Integration with workflow engines.
- Compliance-friendly audit logs.
- Long-term reference/version management.
- Report branding for organizations.

## Exit Criteria

```text
scaudit can be deployed as a managed annotation audit platform for organizations.
```

# Recommended Build Order

## Must Build First

```text
1. Contracts and schemas
2. Config validation
3. Marker evidence
4. Annotation cards
5. Draft report
6. Review table
7. Finalize command
```

## Build Soon After

```text
1. Local reference registry
2. Model adapter
3. Decision engine
4. Better report theme
5. Reproducibility records
```

## Build Later

```text
1. Public reference download
2. LLM explanations
3. scVI/scANVI
4. Condition comparison
5. Web app
```

## Avoid Early

```text
1. Full foundation model integration
2. Live report editing UI
3. Complex server infrastructure
4. Too many public databases
5. Over-precise confidence scores
```

# Product Maturity Levels

## Prototype

```text
Can produce annotation_cards.json for one demo dataset.
```

## MVP

```text
Can run draft audit, produce report, import review, and finalize annotated.h5ad.
```

## Mature Scientific Tool

```text
Can support multiple datasets, references, evidence sources, polished reports, and reproducible publication workflows.
```

## Industry-Level Product

```text
Can support teams, shared infrastructure, scalable execution, versioned audit logs, web review, and managed deployment.
```

# Biggest Risks

## Scope Risk

Trying to build the mature product before the MVP.

## Scientific Risk

Producing polished reports that overstate weak evidence.

## Engineering Risk

Letting schema and output formats drift without validation.

## UX Risk

Making users manage too much reference metadata manually.

## LLM Risk

Allowing explanations to become hidden decisions.

# Recommended Next Step

Start implementation only after converting the five development contracts into concrete schemas:

```text
annotation_card.schema.json
reference_manifest.schema.json
reproducibility.schema.json
review_table.schema.json
llm_output.schema.json
```

Then build the first vertical slice:

```text
config.toml
-> validate
-> marker evidence
-> annotation cards
-> minimal report
-> review table
-> finalize
```
