from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_TEMPLATE = """[project]
name = "scaudit_run"
description = "Single-cell annotation audit"

[dataset]
path = "{dataset_path}"
species = ""
tissue = ""
cluster_key = ""
sample_key = ""
condition_key = ""
batch_key = ""

[gene_harmonization]
input_gene_id_type = "auto"
reference_gene_id_type = "auto"
normalize_symbols = true
ortholog_map = "none"
min_gene_overlap_warning = 0.70
min_gene_overlap_strong_warning = 0.50

[cache]
dir = "~/.cache/scaudit"

[marker_databases.cellmarker]
path = ""

[marker_databases.panglaodb]
path = ""

[marker_databases.user_markers]
path = ""
name = "User marker genes"

[methods]
marker_based = true
ontology_based = false

[methods.marker_databases]
cellmarker = true
panglaodb = false
user_markers = false

[methods.qc]
enabled = true
doublet_warning = true
ambient_rna_warning = true
low_quality_warning = true

[decision]
unit = "cluster"
confidence_mode = "categorical"
prefer_lineage_over_subtype = true
allow_unknown = true
allow_ambiguous = true

[llm]
enabled = false
provider = "openai"
mode = "explain_only"
base_url = ""
api_key_env = "SCAUDIT_LLM_API_KEY"
model = ""
temperature = 0

[report]
enabled = true
format = "html"
multi_page = true
theme = "scaudit"
include_methods = true
include_reproducibility = true
include_cluster_pages = true
include_condition_comparison = false

[output]
dir = "results"
draft_h5ad = true
final_h5ad = true
annotation_cards = true
summary_tables = true
review_table = true
reproducibility = true
figures = true
"""


@dataclass(frozen=True)
class ValidationItem:
    section: str
    status: str
    notes: str


@dataclass(frozen=True)
class Plan:
    dataset_path: str
    output_dir: str
    methods: list[ValidationItem]
    outputs: list[str]
    stages: list[str]


def write_default_config(dataset_path: str, output_path: Path) -> None:
    output_path.write_text(DEFAULT_CONFIG_TEMPLATE.format(dataset_path=dataset_path), encoding="utf-8")


def load_config(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def validate_config(path: Path) -> list[ValidationItem]:
    items: list[ValidationItem] = []
    if not path.exists():
        return [ValidationItem("config", "ERROR", f"{path} was not found")]

    try:
        config = load_config(path)
    except tomllib.TOMLDecodeError as exc:
        return [ValidationItem("config", "ERROR", f"TOML parse error: {exc}")]

    dataset = config.get("dataset")
    if not isinstance(dataset, dict):
        items.append(ValidationItem("dataset", "ERROR", "missing [dataset] section"))
    else:
        dataset_path = str(dataset.get("path", "")).strip()
        if not dataset_path:
            items.append(ValidationItem("dataset.path", "ERROR", "dataset.path is required"))
        elif Path(dataset_path).exists():
            items.append(ValidationItem("dataset.path", "OK", f"{dataset_path} found"))
        else:
            items.append(ValidationItem("dataset.path", "WARN", f"{dataset_path} not found yet"))

        for key in ("species", "tissue", "cluster_key"):
            value = str(dataset.get(key, "")).strip()
            if value:
                items.append(ValidationItem(f"dataset.{key}", "OK", value))
            else:
                items.append(ValidationItem(f"dataset.{key}", "WARN", f"{key} is empty"))

    output = config.get("output")
    if not isinstance(output, dict):
        items.append(ValidationItem("output", "ERROR", "missing [output] section"))
    else:
        output_dir = str(output.get("dir", "")).strip()
        if output_dir:
            items.append(ValidationItem("output.dir", "OK", output_dir))
        else:
            items.append(ValidationItem("output.dir", "ERROR", "output.dir is required"))

    cache = config.get("cache")
    if isinstance(cache, dict):
        cache_dir = str(cache.get("dir", "") or "").strip()
        items.append(ValidationItem("cache.dir", "OK" if cache_dir else "WARN", cache_dir or "default ~/.cache/scaudit"))

    methods = config.get("methods")
    if not isinstance(methods, dict):
        items.append(ValidationItem("methods", "ERROR", "missing [methods] section"))
    else:
        if methods.get("marker_based") is True:
            items.append(ValidationItem("methods.marker_based", "OK", "enabled"))
        else:
            items.append(ValidationItem("methods.marker_based", "WARN", "disabled; MVP expects marker evidence"))

        marker_databases = methods.get("marker_databases", {})
        if isinstance(marker_databases, dict):
            enabled_databases = [name for name, active in marker_databases.items() if active is True]
            if enabled_databases:
                items.append(ValidationItem("methods.marker_databases", "OK", ", ".join(enabled_databases)))
            else:
                items.append(ValidationItem("methods.marker_databases", "OK", "marker databases disabled"))
    return items


def has_errors(items: list[ValidationItem]) -> bool:
    return any(item.status == "ERROR" for item in items)


def build_plan(config_path: Path) -> Plan:
    config = load_config(config_path)
    dataset = config.get("dataset", {})
    output = config.get("output", {})
    methods = config.get("methods", {})
    marker_databases = methods.get("marker_databases", {}) if isinstance(methods, dict) else {}
    output_dir = str(output.get("dir", "results")) if isinstance(output, dict) else "results"

    method_items = [
        ValidationItem("marker evidence", "OK" if methods.get("marker_based") else "SKIPPED", "Scanpy marker ranking"),
    ]
    if isinstance(marker_databases, dict):
        for name in ("cellmarker", "panglaodb", "user_markers"):
            method_items.append(
                ValidationItem(name, "OK" if marker_databases.get(name) else "SKIPPED", "marker database provider")
            )
    outputs = [
        f"{output_dir}/annotation_cards.json",
        f"{output_dir}/annotation_summary.csv",
        f"{output_dir}/review_table.csv",
        f"{output_dir}/report/index.html",
        f"{output_dir}/reproducibility.json",
    ]
    stages = [
        "Dataset diagnosis",
        "Gene harmonization",
        "Marker evidence",
        "Decision assignment",
        "Report generation",
        "Output writing",
    ]
    return Plan(
        dataset_path=str(dataset.get("path", "")) if isinstance(dataset, dict) else "",
        output_dir=output_dir,
        methods=method_items,
        outputs=outputs,
        stages=stages,
    )
