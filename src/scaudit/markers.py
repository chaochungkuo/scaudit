from __future__ import annotations

import csv
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Curated marker gene sets for common cell types.
# Format: {cell_type: [gene, ...]}  — symbols, human unless noted.
# Used as a lightweight label-proposal fallback for marker-based reports.

MARKER_DB: dict[str, list[str]] = {
    # ── Immune ──────────────────────────────────────────────────────────────
    "T cell": ["CD3D", "CD3E", "CD3G", "TRAC", "TRBC1", "TRBC2"],
    "CD4 T cell": ["CD3D", "CD4", "IL7R", "CD40LG", "CXCR3", "CCR7"],
    "CD8 T cell": ["CD3D", "CD8A", "CD8B", "GZMB", "GZMK", "PRF1", "NKG7"],
    "Regulatory T cell": ["CD3D", "CD4", "FOXP3", "IL2RA", "CTLA4", "IKZF2"],
    "NK cell": ["NCAM1", "GNLY", "NKG7", "KLRD1", "KLRB1", "FCGR3A", "TYROBP"],
    "B cell": ["CD19", "CD79A", "CD79B", "MS4A1", "BANK1", "IGHM"],
    "Plasma cell": ["IGHG1", "IGHG2", "MZB1", "SDC1", "XBP1", "PRDM1"],
    "Macrophage": ["CD68", "CSF1R", "MRC1", "MARCO", "LYVE1", "C1QA", "C1QB"],
    "Monocyte": ["CD14", "LYZ", "FCN1", "S100A8", "S100A9", "VCAN", "CSF3R"],
    "Classical monocyte": ["CD14", "LYZ", "VCAN", "S100A8", "FCN1", "CSF3R"],
    "Non-classical monocyte": ["FCGR3A", "CDKN1C", "HES4", "LILRA3", "LST1"],
    "Dendritic cell": ["CLEC9A", "CLEC10A", "CD1C", "FCER1A", "HLA-DQA1", "IRF4"],
    "Plasmacytoid DC": ["LILRA4", "CLEC4C", "IRF7", "SIGLEC6", "PTGDS"],
    "Neutrophil": ["ELANE", "MPO", "AZU1", "CAMP", "CEACAM8", "S100A8"],
    "Mast cell": ["TPSAB1", "CPA3", "KIT", "IL4", "HPGDS", "HDC"],
    "Basophil": ["FCER1A", "IL4", "CLC", "HDC", "PRG2"],
    "Eosinophil": ["SIGLEC8", "CLC", "PRG2", "EPX", "IL5RA"],
    # ── Epithelial ───────────────────────────────────────────────────────────
    "Epithelial cell": ["EPCAM", "CDH1", "KRT8", "KRT18", "KRT19", "KRT7"],
    "Enterocyte": ["FABP1", "APOA1", "SLC5A1", "ALDOB", "ANPEP", "VIL1"],
    "Goblet cell": ["MUC2", "FCGBP", "CLCA1", "TFF3", "SPDEF", "AGR2"],
    "Paneth cell": ["DEFA5", "DEFA6", "LYZ", "MUC2", "TFF3"],
    "Tuft cell": ["POU2F3", "TRPM5", "AVIL", "SH2D6", "PTPRT"],
    "Enteroendocrine cell": ["CHGA", "CHGB", "SCG5", "NEUROD1", "PAX4"],
    "Alveolar type 1": ["AGER", "PDPN", "CAV1", "HOPX", "AQP5"],
    "Alveolar type 2": ["SFTPC", "SFTPA1", "SFTPA2", "ABCA3", "SFTPB", "NKX2-1"],
    "Club cell": ["SCGB1A1", "SCGB3A2", "CYP2B6", "CYBA"],
    "Ciliated cell": ["FOXJ1", "TUBA1A", "DNAI1", "DNAH5", "CCDC40"],
    "Keratinocyte": ["KRT5", "KRT14", "KRT1", "KRT10", "DSG1", "TP63"],
    "Hepatocyte": ["ALB", "APOB", "APOC3", "CYP3A4", "SERPINA1", "F9"],
    "Cholangiocyte": ["EPCAM", "KRT7", "KRT19", "CLDN4", "CFTR", "ANXA4"],
    "Proximal tubule": ["SLC5A2", "CUBN", "LRP2", "UMOD", "SLC34A1"],
    "Collecting duct": ["AQP2", "CALB1", "ATP6V0D2", "FOXI1"],
    # ── Stromal ──────────────────────────────────────────────────────────────
    "Fibroblast": ["DCN", "COL1A1", "COL1A2", "LUM", "PDGFRA", "FAP", "THY1"],
    "Myofibroblast": ["ACTA2", "TAGLN", "MYH11", "ACTG2", "PDGFRB"],
    "Endothelial cell": ["PECAM1", "CDH5", "VWF", "ENG", "KDR", "ESAM", "ERG"],
    "Lymphatic endothelial": ["PROX1", "LYVE1", "CCL21", "PDPN", "FLT4"],
    "Pericyte": ["RGS5", "ACTA2", "PDGFRB", "CSPG4", "NOTCH3"],
    "Smooth muscle cell": ["ACTA2", "TAGLN", "MYH11", "CNN1", "MYLK"],
    "Adipocyte": ["ADIPOQ", "FABP4", "LEP", "PPARG", "CEBPA", "PLIN1"],
    # ── Cardiac ──────────────────────────────────────────────────────────────
    "Cardiomyocyte": ["MYH7", "MYH6", "TNNT2", "TNNI3", "ACTC1", "NPPA", "NPPB"],
    "Cardiac fibroblast": ["DCN", "COL1A1", "POSTN", "TCF21", "PDGFRA"],
    # ── Neural ───────────────────────────────────────────────────────────────
    "Neuron": ["RBFOX3", "MAP2", "TUBB3", "SNAP25", "SYP", "NCAM1"],
    "Excitatory neuron": ["SLC17A7", "SATB2", "CUX1", "RBFOX1"],
    "Inhibitory neuron": ["GAD1", "GAD2", "SLC32A1", "PVALB", "SST", "VIP"],
    "Astrocyte": ["GFAP", "AQP4", "S100B", "ALDH1L1", "SLC1A3", "CLU"],
    "Oligodendrocyte": ["MBP", "MOG", "OLIG2", "PLP1", "MAG", "CNP"],
    "OPC": ["PDGFRA", "CSPG4", "OLIG1", "SOX10", "ASCL1"],
    "Microglia": ["CX3CR1", "P2RY12", "TMEM119", "SALL1", "HEXB", "SIGLECH"],
    "Schwann cell": ["MPZ", "MBP", "S100B", "SOX10", "PLP1"],
    # ── Stem / progenitor ────────────────────────────────────────────────────
    "Hematopoietic stem cell": ["CD34", "KIT", "FLT3", "GATA2", "RUNX1"],
    "Erythrocyte": ["HBA1", "HBA2", "HBB", "GYPA", "ALAS2"],
    "Platelet": ["PPBP", "PF4", "GP1BA", "ITGA2B", "TUBB1"],
    "Erythroblast": ["GYPA", "GATA1", "KLF1", "TFRC", "HBB"],
}


def lookup_cell_type(
    query_genes: set[str],
    min_jaccard: float = 0.05,
    top_n: int = 5,
) -> list[dict]:
    """Return top matching cell types from the built-in marker DB.

    Args:
        query_genes: set of marker gene symbols (log2FC-filtered).
        min_jaccard: minimum Jaccard similarity to report.
        top_n: maximum number of matches to return.

    Returns:
        List of dicts sorted by Jaccard descending, each with
        {ref_id, label, jaccard, n_shared}.
    """
    results: list[dict] = []
    for cell_type, known_genes in MARKER_DB.items():
        known = set(known_genes)
        inter = len(query_genes & known)
        if inter == 0:
            continue
        jaccard = inter / len(query_genes | known)
        if jaccard >= min_jaccard:
            results.append(
                {
                    "ref_id": "builtin",
                    "label": cell_type,
                    "jaccard": round(jaccard, 3),
                    "n_shared": inter,
                }
            )
    results.sort(key=lambda x: x["jaccard"], reverse=True)
    return results[:top_n]


@dataclass(frozen=True)
class MarkerEvidenceResult:
    rows: list[dict[str, Any]]
    warnings: list[str]
    method: str


def compute_marker_evidence(dataset_path: Path, cluster_key: str, top_n: int = 10) -> MarkerEvidenceResult:
    if not dataset_path.exists():
        return MarkerEvidenceResult([], [f"Dataset file not found: {dataset_path}"], "scanpy.rank_genes_groups")
    if not cluster_key:
        return MarkerEvidenceResult([], ["cluster_key is required for marker evidence."], "scanpy.rank_genes_groups")
    if importlib.util.find_spec("scanpy") is None:
        return MarkerEvidenceResult([], ["scanpy is not installed; marker evidence was skipped."], "scanpy.rank_genes_groups")

    try:
        import scanpy as sc

        adata = sc.read_h5ad(dataset_path)
        if cluster_key not in adata.obs:
            return MarkerEvidenceResult(
                [],
                [f"cluster_key '{cluster_key}' was not found in .obs; marker evidence was skipped."],
                "scanpy.rank_genes_groups",
            )

        sc.tl.rank_genes_groups(adata, groupby=cluster_key, method="wilcoxon", n_genes=top_n)
        rows = marker_rows_from_rank_genes_groups(adata.uns["rank_genes_groups"], top_n=top_n)
        return MarkerEvidenceResult(rows, [], "scanpy.rank_genes_groups.wilcoxon")
    except Exception as exc:  # pragma: no cover - depends on optional scanpy/h5ad internals
        return MarkerEvidenceResult([], [f"Marker evidence failed: {exc}"], "scanpy.rank_genes_groups")


def marker_rows_from_rank_genes_groups(rank_result: Any, top_n: int = 10) -> list[dict[str, Any]]:
    names = rank_result.get("names")
    if names is None:
        return []

    groups = _rank_groups(names)
    rows: list[dict[str, Any]] = []
    for group in groups:
        for rank_index in range(min(top_n, len(names[group]))):
            row = {
                "cluster_id": str(group),
                "rank": rank_index + 1,
                "gene": _string_value(names[group][rank_index]),
                "score": _optional_float(rank_result.get("scores"), group, rank_index),
                "logfoldchange": _optional_float(rank_result.get("logfoldchanges"), group, rank_index),
                "pvalue": _optional_float(rank_result.get("pvals"), group, rank_index),
                "pvalue_adj": _optional_float(rank_result.get("pvals_adj"), group, rank_index),
            }
            rows.append(row)
    return rows


def attach_marker_evidence(annotation_cards: list[dict[str, Any]], marker_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows_by_cluster: dict[str, list[dict[str, Any]]] = {}
    for row in marker_rows:
        rows_by_cluster.setdefault(str(row["cluster_id"]), []).append(row)

    for card in annotation_cards:
        cluster_id = str(card.get("cluster_id", ""))
        evidence_rows = rows_by_cluster.get(cluster_id, [])
        markers = [
            {
                "gene": row["gene"],
                "rank": row["rank"],
                "score": row["score"],
                "logfoldchange": row["logfoldchange"],
                "pvalue_adj": row["pvalue_adj"],
            }
            for row in evidence_rows
        ]
        card.setdefault("evidence", {}).setdefault("markers", [])
        card["evidence"]["markers"] = markers
        if markers:
            card.setdefault("reasoning", {})["summary"] = "Marker evidence has been computed; decision assignment is pending."
            uncertainties = card.setdefault("reasoning", {}).setdefault("uncertainties", [])
            card["reasoning"]["uncertainties"] = [
                item for item in uncertainties if item != "No marker, model, or reference evidence has been computed yet."
            ]
    return annotation_cards


def write_marker_evidence_csv(path: Path, marker_rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["cluster_id", "rank", "gene", "score", "logfoldchange", "pvalue", "pvalue_adj"],
        )
        writer.writeheader()
        writer.writerows(marker_rows)


def _rank_groups(names: Any) -> list[str]:
    dtype_names = getattr(getattr(names, "dtype", None), "names", None)
    if dtype_names:
        return list(map(str, dtype_names))
    if isinstance(names, dict):
        return list(map(str, names.keys()))
    return []


def _optional_float(values: Any, group: str, rank_index: int) -> float | None:
    if values is None:
        return None
    try:
        return float(values[group][rank_index])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _string_value(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)
