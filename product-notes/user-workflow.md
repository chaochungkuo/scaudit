# User Workflow and CLI Flow

This document defines how a user should move through scaudit from input data to final annotation output.

## Core UX Question

A user has an input `.h5ad`. They need to know:

```text
What command do I run?
Do I run everything at once or in stages?
How do I inspect the report?
How do I decide which annotations to accept?
How do I produce the final annotated output?
```

## Recommended UX Model

scaudit should support two workflows:

```text
1. One-command workflow
2. Staged audit workflow
3. Config-file workflow
```

The staged audit workflow should be the conceptual default for serious analysis, while the one-command workflow should be available for convenience.

For reproducible analysis, `config.toml` should be the recommended interface. Users should not be forced to express all configuration through command-line flags.

## Workflow A: One-Command Run

## Use Case

For users who want a complete first-pass annotation audit with minimal setup.

## Command

```bash
scaudit annotate input.h5ad \
  --species mouse \
  --tissue heart \
  --cluster-key leiden \
  --out results/
```

## What It Does

```text
Input data
-> Dataset diagnosis
-> Gene harmonization
-> Reference selection / audit
-> Marker evidence
-> Model evidence
-> Evidence fusion
-> Decision assignment
-> Optional LLM explanations
-> HTML report generation
-> Draft annotation outputs
```

## Outputs

```text
results/
├── report/
│   ├── index.html
│   ├── annotation.html
│   ├── clusters/
│   ├── methods.html
│   └── reproducibility.html
├── annotation_cards.json
├── annotation_summary.csv
├── review_table.csv
├── draft_annotated.h5ad
└── reproducibility.json
```

## Interpretation

The one-command run produces a **draft annotation**, not necessarily the final biological truth.

The user should inspect:

- `report/index.html`
- `report/annotation.html`
- `report/clusters/index.html`
- `review_table.csv`

## Workflow B: Staged Audit Workflow

## Use Case

Recommended for careful analysis, publication, collaboration, or uncertain datasets.

## Stage 1: Diagnose Dataset

```bash
scaudit diagnose input.h5ad \
  --out results/
```

Purpose:

- Inspect dataset structure.
- Detect metadata keys.
- Check cluster keys.
- Check gene identifiers.
- Identify missing fields.
- Flag obvious QC or batch issues.

Outputs:

```text
results/diagnosis.json
results/report/dataset.html
```

User decision:

```text
Are the metadata keys correct?
Is the cluster key correct?
Is gene ID detection correct?
Do I need to supply species, tissue, condition, sample, or batch keys?
```

## Stage 2: Configure Run

The user can create a config file:

```bash
scaudit init-config input.h5ad \
  --format toml \
  --out config.toml
```

Example:

```toml
[dataset]
path = "input.h5ad"
species = "mouse"
tissue = "heart"
cluster_key = "leiden"
sample_key = "sample"
condition_key = "genotype"
batch_key = "sample"

[references]
auto_select = true
max_references = 3

[methods]
marker_based = true
reference_based = true

[methods.model_based]
celltypist = true
scanvi = false

[llm]
enabled = false
mode = "explain_only"

[output]
dir = "results"
report = true
draft_h5ad = true
review_table = true
```

User decision:

```text
Which cluster key should be used?
Which methods should run?
Should LLM explanation be enabled?
Should condition comparison be included?
```

## Stage 3: Plan Run

```bash
scaudit validate config.toml
scaudit plan config.toml
```

Purpose:

- Show what will be run before expensive computation.
- Show available modules.
- Show missing dependencies.
- Show selected references.
- Estimate outputs.

Example output:

```text
Dataset: input.h5ad
Cluster key: leiden
Methods: markers, CellTypist
References: mouse_heart_atlas_v1
LLM: disabled
Report: enabled
Expected output: draft annotation + review table + HTML report
```

User decision:

```text
Does this plan look correct?
Should I adjust config before running?
```

## Stage 4: Run Audit

```bash
scaudit run config.toml
```

Purpose:

- Execute evidence generation.
- Build draft decisions.
- Render the report.

Outputs:

```text
results/annotation_cards.json
results/annotation_summary.csv
results/review_table.csv
results/draft_annotated.h5ad
results/report/index.html
```

User decision:

```text
Which clusters are accepted?
Which clusters need manual correction?
Which clusters should remain ambiguous or unknown?
```

## Stage 5: Review Results

The user opens:

```text
results/report/index.html
```

They inspect:

- Overall summary.
- Ambiguous clusters.
- Needs-review clusters.
- Cluster-level evidence pages.
- Marker support.
- Model/reference agreement.
- Suggested validation.

The review table is exported as:

```text
results/review_table.csv
```

Example columns:

```text
cluster_id
proposed_label
decision
confidence
review_status
reviewed_label
reviewer_note
```

Example edits:

```csv
cluster_id,proposed_label,decision,confidence,review_status,reviewed_label,reviewer_note
4,Cardiomyocyte,Accepted,high,accepted,Cardiomyocyte,
7,NK cell,Needs review,medium,changed,T cell,CD3D/CD3E support T cell identity
12,Unknown,Unknown,low,accepted,Unknown,Possible novel/disease state
```

## Stage 6: Import Review

```bash
scaudit review import results/review_table.csv \
  --run results/
```

Purpose:

- Validate manual corrections.
- Check labels are non-empty where required.
- Preserve reviewer notes.
- Create reviewed annotation records.

Outputs:

```text
results/reviewed_annotation_cards.json
results/review_audit.json
```

## Stage 7: Finalize Annotation

```bash
scaudit finalize results/ \
  --out final/
```

Purpose:

- Produce the final annotated dataset.
- Save final annotation labels into `.obs`.
- Freeze reproducibility records.
- Generate final report.

Outputs:

```text
final/
├── annotated.h5ad
├── final_annotation_cards.json
├── final_annotation_summary.csv
├── review_audit.json
├── reproducibility.json
└── report/
    └── index.html
```

## Final Annotation Columns

Recommended `.obs` fields:

```text
scaudit_label
scaudit_decision
scaudit_confidence
scaudit_review_status
scaudit_label_source
```

Example:

```text
scaudit_label = "Cardiomyocyte"
scaudit_decision = "Accepted"
scaudit_confidence = "high"
scaudit_review_status = "accepted"
scaudit_label_source = "reviewed"
```

## Important Product Decision

The first `run` should produce a draft annotation.

The `finalize` step should produce the final annotation.

This separation is important because scaudit is an audit framework, not just an automatic labeler.

## Recommended Command Set

## Simple Commands

```bash
scaudit annotate input.h5ad --species mouse --tissue heart --cluster-key leiden --out results/
```

Runs the full draft audit.

## Staged Commands

```bash
scaudit diagnose input.h5ad --out results/
scaudit init-config input.h5ad --format toml --out config.toml
scaudit validate config.toml
scaudit plan config.toml
scaudit run config.toml
scaudit review import results/review_table.csv --run results/
scaudit finalize results/ --out final/
```

## Utility Commands

```bash
scaudit doctor
scaudit reference search --species mouse --tissue heart
scaudit reference list
scaudit debug --run results/ --cluster 7
scaudit report results/
```

## Recommended User Journey

For first-time users:

```text
annotate -> inspect report -> edit review table -> finalize
```

For serious publication workflows:

```text
diagnose -> init-config -> plan -> run -> inspect report -> review import -> finalize
```

For advanced users:

```text
edit config.toml -> validate -> plan -> run -> debug cluster -> finalize
```

## Report Timing

The user should be able to view reports at multiple stages:

```text
After diagnose:
  dataset/QC report

After run:
  draft annotation audit report

After finalize:
  final reviewed annotation report
```

## Final Decision Model

The user decides final labels through the review table or future UI.

scaudit decides:

```text
proposed_label
decision
confidence
warnings
```

The human can decide:

```text
accept proposed label
change label
mark ambiguous
mark unknown
add reviewer note
```

Final outputs should always record whether a label came from:

```text
scaudit_auto
human_reviewed
human_changed
```

## MVP Recommendation

Implement this order:

```text
1. scaudit annotate
2. scaudit finalize
3. scaudit diagnose
4. scaudit init-config / plan
5. scaudit debug
```

Rationale:

- `annotate` proves the full draft workflow.
- `finalize` proves audit separation and final output.
- `diagnose`, `plan`, and `debug` improve usability after the core path exists.
