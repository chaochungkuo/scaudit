from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from scaudit import __version__
from scaudit.data import ClusterEvidence, compute_cluster_evidence
from scaudit.providers.schema import package_versions, relative_to, render_qmd, utc_now, write_json


REFERENCE_PROVIDER_ID = "reference_mapping"
REFERENCE_PROVIDER_VERSION = "0.1.0"
REFERENCE_MATCH_FIELDS = ["cluster_id", "rank", "ref_id", "label", "jaccard", "n_shared"]
REFERENCE_SUMMARY_FIELDS = ["ref_id", "n_matches", "max_jaccard", "mean_jaccard", "labels"]


def render_reference_provider_report(
    dataset_path: Path,
    cluster_key: str,
    output_dir: Path,
    *,
    evidence: dict[str, ClusterEvidence] | None = None,
    reference_registry_path: Path | None = None,
    sample_key: str = "",
    batch_key: str = "",
) -> dict[str, Any]:
    provider_dir = output_dir / "evidence_reports" / REFERENCE_PROVIDER_ID
    started_at = utc_now()
    payload = write_reference_provider_outputs(
        dataset_path,
        cluster_key,
        provider_dir,
        evidence=evidence,
        reference_registry_path=reference_registry_path,
        sample_key=sample_key,
        batch_key=batch_key,
        started_at=started_at,
    )
    qmd_path = provider_dir / "reference_mapping.qmd"
    _write_reference_qmd(qmd_path, dataset_path, cluster_key, provider_dir)
    html_path, render_warning = render_qmd(qmd_path)
    if html_path is None:
        html_path = provider_dir / "reference_mapping.html"
        _write_fallback_html(html_path, payload)
        payload.setdefault("warnings", []).append(render_warning or "Quarto render failed; wrote a fallback HTML provider report.")
        payload["run"]["status"] = "warning"
    payload["artifacts"]["qmd"] = relative_to(qmd_path, output_dir)
    payload["artifacts"]["html"] = relative_to(html_path, output_dir)
    write_json(provider_dir / "reference_mapping.evidence.json", payload)
    return _provider_index_entry(payload, output_dir)


def write_reference_provider_outputs(
    dataset_path: Path,
    cluster_key: str,
    output_dir: Path,
    *,
    evidence: dict[str, ClusterEvidence] | None = None,
    reference_registry_path: Path | None = None,
    sample_key: str = "",
    batch_key: str = "",
    started_at: str | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    started_at = started_at or utc_now()
    if evidence is None:
        evidence = compute_cluster_evidence(
            dataset_path,
            cluster_key,
            reference_registry_path=reference_registry_path,
            sample_key=sample_key,
            batch_key=batch_key,
        )
    if reference_registry_path is None or not reference_registry_path.exists():
        warnings.append("No external reference registry was selected; reference mapping was not run.")
    if not evidence:
        warnings.append("No cluster evidence was available for reference mapping.")

    match_rows = _reference_match_rows(evidence or {})
    summary_rows = _reference_summary_rows(match_rows)
    _write_csv(tables_dir / "reference_matches.csv", match_rows, REFERENCE_MATCH_FIELDS)
    _write_csv(tables_dir / "reference_summary.csv", summary_rows, REFERENCE_SUMMARY_FIELDS)
    callout_path = output_dir / "callouts.md"
    callout_path.write_text(_callout_markdown(warnings, match_rows), encoding="utf-8")

    status = "success" if match_rows and not warnings else "warning" if warnings else "missing"
    payload = {
        "schema_version": "0.1.0",
        "provider": {
            "id": REFERENCE_PROVIDER_ID,
            "name": "Reference-based mapping",
            "version": REFERENCE_PROVIDER_VERSION,
            "purpose": "Biological grounding",
        },
        "run": {
            "status": status,
            "started_at": started_at,
            "completed_at": utc_now(),
            "input_h5ad": str(dataset_path),
            "cluster_key": cluster_key,
            "reference_registry": str(reference_registry_path) if reference_registry_path else "",
        },
        "software": package_versions(["scanpy", "anndata", "pandas", "numpy"]),
        "methods": [
            {
                "step": "Query marker sets",
                "tool": "scanpy.tl.rank_genes_groups",
                "parameters": {
                    "method": "wilcoxon",
                    "marker_filter": "padj < 0.05 and log2FC > 0.5",
                },
            },
            {
                "step": "Reference marker sets",
                "tool": "scanpy.tl.rank_genes_groups",
                "parameters": {
                    "method": "wilcoxon",
                    "n_top_reference_markers": 20,
                    "groupby": "reference manifest label_key",
                },
            },
            {
                "step": "Reference matching",
                "formula": "Jaccard(query cluster marker genes, reference label marker genes)",
                "threshold": "Report matches with Jaccard > 0.05",
            },
        ],
        "artifacts": {
            "qmd": "reference_mapping.qmd",
            "html": "reference_mapping.html",
            "figures": [],
            "tables": ["tables/reference_matches.csv", "tables/reference_summary.csv"],
        },
        "results": {
            "summary": _summary(match_rows, summary_rows),
            "clusters": _cluster_results(match_rows),
            "references": summary_rows,
        },
        "warnings": warnings,
        "scaudit_version": __version__,
    }
    write_json(output_dir / "reference_mapping.evidence.json", payload)
    return payload


def _provider_index_entry(payload: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    provider = payload.get("provider", {})
    results = payload.get("results", {})
    artifacts = payload.get("artifacts", {})
    return {
        "id": provider.get("id", REFERENCE_PROVIDER_ID),
        "name": provider.get("name", "Reference-based mapping"),
        "purpose": provider.get("purpose", "Biological grounding"),
        "status": payload.get("run", {}).get("status", "unknown"),
        "top_finding": results.get("summary", {}).get("top_finding", ""),
        "html": artifacts.get("html", "evidence_reports/reference_mapping/reference_mapping.html"),
        "json": relative_to(output_dir / "evidence_reports" / REFERENCE_PROVIDER_ID / "reference_mapping.evidence.json", output_dir),
        "warnings": payload.get("warnings", []),
    }


def _reference_match_rows(evidence: dict[str, ClusterEvidence]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cluster_id, ev in sorted(evidence.items(), key=lambda item: str(item[0])):
        external = [match for match in ev.reference_matches if isinstance(match, dict) and match.get("ref_id") != "builtin"]
        for rank, match in enumerate(external, start=1):
            rows.append(
                {
                    "cluster_id": str(cluster_id),
                    "rank": rank,
                    "ref_id": str(match.get("ref_id") or ""),
                    "label": str(match.get("label") or ""),
                    "jaccard": match.get("jaccard", ""),
                    "n_shared": match.get("n_shared", ""),
                }
            )
    return rows


def _reference_summary_rows(match_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_ref: dict[str, list[dict[str, Any]]] = {}
    for row in match_rows:
        by_ref.setdefault(str(row["ref_id"]), []).append(row)
    rows = []
    for ref_id, ref_rows in sorted(by_ref.items()):
        jaccards = [float(row["jaccard"]) for row in ref_rows if isinstance(row.get("jaccard"), (int, float))]
        labels = sorted({str(row.get("label") or "") for row in ref_rows if row.get("label")})
        rows.append(
            {
                "ref_id": ref_id,
                "n_matches": len(ref_rows),
                "max_jaccard": round(max(jaccards), 3) if jaccards else "",
                "mean_jaccard": round(sum(jaccards) / len(jaccards), 3) if jaccards else "",
                "labels": ", ".join(labels[:12]),
            }
        )
    return rows


def _summary(match_rows: list[dict[str, Any]], summary_rows: list[dict[str, Any]]) -> dict[str, Any]:
    cluster_ids = {str(row["cluster_id"]) for row in match_rows}
    best = max(match_rows, key=lambda row: float(row["jaccard"] or 0), default=None)
    if best:
        top_finding = (
            f"{len(cluster_ids)} clusters have external reference matches; "
            f"best match {best['ref_id']}:{best['label']} (J={float(best['jaccard']):.2f})"
        )
    else:
        top_finding = "No external reference matches available"
    return {
        "n_reference_sources": len(summary_rows),
        "n_clusters_with_reference_matches": len(cluster_ids),
        "n_matches": len(match_rows),
        "top_finding": top_finding,
    }


def _cluster_results(match_rows: list[dict[str, Any]]) -> dict[str, Any]:
    clusters: dict[str, Any] = {}
    for row in match_rows:
        clusters.setdefault(str(row["cluster_id"]), {"reference_matches": []})
        clusters[str(row["cluster_id"])]["reference_matches"].append(dict(row))
    return clusters


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _callout_markdown(warnings: list[str], match_rows: list[dict[str, Any]]) -> str:
    lines = [
        "::: {.callout-note}",
        "This focused report evaluates external reference-based grounding only. Built-in marker database overlaps remain part of the marker-based evidence report.",
        ":::",
        "",
    ]
    if match_rows:
        lines.extend(
            [
                "::: {.callout-important}",
                f"{len({str(row['cluster_id']) for row in match_rows})} clusters have at least one external reference match.",
                ":::",
                "",
            ]
        )
    if warnings:
        lines.extend(["::: {.callout-warning}", "Warnings detected:", ""])
        lines.extend(f"- {warning}" for warning in warnings[:6])
        lines.extend([":::", ""])
    if not match_rows:
        lines.extend(
            [
                "::: {.callout-caution}",
                "No external reference matches are available. Interpret annotation labels using marker and model evidence until a suitable reference is selected.",
                ":::",
                "",
            ]
        )
    lines.extend(
        [
            "::: {.callout-tip}",
            "Register a local reference with `scaudit reference add ...` and select it with `scaudit reference use ... --config config.toml`.",
            ":::",
            "",
        ]
    )
    return "\n".join(lines)


def _write_reference_qmd(qmd_path: Path, dataset_path: Path, cluster_key: str, provider_dir: Path) -> None:
    text = f"""---
title: "Reference-Based Mapping"
subtitle: "External reference label matching and gene overlap"
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
  provider_id: "reference_mapping"
  provider_version: "{REFERENCE_PROVIDER_VERSION}"
  evidence_layer: "Reference-based mapping"
  purpose: "Biological grounding"
  standard_output: "reference_mapping.evidence.json"

params:
  input_h5ad: "{dataset_path}"
  cluster_key: "{cluster_key}"
  output_dir: "{provider_dir}"
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
</style>

## Question

Do external reference datasets biologically ground the cluster labels?

{{{{< include callouts.md >}}}}

## Inputs and Parameters

| Field | Value |
| --- | --- |
| Input h5ad | `{dataset_path}` |
| Cluster key | `{cluster_key}` |
| Query marker rule | `padj < 0.05 and log2FC > 0.5` |
| Reference marker method | `scanpy.tl.rank_genes_groups(method="wilcoxon")` |
| Match score | `Jaccard(query markers, reference label markers)` |

## Reproducible Execution

```{{python}}
#| eval: false
from pathlib import Path
from scaudit.providers.reference_mapping import write_reference_provider_outputs

payload = write_reference_provider_outputs(
    Path(r"{dataset_path}"),
    r"{cluster_key}",
    Path(r"{provider_dir}"),
)
payload["results"]["summary"]
```

## Key Results

```{{python}}
import json
from pathlib import Path

payload = json.loads(Path("reference_mapping.evidence.json").read_text())
payload["results"]["summary"]
```

## Reference Summary

```{{python}}
import pandas as pd

pd.read_csv("tables/reference_summary.csv")
```

## Cluster-Level Reference Matches

```{{python}}
import pandas as pd

pd.read_csv("tables/reference_matches.csv").head(50)
```

## Reproducibility

The machine-readable provider output is `reference_mapping.evidence.json`. Reviewable source tables are stored under `tables/`.
"""
    qmd_path.write_text(text, encoding="utf-8")


def _write_fallback_html(path: Path, payload: dict[str, Any]) -> None:
    summary = payload.get("results", {}).get("summary", {})
    warnings = payload.get("warnings", [])
    warning_html = "".join(f"<li>{warning}</li>" for warning in warnings)
    path.write_text(
        f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Reference-Based Mapping</title></head>
<body>
<h1>Reference-Based Mapping</h1>
<p>This fallback report was written because Quarto rendering was unavailable. The qmd, evidence JSON, and tables are available in the same directory.</p>
<h2>Summary</h2>
<pre>{summary}</pre>
<h2>Warnings</h2>
<ul>{warning_html}</ul>
<h2>Artifacts</h2>
<ul>
<li><a href="reference_mapping.qmd">reference_mapping.qmd</a></li>
<li><a href="reference_mapping.evidence.json">reference_mapping.evidence.json</a></li>
<li><a href="tables/reference_matches.csv">reference_matches.csv</a></li>
<li><a href="tables/reference_summary.csv">reference_summary.csv</a></li>
</ul>
</body>
</html>
""",
        encoding="utf-8",
    )
