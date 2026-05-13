from __future__ import annotations

from pathlib import Path
from typing import Any

from scaudit.data import ClusterEvidence
from scaudit.providers.marker_database import (
    MarkerDatabaseSpec,
    render_marker_database_provider_report,
    write_marker_database_provider_outputs,
)


PANGLAODB_SPEC = MarkerDatabaseSpec(
    provider_id="panglaodb",
    provider_name="PanglaoDB database evidence",
    provider_version="0.1.0",
    title="PanglaoDB Database Evidence",
    subtitle="Mouse and human marker database overlap for cluster interpretation",
    purpose="Curated marker database support",
    database_name="PanglaoDB",
    publication="PanglaoDB, Database 2019",
    source_url="https://panglaodb.se/markers.html",
    result_file="panglaodb.evidence.json",
    label_aliases=("cell type", "cell.type", "celltype", "cell-type", "cell type name"),
    gene_aliases=("official gene symbol", "official.gene.symbol", "gene", "gene symbol", "symbol"),
    cache_relative_path="marker_databases/panglaodb/PanglaoDB_markers_27_Mar_2020.tsv.gz",
    download_url="https://panglaodb.se/markers/PanglaoDB_markers_27_Mar_2020.tsv.gz",
    tissue_aliases=("organ", "tissue", "organ system"),
)


def render_panglaodb_provider_report(
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
    return render_marker_database_provider_report(
        PANGLAODB_SPEC,
        dataset_path,
        cluster_key,
        output_dir,
        evidence=evidence,
        database_path=database_path,
        cache_root=cache_root,
        species=species,
        tissue=tissue,
        sample_key=sample_key,
        batch_key=batch_key,
    )


def write_panglaodb_provider_outputs(
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
    return write_marker_database_provider_outputs(
        PANGLAODB_SPEC,
        dataset_path,
        cluster_key,
        output_dir,
        evidence=evidence,
        database_path=database_path,
        cache_root=cache_root,
        species=species,
        tissue=tissue,
        sample_key=sample_key,
        batch_key=batch_key,
        started_at=started_at,
    )
