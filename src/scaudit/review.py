from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass
from pathlib import Path


REVIEW_COLUMNS = [
    "cluster_id",
    "proposed_label",
    "decision",
    "confidence",
    "review_status",
    "reviewed_label",
    "reviewer_note",
]


@dataclass(frozen=True)
class ReviewImportResult:
    run_dir: Path
    source: Path
    reviewed_table: Path
    audit_path: Path
    row_count: int
    warnings: list[str]


def import_review_table(source: Path, run_dir: Path) -> ReviewImportResult:
    if not source.exists():
        raise FileNotFoundError(f"review table not found: {source}")
    if not run_dir.exists():
        raise FileNotFoundError(f"run directory not found: {run_dir}")

    rows, warnings = _read_review_rows(source)
    reviewed_table = run_dir / "reviewed_review_table.csv"
    audit_path = run_dir / "review_audit.json"

    shutil.copyfile(source, reviewed_table)
    audit = {
        "source": str(source),
        "reviewed_table": str(reviewed_table),
        "row_count": len(rows),
        "warnings": warnings,
        "status": "imported",
    }
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ReviewImportResult(run_dir, source, reviewed_table, audit_path, len(rows), warnings)


def _read_review_rows(source: Path) -> tuple[list[dict[str, str]], list[str]]:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("review table has no header")
        missing = [column for column in REVIEW_COLUMNS if column not in reader.fieldnames]
        if missing:
            raise ValueError(f"review table missing required columns: {', '.join(missing)}")
        rows = [dict(row) for row in reader]

    warnings: list[str] = []
    for index, row in enumerate(rows, start=2):
        review_status = row.get("review_status", "").strip()
        reviewed_label = row.get("reviewed_label", "").strip()
        if review_status in {"accepted", "changed"} and not reviewed_label:
            warnings.append(f"row {index}: review_status={review_status} but reviewed_label is empty")
    return rows, warnings
