from __future__ import annotations

from pathlib import Path
from typing import Any

from scaudit.data import ClusterEvidence
from scaudit.providers.marker_database import (
    MarkerDatabaseSpec,
    render_marker_database_provider_report,
    write_marker_database_provider_outputs,
)


USER_MARKERS_SPEC = MarkerDatabaseSpec(
    provider_id="user_markers",
    provider_name="User marker database evidence",
    provider_version="0.1.0",
    title="User Marker Database Evidence",
    subtitle="User-supplied marker database overlap for project-specific cluster interpretation",
    purpose="User-defined marker database support",
    database_name="User marker genes",
    publication="User supplied marker list",
    source_url="local file",
    result_file="user_markers.evidence.json",
    label_aliases=("cell_type", "cell type", "celltype", "label", "annotation", "cell", "cell name"),
    gene_aliases=("gene", "gene_symbol", "gene symbol", "symbol", "marker", "marker gene"),
    species_aliases=("species", "organism"),
    tissue_aliases=("tissue", "organ", "context"),
    cache_relative_path="",
)


def render_user_markers_provider_report(
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
        USER_MARKERS_SPEC,
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


def write_user_markers_provider_outputs(
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
        USER_MARKERS_SPEC,
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
