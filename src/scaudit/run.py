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
    _write_json(outputs.diagnosis, _diagnosis_payload(config))
    _write_json(outputs.annotation_cards, [])
    _write_annotation_summary(outputs.annotation_summary)
    _write_review_table(outputs.review_table)
    _write_json(outputs.reproducibility, _reproducibility_payload(config))
    _write_report_placeholder(outputs.report_index)
    return outputs


def _diagnosis_payload(config: dict[str, Any]) -> dict[str, Any]:
    dataset = config.get("dataset", {})
    return {
        "dataset": {
            "path": dataset.get("path", ""),
            "species": dataset.get("species", ""),
            "tissue": dataset.get("tissue", ""),
            "cluster_key": dataset.get("cluster_key", ""),
        },
        "status": "placeholder",
        "warnings": [
            "Dataset diagnosis is a placeholder until AnnData reading is implemented."
        ],
    }


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


def _write_annotation_summary(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["cluster_id", "proposed_label", "decision", "confidence", "review_priority"])


def _write_review_table(path: Path) -> None:
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


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_report_placeholder(path: Path) -> None:
    path.write_text(
        """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>scaudit report</title>
</head>
<body>
  <main>
    <h1>scaudit annotation audit</h1>
    <p>This placeholder report confirms that the run output structure was created.</p>
    <p>Marker evidence and cluster pages will be generated in the next implementation phases.</p>
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )
