# CLI UX and Terminal Output

This document defines the desired command-line user experience for scaudit. The CLI should feel like a polished scientific engineering tool, not a minimal script wrapper.

## Product Requirement

scaudit should provide a high-quality terminal experience with:

- Rich formatted output.
- Clear colors and semantic highlighting.
- Spinners for active work.
- Progress bars for long tasks.
- Structured tables.
- Status badges.
- Helpful warnings.
- Clear errors with suggested fixes.
- Final summaries with output paths and next commands.

The terminal should guide the user through the audit workflow and make long-running analysis feel transparent.

## Recommended Library

Use `rich` for terminal rendering.

Possible companion:

- `typer` for CLI command structure.
- `rich` for console rendering, tables, panels, progress bars, tracebacks, markdown, and syntax highlighting.

Recommended Python stack:

```text
typer + rich
```

## Visual Style

Use a restrained scientific palette inspired by the logo:

```text
deep navy      primary text / headers
purple         reasoning / LLM / review
blue           model evidence
teal           reference evidence
green          accepted / success
yellow         ambiguous / warning
orange         needs review
red            errors / artifacts
gray           unknown / unavailable
```

Colors should be semantic and consistent across commands.

## Standard Status Badges

```text
[OK]             success / valid
[WARN]           warning but execution can continue
[REVIEW]         user should inspect
[ERROR]          execution cannot continue
[SKIPPED]        optional module disabled or unavailable
[DRAFT]          draft annotation output
[FINAL]          finalized output
```

## Command Output Patterns

## `scaudit doctor`

Should show environment capability as a table:

```text
scaudit doctor

Environment
┌──────────────┬───────────┬─────────────────────────────┐
│ Component    │ Status    │ Details                     │
├──────────────┼───────────┼─────────────────────────────┤
│ Python       │ OK        │ 3.11.8                      │
│ scanpy       │ OK        │ installed                   │
│ anndata      │ OK        │ installed                   │
│ celltypist   │ SKIPPED   │ optional feature not active │
│ scvi-tools   │ SKIPPED   │ optional feature not active │
│ quarto       │ WARN      │ not found in PATH           │
│ llm          │ SKIPPED   │ disabled                    │
└──────────────┴───────────┴─────────────────────────────┘

Next:
  scaudit init-config input.h5ad --format toml --out config.toml
```

## `scaudit validate config.toml`

Should show config validation by section:

```text
Validating config.toml

┌────────────────────┬────────┬──────────────────────────────┐
│ Section            │ Status │ Notes                        │
├────────────────────┼────────┼──────────────────────────────┤
│ dataset            │ OK     │ input.h5ad found             │
│ cluster_key        │ OK     │ leiden found in .obs         │
│ gene_harmonization │ WARN   │ gene ID type inferred symbol │
│ references         │ OK     │ auto_select enabled          │
│ methods            │ OK     │ marker_based enabled         │
│ report             │ WARN   │ quarto not found             │
└────────────────────┴────────┴──────────────────────────────┘

Validation completed with 2 warnings.
```

Warnings should include fixes:

```text
WARN: Quarto was not found.
Fix: install Quarto or set report.enabled = false
```

## `scaudit plan config.toml`

Should show the execution plan before expensive computation:

```text
Run plan

Dataset:
  input.h5ad
  42,381 cells · 18 clusters · mouse · heart

Methods:
  OK marker evidence
  OK reference audit
  SKIPPED CellTypist
  SKIPPED scVI
  SKIPPED LLM explanation

Outputs:
  results/annotation_cards.json
  results/review_table.csv
  results/report/index.html
  results/reproducibility.json

Estimated stages:
  1. Dataset diagnosis
  2. Marker evidence
  3. Decision assignment
  4. Report generation
```

## `scaudit run config.toml`

Should show a clear stage progression:

```text
scaudit run config.toml

Running scaudit annotation audit

[1/7] Loading dataset             OK      42,381 cells
[2/7] Diagnosing metadata         OK      cluster_key=leiden
[3/7] Harmonizing genes           WARN    overlap report created
[4/7] Computing marker evidence   RUNNING ███████░░░ 70%
[5/7] Building annotation cards   PENDING
[6/7] Rendering report            PENDING
[7/7] Writing outputs             PENDING
```

For long tasks:

- Use progress bars.
- Show current cluster/reference/model where useful.
- Avoid noisy logs by default.
- Write detailed logs to file.

## Final Run Summary

Every successful run should end with a clear summary:

```text
Draft annotation audit complete

Summary:
  Clusters: 18
  Accepted: 12
  Ambiguous: 4
  Unknown: 1
  Needs review: 1

Outputs:
  Report: results/report/index.html
  Annotation cards: results/annotation_cards.json
  Review table: results/review_table.csv
  Draft h5ad: results/draft_annotated.h5ad

Next:
  Open results/report/index.html
  Edit results/review_table.csv
  Run scaudit review import results/review_table.csv --run results/
  Run scaudit finalize results/ --out final/
```

## `scaudit debug --cluster`

Should show a focused explanation panel:

```text
Cluster 7 Debug

Proposed label: NK cell
Decision: Needs review
Reason: lineage-level conflict

Evidence:
┌───────────┬──────────────┬────────────┬────────────────────┐
│ Source    │ Label        │ Confidence │ Notes              │
├───────────┼──────────────┼────────────┼────────────────────┤
│ Markers   │ T cell       │ medium     │ CD3D, CD3E present │
│ CellTypist│ NK cell      │ medium     │ NKG7, GNLY present │
│ Reference │ lymphocyte   │ high       │ lineage only       │
└───────────┴──────────────┴────────────┴────────────────────┘

Recommendation:
  Review CD3D, CD3E, NKG7, GNLY and consider T/NK ambiguity.
```

## Logging Levels

Default CLI output should be clean and high-level.

Detailed logs should go to:

```text
results/logs/scaudit.log
```

Recommended flags:

```bash
--quiet
--verbose
--debug
--no-color
--json
```

## Machine-Readable Mode

For workflow engines and CI:

```bash
scaudit run config.toml --json
```

This should output machine-readable status without rich formatting.

## Error Design

Errors should be actionable:

Bad:

```text
KeyError: leiden
```

Good:

```text
ERROR: cluster_key 'leiden' was not found in input.h5ad .obs

Available .obs keys:
  sample
  genotype
  batch
  cell_type

Fix:
  Edit config.toml:
    [dataset]
    cluster_key = "cell_type"
```

## MVP CLI UX Requirements

The first implementation should include:

```text
- rich console output
- colored status badges
- validation tables
- run progress stages
- final output summary
- actionable errors
- --no-color
- --json for automation
```

## Mature CLI UX Requirements

Later versions should add:

```text
- nested progress bars for per-cluster/per-reference work
- live updating run dashboard
- report path clickable where terminal supports it
- rich tracebacks in debug mode
- structured log viewer
- cache status tables
- reference registry tables
```

## Product Standard

The CLI should make the user feel:

```text
The workflow is complex, but I know exactly what is happening.
I can see progress.
I can understand warnings.
I know where outputs are.
I know what to do next.
```
