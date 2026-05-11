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
from scaudit.config import load_config, write_default_config
from scaudit.data import ClusterEvidence, compute_cluster_evidence, diagnose_dataset
from scaudit.markers import write_marker_evidence_csv
from scaudit.references import load_registry, registry_path
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

    diagnosis = diagnose_dataset(dataset_path, cluster_key=cluster_key, sample_key=sample_key)
    diagnosis_payload = diagnosis.to_dict()

    selected_refs = config.get("references", {}).get("selected", [])
    ref_registry_path = registry_path() if selected_refs else None
    evidence = compute_cluster_evidence(
        dataset_path,
        cluster_key=cluster_key,
        reference_registry_path=ref_registry_path,
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
    render_draft_report(report_dir, outputs.diagnosis, outputs.annotation_cards)
    return outputs


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
    celltypist_label = ev.celltypist_label if ev else None
    celltypist_prob = ev.celltypist_prob if ev else None
    ref_matches = ev.reference_matches if ev else []
    qc_warnings = ev.qc_warnings if ev else []

    proposed_label, decision, confidence, reasoning, uncertainty = _assign_annotation(
        cluster_id=cluster_id,
        cell_count=cell_count,
        markers=markers,
        celltypist_label=celltypist_label,
        celltypist_prob=celltypist_prob,
        ref_matches=ref_matches,
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
            "models": (
                [{"model": "CellTypist", "label": celltypist_label, "probability": celltypist_prob}]
                if celltypist_label
                else []
            ),
            "references": ref_matches[:3],
            "ontology": [],
            "qc": ev.qc_metrics if ev else {},
            "composition": ev.composition if ev else {},
            "qc_warnings": qc_warnings,
        },
        "uncertainty": uncertainty,
        "reasoning": reasoning,
        "provenance": {
            "parameters": {},
            "models": ["CellTypist"] if celltypist_label else [],
            "references": [m["ref_id"] for m in ref_matches[:3]],
            "cell_count": cell_count,
        },
    }


def _assign_annotation(
    cluster_id: str,
    cell_count: int,
    markers: list,
    celltypist_label: str | None,
    celltypist_prob: float | None,
    ref_matches: list[dict[str, Any]],
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

    # --- model evidence ---
    model_confidence = "unknown"
    if celltypist_label and celltypist_prob is not None:
        if celltypist_prob >= 0.75:
            model_confidence = "high"
            supports.append(f"CellTypist predicts '{celltypist_label}' (majority vote {celltypist_prob:.0%})")
        elif celltypist_prob >= 0.50:
            model_confidence = "medium"
            supports.append(f"CellTypist suggests '{celltypist_label}' ({celltypist_prob:.0%} majority)")
        else:
            model_confidence = "low"
            uncertainties.append(f"CellTypist shows ambiguous vote for '{celltypist_label}' ({celltypist_prob:.0%})")
    else:
        uncertainties.append("No CellTypist prediction available for this cluster.")

    # --- reference evidence ---
    ref_confidence = "unknown"
    best_ref = ref_matches[0] if ref_matches else None
    if best_ref and best_ref["jaccard"] >= 0.20:
        ref_confidence = "high"
        supports.append(
            f"Reference '{best_ref['ref_id']}' matches cell type '{best_ref['label']}' "
            f"(Jaccard {best_ref['jaccard']:.2f}, {best_ref['n_shared']} shared genes)"
        )
    elif best_ref and best_ref["jaccard"] >= 0.08:
        ref_confidence = "medium"
        supports.append(
            f"Weak reference match: '{best_ref['label']}' from '{best_ref['ref_id']}' "
            f"(Jaccard {best_ref['jaccard']:.2f})"
        )
    elif ref_matches:
        ref_confidence = "low"
        uncertainties.append("All reference matches have Jaccard < 0.08; identity is uncertain.")
    else:
        uncertainties.append("No reference datasets were matched against this cluster.")

    # --- proposed label ---
    proposed_label: str | None = None
    if celltypist_label:
        proposed_label = celltypist_label
    elif best_ref and best_ref["jaccard"] >= 0.10:
        proposed_label = best_ref["label"]

    # --- overall confidence ---
    level_rank = {"high": 3, "medium": 2, "low": 1, "unknown": 0}
    min_rank = min(level_rank[marker_lineage], level_rank[model_confidence], level_rank[ref_confidence])
    max_rank = max(level_rank[marker_lineage], level_rank[model_confidence], level_rank[ref_confidence])
    avg_rank = (level_rank[marker_lineage] + level_rank[model_confidence] + level_rank[ref_confidence]) / 3

    rank_to_level = {3: "high", 2: "medium", 1: "low", 0: "unknown"}

    if avg_rank >= 2.5:
        overall = "high"
    elif avg_rank >= 1.5:
        overall = "medium"
    elif avg_rank >= 0.5:
        overall = "low"
    else:
        overall = "unknown"

    # flag contradictions between evidence sources
    if celltypist_label and best_ref and best_ref["jaccard"] >= 0.10:
        if celltypist_label.lower() != best_ref["label"].lower():
            contradictions.append(
                f"CellTypist suggests '{celltypist_label}' but best reference match is '{best_ref['label']}'"
            )
            overall = "low" if overall == "medium" else overall

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
    elif not markers and not celltypist_label and not ref_matches:
        decision = "Needs review"
        summary = f"Cluster {cluster_id}: no evidence has been computed yet."
    elif contradictions:
        decision = "Ambiguous"
        summary = (
            f"Cluster {cluster_id}: evidence sources disagree. "
            f"Review marker genes and reference matches carefully."
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

    confidence = {"lineage": marker_lineage, "subtype": ref_confidence, "overall": overall}
    uncertainty = {
        "model_disagreement": "high" if contradictions else "low" if celltypist_label else "unknown",
        "reference_distance": "low" if (best_ref and best_ref["jaccard"] >= 0.20) else "high" if best_ref else "unknown",
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
