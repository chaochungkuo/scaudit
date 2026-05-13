<p align="center">
  <img src="docs/assets/scaudit-logo.svg" alt="scaudit logo" width="560">
</p>

<p align="center">
  <a href="https://github.com/chaochungkuo/scaudit"><img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white"></a>
  <a href="https://github.com/chaochungkuo/scaudit/blob/main/LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-2FB344"></a>
  <a href="https://github.com/chaochungkuo/scaudit"><img alt="Version: 0.1.0" src="https://img.shields.io/badge/version-0.1.0-6D5DF6"></a>
  <a href="https://github.com/chaochungkuo/scaudit"><img alt="Status: early MVP" src="https://img.shields.io/badge/status-early%20MVP-12B5CB"></a>
</p>

# scaudit

Transparent marker-based annotation audit framework for single-cell RNA-seq.

scaudit turns cluster annotation into structured evidence records, confidence calls, human-review tables, and static HTML reports — so every label is traceable, auditable, and reproducible.

**Core thesis**: annotation = Evidence + Reasoning + Decision.

Current status: marker-based provider-report MVP. The current vertical slice supports `.h5ad` diagnosis, config validation, run planning, marker evidence generation, curated/user marker database matching, optional LLM explanations, draft annotation cards, review tables, reproducibility records, static HTML reports, and focused qmd provider reports for method-level auditability.

---

## Quickstart

Use this path when you already have a clustered `.h5ad` file and know the cluster column.

```bash
# One-command annotation audit
scaudit annotate input.h5ad \
  --cluster-key leiden \
  --species mouse \
  --tissue heart \
  --out results/

# Open the report
open results/report/report.html
```

For the config-based workflow used by most provider comparisons:

```bash
scaudit init-config input.h5ad --out config.toml
scaudit validate config.toml
scaudit plan config.toml
scaudit run config.toml
open results/report/report.html
```

## Install

```bash
# Development (pixi)
pixi run scaudit --help

# Or directly
pip install -e .
```

## Use on real data

Use this workflow for a real clustered `.h5ad` file.

1. Create a config.

   ```bash
   pixi run scaudit init-config your_data.h5ad --out config.toml
   ```

   In Codex workspaces that require the local RTK wrapper, run:

   ```bash
   rtk pixi run scaudit init-config your_data.h5ad --out config.toml
   ```

2. Edit the required dataset fields.

   ```toml
   [dataset]
   path = "your_data.h5ad"
   species = "human"
   tissue = "blood"
   cluster_key = "leiden"
   sample_key = ""
   batch_key = ""
   ```

   `cluster_key` must exist in `adata.obs`. UMAP coordinates are recommended for the main report.

3. Configure marker databases.

   ```toml
   [cache]
   dir = "~/.cache/scaudit"

   [marker_databases.cellmarker]
   path = ""

   [marker_databases.panglaodb]
   path = ""

   [marker_databases.user_markers]
   path = "examples/templates/user_marker_genes.csv"
   name = "Project marker genes"

   [methods]
   marker_based = true

   [methods.marker_databases]
   cellmarker = true
   panglaodb = true
   user_markers = true

   [output]
   dir = "results"
   ```

   Empty CellMarker/PanglaoDB paths mean scaudit downloads them into the cache on first use and reuses them later. `user_markers.path` should point to a local CSV/TSV file.

4. Prepare user-defined marker genes if enabled.

   Start from `examples/templates/user_marker_genes.csv`:

   ```csv
   cell_type,gene,species,tissue,source,notes
   CD4 T cell,IL7R,human,blood,my_lab,
   B cell,MS4A1,human,blood,my_lab,
   Monocyte,LYZ,human,blood,my_lab,
   ```

5. Validate, plan, and run.

   ```bash
   pixi run scaudit validate config.toml
   pixi run scaudit plan config.toml
   pixi run scaudit run config.toml
   ```

   With RTK:

   ```bash
   rtk pixi run scaudit validate config.toml
   rtk pixi run scaudit plan config.toml
   rtk pixi run scaudit run config.toml
   ```

6. Open the report.

   ```bash
   open results/report/report.html
   ```

   Key outputs:

   ```text
   results/report/report.html
   results/review_table.csv
   results/marker_evidence.csv
   results/evidence_reports/marker_based/marker_based.html
   results/evidence_reports/cellmarker/cellmarker.html
   results/evidence_reports/panglaodb/panglaodb.html
   results/evidence_reports/user_markers/user_markers.html
   results/evidence_reports/cross_provider_summary.csv
   ```

7. Try the included PBMC3k example.

   The repository config is already set up for PBMC3k:

   ```bash
   pixi run scaudit run config.toml
   open examples/pbmc3k/results_llm/report/report.html
   ```

   With RTK:

   ```bash
   rtk pixi run scaudit run config.toml
   open examples/pbmc3k/results_llm/report/report.html
   ```

## User workflow

1. Prepare an input `.h5ad`.

   The dataset should contain a cluster column in `adata.obs`, such as `leiden`, `louvain`, or a project-specific clustering key. UMAP coordinates are recommended because the main report uses them for cluster overview plots.

2. Create a config file.

   ```bash
   scaudit init-config input.h5ad --out config.toml
   ```

   Edit the dataset fields:

   ```toml
   [dataset]
   path = "input.h5ad"
   species = "human"
   tissue = "blood"
   cluster_key = "leiden"
   sample_key = ""
   batch_key = ""
   ```

3. Choose evidence providers.

   Marker ranking is the core local evidence layer. Database providers compare those cluster markers against curated marker databases.

   ```toml
   [methods]
   marker_based = true

   [methods.marker_databases]
   cellmarker = true
   panglaodb = true
   user_markers = false
   ```

   If `path` is empty, scaudit downloads the database to the cache on first use and reuses it later.

   ```toml
   [marker_databases.cellmarker]
   path = ""

   [marker_databases.panglaodb]
   path = ""

   [marker_databases.user_markers]
   path = "examples/templates/user_marker_genes.csv"
   name = "Project marker genes"
   ```

4. Optionally prepare user-defined marker genes.

   Start from `examples/templates/user_marker_genes.csv`. Use one marker gene per row:

   ```csv
   cell_type,gene,species,tissue,source,notes
   CD4 T cell,IL7R,human,blood,my_lab,Naive T cell support
   B cell,MS4A1,human,blood,my_lab,
   Monocyte,LYZ,human,blood,paper_2025,
   ```

   The required columns are `cell_type` and `gene`. The optional columns are `species`, `tissue`, `source`, and `notes`. Enable the provider with:

   ```toml
   [methods.marker_databases]
   user_markers = true
   ```

5. Validate before running.

   ```bash
   scaudit validate config.toml
   scaudit plan config.toml
   ```

   `validate` checks config structure. `plan` shows which providers will run, skip, or need configuration.

6. Run the audit.

   ```bash
   scaudit run config.toml
   ```

   On the first database-backed run, scaudit may download CellMarker or PanglaoDB into the cache. User marker files are read from the configured local path. Later runs reuse cached provider databases and record paths and checksums in provider JSON.

7. Read the report.

   Open the main report first:

   ```bash
   open results/report/report.html
   ```

   Suggested reading order:

   1. Overview and UMAP: check cluster structure, confidence, and sample distribution.
   2. Provider status: confirm which evidence providers succeeded or skipped.
   3. Cross-provider summary: compare marker-based, CellMarker, PanglaoDB, and user marker labels per cluster.
   4. Review priorities: inspect clusters with disagreement, weak evidence, or missing evidence.
   5. Provider reports: open focused reports for marker-based evidence, CellMarker, PanglaoDB, and user markers.

8. Review and finalize.

   Edit the review table if manual decisions are needed, then import it:

   ```bash
   scaudit review import results/review_table.csv --run results/
   scaudit finalize results/ --out finalized/
   ```

## AI or agent workflow

Use this section when an AI coding agent or automation is operating the repository.

1. Read repository instructions first.

   In this workspace, read `AGENTS.md` and follow any referenced local instructions before running commands. Keep existing user changes intact; do not reset or revert unrelated work.

2. Prefer the config workflow.

   The expected end-to-end command sequence is:

   ```bash
   pixi run scaudit validate config.toml
   pixi run scaudit plan config.toml
   pixi run scaudit run config.toml
   ```

   In Codex workspaces that require the RTK wrapper, use the local wrapper required by `AGENTS.md`, for example:

   ```bash
   rtk pixi run scaudit run config.toml
   ```

3. Never simulate provider outputs.

   If a provider requires an external package, database, API key, or configured path, either configure it correctly or let scaudit report a skipped/warning state. Do not fabricate predictions, labels, scores, or provider JSON.

4. Keep provider boundaries explicit.

   Database-backed marker evidence belongs in marker database providers. Tool-backed annotation evidence belongs in official tool providers. LLMs are explain-only and must not become the decision source.

5. Preserve cache semantics.

   Reusable provider data should live outside the repository, usually under:

   ```toml
   [cache]
   dir = "~/.cache/scaudit"
   ```

   If a cache file is missing, scaudit should download and organize it. If it exists, scaudit should reuse it and record the local path and checksum.

6. Verify changes with tests and the PBMC3k run when behavior changes.

   ```bash
   pixi run test
   pixi run scaudit run config.toml
   ```

   For report or frontend changes, open `examples/pbmc3k/results_llm/report/report.html` and inspect the generated main report plus provider reports.

7. Keep reports reader-centered.

   The main report should summarize the workflow, UMAP, provider status, cross-provider comparison, review priorities, artifacts, and methods. Focused provider reports should share the same structure so readers can compare marker-based, CellMarker, PanglaoDB, user markers, and future providers without learning a new layout each time.

## Cache

scaudit stores reusable provider data outside the repository by default:

```toml
[cache]
dir = "~/.cache/scaudit"
```

Marker database providers use this cache when their explicit `path` is empty. On the first run, scaudit downloads and organizes the database under the cache root; later runs reuse the cached file and record the local path and checksum in provider JSON. Set `SCAUDIT_CACHE_DIR` or `[cache].dir` to move the cache.

Explicit provider paths still take precedence:

```toml
[marker_databases.cellmarker]
path = ""

[marker_databases.panglaodb]
path = ""

[marker_databases.user_markers]
path = "examples/templates/user_marker_genes.csv"
name = "Project marker genes"
```

A user-defined marker gene template is available at
`examples/templates/user_marker_genes.csv`. The expected format is one marker
gene per row, with required `cell_type` and `gene` columns plus optional
`species`, `tissue`, `source`, and `notes` columns.

## What scaudit produces

```text
results/
├── config.resolved.toml      # Exact parameters used
├── diagnosis.json            # Dataset structure, gene IDs, QC metadata, UMAP coords
├── marker_evidence.csv       # Cluster-level ranked markers
├── annotation_cards.json     # Per-cluster evidence + decisions
├── annotation_summary.csv    # Summary table
├── review_table.csv          # Editable human-review worksheet
├── reproducibility.json      # Versions, hashes, environment
├── report/
│   ├── report.html           # Interactive audit report (Plotly UMAP)
│   └── review.html           # In-browser review table with CSV download
└── evidence_reports/
    ├── provider_reports.json # Main-report index of focused provider reports
    ├── marker_based/         # qmd/html/json/tables/figures for marker evidence
    ├── cellmarker/           # qmd/html/json/tables for CellMarker database overlap
    ├── panglaodb/            # qmd/html/json/tables for PanglaoDB database overlap
    └── user_markers/         # qmd/html/json/tables for user-defined marker overlap
```

## Evidence sources (per cluster)

| Source | Method | Status |
|---|---|---|
| Marker genes | Scanpy Wilcoxon DE, top 20 per cluster | ✅ implemented |
| Builtin marker DB | Jaccard against ~60 curated cell-type gene sets | ✅ implemented |
| CellMarker 2.0 | Curated database overlap from configured CellMarker table | ✅ implemented |
| PanglaoDB | Curated mouse/human marker database overlap from configured PanglaoDB table | ✅ implemented |
| User marker genes | Local CSV/TSV marker list using `cell_type` and `gene` columns | ✅ implemented |
| LLM summaries | Explain marker evidence only; never decide labels | ✅ optional |
| ScType / scCATCH / SCSA | External marker tools | ⏸ intentionally skipped |
| CellTypist / scVI / scANVI | Model-based prediction | ⏸ out of scope |
| Reference h5ad mapping | External reference mapping | ⏸ out of scope |

## Decision states

| Decision | Meaning |
|---|---|
| **Accepted** | High confidence, all evidence layers agree |
| **Ambiguous** | Evidence sources disagree |
| **Needs review** | Moderate or incomplete evidence |
| **Unknown** | No usable evidence |
| **Artifact warning** | Very small cluster or QC signal |

## Full workflow

```bash
# Config-based workflow
scaudit init-config input.h5ad --out config.toml
scaudit validate config.toml
scaudit plan config.toml
scaudit run config.toml

# Import human review
scaudit review import results/review_table.csv --run results/

# Finalize
scaudit finalize results/ --out finalized/
```

Dataset inspection only:

```bash
scaudit diagnose input.h5ad --cluster-key leiden
```

## Environment check

```bash
scaudit doctor
```

## LLM configuration

LLM summaries are optional and explain-only. For an OpenAI-compatible endpoint such as KI Connect, put the URL and model in `config.toml` and keep the token in an environment variable:

```toml
[llm]
enabled = true
provider = "openai"
mode = "explain_only"
base_url = "https://chat.kiconnect.nrw/api/v1"
api_key_env = "KICONNECT_API_KEY"
model = "your-model-name"
temperature = 0
```

Then run:

```bash
export KICONNECT_API_KEY="..."
scaudit run config.toml
```

For one-command runs, `scaudit annotate ...` enables LLM summaries by default when an API key is configured; pass `--no-llm` to skip them.

## Roadmap

Near-term development is focused on transparent evidence providers and public-dataset validation:

| Stage | Status | Scope |
| --- | --- | --- |
| Public PBMC3k end-to-end run | ✅ implemented | `examples/pbmc3k/run.sh` exercises diagnosis, annotation, review import, and finalize. |
| Marker-based provider report | ✅ implemented | Focused qmd/html/json provider report with marker tables, signature scoring, and publication figure exports. |
| Conservative decision engine | 🚧 MVP implemented | Current labels use heuristic evidence agreement; next step is provider-JSON-driven decision logic. |
| Marker database provider reports | ✅ implemented | CellMarker 2.0, PanglaoDB, and user marker providers use explicit database provenance and shared overlap scoring. |
| External marker tools | ⏸ out of scope | ScType, scCATCH, and SCSA are intentionally disabled; no simulated predictions. |
| Reference/model mapping | ⏸ out of scope | Reference h5ad mapping, CellTypist, scVI, and scANVI are not part of the marker-based final check. |
| LLM explanation provider report | ⏳ optional | Explain-only report with model metadata and evidence payload provenance. |

## Development

```bash
pixi run test
pixi run scaudit --help
```

## Design principles

- Evidence is always explicit and traceable.
- The LLM explains but never decides.
- Confidence levels are conservative (low by default, high only with multi-source agreement).
- All outputs are static files — no server required.
- Graceful fallback when optional dependencies are absent.

## Project notes

See [`product-notes/`](product-notes/) for architecture decisions, roadmap, methods, and design philosophy.

See [`docs/provider-reports-design.md`](docs/provider-reports-design.md) for the focused qmd provider report design, callout usage, and evidence JSON contract. See [`docs/provider-dependency-management.md`](docs/provider-dependency-management.md) for the pixi environment strategy for Python, R-backed, and database-backed evidence providers.
