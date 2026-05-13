from __future__ import annotations

from pathlib import Path
from typing import Any

from scaudit.data import ClusterEvidence
from scaudit.providers.marker_database import (
    MarkerDatabaseSpec,
    render_marker_database_provider_report,
    write_marker_database_provider_outputs,
)


CELLMARKER_SPEC = MarkerDatabaseSpec(
    provider_id="cellmarker",
    provider_name="CellMarker database evidence",
    provider_version="0.1.0",
    title="CellMarker Database Evidence",
    subtitle="Curated marker database overlap for cluster interpretation",
    purpose="Curated marker database support",
    database_name="CellMarker 2.0",
    publication="CellMarker 2.0, Nucleic Acids Research 2023",
    source_url="http://bio-bigdata.hrbmu.edu.cn/CellMarker/",
    result_file="cellmarker.evidence.json",
    label_aliases=("cell type", "celltype", "cell_name", "cell name", "cell"),
    gene_aliases=("symbol", "gene symbol", "gene", "marker", "marker gene", "cell marker"),
    tissue_aliases=("tissue_type", "tissue type", "tissue_class", "tissue class", "tissue"),
    cache_relative_path="marker_databases/cellmarker/Cell_marker_Human.xlsx",
    species_download_urls={
        "hs": "https://bio-bigdata.hrbmu.edu.cn/CellMarker/CellMarker_download_files/file/Cell_marker_Human.xlsx",
        "mm": "https://bio-bigdata.hrbmu.edu.cn/CellMarker/CellMarker_download_files/file/Cell_marker_Mouse.xlsx",
        "": "https://bio-bigdata.hrbmu.edu.cn/CellMarker/CellMarker_download_files/file/Cell_marker_Human.xlsx",
    },
    species_cache_relative_paths={
        "hs": "marker_databases/cellmarker/Cell_marker_Human.xlsx",
        "mm": "marker_databases/cellmarker/Cell_marker_Mouse.xlsx",
        "": "marker_databases/cellmarker/Cell_marker_Human.xlsx",
    },
)


def render_cellmarker_provider_report(
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
        CELLMARKER_SPEC,
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


def write_cellmarker_provider_outputs(
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
        CELLMARKER_SPEC,
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
