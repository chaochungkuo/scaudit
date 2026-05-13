# User-Defined Marker Gene Template

Use `examples/templates/user_marker_genes.csv` as the starting point for a user-supplied marker database.

Required columns:

| Column | Meaning |
| --- | --- |
| `cell_type` | Annotation label or cell type name. |
| `gene` | Marker gene symbol. One row per marker gene. |

Optional columns:

| Column | Meaning |
| --- | --- |
| `species` | Species or organism, for example `human` or `mouse`. |
| `tissue` | Tissue, organ, or dataset context, for example `blood`. |
| `source` | Provenance label, such as `my_lab`, `paper_2025`, or `curator_initials`. |
| `notes` | Free-text notes for human review. |

Minimal valid file:

```csv
cell_type,gene
CD4 T cell,IL7R
CD4 T cell,CCR7
B cell,MS4A1
NK cell,NKG7
Monocyte,LYZ
```

Preferred file:

```csv
cell_type,gene,species,tissue,source,notes
CD4 T cell,IL7R,human,blood,my_lab,Naive T cell support
B cell,MS4A1,human,blood,my_lab,
Monocyte,LYZ,human,blood,paper_2025,
```

Keep gene symbols in the same naming system as the input dataset where possible. scaudit can normalize simple symbol case during matching, but it cannot infer every synonym or ortholog relationship from a free-text marker list.
