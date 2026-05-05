#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EXAMPLE_DIR="$ROOT_DIR/examples/pbmc3k"
DATA_DIR="$EXAMPLE_DIR/data"
RESULTS_DIR="$EXAMPLE_DIR/results"
FINAL_DIR="$EXAMPLE_DIR/final"
DATASET_PATH="$DATA_DIR/pbmc3k_scaudit.h5ad"

mkdir -p "$DATA_DIR"
rm -rf "$RESULTS_DIR" "$FINAL_DIR"

echo "[1/4] Preparing PBMC3k dataset"
python - "$DATASET_PATH" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

try:
    import scanpy as sc
    from sklearn.cluster import KMeans
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing optional dependency for this example: "
        f"{exc.name}. Install with: python -m pip install scanpy anndata pandas numpy scikit-learn"
    ) from exc

out_path = Path(sys.argv[1])
out_path.parent.mkdir(parents=True, exist_ok=True)
sc.settings.datasetdir = str(out_path.parent)

adata = sc.datasets.pbmc3k()
adata.var_names_make_unique()
adata.obs["sample"] = "pbmc3k"
sc.pp.filter_cells(adata, min_genes=200)
sc.pp.filter_genes(adata, min_cells=3)
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
adata.raw = adata.copy()
sc.pp.highly_variable_genes(adata, min_mean=0.0125, max_mean=3, min_disp=0.5)
sc.pp.scale(adata, max_value=10)
sc.tl.pca(adata, svd_solver="arpack")

kmeans = KMeans(n_clusters=8, random_state=42, n_init=10)
adata.obs["scaudit_cluster"] = kmeans.fit_predict(adata.obsm["X_pca"][:, :20]).astype(str)

try:
    sc.pp.neighbors(adata, n_neighbors=10, n_pcs=20)
    sc.tl.umap(adata, random_state=42)
except Exception:
    pass

adata.write_h5ad(out_path)
print(out_path)
PY

echo "[2/4] Running scaudit annotate"
PYTHONPATH="$ROOT_DIR/src" python -m scaudit annotate "$DATASET_PATH" \
  --cluster-key scaudit_cluster \
  --species human \
  --tissue blood \
  --sample-key sample \
  --out "$RESULTS_DIR" \
  --no-llm

echo "[3/4] Importing review table"
PYTHONPATH="$ROOT_DIR/src" python -m scaudit review import "$RESULTS_DIR/review_table.csv" --run "$RESULTS_DIR"

echo "[4/4] Finalizing"
PYTHONPATH="$ROOT_DIR/src" python -m scaudit finalize "$RESULTS_DIR" --out "$FINAL_DIR"

echo
echo "PBMC3k E2E complete"
echo "Report: $RESULTS_DIR/report/report.html"
