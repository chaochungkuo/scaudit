# Provider Reports Design

## Goal

scaudit should produce reports that are readable for biologists and auditable by experienced bioinformaticians. The main report gives a bird's-eye view across all evidence layers, while focused provider reports expose one method, tool, or database family at a time.

The report system should avoid a black-box workflow without making the primary report too long.

## Report Hierarchy

```text
results/
  report/
    report.html
  evidence_reports/
    marker_based/
      marker_based.qmd
      marker_based.html
      marker_based.evidence.json
      figures/
      tables/
    reference_mapping/
      reference_mapping.qmd
      reference_mapping.html
      reference_mapping.evidence.json
    model_prediction/
      celltypist.qmd
      celltypist.html
      celltypist.evidence.json
    ontology_reasoning/
      cell_ontology.qmd
      cell_ontology.html
      cell_ontology.evidence.json
    llm_explanation/
      llm_explanation.qmd
      llm_explanation.html
      llm_explanation.evidence.json
```

The main report should summarize status, top findings, agreement or disagreement, and links to provider reports. It should not combine all tool details into one long page.

Each provider report should answer one focused question:

| Provider report | Focus |
| --- | --- |
| Marker-based evidence | Differential markers, marker strength, marker signatures, marker expression figures |
| Reference-based mapping | External/local reference label matching and gene overlap |
| Model-based prediction | CellTypist or other classifier predictions |
| Ontology reasoning | Cell ontology mapping and hierarchy consistency |
| LLM explanation | Human-readable interpretation generated from structured evidence |

## QMD Metadata Convention

Provider qmd files should use consistent metadata so they can be rendered and indexed by scaudit.

```yaml
---
title: "Marker-Based Evidence"
subtitle: "Differential markers, marker signatures, and expression visualization"
format:
  html:
    toc: true
    code-fold: true
    code-summary: "Show analysis code"
    embed-resources: false
execute:
  echo: true
  warning: true
  message: false
  error: false

scaudit:
  provider_id: "marker_based"
  provider_version: "0.1.0"
  evidence_layer: "Marker-based evidence"
  purpose: "Biological interpretability"
  standard_output: "marker_based.evidence.json"

params:
  input_h5ad: "../input.h5ad"
  cluster_key: "leiden"
  output_dir: "../results/evidence_reports/marker_based"
  n_top_genes: 50
  de_method: "wilcoxon"
  use_raw: true
  min_log2fc: 0.5
  max_padj: 0.05
  strong_log2fc: 1.0
  strong_padj: 0.01
---
```

Code should be present for auditability but folded by default. This keeps reports approachable for biologists while allowing technical readers to inspect the exact commands, parameters, and transformations.

## Provider Report Structure

Each provider report should be short, focused, and predictable:

1. Question
2. Inputs and parameters
3. Key results
4. Publication-quality figures
5. Cluster-level evidence table
6. Warnings and limitations
7. Reproducibility and standard output

Provider reports should avoid mixing unrelated evidence sources. For example, the marker report may mention that reference or model evidence exists in the main report, but it should not embed the reference mapping workflow.

## Callout Usage

QMD callouts should improve readability without replacing structured evidence. Use them consistently:

| Callout | Use in scaudit provider reports |
| --- | --- |
| `note` | Neutral method context, assumptions, or interpretation boundaries |
| `warning` | Data quality, gene ID mismatch, low overlap, weak evidence, or missing inputs |
| `important` | A key result that changes interpretation or should be reviewed |
| `tip` | Optional reviewer guidance, such as how to rerun with a different threshold |
| `caution` | Potentially misleading results, unsupported labels, or conflicts across evidence |

Recommended usage:

- Use `note` for method descriptions and scope.
- Use `warning` for automated QC and reliability flags.
- Use `important` sparingly for the most decision-relevant result.
- Use `tip` only when there is an actionable reviewer step.
- Use `caution` when the report detects a high-risk interpretation issue.

Example:

```markdown
::: {.callout-note}
This report evaluates marker-based interpretability only. It does not use reference mapping or model prediction to assign labels.
:::

::: {.callout-warning}
Cluster 7 has few informative markers after filtering with padj < 0.05 and log2FC > 0.5.
:::

::: {.callout-important}
Most T cell marker signatures are supported by CD3D, CD3E, and TRAC, with high signature coverage.
:::

::: {.callout-tip}
To test stricter marker evidence, rerun this report with `min_log2fc: 1.0`.
:::

::: {.callout-caution}
Marker evidence and reference mapping disagree for this cluster. Treat the proposed label as provisional.
:::
```

Callouts should be generated from explicit evidence and warnings, not from LLM-only interpretation.

## Standard Evidence JSON

Every provider report should write a standard evidence JSON file. The main report reads these files instead of parsing rendered HTML.

```json
{
  "schema_version": "0.1.0",
  "provider": {
    "id": "marker_based",
    "name": "Marker-based evidence",
    "version": "0.1.0",
    "purpose": "Biological interpretability"
  },
  "run": {
    "status": "success",
    "started_at": "2026-05-12T10:00:00Z",
    "completed_at": "2026-05-12T10:01:00Z",
    "input_h5ad": "input.h5ad",
    "cluster_key": "leiden"
  },
  "software": {
    "python": "3.11",
    "scanpy": "1.x",
    "anndata": "0.x",
    "pandas": "2.x",
    "matplotlib": "3.x"
  },
  "methods": [
    {
      "step": "Differential expression",
      "tool": "scanpy.tl.rank_genes_groups",
      "parameters": {
        "method": "wilcoxon",
        "n_genes": 50,
        "use_raw": true,
        "key_added": "rank_genes"
      }
    },
    {
      "step": "Marker filtering",
      "rule": "padj < 0.05 and log2FC > 0.5"
    },
    {
      "step": "Marker signature scoring",
      "tool": "scaudit.markers.MARKER_DB",
      "formula": "coverage = matched signature genes / signature genes; overlap = Jaccard(query markers, signature genes)"
    }
  ],
  "artifacts": {
    "qmd": "marker_based.qmd",
    "html": "marker_based.html",
    "figures": [],
    "tables": []
  },
  "results": {
    "clusters": {}
  },
  "warnings": []
}
```

## Figure Standards

Provider reports should produce publication-quality static figures. Interactive figures may still appear in the main report, but provider reports should export manuscript-friendly artifacts.

Recommended packages:

| Figure type | Preferred package |
| --- | --- |
| UMAP overview | `scanpy.pl` with `matplotlib` |
| Marker dotplot | `scanpy.pl.dotplot` |
| Marker heatmap or matrixplot | `scanpy.pl.matrixplot`, `seaborn`, or `PyComplexHeatmap` |
| Clustered heatmap | `seaborn.clustermap` or `PyComplexHeatmap` |
| Violin plots | `scanpy.pl.violin` or `seaborn` |
| Composition bars | `seaborn` or `matplotlib` |

Default plotting settings should favor reproducible static output:

```python
import matplotlib as mpl

mpl.rcParams.update({
    "figure.dpi": 120,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "font.size": 8,
    "axes.titlesize": 9,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
})
```

Each core figure should save:

```text
figure.svg
figure.pdf
figure.png
figure.source.csv
```

SVG and PDF support publication workflows. PNG supports browser previews. Source CSV makes the figure auditable.

## Table Standards

Tables should be both human-readable and machine-readable.

| Output | Purpose |
| --- | --- |
| HTML table in qmd | Human review |
| CSV | Simple downstream inspection |
| Parquet, optional | Larger data tables with types preserved |
| JSON summary | Main report ingestion |

Recommended packages:

- `pandas` for table creation and export.
- `great_tables` for polished static HTML tables when available.
- Quarto native tables for small method and parameter tables.

## First Implementation Target

The first provider report should be `marker_based.qmd` because marker evidence is the most interpretable and the easiest for bioinformaticians to audit.

Initial outputs:

- Differential marker table by cluster.
- Marker strength summary.
- Marker signature scoring table.
- Dotplot for top marker genes.
- Publication heatmap or matrixplot.
- `marker_based.evidence.json`.
- Links from the main report to the marker provider report.

After the marker provider pattern is stable, the same contract can be extended to reference mapping, CellTypist model prediction, ontology reasoning, and LLM explanation.
