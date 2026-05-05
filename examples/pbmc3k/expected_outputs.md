# Expected PBMC3k outputs

After running `pixi run bash examples/pbmc3k/run.sh`, the following files should exist:

```text
examples/pbmc3k/data/pbmc3k_scaudit.h5ad
examples/pbmc3k/results/config.resolved.toml
examples/pbmc3k/results/diagnosis.json
examples/pbmc3k/results/marker_evidence.csv
examples/pbmc3k/results/annotation_cards.json
examples/pbmc3k/results/annotation_summary.csv
examples/pbmc3k/results/review_table.csv
examples/pbmc3k/results/reproducibility.json
examples/pbmc3k/results/report/report.html
examples/pbmc3k/results/report/review.html
examples/pbmc3k/final/final_annotation_cards.json
examples/pbmc3k/final/final_annotation_summary.csv
examples/pbmc3k/final/review_audit.json
examples/pbmc3k/final/reproducibility.json
examples/pbmc3k/final/report/report.html
```

Minimum content checks:

- `diagnosis.json` has `readable: true`.
- `diagnosis.json` has `cluster_count` greater than zero.
- `marker_evidence.csv` has more than one row.
- At least one annotation card has non-empty `evidence.markers`.
- `report/report.html` contains `scaudit report`.
