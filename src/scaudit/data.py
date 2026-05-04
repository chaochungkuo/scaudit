from __future__ import annotations

import importlib.util
from dataclasses import dataclass
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
            "warnings": self.warnings,
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
        warnings=warnings,
    )
