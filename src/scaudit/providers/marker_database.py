from __future__ import annotations

import csv
import hashlib
import html
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from scaudit import __version__
from scaudit.cache import CachedResource, ensure_cached_resource
from scaudit.data import ClusterEvidence, compute_cluster_evidence
from scaudit.providers.marker_based import _save_figure, _write_cluster_umap
from scaudit.providers.schema import package_versions, relative_to, render_qmd, utc_now, write_json


STATUS_FIELDS = ["provider_id", "status", "database_path", "cache_root", "database_sha256", "reason"]
MATCH_FIELDS = [
    "cluster_id",
    "rank",
    "label",
    "species",
    "tissue",
    "score",
    "confidence",
    "n_matched",
    "n_signature_genes",
    "coverage",
    "jaccard",
    "matched_genes",
    "missing_genes",
    "source",
]
METADATA_FIELDS = ["database_name", "publication", "source_url", "local_path", "sha256", "n_rows", "n_signatures"]
BEST_MATCH_FIELDS = [
    "cluster_id",
    "label",
    "score",
    "confidence",
    "n_matched",
    "n_signature_genes",
    "coverage",
    "jaccard",
    "matched_genes",
]
NORMALIZED_FIELDS = [
    "cluster_id",
    "provider_id",
    "provider_type",
    "rank",
    "label",
    "score",
    "score_name",
    "confidence_bucket",
    "n_matched",
    "n_signature_genes",
    "coverage",
    "jaccard",
    "matched_genes",
    "missing_genes",
    "evidence_role",
    "provenance",
    "warnings",
]


@dataclass(frozen=True)
class MarkerDatabaseSpec:
    provider_id: str
    provider_name: str
    provider_version: str
    title: str
    subtitle: str
    purpose: str
    database_name: str
    publication: str
    source_url: str
    result_file: str
    label_aliases: tuple[str, ...]
    gene_aliases: tuple[str, ...]
    cache_relative_path: str
    download_url: str = ""
    species_download_urls: dict[str, str] | None = None
    species_cache_relative_paths: dict[str, str] | None = None
    species_aliases: tuple[str, ...] = ("species", "organism")
    tissue_aliases: tuple[str, ...] = ("tissue", "organ", "organ system", "cancer type", "tissue type")


def render_marker_database_provider_report(
    spec: MarkerDatabaseSpec,
    dataset_path: Path,
    cluster_key: str,
    output_dir: Path,
    *,
    evidence: dict[str, ClusterEvidence] | None = None,
    database_path: Path | None = None,
    cache_root: Path | None = None,
    species: str = "",
    tissue: str = "",
    sample_key: str = "",
    batch_key: str = "",
) -> dict[str, Any]:
    provider_dir = output_dir / "evidence_reports" / spec.provider_id
    started_at = utc_now()
    payload = write_marker_database_provider_outputs(
        spec,
        dataset_path,
        cluster_key,
        provider_dir,
        evidence=evidence,
        database_path=database_path,
        cache_root=cache_root,
        species=species,
        tissue=tissue,
        sample_key=sample_key,
        batch_key=batch_key,
        started_at=started_at,
    )
    qmd_path = provider_dir / f"{spec.provider_id}.qmd"
    _write_database_qmd(qmd_path, spec, dataset_path, cluster_key, provider_dir, database_path=database_path, species=species, tissue=tissue)
    html_path, render_warning = render_qmd(qmd_path)
    if html_path is None:
        html_path = provider_dir / f"{spec.provider_id}.html"
        _write_fallback_html(html_path, spec, payload)
        payload.setdefault("warnings", []).append(render_warning or "Quarto render failed; wrote a fallback HTML provider report.")
        payload["run"]["status"] = "warning" if payload["run"]["status"] != "success" else "success"
    payload["artifacts"]["qmd"] = relative_to(qmd_path, output_dir)
    payload["artifacts"]["html"] = relative_to(html_path, output_dir)
    write_json(provider_dir / spec.result_file, payload)
    return provider_index_entry(spec, payload, output_dir)


def write_marker_database_provider_outputs(
    spec: MarkerDatabaseSpec,
    dataset_path: Path,
    cluster_key: str,
    output_dir: Path,
    *,
    evidence: dict[str, ClusterEvidence] | None = None,
    database_path: Path | None = None,
    cache_root: Path | None = None,
    species: str = "",
    tissue: str = "",
    sample_key: str = "",
    batch_key: str = "",
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
        evidence = compute_cluster_evidence(dataset_path, cluster_key, sample_key=sample_key, batch_key=batch_key)
    if not evidence:
        warnings.append(f"No cluster marker evidence was available; {spec.database_name} overlap could not be computed.")

    signatures: list[dict[str, Any]] = []
    db_rows = 0
    db_sha = ""
    resolved_database_path = database_path
    if resolved_database_path is None or not str(resolved_database_path):
        resolved_database_path = resolve_cached_database_path(spec, cache_root, species=species, warnings=warnings)
    if resolved_database_path is None or not str(resolved_database_path):
        warnings.append(f"{spec.database_name} database path is not configured and could not be cached; provider was skipped.")
    elif not resolved_database_path.exists():
        warnings.append(f"{spec.database_name} database file not found: {resolved_database_path}")
    else:
        db_sha = sha256(resolved_database_path)
        rows = read_marker_rows(resolved_database_path, warnings, spec.database_name)
        db_rows = len(rows)
        signatures = signature_rows(rows, spec=spec, species=species, tissue=tissue)
        if not signatures and tissue:
            signatures = signature_rows(rows, spec=spec, species=species, tissue="")
            if signatures:
                warnings.append(
                    f"No {spec.database_name} signatures matched tissue '{tissue}'; using species-only {spec.database_name} signatures."
                )
        if not signatures:
            warnings.append(f"No {spec.database_name} signatures matched the requested species/tissue filters.")

    match_rows = match_rows_from_signatures(evidence or {}, signatures, source=spec.database_name)
    best_rows = best_match_rows(match_rows)
    status = "success" if match_rows else "skipped" if warnings else "warning"
    reason = f"Computed {spec.database_name} database overlap." if match_rows else warnings[0] if warnings else f"No {spec.database_name} matches were produced."
    status_rows = [
        {
            "provider_id": spec.provider_id,
            "status": status,
            "database_path": str(database_path or ""),
            "cache_root": str(cache_root or ""),
            "database_sha256": db_sha,
            "reason": reason,
        }
    ]
    metadata_rows = [
        {
            "database_name": spec.database_name,
            "publication": spec.publication,
            "source_url": spec.source_url,
            "local_path": str(resolved_database_path or ""),
            "sha256": db_sha,
            "n_rows": db_rows,
            "n_signatures": len(signatures),
        }
    ]
    write_csv(tables_dir / "provider_status.csv", status_rows, STATUS_FIELDS)
    write_csv(tables_dir / "database_metadata.csv", metadata_rows, METADATA_FIELDS)
    write_csv(tables_dir / "database_matches.csv", match_rows, MATCH_FIELDS)
    write_csv(tables_dir / "best_database_matches.csv", best_rows, BEST_MATCH_FIELDS)
    write_csv(tables_dir / "cluster_label_evidence.csv", normalized_rows(match_rows, spec), NORMALIZED_FIELDS)
    figure_artifacts: list[Path] = []
    figure_artifacts.extend(_write_cluster_umap(dataset_path, cluster_key, figures_dir, tables_dir, warnings))
    figure_artifacts.extend(write_database_score_heatmap(figures_dir, tables_dir, match_rows, spec, warnings))
    (output_dir / "cluster_match_tabs.md").write_text(match_tabs_markdown(match_rows, spec), encoding="utf-8")
    (output_dir / "database_visuals.md").write_text(database_visuals_markdown(output_dir, figure_artifacts, match_rows, spec), encoding="utf-8")
    (output_dir / "callouts.md").write_text(callout_markdown(warnings, match_rows, spec), encoding="utf-8")

    payload = {
        "schema_version": "0.1.0",
        "provider": {
            "id": spec.provider_id,
            "name": spec.provider_name,
            "version": spec.provider_version,
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
            "database_path": str(resolved_database_path or ""),
            "cache_root": str(cache_root or ""),
            "database_sha256": db_sha,
        },
        "software": package_versions(["pandas", "numpy"]),
        "methods": [
            {
                "step": "Database input",
                "database": spec.database_name,
                "source_url": spec.source_url,
                "publication": spec.publication,
                "local_path": str(resolved_database_path or ""),
                "sha256": db_sha,
            },
            {"step": "Signature construction", "rule": "Group marker genes by species, tissue, and cell type after optional species/tissue filtering."},
            {
                "step": "Marker overlap scoring",
                "formula": f"coverage = matched {spec.database_name} genes / {spec.database_name} signature genes; jaccard = matched genes / union(query markers, database signature)",
            },
        ],
        "artifacts": {
            "qmd": f"{spec.provider_id}.qmd",
            "html": f"{spec.provider_id}.html",
            "figures": [relative_to(Path(item), output_dir) for item in figure_artifacts],
            "tables": [
                "tables/provider_status.csv",
                "tables/database_metadata.csv",
                "tables/database_matches.csv",
                "tables/best_database_matches.csv",
                "tables/cluster_label_evidence.csv",
                "tables/database_score_heatmap.source.csv",
            ],
        },
        "results": {
            "summary": summary(match_rows, signatures, spec),
            "clusters": cluster_results(match_rows),
            "database": metadata_rows[0],
        },
        "warnings": warnings,
        "scaudit_version": __version__,
    }
    write_json(output_dir / spec.result_file, payload)
    return payload


def resolve_cached_database_path(spec: MarkerDatabaseSpec, cache_root: Path | None, *, species: str, warnings: list[str]) -> Path | None:
    if cache_root is None:
        return None
    species_key = normalize_species(species)
    url = ""
    if spec.species_download_urls:
        url = spec.species_download_urls.get(species_key, "") or spec.species_download_urls.get("", "")
    if not url:
        url = spec.download_url
    relative_path = spec.cache_relative_path
    if spec.species_cache_relative_paths:
        relative_path = spec.species_cache_relative_paths.get(species_key, "") or spec.species_cache_relative_paths.get("", "") or relative_path
    if not relative_path:
        warnings.append(f"{spec.database_name} requires an explicit local database path.")
        return None
    resource = CachedResource(
        provider_id=spec.provider_id,
        name=spec.database_name,
        url=url,
        relative_path=relative_path,
    )
    return ensure_cached_resource(resource, cache_root, warnings)


def read_marker_rows(path: Path, warnings: list[str], database_name: str) -> list[dict[str, str]]:
    if path.suffix.lower() == ".xlsx":
        return read_xlsx_rows(path, warnings, database_name)
    delimiter = "\t" if path.suffix.lower() in {".tsv", ".txt", ".gz"} else ","
    rows: list[dict[str, str]] = []
    opener: Any
    if path.suffix.lower() == ".gz":
        import gzip

        opener = lambda p, encoding: gzip.open(p, mode="rt", newline="", encoding=encoding)
    else:
        opener = lambda p, encoding: p.open(newline="", encoding=encoding)
    try:
        with opener(path, "utf-8-sig") as handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            if not reader.fieldnames:
                warnings.append(f"{database_name} database file has no header: {path}")
                return []
            rows.extend({str(key or "").strip(): str(value or "").strip() for key, value in row.items()} for row in reader)
    except UnicodeDecodeError:
        with opener(path, "latin-1") as handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            rows.extend({str(key or "").strip(): str(value or "").strip() for key, value in row.items()} for row in reader)
    except Exception as exc:
        warnings.append(f"Could not read {database_name} database file: {exc}")
    return rows


def read_xlsx_rows(path: Path, warnings: list[str], database_name: str) -> list[dict[str, str]]:
    try:
        with zipfile.ZipFile(path) as archive:
            shared_strings = _xlsx_shared_strings(archive)
            sheet_name = _xlsx_first_sheet_path(archive)
            with archive.open(sheet_name) as handle:
                root = ET.parse(handle).getroot()
    except Exception as exc:
        warnings.append(f"Could not read {database_name} xlsx database file: {exc}")
        return []

    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    parsed_rows: list[list[str]] = []
    for row in root.findall(".//x:sheetData/x:row", ns):
        values_by_index: dict[int, str] = {}
        for cell in row.findall("x:c", ns):
            ref = str(cell.attrib.get("r", ""))
            index = _xlsx_column_index(ref)
            if index is None:
                continue
            values_by_index[index] = _xlsx_cell_value(cell, shared_strings, ns)
        if values_by_index:
            max_index = max(values_by_index)
            parsed_rows.append([values_by_index.get(index, "") for index in range(max_index + 1)])
    if not parsed_rows:
        warnings.append(f"{database_name} xlsx database file has no rows: {path}")
        return []
    headers = [str(item).strip() for item in parsed_rows[0]]
    rows = []
    for values in parsed_rows[1:]:
        row = {headers[index]: str(values[index]).strip() if index < len(values) else "" for index in range(len(headers)) if headers[index]}
        if any(row.values()):
            rows.append(row)
    return rows


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        with archive.open("xl/sharedStrings.xml") as handle:
            root = ET.parse(handle).getroot()
    except KeyError:
        return []
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings: list[str] = []
    for item in root.findall("x:si", ns):
        strings.append("".join(text.text or "" for text in item.findall(".//x:t", ns)))
    return strings


def _xlsx_first_sheet_path(archive: zipfile.ZipFile) -> str:
    workbook = ET.parse(archive.open("xl/workbook.xml")).getroot()
    ns = {
        "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    first_sheet = workbook.find(".//x:sheets/x:sheet", ns)
    if first_sheet is None:
        return "xl/worksheets/sheet1.xml"
    rel_id = first_sheet.attrib.get(f"{{{ns['r']}}}id")
    rels = ET.parse(archive.open("xl/_rels/workbook.xml.rels")).getroot()
    rel_ns = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
    for rel in rels.findall("rel:Relationship", rel_ns):
        if rel.attrib.get("Id") == rel_id:
            target = rel.attrib.get("Target", "worksheets/sheet1.xml")
            return "xl/" + target.lstrip("/")
    return "xl/worksheets/sheet1.xml"


def _xlsx_column_index(ref: str) -> int | None:
    match = re.match(r"([A-Z]+)", ref)
    if not match:
        return None
    index = 0
    for char in match.group(1):
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def _xlsx_cell_value(cell: ET.Element, shared_strings: list[str], ns: dict[str, str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//x:t", ns))
    value_node = cell.find("x:v", ns)
    if value_node is None or value_node.text is None:
        return ""
    value = value_node.text
    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except (IndexError, ValueError):
            return ""
    return value


def signature_rows(rows: list[dict[str, str]], *, spec: MarkerDatabaseSpec, species: str, tissue: str) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], set[str]] = {}
    species_filter = normalize_species(species)
    tissue_filter = norm(tissue)
    for row in rows:
        gene = value(row, spec.gene_aliases)
        label = value(row, spec.label_aliases)
        row_species = value(row, spec.species_aliases)
        row_tissue = value(row, spec.tissue_aliases)
        if not gene or not label:
            continue
        if species_filter and row_species and species_filter not in normalize_species(row_species):
            continue
        if tissue_filter and row_tissue and tissue_filter not in norm(row_tissue):
            continue
        key = (row_species or "unspecified", row_tissue or "unspecified", label)
        grouped.setdefault(key, set()).add(gene.upper())
    signatures = [
        {"species": key[0], "tissue": key[1], "label": key[2], "genes": sorted(genes)}
        for key, genes in grouped.items()
        if genes
    ]
    signatures.sort(key=lambda item: (str(item["species"]), str(item["tissue"]), str(item["label"])))
    return signatures


def match_rows_from_signatures(evidence: dict[str, ClusterEvidence], signatures: list[dict[str, Any]], *, source: str, top_n: int = 5) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cluster_id, ev in sorted(evidence.items(), key=lambda item: str(item[0])):
        query = {marker.gene.upper() for marker in ev.markers if marker.gene and is_informative(marker)}
        if not query:
            continue
        scored = []
        for signature in signatures:
            genes = set(signature["genes"])
            matched = sorted(query & genes)
            if not matched:
                continue
            missing = sorted(genes - query)
            coverage = len(matched) / len(genes) if genes else 0.0
            jaccard = len(matched) / len(query | genes)
            score = (coverage * 0.65) + (jaccard * 0.35)
            scored.append((score, coverage, jaccard, len(matched), signature, matched, missing))
        scored.sort(key=lambda item: (item[0], item[1], item[2], item[3]), reverse=True)
        for rank, (score, coverage, jaccard, n_matched, signature, matched, missing) in enumerate(scored[:top_n], start=1):
            rows.append(
                {
                    "cluster_id": str(cluster_id),
                    "rank": rank,
                    "label": signature["label"],
                    "species": signature["species"],
                    "tissue": signature["tissue"],
                    "score": f"{score:.3f}",
                    "confidence": confidence(score, n_matched),
                    "n_matched": n_matched,
                    "n_signature_genes": len(signature["genes"]),
                    "coverage": f"{coverage:.3f}",
                    "jaccard": f"{jaccard:.3f}",
                    "matched_genes": ", ".join(matched),
                    "missing_genes": ", ".join(missing[:20]),
                    "source": source,
                }
            )
    return rows


def normalized_rows(match_rows: list[dict[str, Any]], spec: MarkerDatabaseSpec) -> list[dict[str, Any]]:
    rows = []
    for row in match_rows:
        rows.append(
            {
                "cluster_id": row["cluster_id"],
                "provider_id": spec.provider_id,
                "provider_type": "marker_database",
                "rank": row["rank"],
                "label": row["label"],
                "score": row["score"],
                "score_name": f"{spec.provider_id}_overlap",
                "confidence_bucket": row["confidence"],
                "n_matched": row["n_matched"],
                "n_signature_genes": row["n_signature_genes"],
                "coverage": row["coverage"],
                "jaccard": row["jaccard"],
                "matched_genes": row["matched_genes"],
                "missing_genes": row["missing_genes"],
                "evidence_role": "supports" if row["confidence"] in {"high", "moderate"} else "weak_support",
                "provenance": row["source"],
                "warnings": "",
            }
        )
    return rows


def best_match_rows(match_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for row in match_rows:
        cluster_id = str(row.get("cluster_id", ""))
        if not cluster_id:
            continue
        current = best.get(cluster_id)
        if current is None or float(row.get("score") or 0) > float(current.get("score") or 0):
            best[cluster_id] = row
    rows: list[dict[str, Any]] = []
    for cluster_id in sorted(best):
        row = best[cluster_id]
        rows.append(
            {
                "cluster_id": cluster_id,
                "label": row.get("label", ""),
                "score": row.get("score", ""),
                "confidence": row.get("confidence", ""),
                "n_matched": row.get("n_matched", ""),
                "n_signature_genes": row.get("n_signature_genes", ""),
                "coverage": row.get("coverage", ""),
                "jaccard": row.get("jaccard", ""),
                "matched_genes": row.get("matched_genes", ""),
            }
        )
    return rows


def write_database_score_heatmap(
    figures_dir: Path,
    tables_dir: Path,
    match_rows: list[dict[str, Any]],
    spec: MarkerDatabaseSpec,
    warnings: list[str],
) -> list[Path]:
    if not match_rows:
        return []
    try:
        import matplotlib.pyplot as plt
        import pandas as pd
        import seaborn as sns
    except Exception:
        warnings.append("matplotlib, pandas, or seaborn was unavailable; database score heatmap figure was skipped.")
        return []

    clusters = sorted({str(row["cluster_id"]) for row in match_rows})
    labels = top_labels_for_heatmap(match_rows, max_labels=20)
    if not clusters or not labels:
        return []
    matrix = pd.DataFrame(0.0, index=labels, columns=clusters)
    for row in match_rows:
        label = str(row.get("label") or "")
        cluster = str(row.get("cluster_id") or "")
        if label in matrix.index and cluster in matrix.columns:
            matrix.loc[label, cluster] = max(matrix.loc[label, cluster], float(row.get("score") or 0.0))
    matrix.to_csv(tables_dir / "database_score_heatmap.source.csv")

    height = max(3.0, min(10.0, 0.26 * len(labels) + 1.5))
    width = max(4.0, min(12.0, 0.42 * len(clusters) + 3.0))
    fig, ax = plt.subplots(figsize=(width, height))
    sns.heatmap(matrix, cmap="viridis", vmin=0, linewidths=0.2, linecolor="#eeeeee", cbar_kws={"label": f"{spec.database_name} overlap score"}, ax=ax)
    ax.set_xlabel("Cluster")
    ax.set_ylabel("Database label")
    ax.set_title(f"{spec.database_name} top label scores")
    fig.subplots_adjust(left=0.28, right=0.92, top=0.9, bottom=0.12)
    return _save_figure(fig, figures_dir / "database_score_heatmap")


def top_labels_for_heatmap(match_rows: list[dict[str, Any]], *, max_labels: int) -> list[str]:
    best_by_label: dict[str, float] = {}
    for row in match_rows:
        label = str(row.get("label") or "")
        if not label:
            continue
        best_by_label[label] = max(best_by_label.get(label, 0.0), float(row.get("score") or 0.0))
    return [label for label, _score in sorted(best_by_label.items(), key=lambda item: (item[1], item[0]), reverse=True)[:max_labels]]


def database_visuals_markdown(output_dir: Path, figure_artifacts: list[Path], match_rows: list[dict[str, Any]], spec: MarkerDatabaseSpec) -> str:
    available = {Path(path).name for path in figure_artifacts}
    lines: list[str] = []
    if "cluster_umap.png" in available:
        lines.extend(
            [
                "::: {.database-score-workspace}",
                "::: {.database-score-umap}",
                "![Cluster UMAP](figures/cluster_umap.png)",
                ":::",
                "",
                "::: {.database-score-tabs}",
                "{{< include cluster_match_tabs.md >}}",
                ":::",
                ":::",
                "",
            ]
        )
    else:
        lines.extend(["{{< include cluster_match_tabs.md >}}", ""])
    if "database_score_heatmap.png" in available:
        lines.extend(
            [
                "## Score Heatmap",
                "",
                f"The heatmap shows the maximum {spec.database_name} overlap score for each displayed label and cluster.",
                "",
                "![Database score heatmap](figures/database_score_heatmap.png)",
                "",
            ]
        )
    return "\n".join(lines)


def provider_index_entry(spec: MarkerDatabaseSpec, payload: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    artifacts = payload.get("artifacts", {})
    return {
        "id": spec.provider_id,
        "name": payload.get("provider", {}).get("name", spec.provider_name),
        "purpose": payload.get("provider", {}).get("purpose", spec.purpose),
        "status": payload.get("run", {}).get("status", "unknown"),
        "top_finding": payload.get("results", {}).get("summary", {}).get("top_finding", ""),
        "html": artifacts.get("html", f"evidence_reports/{spec.provider_id}/{spec.provider_id}.html"),
        "json": relative_to(output_dir / "evidence_reports" / spec.provider_id / spec.result_file, output_dir),
        "warnings": payload.get("warnings", []),
    }


def summary(match_rows: list[dict[str, Any]], signatures: list[dict[str, Any]], spec: MarkerDatabaseSpec) -> dict[str, Any]:
    clusters = {str(row["cluster_id"]) for row in match_rows}
    best = max(match_rows, key=lambda row: float(row["score"] or 0), default=None)
    if best:
        top_finding = f"{spec.database_name} supports labels for {len(clusters)} clusters; best match Cluster {best['cluster_id']}:{best['label']} (score {float(best['score']):.2f})."
    else:
        top_finding = f"No {spec.database_name} database matches available."
    return {
        "n_signatures": len(signatures),
        "n_clusters_with_matches": len(clusters),
        "n_matches": len(match_rows),
        "top_finding": top_finding,
    }


def cluster_results(match_rows: list[dict[str, Any]]) -> dict[str, Any]:
    clusters: dict[str, Any] = {}
    for row in match_rows:
        clusters.setdefault(str(row["cluster_id"]), {"matches": []})
        clusters[str(row["cluster_id"])]["matches"].append(dict(row))
    return clusters


def callout_markdown(warnings: list[str], match_rows: list[dict[str, Any]], spec: MarkerDatabaseSpec) -> str:
    lines = [
        "::: {.callout-note}",
        f"This report evaluates curated {spec.database_name} database overlap only. It does not execute or simulate an annotation tool.",
        ":::",
        "",
    ]
    if warnings:
        lines.extend(["::: {.callout-warning}", "Warnings detected:", ""])
        lines.extend(f"- {warning}" for warning in warnings)
        lines.extend([":::", ""])
    if match_rows:
        high = sum(1 for row in match_rows if row.get("rank") == 1 and row.get("confidence") == "high")
        lines.extend(["::: {.callout-important}", f"{high} clusters have high-confidence top {spec.database_name} database support.", ":::", ""])
    return "\n".join(lines)


def match_tabs_markdown(match_rows: list[dict[str, Any]], spec: MarkerDatabaseSpec) -> str:
    if not match_rows:
        return f"No {spec.database_name} database matches are available. Check provider warnings and database configuration.\n"
    clusters = sorted({str(row["cluster_id"]) for row in match_rows})
    lines = ["::: {.panel-tabset}", ""]
    for cluster in clusters:
        rows = [row for row in match_rows if str(row["cluster_id"]) == cluster]
        rows.sort(key=lambda row: int(row.get("rank") or 9999))
        lines.append(f"## Cluster {html.escape(cluster)}")
        lines.append("")
        lines.append(match_table(rows))
        lines.append("")
        lines.append("<details class=\"match-gene-details\">")
        lines.append("<summary>Show matched and missing genes</summary>")
        lines.append("")
        lines.append(match_gene_details(rows))
        lines.append("</details>")
        lines.append("")
    lines.extend([":::", ""])
    return "\n".join(lines)


def match_table(rows: list[dict[str, Any]]) -> str:
    headers = ["Rank", "Label", "Score", "Confidence", "Matched", "Coverage", "Jaccard", "Genes"]
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('rank', '')))}</td>"
            f"<td>{html.escape(str(row.get('label', '')))}</td>"
            f"<td>{format_decimal(row.get('score'))}</td>"
            f"<td>{html.escape(str(row.get('confidence', '')))}</td>"
            f"<td>{html.escape(str(row.get('n_matched', '')))}</td>"
            f"<td>{format_fraction(row.get('coverage'))}</td>"
            f"<td>{format_decimal(row.get('jaccard'))}</td>"
            f"<td>{html.escape(str(row.get('matched_genes', '')))}</td>"
            "</tr>"
        )
    return f"<table class=\"scaudit-table database-match-table\"><thead><tr>{''.join(f'<th>{header}</th>' for header in headers)}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def match_gene_details(rows: list[dict[str, Any]]) -> str:
    items = []
    for row in rows:
        label = html.escape(str(row.get("label", "")))
        matched = html.escape(str(row.get("matched_genes", "") or "none"))
        missing = html.escape(str(row.get("missing_genes", "") or "none"))
        items.append(
            "<section class=\"match-gene-block\">"
            f"<h4>{label}</h4>"
            f"<p><strong>Matched genes:</strong> {matched}</p>"
            f"<p><strong>Missing database genes:</strong> {missing}</p>"
            "</section>"
        )
    return "\n".join(items)


def _write_database_qmd(
    qmd_path: Path,
    spec: MarkerDatabaseSpec,
    dataset_path: Path,
    cluster_key: str,
    provider_dir: Path,
    *,
    database_path: Path | None,
    species: str,
    tissue: str,
) -> None:
    qmd_path.write_text(
        f"""---
title: "{spec.title}"
subtitle: "{spec.subtitle}"
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
jupyter: python3

scaudit:
  provider_id: "{spec.provider_id}"
  provider_version: "{spec.provider_version}"
  evidence_layer: "{spec.provider_name}"
  purpose: "{spec.purpose}"
  standard_output: "{spec.result_file}"

params:
  input_h5ad: "{dataset_path}"
  cluster_key: "{cluster_key}"
  output_dir: "{provider_dir}"
  database_path: "{database_path or ''}"
  species: "{species}"
  tissue: "{tissue}"
---

<style>
details.code-fold > summary {{
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border: 0;
  border-radius: 6px;
  padding: 0.25rem 0.65rem;
  margin: 0.35rem 0;
  background: #f4f7fb;
  color: #18324a;
  font-size: 0.86rem;
  font-weight: 600;
  cursor: pointer;
}}

pre,
div.sourceCode {{
  border: 0 !important;
  box-shadow: none !important;
}}

details.code-fold[open] > summary {{
  background: #e8eef8;
}}

.scaudit-table {{
  border-collapse: collapse;
  border: 0;
  border-color: transparent;
  width: 100%;
  font-size: 0.92rem;
}}

.table,
.dataframe,
table {{
  --bs-table-border-color: transparent;
  --bs-table-striped-bg: transparent;
  --bs-table-bg: transparent;
  --bs-border-color: transparent;
  border: 0 !important;
  border-width: 0 !important;
  border-color: transparent !important;
  box-shadow: none !important;
}}

.table > :not(caption) > * > *,
.dataframe > :not(caption) > * > *,
table > :not(caption) > * > *,
table th,
table td,
thead,
tbody,
tr {{
  border: 0 !important;
  border-width: 0 !important;
  border-color: transparent !important;
  box-shadow: none !important;
}}

.table *,
.dataframe *,
table * {{
  border: 0 !important;
  border-width: 0 !important;
  border-color: transparent !important;
  box-shadow: none !important;
}}

.table-striped > tbody > tr:nth-of-type(odd) > * {{
  --bs-table-accent-bg: transparent;
}}

.scaudit-table th,
.scaudit-table td {{
  border: 0;
  padding: 0.35rem 0.45rem;
  vertical-align: top;
}}

.scaudit-table tbody tr:last-child td {{
  border-bottom: 0 !important;
}}

.scaudit-table th {{
  background: #f4f7fb;
  color: #18324a;
  font-weight: 700;
}}

figure,
.figure,
.quarto-figure,
.cell-output-display,
.scaudit-table {{
  border: 0 !important;
  box-shadow: none !important;
}}

figure img,
.quarto-figure img,
.cell-output-display img {{
  border: 0 !important;
  box-shadow: none !important;
}}

.database-score-workspace {{
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}}

.database-score-umap img {{
  width: 100%;
  height: auto;
}}

.database-score-tabs {{
  min-width: 0;
}}

.panel-tabset .tab-content,
.panel-tabset,
.panel-tabset .tab-pane,
.panel-tabset .nav-tabs,
.panel-tabset .nav-item,
.panel-tabset .nav-tabs .nav-link,
.panel-tabset .nav-tabs .nav-link.active {{
  border: 0 !important;
  border-width: 0 !important;
  border-color: transparent !important;
  border-bottom: 0 !important;
  box-shadow: none !important;
}}

.match-gene-details {{
  margin: 0.35rem 0 1.1rem;
  padding: 0.55rem 0.7rem;
  background: #fbfcff;
}}

.match-gene-details summary {{
  color: #18324a;
  cursor: pointer;
  font-weight: 650;
}}

.match-gene-block {{
  border: 0;
  margin-top: 0.65rem;
  padding-top: 0.55rem;
}}

.match-gene-block h4 {{
  margin: 0 0 0.25rem;
  font-size: 0.95rem;
}}

.match-gene-block p {{
  margin: 0.2rem 0;
  overflow-wrap: anywhere;
}}

@media (max-width: 840px) {{
  .database-score-workspace {{
    grid-template-columns: minmax(0, 1fr);
  }}
}}
</style>

## Question

Which cluster labels are supported by curated {spec.database_name} marker genes?

{{{{< include callouts.md >}}}}

## Inputs and Parameters

| Field | Value |
| --- | --- |
| Input h5ad | `{dataset_path}` |
| Cluster key | `{cluster_key}` |
| Database table | `{database_path or ''}` |
| Species filter | `{species}` |
| Tissue filter | `{tissue}` |
| Source | `{spec.source_url}` |

## Reproducible Execution

```{{python}}
#| eval: false
from pathlib import Path
from scaudit.providers.{spec.provider_id} import write_{spec.provider_id}_provider_outputs

payload = write_{spec.provider_id}_provider_outputs(
    Path(r"{dataset_path}"),
    r"{cluster_key}",
    Path(r"{provider_dir}"),
    database_path=Path(r"{database_path}") if r"{database_path or ''}" else None,
    species=r"{species}",
    tissue=r"{tissue}",
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

## Best Match Summary

Each cluster is summarized by its top {spec.database_name} label under the current overlap scorer. These scores are marker-overlap evidence, not model probabilities.

```{{python}}
import pandas as pd
from IPython.display import HTML

best = pd.read_csv("tables/best_database_matches.csv")
HTML(best.to_html(index=False, classes="scaudit-table", border=0))
```

## {spec.database_name} Match Scoring

Overlap scoring compares the query cluster marker set with each curated {spec.database_name} signature.

- `coverage` = matched database genes / database signature genes
- `jaccard` = matched genes / union(query markers, database signature genes)
- `score` = `0.65 * coverage + 0.35 * jaccard`
- `confidence` is a coarse bucket derived from score and matched-gene count

{{{{< include database_visuals.md >}}}}

## Output Artifacts

- `{spec.result_file}`
- `tables/database_matches.csv`
- `tables/best_database_matches.csv`
- `tables/cluster_label_evidence.csv`
- `tables/database_metadata.csv`
- `tables/database_score_heatmap.source.csv`
""",
        encoding="utf-8",
    )


def _write_fallback_html(path: Path, spec: MarkerDatabaseSpec, payload: dict[str, Any]) -> None:
    summary_payload = payload.get("results", {}).get("summary", {})
    warnings = payload.get("warnings", [])
    warning_html = "".join(f"<li>{html.escape(str(warning))}</li>" for warning in warnings)
    path.write_text(
        f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{html.escape(spec.title)}</title></head>
<body>
<h1>{html.escape(spec.title)}</h1>
<p>{html.escape(str(summary_payload.get("top_finding", "")))}</p>
<h2>Warnings</h2><ul>{warning_html}</ul>
<p>Machine-readable output: <a href="{html.escape(spec.result_file)}">{html.escape(spec.result_file)}</a></p>
</body></html>
""",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def value(row: dict[str, str], candidates: tuple[str, ...]) -> str:
    lowered = {norm(key): item for key, item in row.items()}
    for candidate in candidates:
        item = lowered.get(norm(candidate))
        if item:
            return item
    return ""


def norm(value: str) -> str:
    return str(value or "").strip().lower().replace("_", " ")


def normalize_species(value: str) -> str:
    text = norm(value)
    if text in {"human", "homo sapiens", "hs"}:
        return "hs"
    if text in {"mouse", "mus musculus", "mm"}:
        return "mm"
    return text


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_informative(marker: Any) -> bool:
    try:
        return float(marker.pval_adj) < 0.05 and float(marker.log2fc) > 0.5
    except (TypeError, ValueError):
        return bool(getattr(marker, "gene", ""))


def confidence(score: float, n_matched: int) -> str:
    if score >= 0.5 and n_matched >= 3:
        return "high"
    if score >= 0.25 and n_matched >= 2:
        return "moderate"
    return "low"


def format_decimal(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return html.escape(str(value or ""))


def format_fraction(value: Any) -> str:
    try:
        return f"{float(value):.0%}"
    except (TypeError, ValueError):
        return html.escape(str(value or ""))
