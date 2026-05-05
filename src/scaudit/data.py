from __future__ import annotations

import importlib.util
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DatasetDiagnosis:
    path: str
    file_exists: bool
    readable: bool
    n_obs: int | None
    n_vars: int | None
    obs_keys: list[str]
    var_names_preview: list[str]
    cluster_key: str
    cluster_count: int | None
    cluster_sizes: dict[str, int]
    warnings: list[str]
    umap_coords: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "file_exists": self.file_exists,
            "readable": self.readable,
            "n_obs": self.n_obs,
            "n_vars": self.n_vars,
            "obs_keys": self.obs_keys,
            "var_names_preview": self.var_names_preview,
            "cluster_key": self.cluster_key,
            "cluster_count": self.cluster_count,
            "cluster_sizes": self.cluster_sizes,
            "umap_coords": self.umap_coords,
            "warnings": self.warnings,
        }


@dataclass
class MarkerGene:
    gene: str
    score: float
    log2fc: float
    pval_adj: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene": self.gene,
            "score": round(self.score, 4),
            "log2fc": round(self.log2fc, 4),
            "pval_adj": round(self.pval_adj, 6),
        }


@dataclass
class ClusterEvidence:
    cluster_id: str
    markers: list[MarkerGene] = field(default_factory=list)
    celltypist_label: str | None = None
    celltypist_prob: float | None = None
    reference_matches: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "markers": [m.to_dict() for m in self.markers],
            "celltypist_label": self.celltypist_label,
            "celltypist_prob": self.celltypist_prob,
            "reference_matches": self.reference_matches,
        }


def diagnose_dataset(path: Path, cluster_key: str = "") -> DatasetDiagnosis:
    warnings: list[str] = []
    if not path.exists():
        return DatasetDiagnosis(
            path=str(path),
            file_exists=False,
            readable=False,
            n_obs=None,
            n_vars=None,
            obs_keys=[],
            var_names_preview=[],
            cluster_key=cluster_key,
            cluster_count=None,
            cluster_sizes={},
            warnings=[f"Dataset file not found: {path}"],
        )

    if importlib.util.find_spec("anndata") is None:
        return DatasetDiagnosis(
            path=str(path),
            file_exists=True,
            readable=False,
            n_obs=None,
            n_vars=None,
            obs_keys=[],
            var_names_preview=[],
            cluster_key=cluster_key,
            cluster_count=None,
            cluster_sizes={},
            warnings=["anndata is not installed; cannot inspect .h5ad contents yet."],
        )

    try:
        import anndata as ad

        adata = ad.read_h5ad(path, backed="r")
    except Exception as exc:  # pragma: no cover - depends on optional anndata/h5ad internals
        return DatasetDiagnosis(
            path=str(path),
            file_exists=True,
            readable=False,
            n_obs=None,
            n_vars=None,
            obs_keys=[],
            var_names_preview=[],
            cluster_key=cluster_key,
            cluster_count=None,
            cluster_sizes={},
            warnings=[f"Failed to read h5ad: {exc}"],
        )

    obs_keys = list(map(str, adata.obs_keys()))
    var_names_preview = [str(name) for name in list(adata.var_names[:10])]
    cluster_sizes: dict[str, int] = {}
    cluster_count: int | None = None
    if cluster_key:
        if cluster_key in adata.obs:
            counts = adata.obs[cluster_key].astype(str).value_counts().sort_index()
            cluster_sizes = {str(index): int(value) for index, value in counts.items()}
            cluster_count = len(cluster_sizes)
        else:
            warnings.append(f"cluster_key '{cluster_key}' was not found in .obs")
    else:
        warnings.append("No cluster_key was provided.")

    umap_coords: dict[str, Any] = {}
    if cluster_key and cluster_sizes and "X_umap" in adata.obsm:
        try:
            umap_coords = _extract_umap_coords(adata, cluster_key, cluster_sizes, max_per_cluster=500)
        except Exception as exc:  # pragma: no cover
            warnings.append(f"Could not extract UMAP coordinates: {exc}")

    return DatasetDiagnosis(
        path=str(path),
        file_exists=True,
        readable=True,
        n_obs=int(adata.n_obs),
        n_vars=int(adata.n_vars),
        obs_keys=obs_keys,
        var_names_preview=var_names_preview,
        cluster_key=cluster_key,
        cluster_count=cluster_count,
        cluster_sizes=cluster_sizes,
        umap_coords=umap_coords,
        warnings=warnings,
    )


def _extract_umap_coords(
    adata: Any,
    cluster_key: str,
    cluster_sizes: dict[str, int],
    max_per_cluster: int = 500,
) -> dict[str, Any]:
    import numpy as np

    umap = adata.obsm["X_umap"]
    cluster_series = adata.obs[cluster_key].astype(str)
    rng = np.random.default_rng(42)

    coords: dict[str, Any] = {}
    for cluster_id in cluster_sizes:
        indices = np.where(cluster_series.values == cluster_id)[0]
        if len(indices) > max_per_cluster:
            indices = rng.choice(indices, max_per_cluster, replace=False)
        pts = umap[sorted(indices.tolist())]
        coords[cluster_id] = {
            "x": [round(float(v), 4) for v in pts[:, 0]],
            "y": [round(float(v), 4) for v in pts[:, 1]],
        }
    return coords


def compute_cluster_evidence(
    path: Path,
    cluster_key: str,
    n_top_genes: int = 20,
    reference_registry_path: Path | None = None,
) -> dict[str, ClusterEvidence]:
    """Compute per-cluster evidence: markers, CellTypist labels, reference matches."""
    if not path.exists() or importlib.util.find_spec("anndata") is None:
        return {}

    try:
        import anndata as ad
        adata = ad.read_h5ad(path)
    except Exception:  # pragma: no cover
        return {}

    if cluster_key not in adata.obs:
        return {}

    adata.obs[cluster_key] = adata.obs[cluster_key].astype(str)
    cluster_ids = sorted(adata.obs[cluster_key].unique().tolist())
    evidence: dict[str, ClusterEvidence] = {cid: ClusterEvidence(cluster_id=cid) for cid in cluster_ids}

    _fill_marker_evidence(adata, cluster_key, evidence, n_top_genes)
    _fill_marker_db_evidence(evidence)
    _fill_celltypist_evidence(adata, cluster_key, evidence)
    if reference_registry_path and reference_registry_path.exists():
        _fill_reference_evidence(evidence, reference_registry_path)

    return evidence


def _fill_marker_evidence(
    adata: Any,
    cluster_key: str,
    evidence: dict[str, ClusterEvidence],
    n_top_genes: int,
) -> None:
    if importlib.util.find_spec("scanpy") is None:
        return
    try:
        import scanpy as sc
        import numpy as np

        sc.settings.verbosity = 0
        sc.tl.rank_genes_groups(
            adata,
            groupby=cluster_key,
            method="wilcoxon",
            n_genes=n_top_genes,
            use_raw=False,
            key_added="rank_genes",
        )

        rgg = adata.uns["rank_genes"]
        names = rgg["names"]
        scores = rgg["scores"]
        logfcs = rgg.get("logfoldchanges", {})
        pvals = rgg.get("pvals_adj", {})

        for cluster_id in evidence:
            if cluster_id not in names.dtype.names:
                continue
            genes = names[cluster_id]
            sc_arr = scores[cluster_id] if cluster_id in scores.dtype.names else [0.0] * len(genes)
            lfc_arr = logfcs[cluster_id] if cluster_id in logfcs.dtype.names else [0.0] * len(genes)
            pv_arr = pvals[cluster_id] if cluster_id in pvals.dtype.names else [1.0] * len(genes)
            markers = [
                MarkerGene(
                    gene=str(g),
                    score=float(s),
                    log2fc=float(l),
                    pval_adj=float(p),
                )
                for g, s, l, p in zip(genes, sc_arr, lfc_arr, pv_arr)
                if str(g) != "nan"
            ]
            evidence[cluster_id].markers = markers
    except Exception:  # pragma: no cover - scanpy internals vary
        pass


def _fill_marker_db_evidence(evidence: dict[str, ClusterEvidence]) -> None:
    from scaudit.markers import lookup_cell_type

    for ev in evidence.values():
        query_genes = {m.gene for m in ev.markers if m.log2fc > 0.5 and m.pval_adj < 0.05}
        if not query_genes:
            continue
        db_matches = lookup_cell_type(query_genes)
        # Prepend builtin matches before any reference h5ad matches (added later)
        ev.reference_matches = db_matches + ev.reference_matches


def _fill_celltypist_evidence(
    adata: Any,
    cluster_key: str,
    evidence: dict[str, ClusterEvidence],
) -> None:
    if importlib.util.find_spec("celltypist") is None:
        return
    try:
        import celltypist

        model = celltypist.models.Model.load()
        predictions = celltypist.annotate(adata, model=model, majority_voting=True, over_clustering=cluster_key)
        votes = predictions.predicted_labels

        if hasattr(votes, "majority_voting"):
            col = votes["majority_voting"]
        elif cluster_key in votes.columns:
            col = votes[cluster_key]
        else:
            return

        for cluster_id in evidence:
            mask = adata.obs[cluster_key] == cluster_id
            if mask.sum() == 0:
                continue
            cluster_votes = col[mask]
            top_label = cluster_votes.value_counts().idxmax()
            top_prob = float(cluster_votes.value_counts(normalize=True).max())
            evidence[cluster_id].celltypist_label = str(top_label)
            evidence[cluster_id].celltypist_prob = round(top_prob, 3)
    except Exception:  # pragma: no cover
        pass


def _fill_reference_evidence(
    evidence: dict[str, ClusterEvidence],
    registry_path: Path,
) -> None:
    if importlib.util.find_spec("anndata") is None or importlib.util.find_spec("scanpy") is None:
        return
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover
        return

    query_marker_sets = _build_marker_sets(evidence)
    if not query_marker_sets:
        return

    for ref_id, ref_entry in registry.items():
        try:
            _match_one_reference(ref_id, ref_entry, evidence, query_marker_sets)
        except Exception:  # pragma: no cover - reference data may vary
            continue


def _build_marker_sets(evidence: dict[str, ClusterEvidence]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for cid, ev in evidence.items():
        genes = {m.gene for m in ev.markers if m.log2fc > 0.5 and m.pval_adj < 0.05}
        if genes:
            result[cid] = genes
    return result


def _match_one_reference(
    ref_id: str,
    ref_entry: dict[str, Any],
    evidence: dict[str, ClusterEvidence],
    query_marker_sets: dict[str, set[str]],
    n_top: int = 20,
) -> None:
    import anndata as ad
    import scanpy as sc

    manifest_path = Path(ref_entry.get("manifest_path", ""))
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ref_data_path = Path(manifest.get("path", ""))
    label_key = str(manifest.get("label_key", ""))
    if not ref_data_path.exists() or not label_key:
        return

    rdata = ad.read_h5ad(ref_data_path)
    if label_key not in rdata.obs:
        return

    rdata.obs[label_key] = rdata.obs[label_key].astype(str)
    sc.settings.verbosity = 0
    sc.tl.rank_genes_groups(rdata, groupby=label_key, method="wilcoxon", n_genes=n_top, use_raw=False)
    ref_rgg = rdata.uns["rank_genes"]

    for cell_type in ref_rgg["names"].dtype.names:
        ref_genes = {str(g) for g in ref_rgg["names"][cell_type] if str(g) != "nan"}
        for cid, query_genes in query_marker_sets.items():
            jaccard = _jaccard(query_genes, ref_genes)
            if jaccard > 0.05:
                evidence[cid].reference_matches.append(
                    {
                        "ref_id": ref_id,
                        "label": cell_type,
                        "jaccard": round(jaccard, 3),
                        "n_shared": len(query_genes & ref_genes),
                    }
                )

    for cid in evidence:
        matches = evidence[cid].reference_matches
        matches.sort(key=lambda m: m["jaccard"], reverse=True)
        evidence[cid].reference_matches = matches[:5]


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
