from __future__ import annotations

import csv
import html
import math
from pathlib import Path
from typing import Any

from scaudit import __version__
from scaudit.data import ClusterEvidence, compute_cluster_evidence
from scaudit.providers.schema import package_versions, relative_to, render_qmd, utc_now, write_json


MARKER_PROVIDER_ID = "marker_based"
MARKER_PROVIDER_VERSION = "0.1.0"
MARKER_TABLE_FIELDS = ["cluster_id", "rank", "gene", "score", "log2fc", "pval_adj", "strength"]
SIGNATURE_TABLE_FIELDS = [
    "cluster_id",
    "rank",
    "label",
    "source",
    "tool",
    "n_matched",
    "n_signature_genes",
    "coverage",
    "overlap_score",
    "matched_genes",
    "missing_genes",
]
STRENGTH_TABLE_FIELDS = ["cluster_id", "n_markers", "strong", "moderate", "weak"]


def render_marker_provider_report(
    dataset_path: Path,
    cluster_key: str,
    output_dir: Path,
    *,
    evidence: dict[str, ClusterEvidence] | None = None,
    sample_key: str = "",
    batch_key: str = "",
    n_top_genes: int = 50,
) -> dict[str, Any]:
    provider_dir = output_dir / "evidence_reports" / MARKER_PROVIDER_ID
    started_at = utc_now()
    payload = write_marker_provider_outputs(
        dataset_path,
        cluster_key,
        provider_dir,
        evidence=evidence,
        sample_key=sample_key,
        batch_key=batch_key,
        n_top_genes=n_top_genes,
        started_at=started_at,
    )
    qmd_path = provider_dir / "marker_based.qmd"
    _write_marker_qmd(qmd_path, dataset_path, cluster_key, provider_dir, n_top_genes=n_top_genes)
    html_path, render_warning = render_qmd(qmd_path)
    if html_path is None:
        html_path = provider_dir / "marker_based.html"
        _write_fallback_html(html_path, payload)
        payload.setdefault("warnings", []).append(render_warning or "Quarto render failed; wrote a fallback HTML provider report.")
        payload["run"]["status"] = "warning"
    payload["artifacts"]["qmd"] = relative_to(qmd_path, output_dir)
    payload["artifacts"]["html"] = relative_to(html_path, output_dir)
    write_json(provider_dir / "marker_based.evidence.json", payload)
    return _provider_index_entry(payload, output_dir)


def write_marker_provider_outputs(
    dataset_path: Path,
    cluster_key: str,
    output_dir: Path,
    *,
    evidence: dict[str, ClusterEvidence] | None = None,
    sample_key: str = "",
    batch_key: str = "",
    n_top_genes: int = 50,
    started_at: str | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = output_dir / "figures"
    tables_dir = output_dir / "tables"
    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    started_at = started_at or utc_now()
    if evidence is None:
        evidence = compute_cluster_evidence(
            dataset_path,
            cluster_key,
            n_top_genes=n_top_genes,
            sample_key=sample_key,
            batch_key=batch_key,
        )
    if not evidence:
        warnings.append("No marker evidence was computed. Check the input h5ad path, cluster key, and scanpy availability.")

    marker_rows = _marker_rows(evidence)
    signature_rows = _signature_rows(evidence)
    strength_rows = _strength_rows(evidence)
    _write_csv(tables_dir / "differential_markers.csv", marker_rows, MARKER_TABLE_FIELDS)
    _write_csv(tables_dir / "marker_signatures.csv", signature_rows, SIGNATURE_TABLE_FIELDS)
    _write_csv(tables_dir / "marker_strength_summary.csv", strength_rows, STRENGTH_TABLE_FIELDS)

    figure_artifacts = []
    figure_artifacts.extend(_write_cluster_umap(dataset_path, cluster_key, figures_dir, tables_dir, warnings))
    figure_artifacts.extend(_write_marker_heatmap(figures_dir, tables_dir, marker_rows, warnings))
    figure_artifacts.extend(_write_marker_dotplot(dataset_path, cluster_key, figures_dir, tables_dir, marker_rows, warnings))
    callout_path = output_dir / "callouts.md"
    callout_path.write_text(_callout_markdown(warnings, strength_rows, signature_rows), encoding="utf-8")
    signature_tabs_path = output_dir / "cluster_signature_tabs.md"
    signature_tabs_path.write_text(_signature_tabs_markdown(signature_rows), encoding="utf-8")
    marker_tabs_path = output_dir / "cluster_marker_tabs.md"
    marker_tabs_path.write_text(_marker_tabs_markdown(marker_rows), encoding="utf-8")

    payload = {
        "schema_version": "0.1.0",
        "provider": {
            "id": MARKER_PROVIDER_ID,
            "name": "Marker-based evidence",
            "version": MARKER_PROVIDER_VERSION,
            "purpose": "Biological interpretability",
        },
        "run": {
            "status": "success" if not warnings else "warning",
            "started_at": started_at,
            "completed_at": utc_now(),
            "input_h5ad": str(dataset_path),
            "cluster_key": cluster_key,
        },
        "software": package_versions(["scanpy", "anndata", "pandas", "numpy", "matplotlib", "seaborn"]),
        "methods": [
            {
                "step": "Differential expression",
                "tool": "scanpy.tl.rank_genes_groups",
                "parameters": {
                    "method": "wilcoxon",
                    "n_genes": n_top_genes,
                    "use_raw": True,
                    "key_added": "rank_genes",
                },
            },
            {"step": "Marker filtering", "rule": "padj < 0.05 and log2FC > 0.5"},
            {
                "step": "Marker signature scoring",
                "tool": "scaudit.markers.MARKER_DB",
                "formula": "coverage = matched signature genes / signature genes; overlap = Jaccard(query markers, signature genes)",
            },
        ],
        "artifacts": {
            "qmd": "marker_based.qmd",
            "html": "marker_based.html",
            "figures": [relative_to(Path(item), output_dir) for item in figure_artifacts],
            "tables": [
                "tables/differential_markers.csv",
                "tables/marker_signatures.csv",
                "tables/marker_strength_summary.csv",
                "tables/marker_log2fc_heatmap.source.csv",
                "tables/marker_expression_dotplot.source.csv",
                "tables/cluster_umap.source.csv",
            ],
        },
        "results": {
            "summary": _summary(strength_rows, signature_rows),
            "clusters": _cluster_results(evidence),
        },
        "warnings": warnings,
        "scaudit_version": __version__,
    }
    write_json(output_dir / "marker_based.evidence.json", payload)
    return payload


def _provider_index_entry(payload: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    provider = payload.get("provider", {})
    results = payload.get("results", {})
    artifacts = payload.get("artifacts", {})
    return {
        "id": provider.get("id", MARKER_PROVIDER_ID),
        "name": provider.get("name", "Marker-based evidence"),
        "purpose": provider.get("purpose", "Biological interpretability"),
        "status": payload.get("run", {}).get("status", "unknown"),
        "top_finding": results.get("summary", {}).get("top_finding", ""),
        "html": artifacts.get("html", "evidence_reports/marker_based/marker_based.html"),
        "json": relative_to(output_dir / "evidence_reports" / MARKER_PROVIDER_ID / "marker_based.evidence.json", output_dir),
        "warnings": payload.get("warnings", []),
    }


def _marker_rows(evidence: dict[str, ClusterEvidence]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cluster_id, ev in sorted(evidence.items(), key=lambda item: str(item[0])):
        for rank, marker in enumerate(ev.markers, start=1):
            rows.append(
                {
                    "cluster_id": str(cluster_id),
                    "rank": rank,
                    "gene": marker.gene,
                    "score": marker.score,
                    "log2fc": marker.log2fc,
                    "pval_adj": marker.pval_adj,
                    "strength": _marker_strength(marker.log2fc, marker.pval_adj, marker.score),
                }
            )
    return rows


def _signature_rows(evidence: dict[str, ClusterEvidence]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cluster_id, ev in sorted(evidence.items(), key=lambda item: str(item[0])):
        for rank, signature in enumerate(ev.marker_signatures, start=1):
            rows.append(
                {
                    "cluster_id": str(cluster_id),
                    "rank": rank,
                    "label": signature.get("label", ""),
                    "source": signature.get("source", ""),
                    "tool": signature.get("tool", ""),
                    "n_matched": signature.get("n_matched", 0),
                    "n_signature_genes": signature.get("n_signature_genes", 0),
                    "coverage": signature.get("coverage", 0),
                    "overlap_score": signature.get("overlap_score", 0),
                    "matched_genes": ", ".join(map(str, signature.get("matched_genes", []))),
                    "missing_genes": ", ".join(map(str, signature.get("missing_genes", []))),
                }
            )
    return rows


def _strength_rows(evidence: dict[str, ClusterEvidence]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cluster_id, ev in sorted(evidence.items(), key=lambda item: str(item[0])):
        counts = {"strong": 0, "moderate": 0, "weak": 0}
        for marker in ev.markers:
            counts[_marker_strength(marker.log2fc, marker.pval_adj, marker.score)] += 1
        rows.append(
            {
                "cluster_id": str(cluster_id),
                "n_markers": len(ev.markers),
                "strong": counts["strong"],
                "moderate": counts["moderate"],
                "weak": counts["weak"],
            }
        )
    return rows


def _cluster_results(evidence: dict[str, ClusterEvidence]) -> dict[str, Any]:
    clusters: dict[str, Any] = {}
    for cluster_id, ev in sorted(evidence.items(), key=lambda item: str(item[0])):
        clusters[str(cluster_id)] = {
            "top_markers": [marker.to_dict() for marker in ev.markers[:10]],
            "marker_signatures": ev.marker_signatures[:5],
            "strength_summary": {
                "strong": sum(1 for marker in ev.markers if _marker_strength(marker.log2fc, marker.pval_adj, marker.score) == "strong"),
                "moderate": sum(1 for marker in ev.markers if _marker_strength(marker.log2fc, marker.pval_adj, marker.score) == "moderate"),
                "weak": sum(1 for marker in ev.markers if _marker_strength(marker.log2fc, marker.pval_adj, marker.score) == "weak"),
            },
        }
    return clusters


def _summary(strength_rows: list[dict[str, Any]], signature_rows: list[dict[str, Any]]) -> dict[str, Any]:
    n_clusters = len(strength_rows)
    strong_clusters = sum(1 for row in strength_rows if int(row.get("strong", 0)) >= 3)
    top_signature = signature_rows[0]["label"] if signature_rows else ""
    top_finding = f"{strong_clusters}/{n_clusters} clusters have at least 3 strong markers" if n_clusters else "No marker evidence available"
    if top_signature:
        top_finding += f"; top signature: {top_signature}"
    return {
        "n_clusters": n_clusters,
        "clusters_with_strong_marker_support": strong_clusters,
        "n_signature_matches": len(signature_rows),
        "top_finding": top_finding,
    }


def _marker_strength(log2fc: float, pval_adj: float, score: float) -> str:
    if pval_adj >= 0.05:
        return "weak"
    if math.isnan(log2fc):
        return "moderate" if score > 0 else "weak"
    if log2fc > 1.0 and pval_adj < 0.01:
        return "strong"
    if log2fc > 0.5:
        return "moderate"
    return "weak"


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = fieldnames or (list(rows[0].keys()) if rows else [])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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


def _write_marker_heatmap(figures_dir: Path, tables_dir: Path, marker_rows: list[dict[str, Any]], warnings: list[str]) -> list[Path]:
    if not marker_rows:
        return []
    try:
        import matplotlib.pyplot as plt
        import pandas as pd
        import seaborn as sns
    except Exception:
        warnings.append("matplotlib, pandas, or seaborn was unavailable; marker heatmap figure was skipped.")
        return []

    selected_genes = _balanced_marker_genes(marker_rows, per_cluster=4, max_genes=32)
    clusters = sorted({str(row["cluster_id"]) for row in marker_rows})
    matrix = pd.DataFrame(0.0, index=selected_genes, columns=clusters)
    for row in marker_rows:
        gene = str(row["gene"])
        cluster = str(row["cluster_id"])
        if gene in matrix.index and cluster in matrix.columns:
            matrix.loc[gene, cluster] = float(row.get("log2fc") or 0.0)
    source_path = tables_dir / "marker_log2fc_heatmap.source.csv"
    matrix.to_csv(source_path)

    height = max(3.0, min(10.0, 0.24 * len(selected_genes) + 1.5))
    width = max(4.0, min(12.0, 0.42 * len(clusters) + 3.0))
    fig, ax = plt.subplots(figsize=(width, height))
    sns.heatmap(matrix, cmap="vlag", center=0, linewidths=0.2, linecolor="#eeeeee", cbar_kws={"label": "log2FC"}, ax=ax)
    ax.set_xlabel("Cluster")
    ax.set_ylabel("Marker gene")
    ax.set_title("Top marker log2FC by cluster")
    fig.subplots_adjust(left=0.24, right=0.92, top=0.92, bottom=0.08)
    return _save_figure(fig, figures_dir / "marker_log2fc_heatmap")


def _write_marker_dotplot(dataset_path: Path, cluster_key: str, figures_dir: Path, tables_dir: Path, marker_rows: list[dict[str, Any]], warnings: list[str]) -> list[Path]:
    if not marker_rows or not dataset_path.exists() or not cluster_key:
        return []
    try:
        import anndata as ad
        import matplotlib.pyplot as plt
        import pandas as pd
    except Exception:
        warnings.append("anndata, pandas, or matplotlib was unavailable; marker dotplot figure was skipped.")
        return []

    try:
        adata = ad.read_h5ad(dataset_path)
    except Exception:
        warnings.append("Input h5ad could not be read for marker dotplot generation.")
        return []
    if cluster_key not in adata.obs:
        warnings.append(f"cluster_key '{cluster_key}' was not found; marker dotplot generation was skipped.")
        return []

    var_names = {str(name): idx for idx, name in enumerate(adata.var_names)}
    genes = [gene for gene in _balanced_marker_genes(marker_rows, per_cluster=3, max_genes=28) if gene in var_names]
    if not genes:
        warnings.append("No marker genes were found in adata.var_names for marker dotplot generation.")
        return []

    clusters = sorted(map(str, adata.obs[cluster_key].astype(str).unique().tolist()))
    cluster_values = adata.obs[cluster_key].astype(str)
    rows = []
    for cluster in clusters:
        mask = (cluster_values == cluster).to_numpy()
        for gene in genes:
            vector = _gene_vector(adata, var_names[gene], mask)
            if vector is None:
                continue
            expressed = sum(1 for value in vector if value > 0)
            total = len(vector) or 1
            rows.append({"cluster_id": cluster, "gene": gene, "mean_expression": sum(vector) / total, "pct_expressed": expressed / total})
    if not rows:
        return []
    df = pd.DataFrame(rows)
    source_path = tables_dir / "marker_expression_dotplot.source.csv"
    df.to_csv(source_path, index=False)

    x_index = {gene: index for index, gene in enumerate(genes)}
    y_index = {cluster: index for index, cluster in enumerate(clusters)}
    fig_width = max(6.0, min(14.0, 0.34 * len(genes) + 3.2))
    fig_height = max(3.0, min(9.0, 0.32 * len(clusters) + 1.8))
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    scatter = ax.scatter(
        [x_index[str(row["gene"])] for _, row in df.iterrows()],
        [y_index[str(row["cluster_id"])] for _, row in df.iterrows()],
        s=[max(8.0, float(row["pct_expressed"]) * 180.0) for _, row in df.iterrows()],
        c=[float(row["mean_expression"]) for _, row in df.iterrows()],
        cmap="viridis",
        edgecolors="#333333",
        linewidths=0.25,
    )
    ax.set_xticks(list(x_index.values()))
    ax.set_xticklabels(genes, rotation=45, ha="right")
    ax.set_yticks(list(y_index.values()))
    ax.set_yticklabels(clusters)
    ax.set_xlabel("Marker gene")
    ax.set_ylabel("Cluster")
    ax.set_title("Marker expression dotplot")
    cbar = fig.colorbar(scatter, ax=ax)
    cbar.set_label("Mean expression")
    return _save_figure(fig, figures_dir / "marker_expression_dotplot")


def _balanced_marker_genes(marker_rows: list[dict[str, Any]], *, per_cluster: int, max_genes: int) -> list[str]:
    genes: list[str] = []
    clusters = sorted({str(row["cluster_id"]) for row in marker_rows})
    for cluster in clusters:
        n_added = 0
        cluster_rows = [row for row in marker_rows if str(row["cluster_id"]) == cluster]
        cluster_rows.sort(key=lambda row: int(row.get("rank") or 9999))
        for row in cluster_rows:
            gene = str(row.get("gene") or "")
            if gene and gene not in genes:
                genes.append(gene)
                n_added += 1
            if n_added >= per_cluster or len(genes) >= max_genes:
                break
        if len(genes) >= max_genes:
            break
    return genes


def _gene_vector(adata: Any, gene_index: int, mask: Any) -> list[float] | None:
    try:
        matrix = adata.raw.X if getattr(adata, "raw", None) is not None else adata.X
        if getattr(adata, "raw", None) is not None:
            raw_names = {str(name): idx for idx, name in enumerate(adata.raw.var_names)}
            gene_name = str(adata.var_names[gene_index])
            if gene_name in raw_names:
                gene_index = raw_names[gene_name]
        column = matrix[mask, gene_index]
        if hasattr(column, "toarray"):
            column = column.toarray()
        return [float(value) for value in list(column.ravel())]
    except Exception:
        return None


def _save_figure(fig: Any, stem: Path) -> list[Path]:
    paths = [stem.with_suffix(suffix) for suffix in (".svg", ".pdf", ".png")]
    for path in paths:
        fig.savefig(path)
    try:
        import matplotlib.pyplot as plt

        plt.close(fig)
    except Exception:
        pass
    return paths


def _callout_markdown(warnings: list[str], strength_rows: list[dict[str, Any]], signature_rows: list[dict[str, Any]]) -> str:
    lines = []
    if warnings:
        lines.extend(["::: {.callout-warning}", "Warnings detected:", ""])
        lines.extend(f"- {warning}" for warning in warnings[:5])
        lines.extend([":::", ""])
    if not signature_rows and strength_rows:
        lines.extend(
            [
                "::: {.callout-caution}",
                "No marker signature matches were found. Treat labels based only on differential markers as provisional.",
                ":::",
                "",
            ]
        )
    return "\n".join(lines)


def _signature_tabs_markdown(signature_rows: list[dict[str, Any]]) -> str:
    if not signature_rows:
        return "No marker signature matches were found.\n"

    clusters = sorted({str(row["cluster_id"]) for row in signature_rows})
    lines = ["::: {.panel-tabset}", ""]
    for cluster in clusters:
        rows = [row for row in signature_rows if str(row["cluster_id"]) == cluster]
        rows.sort(key=lambda row: int(row.get("rank") or 9999))
        lines.append(f"## Cluster {html.escape(cluster)}")
        lines.append("")
        lines.append(_signature_summary_table(rows[:10]))
        lines.append("")
        lines.append("<details class=\"signature-gene-details\">")
        lines.append("<summary>Show matched and missing genes</summary>")
        lines.append("")
        lines.append(_signature_gene_details(rows[:10]))
        lines.append("</details>")
        lines.append("")
    lines.append(":::")
    lines.append("")
    return "\n".join(lines)


def _marker_tabs_markdown(marker_rows: list[dict[str, Any]]) -> str:
    if not marker_rows:
        return "No differential markers were found.\n"

    clusters = sorted({str(row["cluster_id"]) for row in marker_rows})
    lines = ["::: {.panel-tabset}", ""]
    for cluster in clusters:
        rows = [row for row in marker_rows if str(row["cluster_id"]) == cluster]
        rows.sort(key=lambda row: int(row.get("rank") or 9999))
        lines.append(f"## Cluster {html.escape(cluster)}")
        lines.append("")
        lines.append(_marker_summary_table(rows[:50]))
        lines.append("")
    lines.append(":::")
    lines.append("")
    return "\n".join(lines)


def _marker_summary_table(rows: list[dict[str, Any]]) -> str:
    headers = ["Rank", "Gene", "Score", "log2FC", "Adjusted p-value", "Strength"]
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('rank', '')))}</td>"
            f"<td>{html.escape(str(row.get('gene', '')))}</td>"
            f"<td>{_format_decimal(row.get('score'))}</td>"
            f"<td>{_format_decimal(row.get('log2fc'))}</td>"
            f"<td>{_format_pvalue(row.get('pval_adj'))}</td>"
            f"<td>{html.escape(str(row.get('strength', '')))}</td>"
            "</tr>"
        )
    head_html = "".join(f"<th>{header}</th>" for header in headers)
    body_html = "".join(body)
    return f'<table class="scaudit-table cluster-marker-table"><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>'


def _signature_summary_table(rows: list[dict[str, Any]]) -> str:
    headers = ["Rank", "Label", "Matched", "Signature genes", "Coverage", "Overlap"]
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('rank', '')))}</td>"
            f"<td>{html.escape(str(row.get('label', '')))}</td>"
            f"<td>{html.escape(str(row.get('n_matched', '')))}</td>"
            f"<td>{html.escape(str(row.get('n_signature_genes', '')))}</td>"
            f"<td>{_format_fraction(row.get('coverage'))}</td>"
            f"<td>{_format_decimal(row.get('overlap_score'))}</td>"
            "</tr>"
        )
    head_html = "".join(f"<th>{header}</th>" for header in headers)
    body_html = "".join(body)
    return f'<table class="scaudit-table cluster-signature-table"><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>'


def _signature_gene_details(rows: list[dict[str, Any]]) -> str:
    items = []
    for row in rows:
        label = html.escape(str(row.get("label", "")))
        matched = html.escape(str(row.get("matched_genes", "") or "none"))
        missing = html.escape(str(row.get("missing_genes", "") or "none"))
        items.append(
            "<section class=\"signature-gene-block\">"
            f"<h4>{label}</h4>"
            f"<p><strong>Matched genes:</strong> {matched}</p>"
            f"<p><strong>Missing genes:</strong> {missing}</p>"
            "</section>"
        )
    return "\n".join(items)


def _format_fraction(value: Any) -> str:
    try:
        return f"{float(value):.0%}"
    except (TypeError, ValueError):
        return html.escape(str(value or ""))


def _format_decimal(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return html.escape(str(value or ""))


def _format_pvalue(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return html.escape(str(value or ""))
    if number != 0 and abs(number) < 0.01:
        return f"{number:.2e}"
    return f"{number:.2f}"


def _write_marker_qmd(qmd_path: Path, dataset_path: Path, cluster_key: str, provider_dir: Path, *, n_top_genes: int) -> None:
    source_dir = Path(__file__).resolve().parents[2]
    text = f"""---
title: "Marker-Based Evidence"
subtitle: "Differential markers, marker signatures, and expression visualization"
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
  provider_id: "marker_based"
  provider_version: "{MARKER_PROVIDER_VERSION}"
  evidence_layer: "Marker-based evidence"
  purpose: "Biological interpretability"
  standard_output: "marker_based.evidence.json"

params:
  input_h5ad: "{dataset_path}"
  cluster_key: "{cluster_key}"
  output_dir: "{provider_dir}"
  n_top_genes: {n_top_genes}
  de_method: "wilcoxon"
  use_raw: true
  min_log2fc: 0.5
  max_padj: 0.05
  strong_log2fc: 1.0
  strong_padj: 0.01
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

.scaudit-table th {{
  background: #f4f7fb;
  color: #18324a;
  font-weight: 700;
}}

.cluster-signature-table {{
  margin-bottom: 1.2rem;
}}

.cluster-marker-table {{
  margin-bottom: 1.2rem;
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
  border: 1px solid #e1e7ef;
  border-radius: 8px;
}}

.marker-signature-tabs {{
  min-width: 0;
}}

.signature-gene-details {{
  margin: 0.35rem 0 1.1rem;
  border: 1px solid #e1e7ef;
  border-radius: 8px;
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

Which clusters have biologically interpretable marker support?

{{{{< include callouts.md >}}}}

## Inputs and Parameters

| Field | Value |
| --- | --- |
| Input h5ad | `{dataset_path}` |
| Cluster key | `{cluster_key}` |
| Differential expression | `scanpy.tl.rank_genes_groups(method="wilcoxon")` |
| Marker filter | `padj < 0.05 and log2FC > 0.5` |
| Strong marker rule | `padj < 0.01 and log2FC > 1.0` |

## Reproducible Execution

```{{python}}
#| eval: false
from pathlib import Path
import sys

sys.path.insert(0, r"{source_dir}")
from scaudit.providers.marker_based import write_marker_provider_outputs

payload = write_marker_provider_outputs(
    Path(r"{dataset_path}"),
    r"{cluster_key}",
    Path(r"{provider_dir}"),
    n_top_genes={n_top_genes},
)
payload["results"]["summary"]
```

## Key Results

```{{python}}
import json
from pathlib import Path

payload = json.loads(Path("marker_based.evidence.json").read_text())
payload["results"]["summary"]
```

## Marker Strength Summary

```{{python}}
import pandas as pd
from IPython.display import HTML

strength = pd.read_csv("tables/marker_strength_summary.csv")
HTML(strength.to_html(index=False, classes="scaudit-table", border=0))
```

## Marker Signature Scoring

Signature scoring uses `scaudit.markers.MARKER_DB`. Coverage is the fraction of a known marker signature observed in the cluster marker set; overlap score is the Jaccard overlap between query markers and the signature genes.

::: {{.marker-signature-workspace}}
::: {{.marker-signature-umap}}
![Cluster UMAP](figures/cluster_umap.png)
:::

::: {{.marker-signature-tabs}}
{{{{< include cluster_signature_tabs.md >}}}}
:::
:::

Full matched and missing gene lists are available in `tables/marker_signatures.csv` and `marker_based.evidence.json`.

## Differential Marker Table

The table below shows up to 50 markers per cluster. Score and log2FC are rounded to 2 decimal places for readability; very small adjusted p-values use scientific notation. Full-precision values are available in `tables/differential_markers.csv` and `marker_based.evidence.json`.

{{{{< include cluster_marker_tabs.md >}}}}

## Publication Figures

![Marker expression dotplot](figures/marker_expression_dotplot.png)

![Top marker log2FC heatmap](figures/marker_log2fc_heatmap.png)

## Reproducibility

The machine-readable provider output is `marker_based.evidence.json`. Figure source tables are stored under `tables/`, and publication figure exports are stored under `figures/`.
"""
    qmd_path.write_text(text, encoding="utf-8")


def _write_fallback_html(path: Path, payload: dict[str, Any]) -> None:
    summary = payload.get("results", {}).get("summary", {})
    warnings = payload.get("warnings", [])
    warning_html = "".join(f"<li>{warning}</li>" for warning in warnings)
    path.write_text(
        f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Marker-Based Evidence</title></head>
<body>
<h1>Marker-Based Evidence</h1>
<p>This fallback report was written because Quarto was not available. The qmd, evidence JSON, tables, and figures are available in the same directory.</p>
<h2>Summary</h2>
<pre>{summary}</pre>
<h2>Warnings</h2>
<ul>{warning_html}</ul>
<h2>Artifacts</h2>
<ul>
<li><a href="marker_based.qmd">marker_based.qmd</a></li>
<li><a href="marker_based.evidence.json">marker_based.evidence.json</a></li>
<li><a href="tables/differential_markers.csv">differential_markers.csv</a></li>
<li><a href="tables/marker_signatures.csv">marker_signatures.csv</a></li>
</ul>
</body>
</html>
""",
        encoding="utf-8",
    )
