# PBMC3k end-to-end example

This example is the first public-dataset gate for scaudit.

It downloads the public Scanpy PBMC3k dataset, prepares a small clustered `.h5ad`, then runs:

```text
annotate -> review import -> finalize
```

The generated data and outputs are intentionally ignored by git:

```text
examples/pbmc3k/data/
examples/pbmc3k/results/
examples/pbmc3k/final/
```

## Requirements

This example needs optional single-cell dependencies that are not required for the lightweight CLI tests:

```bash
python -m pip install scanpy anndata pandas numpy scikit-learn
```

If the environment already has Scanpy, no extra install step is needed.

## Run

From the repository root:

```bash
pixi run bash examples/pbmc3k/run.sh
```

The script writes:

```text
examples/pbmc3k/data/pbmc3k_scaudit.h5ad
examples/pbmc3k/results/report/report.html
examples/pbmc3k/results/report/review.html
examples/pbmc3k/results/annotation_cards.json
examples/pbmc3k/results/marker_evidence.csv
examples/pbmc3k/results/review_table.csv
examples/pbmc3k/final/final_annotation_cards.json
examples/pbmc3k/final/final_annotation_summary.csv
```

## What this gate validates

- A real public `.h5ad` can be loaded and diagnosed.
- Cluster labels are present before annotation.
- Scanpy marker evidence populates `marker_evidence.csv`.
- Annotation cards contain non-empty marker evidence.
- The static HTML report is generated.
- Review import and finalize run without manual edits.

## Current limitations

The script assigns simple KMeans clusters over PCA coordinates. That keeps the example reproducible without requiring Leiden or igraph, but it is not intended as a best-practice PBMC analysis pipeline.
