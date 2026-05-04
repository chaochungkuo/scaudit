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
from scaudit.config import load_config
from scaudit.data import diagnose_dataset
from scaudit.report import render_draft_report, render_final_report


@dataclass(frozen=True)
class RunOutputs:
    output_dir: Path
    resolved_config: Path
    diagnosis: Path
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


def prepare_run(config_path: Path) -> RunOutputs:
    config = load_config(config_path)
    output_dir = Path(str(config.get("output", {}).get("dir", "results")))
    report_dir = output_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)

    outputs = RunOutputs(
        output_dir=output_dir,
        resolved_config=output_dir / "config.resolved.toml",
        diagnosis=output_dir / "diagnosis.json",
        annotation_cards=output_dir / "annotation_cards.json",
        annotation_summary=output_dir / "annotation_summary.csv",
        review_table=output_dir / "review_table.csv",
        reproducibility=output_dir / "reproducibility.json",
        report_index=report_dir / "index.html",
    )

    shutil.copyfile(config_path, outputs.resolved_config)
    dataset = config.get("dataset", {})
    diagnosis = diagnose_dataset(
        Path(str(dataset.get("path", ""))),
        cluster_key=str(dataset.get("cluster_key", "")),
    )
    diagnosis_payload = diagnosis.to_dict()
    annotation_cards = build_annotation_cards(diagnosis_payload)
    _write_json(outputs.diagnosis, diagnosis_payload)
    _write_json(outputs.annotation_cards, annotation_cards)
    _write_annotation_summary(outputs.annotation_summary, annotation_cards)
    _write_review_table(outputs.review_table, annotation_cards)
    _write_json(outputs.reproducibility, _reproducibility_payload(config))
    render_draft_report(report_dir, outputs.diagnosis, outputs.annotation_cards)
    return outputs


def finalize_run(run_dir: Path, output_dir: Path) -> FinalOutputs:
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
        report_index=report_dir / "index.html",
    )

    _copy_or_default(run_dir / "annotation_cards.json", outputs.annotation_cards, "[]\n")
    _copy_or_default(
        run_dir / "annotation_summary.csv",
        outputs.annotation_summary,
        "cluster_id,proposed_label,decision,confidence,review_priority\n",
    )
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
    render_final_report(report_dir)
    return outputs


def _copy_or_default(source: Path, destination: Path, default_text: str) -> None:
    if source.exists():
        shutil.copyfile(source, destination)
    else:
        destination.write_text(default_text, encoding="utf-8")


def _reproducibility_payload(config: dict[str, Any]) -> dict[str, Any]:
    dataset = config.get("dataset", {})
    return {
        "scaudit_version": __version__,
        "input_file": dataset.get("path", ""),
        "input_hash": None,
        "parameters": config,
        "references": [],
        "models": [],
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def build_annotation_cards(diagnosis: dict[str, Any]) -> list[dict[str, Any]]:
    cluster_sizes = diagnosis.get("cluster_sizes", {})
    if not isinstance(cluster_sizes, dict) or not cluster_sizes:
        return []

    cards: list[dict[str, Any]] = []
    for cluster_id, cell_count in sorted(cluster_sizes.items(), key=lambda item: str(item[0])):
        cards.append(
            {
                "cluster_id": str(cluster_id),
                "proposed_label": None,
                "decision": "Needs review",
                "confidence": {
                    "lineage": "unknown",
                    "subtype": "unknown",
                    "overall": "unknown",
                },
                "evidence": {
                    "markers": [],
                    "models": [],
                    "references": [],
                    "ontology": [],
                    "qc_warnings": [],
                },
                "uncertainty": {
                    "model_disagreement": "unknown",
                    "reference_distance": "unknown",
                    "marker_inconsistency": "unknown",
                },
                "reasoning": {
                    "summary": "Cluster detected during dataset diagnosis. Evidence generation is pending.",
                    "supports": [],
                    "contradictions": [],
                    "uncertainties": ["No marker, model, or reference evidence has been computed yet."],
                    "validation_suggestions": [],
                },
                "provenance": {
                    "parameters": {},
                    "models": [],
                    "references": [],
                    "cell_count": int(cell_count),
                },
            }
        )
    return cards


def _write_annotation_summary(path: Path, annotation_cards: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["cluster_id", "proposed_label", "decision", "confidence", "review_priority"])
        for card in annotation_cards:
            writer.writerow(
                [
                    card["cluster_id"],
                    card["proposed_label"] or "",
                    card["decision"],
                    card["confidence"]["overall"],
                    "review",
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
