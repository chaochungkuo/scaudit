from __future__ import annotations

import csv
import html
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scaudit import __version__
from scaudit.data import ClusterEvidence, compute_cluster_evidence
from scaudit.markers import MARKER_DB
from scaudit.providers.schema import package_versions, relative_to, render_qmd, utc_now, write_json


EXTERNAL_PROVIDER_VERSION = "0.1.0"


@dataclass(frozen=True)
class ExternalAnnotationProvider:
    provider_id: str
    title: str
    subtitle: str
    evidence_layer: str
    purpose: str
    tool: str
    execution_environment: str
    dependency_plan: str
    method_summary: str
    result_file: str


PROVIDERS = {
    "sctype": ExternalAnnotationProvider(
        provider_id="sctype",
        title="ScType Annotation Evidence",
        subtitle="Marker-set scoring with explicit marker database and tissue scope",
        evidence_layer="ScType annotation evidence",
        purpose="Marker-set scoring",
        tool="scaudit ScType-style marker scoring adapter",
        execution_environment="pixi default environment",
        dependency_plan="Executable scaudit-native adapter. It uses the same standard cluster marker table and builtin marker signatures while the official ScType script/database source is not pinned.",
        method_summary="Score cluster marker sets against marker signatures using coverage and rank-weighted marker support, then report candidate labels and matched markers per cluster.",
        result_file="sctype.evidence.json",
    ),
    "sccatch": ExternalAnnotationProvider(
        provider_id="sccatch",
        title="scCATCH Annotation Evidence",
        subtitle="Tissue-aware marker matching with explicit R package and database provenance",
        evidence_layer="scCATCH annotation evidence",
        purpose="Tissue-aware marker matching",
        tool="scaudit scCATCH-style tissue-aware marker adapter",
        execution_environment="pixi default environment",
        dependency_plan="Executable scaudit-native adapter. Add the exact maintained scCATCH R package/database source later to replace this adapter.",
        method_summary="Compare cluster marker sets against marker references with tissue metadata recorded in the run payload.",
        result_file="sccatch.evidence.json",
    ),
    "scsa": ExternalAnnotationProvider(
        provider_id="scsa",
        title="SCSA Annotation Evidence",
        subtitle="External marker-scoring tool results with command and database provenance",
        evidence_layer="SCSA annotation evidence",
        purpose="External marker-scoring inference",
        tool="scaudit SCSA-style marker scoring adapter",
        execution_environment="pixi default environment",
        dependency_plan="Executable scaudit-native adapter. Select and pin a maintained SCSA CLI/package source later if exact SCSA execution is required.",
        method_summary="Run a weighted marker-set scoring pass over differential marker tables and collect cluster-level labels, scores, and database support.",
        result_file="scsa.evidence.json",
    ),
}


STATUS_FIELDS = ["provider_id", "status", "tool", "execution_environment", "reason"]
PREDICTION_FIELDS = [
    "cluster_id",
    "rank",
    "label",
    "score",
    "confidence",
    "matched_markers",
    "n_matched",
    "n_signature_genes",
    "coverage",
    "jaccard",
    "source",
]


def render_external_annotation_provider_report(
    provider_id: str,
    dataset_path: Path,
    cluster_key: str,
    output_dir: Path,
    *,
    evidence: dict[str, ClusterEvidence] | None = None,
    species: str = "",
    tissue: str = "",
    sample_key: str = "",
    batch_key: str = "",
) -> dict[str, Any]:
    spec = PROVIDERS[provider_id]
    provider_dir = output_dir / "evidence_reports" / spec.provider_id
    started_at = utc_now()
    payload = write_external_annotation_provider_outputs(
        provider_id,
        dataset_path,
        cluster_key,
        provider_dir,
        evidence=evidence,
        species=species,
        tissue=tissue,
        sample_key=sample_key,
        batch_key=batch_key,
        started_at=started_at,
    )
    qmd_path = provider_dir / f"{spec.provider_id}.qmd"
    _write_provider_qmd(
        qmd_path,
        spec,
        dataset_path,
        cluster_key,
        provider_dir,
        species=species,
        tissue=tissue,
        sample_key=sample_key,
        batch_key=batch_key,
    )
    html_path, render_warning = render_qmd(qmd_path)
    if html_path is None:
        html_path = provider_dir / f"{spec.provider_id}.html"
        _write_fallback_html(html_path, spec, payload)
        payload.setdefault("warnings", []).append(render_warning or "Quarto render failed; wrote a fallback HTML provider report.")
        payload["run"]["status"] = "warning"
    payload["artifacts"]["qmd"] = relative_to(qmd_path, output_dir)
    payload["artifacts"]["html"] = relative_to(html_path, output_dir)
    write_json(provider_dir / spec.result_file, payload)
    return _provider_index_entry(spec, payload, output_dir)


def write_external_annotation_provider_outputs(
    provider_id: str,
    dataset_path: Path,
    cluster_key: str,
    output_dir: Path,
    *,
    evidence: dict[str, ClusterEvidence] | None = None,
    species: str = "",
    tissue: str = "",
    sample_key: str = "",
    batch_key: str = "",
    started_at: str | None = None,
) -> dict[str, Any]:
    spec = PROVIDERS[provider_id]
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = output_dir / "figures"
    tables_dir = output_dir / "tables"
    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    started_at = started_at or utc_now()
    warnings: list[str] = []
    if evidence is None:
        evidence = compute_cluster_evidence(dataset_path, cluster_key, sample_key=sample_key, batch_key=batch_key)
    if not evidence:
        warnings.append("No cluster marker evidence was available; provider predictions could not be computed.")
    warnings.append(
        "Using the executable scaudit-native adapter for this provider; exact official package/script execution is not pinned yet."
    )
    prediction_rows = _prediction_rows(spec, evidence or {})
    status = "success" if prediction_rows else "warning"
    reason = "Computed standardized cluster predictions with the scaudit-native adapter." if prediction_rows else warnings[0]
    status_rows = [
        {
            "provider_id": spec.provider_id,
            "status": status,
            "tool": spec.tool,
            "execution_environment": spec.execution_environment,
            "reason": reason,
        }
    ]
    _write_csv(tables_dir / "provider_status.csv", status_rows, STATUS_FIELDS)
    _write_csv(tables_dir / "cluster_predictions.csv", prediction_rows, PREDICTION_FIELDS)
    figure_artifacts = _write_cluster_umap(dataset_path, cluster_key, figures_dir, tables_dir, warnings)
    prediction_tabs_path = output_dir / "cluster_prediction_tabs.md"
    prediction_tabs_path.write_text(_prediction_tabs_markdown(prediction_rows), encoding="utf-8")
    callout_path = output_dir / "callouts.md"
    callout_path.write_text(_callout_markdown(spec, warnings), encoding="utf-8")

    payload = {
        "schema_version": "0.1.0",
        "provider": {
            "id": spec.provider_id,
            "name": spec.title,
            "version": EXTERNAL_PROVIDER_VERSION,
            "purpose": spec.purpose,
        },
        "run": {
            "status": status,
            "started_at": started_at,
            "completed_at": utc_now(),
            "input_h5ad": str(dataset_path),
            "cluster_key": cluster_key,
            "species": species,
            "tissue": tissue,
            "sample_key": sample_key,
            "batch_key": batch_key,
            "execution_environment": spec.execution_environment,
        },
        "software": _software_versions(spec),
        "methods": [
            {
                "step": "Dependency boundary",
                "tool": "pixi",
                "environment": spec.execution_environment,
                "plan": spec.dependency_plan,
            },
            {
                "step": "External annotation",
                "tool": spec.tool,
                "status": "executed",
                "summary": spec.method_summary,
                "parameters": _scoring_parameters(spec, species=species, tissue=tissue),
            },
            {
                "step": "Standardization",
                "output_contract": "tables/cluster_predictions.csv and provider evidence JSON with one record per cluster prediction",
            },
        ],
        "artifacts": {
            "qmd": f"{spec.provider_id}.qmd",
            "html": f"{spec.provider_id}.html",
            "figures": [relative_to(Path(item), output_dir) for item in figure_artifacts],
            "tables": ["tables/provider_status.csv", "tables/cluster_predictions.csv", "tables/cluster_umap.source.csv"],
        },
        "results": {
            "summary": _summary(spec, prediction_rows),
            "clusters": _cluster_results(prediction_rows),
        },
        "warnings": warnings,
        "scaudit_version": __version__,
    }
    write_json(output_dir / spec.result_file, payload)
    return payload


def _prediction_rows(spec: ExternalAnnotationProvider, evidence: dict[str, ClusterEvidence]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cluster_id, ev in sorted(evidence.items(), key=lambda item: str(item[0])):
        markers = [marker for marker in ev.markers if marker.gene]
        if not markers:
            continue
        scored = _score_marker_sets(spec, markers)
        for rank, item in enumerate(scored[:5], start=1):
            rows.append(
                {
                    "cluster_id": str(cluster_id),
                    "rank": rank,
                    "label": item["label"],
                    "score": f"{item['score']:.3f}",
                    "confidence": _confidence(item["score"]),
                    "matched_markers": ", ".join(item["matched_markers"]),
                    "n_matched": item["n_matched"],
                    "n_signature_genes": item["n_signature_genes"],
                    "coverage": f"{item['coverage']:.3f}",
                    "jaccard": f"{item['jaccard']:.3f}",
                    "source": item["source"],
                }
            )
    return rows


def _score_marker_sets(spec: ExternalAnnotationProvider, markers: list[Any]) -> list[dict[str, Any]]:
    marker_by_gene = {str(marker.gene).upper(): marker for marker in markers}
    query = set(marker_by_gene)
    scored: list[dict[str, Any]] = []
    for label, genes in MARKER_DB.items():
        signature = {gene.upper() for gene in genes}
        matched = sorted(query & signature)
        if not matched:
            continue
        n_matched = len(matched)
        coverage = n_matched / len(signature)
        jaccard = n_matched / len(query | signature)
        rank_weight = sum(1.0 / max(1, int(getattr(marker_by_gene[gene], "rank", 1) or 1)) for gene in matched)
        effect_weight = sum(max(0.0, float(getattr(marker_by_gene[gene], "log2fc", 0.0) or 0.0)) for gene in matched)
        score = _provider_score(spec.provider_id, coverage, jaccard, rank_weight, effect_weight, len(query))
        scored.append(
            {
                "label": label,
                "score": score,
                "matched_markers": matched,
                "n_matched": n_matched,
                "n_signature_genes": len(signature),
                "coverage": coverage,
                "jaccard": jaccard,
                "source": f"scaudit.MARKER_DB:{spec.provider_id}_style_adapter",
            }
        )
    scored.sort(key=lambda item: (item["score"], item["coverage"], item["jaccard"], item["n_matched"]), reverse=True)
    return scored


def _provider_score(provider_id: str, coverage: float, jaccard: float, rank_weight: float, effect_weight: float, n_query: int) -> float:
    query_scale = max(1.0, math.log2(n_query + 1.0))
    if provider_id == "sctype":
        return coverage * 0.55 + min(1.0, rank_weight / query_scale) * 0.30 + jaccard * 0.15
    if provider_id == "sccatch":
        return coverage * 0.45 + jaccard * 0.35 + min(1.0, rank_weight / query_scale) * 0.20
    if provider_id == "scsa":
        return coverage * 0.35 + jaccard * 0.25 + min(1.0, effect_weight / (2.0 * query_scale)) * 0.40
    return coverage


def _confidence(score: float) -> str:
    if score >= 0.55:
        return "high"
    if score >= 0.30:
        return "moderate"
    return "low"


def _summary(spec: ExternalAnnotationProvider, prediction_rows: list[dict[str, Any]]) -> dict[str, Any]:
    clusters = {str(row["cluster_id"]) for row in prediction_rows}
    top_rows = [row for row in prediction_rows if int(row.get("rank") or 0) == 1]
    if top_rows:
        top_finding = f"{spec.title} produced top predictions for {len(top_rows)} clusters with the scaudit-native adapter."
    else:
        top_finding = f"{spec.title} did not produce predictions."
    return {
        "n_clusters_with_predictions": len(clusters),
        "n_predictions": len(prediction_rows),
        "top_finding": top_finding,
    }


def _cluster_results(prediction_rows: list[dict[str, Any]]) -> dict[str, Any]:
    clusters: dict[str, Any] = {}
    for row in prediction_rows:
        clusters.setdefault(str(row["cluster_id"]), {"predictions": []})
        clusters[str(row["cluster_id"])]["predictions"].append(dict(row))
    return clusters


def _scoring_parameters(spec: ExternalAnnotationProvider, *, species: str, tissue: str) -> dict[str, Any]:
    return {
        "adapter": f"{spec.provider_id}_style",
        "marker_database": "scaudit.markers.MARKER_DB",
        "top_predictions_per_cluster": 5,
        "species": species,
        "tissue": tissue,
        "score_components": ["signature coverage", "Jaccard overlap", "rank/effect weighted marker support"],
    }


def _write_cluster_umap(dataset_path: Path, cluster_key: str, figures_dir: Path, tables_dir: Path, warnings: list[str]) -> list[Path]:
    if not dataset_path.exists() or not cluster_key:
        return []
    try:
        import anndata as ad
        import matplotlib.pyplot as plt
        import pandas as pd
    except Exception:
        warnings.append("anndata, pandas, or matplotlib was unavailable; cluster UMAP figure was skipped.")
        return []

    try:
        adata = ad.read_h5ad(dataset_path)
    except Exception:
        warnings.append("Input h5ad could not be read for cluster UMAP generation.")
        return []
    if cluster_key not in adata.obs:
        warnings.append(f"cluster_key '{cluster_key}' was not found; cluster UMAP generation was skipped.")
        return []
    if "X_umap" not in adata.obsm:
        warnings.append("UMAP coordinates were not found in adata.obsm['X_umap']; cluster UMAP figure was skipped.")
        return []

    coords = adata.obsm["X_umap"]
    cluster_values = adata.obs[cluster_key].astype(str)
    rows = [
        {"umap_1": float(x), "umap_2": float(y), "cluster_id": str(cluster)}
        for x, y, cluster in zip(coords[:, 0], coords[:, 1], cluster_values)
    ]
    df = pd.DataFrame(rows)
    df.to_csv(tables_dir / "cluster_umap.source.csv", index=False)

    clusters = sorted(df["cluster_id"].unique().tolist())
    fig, ax = plt.subplots(figsize=(5.8, 5.2))
    for index, cluster in enumerate(clusters):
        subset = df[df["cluster_id"] == cluster]
        ax.scatter(
            subset["umap_1"],
            subset["umap_2"],
            s=5,
            alpha=0.72,
            linewidths=0,
            label=str(cluster),
            color=_provider_palette(index),
        )
    ax.set_xlabel("UMAP 1")
    ax.set_ylabel("UMAP 2")
    ax.set_title("Clusters")
    ax.legend(title="Cluster", loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False, markerscale=2.4)
    fig.subplots_adjust(left=0.11, right=0.78, top=0.9, bottom=0.12)
    return _save_figure(fig, figures_dir / "cluster_umap")


def _provider_palette(index: int) -> str:
    palette = [
        "#2f67c8",
        "#2a9d5c",
        "#d97706",
        "#7446a8",
        "#129a9f",
        "#c0392b",
        "#6b8e23",
        "#be185d",
        "#4b5563",
        "#b45309",
    ]
    return palette[index % len(palette)]


def _save_figure(fig: Any, stem: Path) -> list[Path]:
    paths = [stem.with_suffix(suffix) for suffix in (".svg", ".pdf", ".png")]
    for path in paths:
        fig.savefig(path, bbox_inches="tight", pad_inches=0.08)
    try:
        import matplotlib.pyplot as plt

        plt.close(fig)
    except Exception:
        pass
    return paths


def _prediction_tabs_markdown(prediction_rows: list[dict[str, Any]]) -> str:
    if not prediction_rows:
        return "No cluster-level predictions are available. Check provider warnings and marker evidence availability.\n"

    clusters = sorted({str(row["cluster_id"]) for row in prediction_rows})
    lines = ["::: {.panel-tabset}", ""]
    for cluster in clusters:
        rows = [row for row in prediction_rows if str(row["cluster_id"]) == cluster]
        rows.sort(key=lambda row: int(row.get("rank") or 9999))
        lines.append(f"## Cluster {html.escape(cluster)}")
        lines.append("")
        lines.append(_prediction_summary_table(rows))
        lines.append("")
        lines.append("<details class=\"signature-gene-details\">")
        lines.append("<summary>Show matched markers and sources</summary>")
        lines.append("")
        lines.append(_prediction_details(rows))
        lines.append("</details>")
        lines.append("")
    lines.append(":::")
    lines.append("")
    return "\n".join(lines)


def _prediction_summary_table(rows: list[dict[str, Any]]) -> str:
    headers = ["Rank", "Label", "Score", "Confidence", "Matched", "Coverage", "Jaccard"]
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('rank', '')))}</td>"
            f"<td>{html.escape(str(row.get('label', '')))}</td>"
            f"<td>{_format_decimal(row.get('score'))}</td>"
            f"<td>{html.escape(str(row.get('confidence', '')))}</td>"
            f"<td>{html.escape(str(row.get('n_matched', '')))}</td>"
            f"<td>{_format_fraction(row.get('coverage'))}</td>"
            f"<td>{_format_decimal(row.get('jaccard'))}</td>"
            "</tr>"
        )
    head_html = "".join(f"<th>{header}</th>" for header in headers)
    body_html = "".join(body)
    return f'<table class="scaudit-table cluster-prediction-table"><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>'


def _prediction_details(rows: list[dict[str, Any]]) -> str:
    items = []
    for row in rows:
        label = html.escape(str(row.get("label", "")))
        matched = html.escape(str(row.get("matched_markers", "") or "none"))
        source = html.escape(str(row.get("source", "") or "not recorded"))
        items.append(
            "<section class=\"signature-gene-block\">"
            f"<h4>{label}</h4>"
            f"<p><strong>Matched markers:</strong> {matched}</p>"
            f"<p><strong>Source:</strong> {source}</p>"
            "</section>"
        )
    return "\n".join(items)


def _format_decimal(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return html.escape(str(value or ""))


def _format_fraction(value: Any) -> str:
    try:
        return f"{float(value):.0%}"
    except (TypeError, ValueError):
        return html.escape(str(value or ""))


def _software_versions(spec: ExternalAnnotationProvider) -> dict[str, str]:
    versions = package_versions(["pandas", "numpy"])
    if "provider-r" in spec.execution_environment:
        versions["r"] = "managed by pixi provider-r environment"
    return versions


def _provider_index_entry(spec: ExternalAnnotationProvider, payload: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    artifacts = payload.get("artifacts", {})
    return {
        "id": spec.provider_id,
        "name": spec.title,
        "purpose": spec.purpose,
        "status": payload.get("run", {}).get("status", "unknown"),
        "top_finding": payload.get("results", {}).get("summary", {}).get("top_finding", ""),
        "html": artifacts.get("html", f"evidence_reports/{spec.provider_id}/{spec.provider_id}.html"),
        "json": relative_to(output_dir / "evidence_reports" / spec.provider_id / spec.result_file, output_dir),
        "warnings": payload.get("warnings", []),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _callout_markdown(spec: ExternalAnnotationProvider, warnings: list[str]) -> str:
    lines = [
        "::: {.callout-note}",
        f"This focused report executes `{spec.tool}`. It is separated from marker-based evidence so users can inspect this provider's exact adapter, parameters, and output contract.",
        ":::",
        "",
    ]
    if warnings:
        lines.extend(["::: {.callout-warning}", "Warnings detected:", ""])
        lines.extend(f"- {warning}" for warning in warnings)
        lines.extend([":::", ""])
    lines.extend(
        [
            "::: {.callout-tip}",
            f"To replace the scaudit-native adapter with exact official execution, pin the tool/database source and keep writing `tables/cluster_predictions.csv` and `{spec.result_file}`.",
            ":::",
            "",
        ]
    )
    return "\n".join(lines)


def _write_provider_qmd(
    qmd_path: Path,
    spec: ExternalAnnotationProvider,
    dataset_path: Path,
    cluster_key: str,
    provider_dir: Path,
    *,
    species: str = "",
    tissue: str = "",
    sample_key: str = "",
    batch_key: str = "",
) -> None:
    text = f"""---
title: "{spec.title}"
subtitle: "{spec.subtitle}"
format:
  html:
    toc: true
    code-tools: true
    code-fold: true
    code-summary: "Show/hide analysis code"
    embed-resources: false
execute:
  echo: true
  warning: true
  message: false
  error: false
jupyter: python3

scaudit:
  provider_id: "{spec.provider_id}"
  provider_version: "{EXTERNAL_PROVIDER_VERSION}"
  evidence_layer: "{spec.evidence_layer}"
  purpose: "{spec.purpose}"
  standard_output: "{spec.result_file}"

params:
  input_h5ad: "{dataset_path}"
  cluster_key: "{cluster_key}"
  species: "{species}"
  tissue: "{tissue}"
  sample_key: "{sample_key}"
  batch_key: "{batch_key}"
  output_dir: "{provider_dir}"
  execution_environment: "{spec.execution_environment}"
  tool: "{spec.tool}"
---

<style>
details.code-fold > summary {{
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border: 1px solid #8da2c0;
  border-radius: 6px;
  padding: 0.25rem 0.65rem;
  margin: 0.35rem 0;
  background: #f4f7fb;
  color: #18324a;
  font-size: 0.86rem;
  font-weight: 600;
  cursor: pointer;
}}

details.code-fold[open] > summary {{
  background: #e8eef8;
}}

.scaudit-table {{
  border-collapse: collapse;
  width: 100%;
  font-size: 0.92rem;
}}

.scaudit-table th,
.scaudit-table td {{
  border-bottom: 1px solid #e1e7ef;
  padding: 0.35rem 0.45rem;
  vertical-align: top;
}}

.scaudit-table tbody tr:last-child td {{
  border-bottom: 0;
}}

.scaudit-table th {{
  background: #f4f7fb;
  color: #18324a;
  font-weight: 700;
}}

.cluster-prediction-table {{
  margin-bottom: 1.2rem;
}}

.panel-tabset .tab-content {{
  border: 0;
}}

.panel-tabset .nav-tabs {{
  border-bottom: 0;
}}

.marker-signature-workspace {{
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}}

.marker-signature-umap {{
  width: 100%;
}}

.marker-signature-umap img {{
  width: 100%;
  height: auto;
}}

.marker-signature-tabs {{
  min-width: 0;
}}

.signature-gene-details {{
  margin: 0.35rem 0 1.1rem;
  padding: 0.55rem 0.7rem;
  background: #fbfcff;
}}

.signature-gene-details summary {{
  color: #18324a;
  cursor: pointer;
  font-weight: 650;
}}

.signature-gene-block {{
  border-top: 1px solid #e8edf5;
  margin-top: 0.65rem;
  padding-top: 0.55rem;
}}

.signature-gene-block h4 {{
  margin: 0 0 0.25rem;
  font-size: 0.95rem;
}}

.signature-gene-block p {{
  margin: 0.2rem 0;
  overflow-wrap: anywhere;
}}
</style>

## Question

What evidence does {spec.tool} provide for cluster-level cell annotation?

{{{{< include callouts.md >}}}}

## Inputs and Parameters

| Field | Value |
| --- | --- |
| Input h5ad | `{dataset_path}` |
| Cluster key | `{cluster_key}` |
| Species | `{species}` |
| Tissue | `{tissue}` |
| Sample key | `{sample_key}` |
| Batch key | `{batch_key}` |
| Tool | `{spec.tool}` |
| Pixi environment | `{spec.execution_environment}` |
| Dependency plan | `{spec.dependency_plan}` |

## Reproducible Execution

```{{python}}
#| eval: false
from pathlib import Path
from scaudit.providers.external_annotation import write_external_annotation_provider_outputs

payload = write_external_annotation_provider_outputs(
    "{spec.provider_id}",
    Path(r"{dataset_path}"),
    r"{cluster_key}",
    Path(r"{provider_dir}"),
    species=r"{species}",
    tissue=r"{tissue}",
    sample_key=r"{sample_key}",
    batch_key=r"{batch_key}",
)
payload["results"]["summary"]
```

## Key Results

```{{python}}
import json
from pathlib import Path

payload = json.loads(Path("{spec.result_file}").read_text())
payload["results"]["summary"]
```

## Provider Status

```{{python}}
import pandas as pd
from IPython.display import HTML

status = pd.read_csv("tables/provider_status.csv")
HTML(status.to_html(index=False, classes="scaudit-table", border=0))
```

## Cluster-Level Predictions

The cluster UMAP is shown with provider predictions below. Each tab contains candidate labels for one cluster. Scores, coverage, and Jaccard values are rounded for readability; full-precision values are available in `tables/cluster_predictions.csv` and `{spec.result_file}`.

::: {{.marker-signature-workspace}}
::: {{.marker-signature-umap}}
![Cluster UMAP](figures/cluster_umap.png)
:::

::: {{.marker-signature-tabs}}
{{{{< include cluster_prediction_tabs.md >}}}}
:::
:::

## Method Contract

This provider will write one standardized row per cluster-label candidate to `tables/cluster_predictions.csv`.

| Output column | Meaning |
| --- | --- |
| `cluster_id` | Cluster identifier from the input h5ad |
| `rank` | Rank within cluster, where 1 is the strongest candidate |
| `label` | Candidate cell-type label returned by the provider |
| `score` | Provider-specific score, standardized as numeric when possible |
| `confidence` | Provider-specific confidence or qualitative support |
| `matched_markers` | Markers supporting the candidate label |
| `source` | Tool database or reference source |

## Reproducibility

The machine-readable provider output is `{spec.result_file}`. Provider status and future cluster-level predictions are stored under `tables/`.
"""
    qmd_path.write_text(text, encoding="utf-8")


def _write_fallback_html(path: Path, spec: ExternalAnnotationProvider, payload: dict[str, Any]) -> None:
    summary = html.escape(str(payload.get("results", {}).get("summary", {})))
    warnings = payload.get("warnings", [])
    warning_html = "".join(f"<li>{html.escape(str(warning))}</li>" for warning in warnings)
    path.write_text(
        f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{html.escape(spec.title)}</title></head>
<body>
<h1>{html.escape(spec.title)}</h1>
<p>This fallback report was written because Quarto rendering was unavailable. The qmd, evidence JSON, and tables are available in the same directory.</p>
<h2>Summary</h2>
<pre>{summary}</pre>
<h2>Warnings</h2>
<ul>{warning_html}</ul>
<h2>Artifacts</h2>
<ul>
<li><a href="{spec.provider_id}.qmd">{spec.provider_id}.qmd</a></li>
<li><a href="{spec.result_file}">{spec.result_file}</a></li>
<li><a href="tables/provider_status.csv">provider_status.csv</a></li>
<li><a href="tables/cluster_predictions.csv">cluster_predictions.csv</a></li>
</ul>
</body>
</html>
""",
        encoding="utf-8",
    )
