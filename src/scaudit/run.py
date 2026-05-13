from __future__ import annotations

import csv
import json
import platform
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scaudit import __version__
from scaudit.cache import cache_root_from_config
from scaudit.config import load_config, write_default_config
from scaudit.data import ClusterEvidence, compute_cluster_evidence, diagnose_dataset
from scaudit.markers import write_marker_evidence_csv
from scaudit.providers import (
    render_cellmarker_provider_report,
    render_marker_provider_report,
    render_panglaodb_provider_report,
    render_user_markers_provider_report,
)
from scaudit.providers.schema import write_json
from scaudit.report import render_draft_report, render_final_report


@dataclass(frozen=True)
class RunOutputs:
    output_dir: Path
    resolved_config: Path
    diagnosis: Path
    marker_evidence: Path
    annotation_cards: Path
    annotation_summary: Path
    review_table: Path
    reproducibility: Path
    report_index: Path


@dataclass(frozen=True)
class FinalOutputs:
    output_dir: Path
    annotation_cards: Path
    annotation_summary: Path
    review_audit: Path
    reproducibility: Path
    report_index: Path
    annotated_h5ad: Path | None = None


def annotate_direct(
    dataset_path: Path,
    cluster_key: str,
    output_dir: Path,
    species: str = "",
    tissue: str = "",
    sample_key: str = "",
    llm: bool = True,
) -> RunOutputs:
    """Run a full annotation audit without requiring a config file.

    Creates a minimal in-memory config, then delegates to the standard
    prepare_run pipeline.  The generated config.resolved.toml is written
    to output_dir so runs are reproducible.
    """
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    write_default_config(str(dataset_path), tmp_path)

    # Patch cluster_key and output dir into the written TOML
    text = tmp_path.read_text(encoding="utf-8")
    text = text.replace('cluster_key = ""', f'cluster_key = "{cluster_key}"')
    if sample_key:
        text = text.replace('sample_key = ""', f'sample_key = "{sample_key}"')
    text = text.replace('dir = "results"', f'dir = "{output_dir}"')
    if species:
        text = text.replace('species = ""', f'species = "{species}"')
    if tissue:
        text = text.replace('tissue = ""', f'tissue = "{tissue}"')
    if llm:
        text = text.replace("enabled = false", "enabled = true", 1)
    tmp_path.write_text(text, encoding="utf-8")

    try:
        outputs = prepare_run(tmp_path, llm=llm)
    finally:
        tmp_path.unlink(missing_ok=True)
    return outputs


def prepare_run(config_path: Path, *, llm: bool = True) -> RunOutputs:
    config = load_config(config_path)
    output_dir = Path(str(config.get("output", {}).get("dir", "results")))
    report_dir = output_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)

    outputs = RunOutputs(
        output_dir=output_dir,
        resolved_config=output_dir / "config.resolved.toml",
        diagnosis=output_dir / "diagnosis.json",
        marker_evidence=output_dir / "marker_evidence.csv",
        annotation_cards=output_dir / "annotation_cards.json",
        annotation_summary=output_dir / "annotation_summary.csv",
        review_table=output_dir / "review_table.csv",
        reproducibility=output_dir / "reproducibility.json",
        report_index=report_dir / "report.html",
    )

    shutil.copyfile(config_path, outputs.resolved_config)
    dataset = config.get("dataset", {})
    dataset_path = Path(str(dataset.get("path", "")))
    cluster_key = str(dataset.get("cluster_key", ""))
    sample_key = str(dataset.get("sample_key", ""))
    batch_key = str(dataset.get("batch_key", ""))
    species = str(dataset.get("species", ""))
    tissue = str(dataset.get("tissue", ""))
    cache_root = cache_root_from_config(config)
    marker_databases = config.get("marker_databases", {})
    cellmarker_config = marker_databases.get("cellmarker", {}) if isinstance(marker_databases, dict) else {}
    cellmarker_path = _optional_path(cellmarker_config.get("path", "")) if isinstance(cellmarker_config, dict) else None
    panglaodb_config = marker_databases.get("panglaodb", {}) if isinstance(marker_databases, dict) else {}
    panglaodb_path = _optional_path(panglaodb_config.get("path", "")) if isinstance(panglaodb_config, dict) else None
    user_markers_config = marker_databases.get("user_markers", {}) if isinstance(marker_databases, dict) else {}
    user_markers_path = _optional_path(user_markers_config.get("path", "")) if isinstance(user_markers_config, dict) else None

    diagnosis = diagnose_dataset(dataset_path, cluster_key=cluster_key, sample_key=sample_key)
    diagnosis_payload = diagnosis.to_dict()

    evidence = compute_cluster_evidence(
        dataset_path,
        cluster_key=cluster_key,
        sample_key=sample_key,
        batch_key=batch_key,
    )

    annotation_cards = build_annotation_cards(diagnosis_payload, evidence)

    llm_config = config.get("llm", {})
    llm_enabled = isinstance(llm_config, dict) and llm_config.get("enabled") is True
    if llm and llm_enabled:
        try:
            from scaudit.llm import enrich_cards_with_llm
            enrich_cards_with_llm(annotation_cards, **_llm_settings(config))
        except Exception:  # pragma: no cover
            pass

    _write_json(outputs.diagnosis, diagnosis_payload)
    write_marker_evidence_csv(outputs.marker_evidence, _marker_rows_from_evidence(evidence))
    _write_json(outputs.annotation_cards, annotation_cards)
    _write_annotation_summary(outputs.annotation_summary, annotation_cards)
    _write_review_table(outputs.review_table, annotation_cards)
    _write_json(outputs.reproducibility, _reproducibility_payload(config))
    provider_reports = [
        render_marker_provider_report(
            dataset_path,
            cluster_key,
            output_dir,
            evidence=evidence,
            sample_key=sample_key,
            batch_key=batch_key,
        )
    ]
    if _cellmarker_enabled(config):
        provider_reports.append(
            render_cellmarker_provider_report(
                dataset_path,
                cluster_key,
                output_dir,
                evidence=evidence,
                database_path=cellmarker_path,
                cache_root=cache_root,
                species=species,
                tissue=tissue,
                sample_key=sample_key,
                batch_key=batch_key,
            )
        )
    if _marker_database_enabled(config, "panglaodb"):
        provider_reports.append(
            render_panglaodb_provider_report(
                dataset_path,
                cluster_key,
                output_dir,
                evidence=evidence,
                database_path=panglaodb_path,
                cache_root=cache_root,
                species=species,
                tissue=tissue,
                sample_key=sample_key,
                batch_key=batch_key,
            )
        )
    if _marker_database_enabled(config, "user_markers"):
        provider_reports.append(
            render_user_markers_provider_report(
                dataset_path,
                cluster_key,
                output_dir,
                evidence=evidence,
                database_path=user_markers_path,
                cache_root=cache_root,
                species=species,
                tissue=tissue,
                sample_key=sample_key,
                batch_key=batch_key,
            )
        )
    provider_index_path = output_dir / "evidence_reports" / "provider_reports.json"
    cross_provider_summary = _write_cross_provider_summary(output_dir, evidence)
    write_json(provider_index_path, {"providers": provider_reports, "cross_provider_summary": cross_provider_summary})
    render_draft_report(report_dir, outputs.diagnosis, outputs.annotation_cards, provider_index_path=provider_index_path)
    return outputs


def _write_cross_provider_summary(output_dir: Path, evidence: dict[str, ClusterEvidence]) -> dict[str, Any]:
    evidence_dir = output_dir / "evidence_reports"
    rows = _cross_provider_rows(evidence_dir, evidence)
    csv_path = evidence_dir / "cross_provider_summary.csv"
    fieldnames = [
        "cluster_id",
        "marker_based_label",
        "marker_based_score",
        "cellmarker_label",
        "cellmarker_score",
        "cellmarker_confidence",
        "panglaodb_label",
        "panglaodb_score",
        "panglaodb_confidence",
        "user_markers_label",
        "user_markers_score",
        "user_markers_confidence",
        "agreement",
        "action",
    ]
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    json_path = evidence_dir / "cross_provider_summary.json"
    payload = {
        "path": "evidence_reports/cross_provider_summary.csv",
        "json": "evidence_reports/cross_provider_summary.json",
        "rows": rows,
    }
    write_json(json_path, payload)
    return payload


def _cross_provider_rows(evidence_dir: Path, evidence: dict[str, ClusterEvidence]) -> list[dict[str, Any]]:
    marker = _top_by_cluster(evidence_dir / "marker_based" / "tables" / "marker_signatures.csv", score_field="overlap_score")
    cellmarker = _top_by_cluster(evidence_dir / "cellmarker" / "tables" / "best_database_matches.csv", score_field="score")
    panglaodb = _top_by_cluster(evidence_dir / "panglaodb" / "tables" / "best_database_matches.csv", score_field="score")
    user_markers = _top_by_cluster(evidence_dir / "user_markers" / "tables" / "best_database_matches.csv", score_field="score")
    cluster_ids = sorted(
        {str(cluster_id) for cluster_id in evidence} | set(marker) | set(cellmarker) | set(panglaodb) | set(user_markers),
        key=_cluster_sort_key,
    )
    rows: list[dict[str, Any]] = []
    for cluster_id in cluster_ids:
        labels = [
            marker.get(cluster_id, {}).get("label", ""),
            cellmarker.get(cluster_id, {}).get("label", ""),
            panglaodb.get(cluster_id, {}).get("label", ""),
            user_markers.get(cluster_id, {}).get("label", ""),
        ]
        agreement = _agreement(labels)
        rows.append(
            {
                "cluster_id": cluster_id,
                "marker_based_label": marker.get(cluster_id, {}).get("label", ""),
                "marker_based_score": marker.get(cluster_id, {}).get("score", ""),
                "cellmarker_label": cellmarker.get(cluster_id, {}).get("label", ""),
                "cellmarker_score": cellmarker.get(cluster_id, {}).get("score", ""),
                "cellmarker_confidence": cellmarker.get(cluster_id, {}).get("confidence", ""),
                "panglaodb_label": panglaodb.get(cluster_id, {}).get("label", ""),
                "panglaodb_score": panglaodb.get(cluster_id, {}).get("score", ""),
                "panglaodb_confidence": panglaodb.get(cluster_id, {}).get("confidence", ""),
                "user_markers_label": user_markers.get(cluster_id, {}).get("label", ""),
                "user_markers_score": user_markers.get(cluster_id, {}).get("score", ""),
                "user_markers_confidence": user_markers.get(cluster_id, {}).get("confidence", ""),
                "agreement": agreement,
                "action": _agreement_action(agreement),
            }
        )
    return rows


def _top_by_cluster(path: Path, *, score_field: str) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    rows: dict[str, dict[str, str]] = {}
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                cluster_id = str(row.get("cluster_id", ""))
                if not cluster_id:
                    continue
                current = rows.get(cluster_id)
                score = _float(row.get(score_field))
                if current is None or score > _float(current.get("score")):
                    rows[cluster_id] = {
                        "label": str(row.get("label", "")),
                        "score": str(row.get(score_field, "")),
                        "confidence": str(row.get("confidence", "")),
                    }
    except Exception:
        return {}
    return rows


def _agreement(labels: list[str]) -> str:
    present = [_canonical_label(label) for label in labels if label]
    informative = [label for label in present if label and label not in {"normal cell", "cancer cell"}]
    if len(informative) < 2:
        return "insufficient"
    if len(set(informative)) == 1:
        return "high"
    broad_groups = {_broad_label_group(label) for label in informative}
    if len(broad_groups) == 1:
        return "lineage"
    return "mixed"


def _agreement_action(agreement: str) -> str:
    if agreement == "high":
        return "Accept if marker evidence is biologically plausible"
    if agreement == "lineage":
        return "Review subtype granularity"
    if agreement == "mixed":
        return "Review provider conflicts"
    return "Review; database support is weak or missing"


def _canonical_label(label: str) -> str:
    text = str(label or "").lower().replace("+", " positive ")
    for char in "-_/(),":
        text = text.replace(char, " ")
    words = [word[:-1] if word.endswith("s") and len(word) > 3 else word for word in text.split()]
    return " ".join(words)


def _broad_label_group(label: str) -> str:
    text = _canonical_label(label)
    if "platelet" in text or "megakaryocyte" in text:
        return "platelet"
    if "monocyte" in text or "macrophage" in text or "dendritic" in text:
        return "myeloid"
    if " t cell" in f" {text}" or text.startswith("t cell") or "nk cell" in text:
        return "t_nk"
    if "b cell" in text or "plasma" in text:
        return "b_cell"
    if "erythroid" in text:
        return "erythroid"
    return text


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _cluster_sort_key(value: Any) -> tuple[int, Any]:
    text = str(value)
    try:
        return (0, int(text))
    except ValueError:
        return (1, text)


def _cellmarker_enabled(config: dict[str, Any]) -> bool:
    return _marker_database_enabled(config, "cellmarker")


def _marker_database_enabled(config: dict[str, Any], provider_id: str) -> bool:
    methods = config.get("methods", {})
    marker_databases = methods.get("marker_databases", {}) if isinstance(methods, dict) else {}
    if not isinstance(marker_databases, dict):
        return False
    return marker_databases.get(provider_id) is True


def _optional_path(value: Any) -> Path | None:
    text = str(value or "").strip()
    return Path(text) if text else None


def finalize_run(run_dir: Path, output_dir: Path, *, write_h5ad: bool = False) -> FinalOutputs:
    if not run_dir.exists():
        raise FileNotFoundError(f"run directory not found: {run_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir = output_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)

    outputs = FinalOutputs(
        output_dir=output_dir,
        annotation_cards=output_dir / "final_annotation_cards.json",
        annotation_summary=output_dir / "final_annotation_summary.csv",
        review_audit=output_dir / "review_audit.json",
        reproducibility=output_dir / "reproducibility.json",
        report_index=report_dir / "report.html",
        annotated_h5ad=(output_dir / "annotated.h5ad") if write_h5ad else None,
    )

    cards = _read_json(run_dir / "annotation_cards.json", [])
    review_rows = _read_review_rows(run_dir / "reviewed_review_table.csv")
    final_cards = _finalize_annotation_cards(cards, review_rows)
    _write_json(outputs.annotation_cards, final_cards)
    _write_annotation_summary(outputs.annotation_summary, final_cards)
    _copy_or_default(run_dir / "reproducibility.json", outputs.reproducibility, "{}\n")
    _copy_or_default(
        run_dir / "review_audit.json",
        outputs.review_audit,
        json.dumps(
            {
                "run_dir": str(run_dir),
                "status": "not_imported",
                "warnings": ["No imported review table was found; draft labels were finalized as-is."],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    if write_h5ad and outputs.annotated_h5ad is not None:
        reproducibility = _read_json(outputs.reproducibility, {})
        _write_annotated_h5ad(outputs.annotated_h5ad, final_cards, reproducibility)
    render_final_report(report_dir)
    return outputs


def _copy_or_default(source: Path, destination: Path, default_text: str) -> None:
    if source.exists():
        shutil.copyfile(source, destination)
    else:
        destination.write_text(default_text, encoding="utf-8")


def _read_review_rows(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return {str(row.get("cluster_id", "")).strip(): dict(row) for row in reader if str(row.get("cluster_id", "")).strip()}


def _finalize_annotation_cards(cards: list[dict[str, Any]], review_rows: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    final_cards: list[dict[str, Any]] = []
    for card in cards:
        updated = json.loads(json.dumps(card))
        cluster_id = str(updated.get("cluster_id", ""))
        row = review_rows.get(cluster_id, {})
        review_status = str(row.get("review_status") or "not_reviewed").strip() or "not_reviewed"
        reviewed_label = str(row.get("reviewed_label") or "").strip()
        reviewer_note = str(row.get("reviewer_note") or "").strip()
        draft_label = str(updated.get("proposed_label") or "").strip()
        draft_decision = str(updated.get("decision") or "Needs review")
        confidence = updated.get("confidence", {})
        final_label = reviewed_label if review_status in {"accepted", "changed"} and reviewed_label else draft_label
        label_source = "reviewed" if review_status in {"accepted", "changed"} and reviewed_label else "draft"
        final_decision = "Accepted" if final_label and review_status in {"accepted", "changed"} else draft_decision
        if review_status == "rejected":
            final_decision = "Needs review"
            label_source = "reviewed"

        updated["final_label"] = final_label
        updated["final_decision"] = final_decision
        updated["review"] = {
            "status": review_status,
            "reviewed_label": reviewed_label,
            "reviewer_note": reviewer_note,
            "label_source": label_source,
        }
        updated["provenance"] = updated.get("provenance", {})
        updated["provenance"]["finalized"] = True
        updated["provenance"]["label_source"] = label_source
        if isinstance(confidence, dict):
            updated["final_confidence"] = str(confidence.get("overall") or "")
        final_cards.append(updated)
    return final_cards


def _write_annotated_h5ad(path: Path, cards: list[dict[str, Any]], reproducibility: dict[str, Any]) -> None:
    if not cards:
        raise ValueError("cannot write annotated h5ad without annotation cards")
    try:
        import anndata as ad
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("anndata is required for --write-h5ad") from exc

    input_path = Path(str(reproducibility.get("input_file") or ""))
    parameters = reproducibility.get("parameters", {})
    dataset = parameters.get("dataset", {}) if isinstance(parameters, dict) else {}
    cluster_key = str(dataset.get("cluster_key") or "")
    if not input_path.exists():
        raise FileNotFoundError(f"input h5ad not found for finalize: {input_path}")
    if not cluster_key:
        raise ValueError("dataset.cluster_key is required to write annotated h5ad")

    adata = ad.read_h5ad(input_path)
    if cluster_key not in adata.obs:
        raise ValueError(f"cluster_key '{cluster_key}' was not found in input h5ad")

    by_cluster = {str(card.get("cluster_id", "")): card for card in cards}
    clusters = adata.obs[cluster_key].astype(str)
    adata.obs["scaudit_label"] = [str(by_cluster.get(value, {}).get("final_label") or "") for value in clusters]
    adata.obs["scaudit_decision"] = [str(by_cluster.get(value, {}).get("final_decision") or by_cluster.get(value, {}).get("decision") or "") for value in clusters]
    adata.obs["scaudit_confidence"] = [
        str(by_cluster.get(value, {}).get("final_confidence") or by_cluster.get(value, {}).get("confidence", {}).get("overall") or "")
        for value in clusters
    ]
    adata.obs["scaudit_review_status"] = [
        str(by_cluster.get(value, {}).get("review", {}).get("status") or "not_reviewed") for value in clusters
    ]
    adata.obs["scaudit_label_source"] = [
        str(by_cluster.get(value, {}).get("review", {}).get("label_source") or "draft") for value in clusters
    ]
    adata.uns["scaudit"] = {
        "scaudit_version": __version__,
        "reproducibility_json": json.dumps(reproducibility, sort_keys=True),
        "final_annotation_cards_json": json.dumps(cards, sort_keys=True),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    adata.write_h5ad(path)


def _reproducibility_payload(config: dict[str, Any]) -> dict[str, Any]:
    dataset = config.get("dataset", {})
    return {
        "scaudit_version": __version__,
        "input_file": dataset.get("path", ""),
        "input_hash": None,
        "parameters": config,
        "references": [],
        "models": [],
        "evidence_methods": {
            "markers": "scanpy.rank_genes_groups.wilcoxon",
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _llm_settings(config: dict[str, Any]) -> dict[str, Any]:
    llm_config = config.get("llm", {})
    if not isinstance(llm_config, dict):
        return {}
    return {
        "provider": str(llm_config.get("provider", "") or ""),
        "base_url": str(llm_config.get("base_url", "") or ""),
        "api_key_env": str(llm_config.get("api_key_env", "") or ""),
        "model": str(llm_config.get("model", "") or ""),
        "temperature": float(llm_config.get("temperature", 0) or 0),
    }


def _marker_rows_from_evidence(evidence: dict[str, ClusterEvidence]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cluster_id, cluster_evidence in sorted(evidence.items(), key=lambda item: str(item[0])):
        for rank, marker in enumerate(cluster_evidence.markers, start=1):
            rows.append(
                {
                    "cluster_id": str(cluster_id),
                    "rank": rank,
                    "gene": marker.gene,
                    "score": marker.score,
                    "logfoldchange": marker.log2fc,
                    "pvalue": None,
                    "pvalue_adj": marker.pval_adj,
                }
            )
    return rows


def build_annotation_cards(
    diagnosis: dict[str, Any],
    evidence: dict[str, ClusterEvidence] | None = None,
) -> list[dict[str, Any]]:
    cluster_sizes = diagnosis.get("cluster_sizes", {})
    if not isinstance(cluster_sizes, dict) or not cluster_sizes:
        return []

    evidence = evidence or {}
    cards: list[dict[str, Any]] = []
    for cluster_id, cell_count in sorted(cluster_sizes.items(), key=lambda item: str(item[0])):
        ev = evidence.get(str(cluster_id))
        cards.append(_build_card(str(cluster_id), int(cell_count), ev))
    return cards


def _build_card(cluster_id: str, cell_count: int, ev: ClusterEvidence | None) -> dict[str, Any]:
    markers = ev.markers if ev else []
    marker_signatures = ev.marker_signatures if ev else []
    marker_db_matches = ev.reference_matches if ev else []
    qc_warnings = ev.qc_warnings if ev else []

    proposed_label, decision, confidence, reasoning, uncertainty = _assign_annotation(
        cluster_id=cluster_id,
        cell_count=cell_count,
        markers=markers,
        marker_db_matches=marker_db_matches,
        qc_warnings=qc_warnings,
    )

    return {
        "cluster_id": cluster_id,
        "proposed_label": proposed_label,
        "decision": decision,
        "confidence": confidence,
        "evidence": {
            "markers": [m.to_dict() for m in markers[:10]],
            "marker_signatures": marker_signatures[:5],
            "models": [],
            "references": marker_db_matches[:3],
            "ontology": [],
            "qc": ev.qc_metrics if ev else {},
            "composition": ev.composition if ev else {},
            "qc_warnings": qc_warnings,
        },
        "uncertainty": uncertainty,
        "reasoning": reasoning,
        "provenance": {
            "parameters": {},
            "models": [],
            "references": [m["ref_id"] for m in marker_db_matches[:3]],
            "cell_count": cell_count,
        },
    }


def _assign_annotation(
    cluster_id: str,
    cell_count: int,
    markers: list,
    marker_db_matches: list[dict[str, Any]],
    qc_warnings: list[str] | None = None,
) -> tuple[str | None, str, dict[str, str], dict[str, Any], dict[str, str]]:
    supports: list[str] = []
    contradictions: list[str] = []
    uncertainties: list[str] = []
    suggestions: list[str] = []
    qc_warnings = qc_warnings or []
    artifact_qc_warnings = [warning for warning in qc_warnings if _is_artifact_qc_warning(warning)]

    # --- marker evidence ---
    strong_markers = [m for m in markers if _marker_strength(m) == "strong"]
    moderate_markers = [m for m in markers if _marker_strength(m) in {"strong", "moderate"}]

    marker_lineage = "unknown"
    if len(strong_markers) >= 5:
        marker_lineage = "high"
        supports.append(f"{len(strong_markers)} strongly enriched marker genes (log2FC > 1, padj < 0.01)")
    elif len(moderate_markers) >= 3:
        marker_lineage = "medium"
        supports.append(f"{len(moderate_markers)} enriched marker genes (log2FC > 0.5, padj < 0.05)")
    elif markers:
        marker_lineage = "low"
        uncertainties.append("Weak marker signal; cluster may overlap with neighbours")
    else:
        uncertainties.append("No marker evidence computed yet. Run with a real h5ad dataset.")

    # --- marker database evidence ---
    db_confidence = "unknown"
    best_db = marker_db_matches[0] if marker_db_matches else None
    if best_db and best_db["jaccard"] >= 0.20:
        db_confidence = "high"
        supports.append(
            f"Marker database '{best_db['ref_id']}' supports '{best_db['label']}' "
            f"(Jaccard {best_db['jaccard']:.2f}, {best_db['n_shared']} shared genes)"
        )
    elif best_db and best_db["jaccard"] >= 0.08:
        db_confidence = "medium"
        supports.append(
            f"Moderate marker database support for '{best_db['label']}' from '{best_db['ref_id']}' "
            f"(Jaccard {best_db['jaccard']:.2f})"
        )
    elif marker_db_matches:
        db_confidence = "low"
        uncertainties.append("All marker database overlaps have Jaccard < 0.08; identity is uncertain.")
    else:
        uncertainties.append("No marker database support was available for this cluster.")

    # --- proposed label ---
    proposed_label: str | None = None
    if best_db and best_db["jaccard"] >= 0.10:
        proposed_label = best_db["label"]

    # --- overall confidence ---
    level_rank = {"high": 3, "medium": 2, "low": 1, "unknown": 0}
    avg_rank = (level_rank[marker_lineage] + level_rank[db_confidence]) / 2

    if avg_rank >= 2.5:
        overall = "high"
    elif avg_rank >= 1.5:
        overall = "medium"
    elif avg_rank >= 0.5:
        overall = "low"
    else:
        overall = "unknown"

    # --- artifact override ---
    if cell_count < 10:
        suggestions.append(f"Very small cluster ({cell_count} cells); validate in QC metrics.")
        suggestions.append("Check if this cluster passes QC thresholds; consider removing or merging.")
    if artifact_qc_warnings:
        uncertainties.extend(artifact_qc_warnings)
        suggestions.append("Review QC distributions before accepting this cluster annotation.")

    # --- decision + summary ---
    if cell_count < 10:
        decision = "Artifact warning"
        summary = f"Cluster {cluster_id} has only {cell_count} cells and may be a doublet or artifact."
    elif artifact_qc_warnings:
        decision = "Artifact warning"
        summary = f"Cluster {cluster_id} has QC evidence consistent with a potential artifact."
    elif not markers and not marker_db_matches:
        decision = "Needs review"
        summary = f"Cluster {cluster_id}: no evidence has been computed yet."
    elif contradictions:
        decision = "Ambiguous"
        summary = (
            f"Cluster {cluster_id}: evidence sources disagree. "
            f"Review marker genes and marker database matches carefully."
        )
    elif overall == "high" and proposed_label:
        decision = "Accepted"
        summary = (
            f"Cluster {cluster_id} has strong, consistent evidence supporting '{proposed_label}'. "
            f"All evidence layers agree."
        )
    elif overall in ("medium", "high") and proposed_label:
        decision = "Needs review"
        summary = (
            f"Cluster {cluster_id} shows moderate evidence for '{proposed_label}'. "
            f"Human review is recommended."
        )
    else:
        decision = "Needs review"
        summary = f"Cluster {cluster_id}: evidence is insufficient for automatic annotation."

    if strong_markers:
        suggestions.append(
            f"Validate top markers {', '.join(m.gene for m in strong_markers[:3])} "
            f"using PMID literature or cell-type databases."
        )
    else:
        suggestions.append("Run with a real h5ad file to obtain marker genes for literature validation.")

    confidence = {"lineage": marker_lineage, "subtype": db_confidence, "overall": overall}
    uncertainty = {
        "provider_disagreement": "unknown",
        "marker_database_distance": "low" if (best_db and best_db["jaccard"] >= 0.20) else "high" if best_db else "unknown",
        "marker_inconsistency": "low" if len(strong_markers) >= 5 else "high" if not markers else "medium",
        "qc_artifact": "high" if artifact_qc_warnings else "low" if qc_warnings else "unknown",
    }
    reasoning = {
        "summary": summary,
        "supports": supports,
        "contradictions": contradictions,
        "uncertainties": uncertainties,
        "validation_suggestions": suggestions,
    }

    return proposed_label, decision, confidence, reasoning, uncertainty


def _is_artifact_qc_warning(warning: str) -> bool:
    lowered = warning.lower()
    return any(
        phrase in lowered
        for phrase in (
            "mitochondrial fraction",
            "doublet score",
            "low detected genes",
            "low total counts",
            "sample or batch effect",
        )
    )


def _marker_strength(marker: Any) -> str:
    if marker.pval_adj >= 0.05:
        return "weak"
    if marker.log2fc != marker.log2fc:
        return "moderate" if marker.score > 0 else "weak"
    if marker.log2fc > 1.0:
        return "strong"
    if marker.log2fc > 0.5:
        return "moderate"
    return "weak"


def _write_annotation_summary(path: Path, annotation_cards: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["cluster_id", "proposed_label", "decision", "confidence", "review_priority", "final_label", "final_decision", "label_source"])
        for card in annotation_cards:
            review = card.get("review", {})
            writer.writerow(
                [
                    card["cluster_id"],
                    card["proposed_label"] or "",
                    card["decision"],
                    card["confidence"]["overall"],
                    "review",
                    card.get("final_label") or card.get("proposed_label") or "",
                    card.get("final_decision") or card.get("decision") or "",
                    review.get("label_source") or "draft",
                ]
            )


def _write_review_table(path: Path, annotation_cards: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "cluster_id",
                "proposed_label",
                "decision",
                "confidence",
                "review_status",
                "reviewed_label",
                "reviewer_note",
            ]
        )
        for card in annotation_cards:
            writer.writerow(
                [
                    card["cluster_id"],
                    card["proposed_label"] or "",
                    card["decision"],
                    card["confidence"]["overall"],
                    "pending",
                    "",
                    "",
                ]
            )


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))
