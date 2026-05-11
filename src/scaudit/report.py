from __future__ import annotations

import html
import json
import math
import random as _rng
from pathlib import Path
from typing import Any


_BADGE_CLASS: dict[str, str] = {
    "Accepted": "badge-accepted",
    "Ambiguous": "badge-ambiguous",
    "Unknown": "badge-unknown",
    "Needs review": "badge-review",
    "Artifact warning": "badge-artifact",
}

_NEEDS_ATTENTION = {"Ambiguous", "Unknown", "Needs review", "Artifact warning"}

_PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.35.2.min.js"
_GITHUB_URL = "https://github.com/chaochungkuo/scaudit"
_LOGO_MARK = """
<svg class="logo-mark" viewBox="0 0 44 44" role="img" aria-label="scaudit logo">
  <circle cx="19" cy="19" r="12" fill="#f8fbff" stroke="#18324a" stroke-width="4"/>
  <path d="M28 28L37 37" stroke="#18324a" stroke-width="5" stroke-linecap="round"/>
  <circle cx="15" cy="17" r="2.2" fill="#6d5df6"/>
  <circle cx="21" cy="13" r="2" fill="#2f80ed"/>
  <circle cx="24" cy="20" r="2.4" fill="#12b5cb"/>
  <circle cx="17" cy="24" r="2.6" fill="#2fb344"/>
  <circle cx="25" cy="26" r="1.9" fill="#7c3aed"/>
</svg>
"""
_GITHUB_MARK = """
<svg class="github-mark" viewBox="0 0 16 16" aria-hidden="true">
  <path fill="currentColor" d="M8 0C3.58 0 0 3.67 0 8.2c0 3.63 2.29 6.7 5.47 7.79.4.08.55-.18.55-.4 0-.2-.01-.86-.01-1.56-2.01.38-2.53-.5-2.69-.96-.09-.23-.48-.96-.82-1.15-.28-.16-.68-.56-.01-.57.63-.01 1.08.59 1.23.83.72 1.24 1.87.89 2.33.68.07-.53.28-.89.51-1.1-1.78-.21-3.64-.91-3.64-4.03 0-.89.31-1.62.82-2.19-.08-.21-.36-1.04.08-2.16 0 0 .67-.22 2.2.84A7.43 7.43 0 0 1 8 3.95c.68 0 1.36.09 2 .27 1.53-1.06 2.2-.84 2.2-.84.44 1.12.16 1.95.08 2.16.51.57.82 1.3.82 2.19 0 3.13-1.87 3.82-3.65 4.03.29.26.54.76.54 1.53 0 1.1-.01 1.99-.01 2.26 0 .22.15.48.55.4A8.1 8.1 0 0 0 16 8.2C16 3.67 12.42 0 8 0Z"/>
</svg>
"""

_DECISION_COLOR: dict[str, str] = {
    "Accepted": "#2a9d5c",
    "Needs review": "#c9600a",
    "Ambiguous": "#d97706",
    "Unknown": "#8899aa",
    "Artifact warning": "#c0392b",
}

_CONFIDENCE_COLOR: dict[str, str] = {
    "high": "#2a9d5c",
    "medium": "#d97706",
    "low": "#c0392b",
    "unknown": "#8899aa",
}

_CLUSTER_PALETTE = [
    "#2f67c8",
    "#2a9d5c",
    "#d97706",
    "#7446a8",
    "#129a9f",
    "#c0392b",
    "#6b8e23",
    "#b45309",
    "#4b5563",
    "#be185d",
]


# ── Public API ────────────────────────────────────────────────────────────────


def render_draft_report(report_dir: Path, diagnosis_path: Path, annotation_cards_path: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    diagnosis = _read_json(diagnosis_path, {})
    cards = _read_json(annotation_cards_path, [])
    report_path = report_dir / "report.html"
    review_path = report_dir / "review.html"
    _write_report_html(report_path, diagnosis, cards, final=False)
    _write_review_html(review_path, cards)
    return report_path


def render_final_report(report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "report.html"
    _write_page(
        report_path,
        title="scaudit — final report",
        body="""
        <section class="hero">
          <p class="eyebrow">Final annotation audit</p>
          <h1>Final report</h1>
          <p>This final report skeleton confirms that final outputs were written.</p>
        </section>
        <section>
          <h2>Outputs written</h2>
          <ul>
            <li><code>final_annotation_cards.json</code></li>
            <li><code>final_annotation_summary.csv</code></li>
            <li><code>annotated.h5ad</code> when finalized with <code>--write-h5ad</code></li>
            <li><code>review_audit.json</code></li>
            <li><code>reproducibility.json</code></li>
          </ul>
        </section>
        """,
        back_link=None,
    )
    return report_path


# ── Report HTML ───────────────────────────────────────────────────────────────


def _write_report_html(
    path: Path, diagnosis: dict[str, Any], cards: list[dict[str, Any]], *, final: bool
) -> None:
    label = "Final annotation audit" if final else "Draft annotation audit"
    n_cells = diagnosis.get("n_obs") or "—"
    n_genes = diagnosis.get("n_vars") or "—"
    n_clusters = diagnosis.get("cluster_count") or len(cards) or "—"
    dataset_path = diagnosis.get("path") or "—"
    warnings = diagnosis.get("warnings") or []

    counts = _decision_counts(cards)
    attention = [c for c in cards if c.get("decision") in _NEEDS_ATTENTION]

    metrics = (
        _metric("Cells", n_cells)
        + _metric("Genes", n_genes)
        + _metric("Clusters", n_clusters)
        + _metric("Needs attention", len(attention), highlight=len(attention) > 0)
    )

    umap_html = _umap_section(cards, diagnosis) if cards else ""
    stack_html = _evidence_stack_section(cards) if cards else ""
    completeness_html = _evidence_completeness_section(cards) if cards else ""
    reference_html = _reference_match_section(cards) if cards else ""
    marker_html = _marker_expression_section(cards) if cards else ""
    attention_html = _attention_panel(attention) if attention else ""
    warning_html = _warning_list(warnings) if warnings else ""
    clusters_html = _cluster_list(cards)
    methods_html = _methods_section(diagnosis)

    body = f"""
    <section class="hero">
      <p class="eyebrow">{html.escape(label)}</p>
      <h1>scaudit report</h1>
      <p class="dataset-path">Dataset: <code>{html.escape(str(dataset_path))}</code></p>
      <div class="decision-summary">
        {"".join(_decision_pill(lbl, count) for lbl, count in counts.items() if count > 0)}
      </div>
    </section>
    <div class="metrics-grid">{metrics}</div>
    {umap_html}
    {stack_html}
    {completeness_html}
    {reference_html}
    {marker_html}
    {attention_html}
    {warning_html}
    {clusters_html}
    {methods_html}
    """

    _write_page(path, title="scaudit report", body=body, back_link=("review.html", "Review table →"))


# ── UMAP overview ─────────────────────────────────────────────────────────────


def _umap_section(cards: list[dict[str, Any]], diagnosis: dict[str, Any]) -> str:
    umap_coords = diagnosis.get("umap_coords") or {}
    has_real = bool(umap_coords)
    subtitle = "Interactive · hover for details" + ("" if has_real else " · placeholder layout")
    plotly_html = _umap_plotly(cards, umap_coords)
    return f"""
    <section class="umap-section">
      <div class="section-header">
        <h2>Cluster overview</h2>
        <span class="muted">{subtitle}</span>
      </div>
      {plotly_html}
    </section>
    """


def _umap_plotly(cards: list[dict[str, Any]], umap_coords: dict[str, Any] | None = None) -> str:
    """Generate an interactive Plotly UMAP scatter.

    Uses real coords from diagnosis['umap_coords'] when available; falls back to
    deterministic Gaussian blobs so the chart is always populated.
    """
    if not cards:
        return ""

    umap_coords = umap_coords or {}
    n = len(cards)
    max_count = max((c.get("provenance", {}).get("cell_count", 0) or 1) for c in cards) or 1
    rng = _rng.Random(1337)

    # Pre-compute Gaussian blob centers for placeholder layout
    centers: list[tuple[float, float]] = []
    for i in range(n):
        base_angle = 2 * math.pi * i / n - math.pi / 2
        r = 4.5 + rng.uniform(-0.6, 0.6)
        angle = base_angle + rng.uniform(-0.15, 0.15)
        centers.append((r * math.cos(angle), r * math.sin(angle)))

    cluster_traces: list[dict] = []
    confidence_points: dict[str, dict[str, list[Any]]] = {}
    sample_points: dict[str, dict[str, list[Any]]] = {}
    for i, card in enumerate(cards):
        count = card.get("provenance", {}).get("cell_count", 0) or 100
        decision = str(card.get("decision", "Unknown"))
        cluster_id = str(card.get("cluster_id", ""))
        proposed = str(card.get("proposed_label") or "")
        confidence = card.get("confidence", {})
        overall = str(confidence.get("overall") or "unknown")
        trace_name = proposed if proposed and proposed not in ("pending", "") else f"Cluster {cluster_id}"

        real = umap_coords.get(cluster_id)
        if real and real.get("x") and real.get("y"):
            xs = real["x"]
            ys = real["y"]
            samples = real.get("sample") or []
        else:
            cx, cy = centers[i]
            sigma = 1.0 + 1.5 * math.sqrt(count / max_count)
            n_dots = min(300, max(50, count // 15 + 40))
            xs = []
            ys = []
            samples = []
            for _ in range(n_dots):
                u1 = rng.random() or 1e-10
                u2 = rng.random()
                z0 = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
                z1 = math.sqrt(-2 * math.log(u1)) * math.sin(2 * math.pi * u2)
                xs.append(round(cx + sigma * z0, 3))
                ys.append(round(cy + sigma * z1, 3))

        hover = (
            f"<b>Cluster {cluster_id}</b><br>"
            f"Label: {html.escape(proposed or '—')}<br>"
            f"Decision: {html.escape(decision)}<br>"
            f"Confidence: {html.escape(overall)}<br>"
            f"Cells: {count:,}"
        )
        cluster_traces.append({
            "type": "scatter",
            "x": xs,
            "y": ys,
            "mode": "markers",
            "name": html.escape(f"Cluster {cluster_id}"),
            "text": [hover] * len(xs),
            "hovertemplate": "%{text}<extra></extra>",
            "marker": {"color": _CLUSTER_PALETTE[i % len(_CLUSTER_PALETTE)], "size": 5, "opacity": 0.55, "line": {"width": 0}},
        })
        _append_points(confidence_points, overall, xs, ys, [hover] * len(xs))
        if samples and len(samples) == len(xs):
            for sample, x, y in zip(samples, xs, ys):
                _append_points(sample_points, str(sample), [x], [y], [hover + f"<br>Sample: {html.escape(str(sample))}"])

    layout = {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "#f6f8fc",
        "showlegend": True,
        "legend": {
            "x": 0.01, "y": 0.99,
            "bgcolor": "rgba(255,255,255,0.88)",
            "bordercolor": "#dce4f0",
            "borderwidth": 1,
            "font": {"size": 11, "color": "#5d6b7c"},
        },
        "margin": {"l": 10, "r": 10, "t": 10, "b": 40},
        "xaxis": {
            "showticklabels": False, "showgrid": False, "zeroline": False, "showline": False,
            "title": {"text": "UMAP 1", "font": {"size": 11, "color": "#9aabb8"}},
            "scaleanchor": "y", "scaleratio": 1,
        },
        "yaxis": {
            "showticklabels": False, "showgrid": False, "zeroline": False, "showline": False,
            "title": {"text": "UMAP 2", "font": {"size": 11, "color": "#9aabb8"}},
        },
        "hovermode": "closest",
    }

    confidence_traces = _grouped_traces(confidence_points, _CONFIDENCE_COLOR)
    sample_traces = _grouped_traces(sample_points)
    trace_sets = {
        "cluster": cluster_traces,
        "confidence": confidence_traces,
    }
    if sample_traces:
        trace_sets["sample"] = sample_traces

    trace_sets_json = json.dumps(trace_sets)
    layout_json = json.dumps(layout)
    config_json = json.dumps({
        "responsive": True, "displaylogo": False,
        "modeBarButtonsToRemove": ["sendDataToCloud", "select2d", "lasso2d", "autoScale2d"],
    })

    return f"""
    <div style="position:relative;height:360px;border-radius:8px;border:1px solid var(--border);overflow:hidden;background:#f6f8fc">
      <div id="umap-loading" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:#f6f8fc;z-index:2;pointer-events:none">
        <p style="color:var(--muted);font-size:13px">Loading interactive UMAP&hellip; (requires internet access)</p>
      </div>
      <div class="umap-tabs" aria-label="UMAP color mode">
        <button type="button" class="umap-tab is-active" data-umap-mode="cluster">Clusters</button>
        <button type="button" class="umap-tab" data-umap-mode="confidence">Confidence</button>
        {'<button type="button" class="umap-tab" data-umap-mode="sample">Samples</button>' if sample_traces else ''}
      </div>
      <div id="umap-plot" style="width:100%;height:100%"></div>
    </div>
    <script async src="{_PLOTLY_CDN}" onload="scauditRenderPlots()"></script>
    <script>
    window.scauditUMAPTraces = {trace_sets_json};
    window.scauditUMAPLayout = {layout_json};
    window.scauditUMAPConfig = {config_json};
    window.scauditRenderUMAP = function() {{
      if (window.scauditUMAPRendered) {{ return; }}
      window.scauditUMAPRendered = true;
      document.getElementById('umap-loading').style.display = 'none';
      Plotly.newPlot('umap-plot', window.scauditUMAPTraces.cluster, window.scauditUMAPLayout, window.scauditUMAPConfig);
      document.querySelectorAll('[data-umap-mode]').forEach(function(button) {{
        button.addEventListener('click', function() {{
          var mode = button.getAttribute('data-umap-mode');
          document.querySelectorAll('[data-umap-mode]').forEach(function(item) {{ item.classList.remove('is-active'); }});
          button.classList.add('is-active');
          Plotly.react('umap-plot', window.scauditUMAPTraces[mode], window.scauditUMAPLayout, window.scauditUMAPConfig);
        }});
      }});
    }};
    window.scauditRenderPlots = function() {{
      if (window.scauditRenderUMAP) {{ window.scauditRenderUMAP(); }}
      if (window.scauditRenderReferenceHeatmap) {{ window.scauditRenderReferenceHeatmap(); }}
      if (window.scauditRenderMarkerHeatmap) {{ window.scauditRenderMarkerHeatmap(); }}
    }};
    </script>"""


def _append_points(target: dict[str, dict[str, list[Any]]], key: str, xs: list[Any], ys: list[Any], text: list[str]) -> None:
    bucket = target.setdefault(key or "unknown", {"x": [], "y": [], "text": []})
    bucket["x"].extend(xs)
    bucket["y"].extend(ys)
    bucket["text"].extend(text)


def _grouped_traces(groups: dict[str, dict[str, list[Any]]], colors: dict[str, str] | None = None) -> list[dict[str, Any]]:
    traces = []
    for index, (name, points) in enumerate(sorted(groups.items(), key=lambda item: item[0])):
        traces.append({
            "type": "scatter",
            "x": points["x"],
            "y": points["y"],
            "mode": "markers",
            "name": html.escape(str(name)),
            "text": points["text"],
            "hovertemplate": "%{text}<extra></extra>",
            "marker": {
                "color": (colors or {}).get(str(name), _CLUSTER_PALETTE[index % len(_CLUSTER_PALETTE)]),
                "size": 5,
                "opacity": 0.55,
                "line": {"width": 0},
            },
        })
    return traces


# ── Evidence stack overview ──────────────────────────────────────────────────


def _evidence_stack_section(cards: list[dict[str, Any]]) -> str:
    rows = [
        {
            "layer": "Marker-based evidence",
            "purpose": "Biological interpretability",
            "tools": "Scanpy rank_genes_groups; built-in marker DB; built-in marker signature scoring",
            "outputs": "DE markers, log2FC, padj, signature coverage/overlap, marker-set overlap",
            "authority": "Can support labels and confidence",
            "available": any(card.get("evidence", {}).get("markers") for card in cards),
        },
        {
            "layer": "Reference-based mapping",
            "purpose": "Biological grounding",
            "tools": "Local/reference h5ad matching; public reference registry",
            "outputs": "Reference labels, Jaccard, shared genes, reference metadata",
            "authority": "Can support labels and expose disagreement",
            "available": any(
                any(isinstance(ref, dict) and ref.get("ref_id") != "builtin" for ref in card.get("evidence", {}).get("references", []))
                for card in cards
            ),
        },
        {
            "layer": "Model-based prediction",
            "purpose": "Statistical inference",
            "tools": "CellTypist; future scVI/scANVI adapters",
            "outputs": "Predicted labels, probabilities, cluster-level votes",
            "authority": "Can support labels but is not directly comparable to reference scores",
            "available": any(card.get("evidence", {}).get("models") for card in cards),
        },
        {
            "layer": "Ontology reasoning",
            "purpose": "Hierarchical consistency",
            "tools": "Planned Cell Ontology layer",
            "outputs": "Lineage/subtype hierarchy, synonym normalization, conflict checks",
            "authority": "Planned consistency check, not yet active",
            "available": any(card.get("evidence", {}).get("ontology") for card in cards),
        },
        {
            "layer": "LLM explanation",
            "purpose": "Human-readable interpretation",
            "tools": "OpenAI-compatible or Anthropic provider",
            "outputs": "Grounded narrative summary from structured evidence",
            "authority": "Explanation only; cannot create labels or override decisions",
            "available": any(card.get("reasoning", {}).get("summary_source") == "llm" for card in cards),
        },
    ]
    row_html = "".join(_evidence_stack_row(row) for row in rows)
    return f"""
    <section class="evidence-stack-section">
      <div class="section-header">
        <h2>Evidence stack</h2>
        <span class="muted">Transparent roles, tools, and authority boundaries</span>
      </div>
      <div class="evidence-stack-grid">{row_html}</div>
    </section>
    """


def _evidence_stack_row(row: dict[str, Any]) -> str:
    status = "Active" if row["available"] else "Missing" if row["layer"] != "Ontology reasoning" else "Planned"
    status_class = "is-active" if row["available"] else "is-planned" if row["layer"] == "Ontology reasoning" else "is-missing"
    return (
        f'<article class="evidence-stack-card">'
        f'<div class="stack-card-head">'
        f'<h3>{html.escape(str(row["layer"]))}</h3>'
        f'<span class="stack-status {status_class}">{html.escape(status)}</span>'
        f"</div>"
        f'<p class="stack-purpose">{html.escape(str(row["purpose"]))}</p>'
        f'<dl class="stack-meta">'
        f'<dt>Tool/package</dt><dd>{html.escape(str(row["tools"]))}</dd>'
        f'<dt>Output</dt><dd>{html.escape(str(row["outputs"]))}</dd>'
        f'<dt>Decision role</dt><dd>{html.escape(str(row["authority"]))}</dd>'
        f"</dl>"
        f"</article>"
    )


# ── Evidence completeness ────────────────────────────────────────────────────


def _evidence_completeness_section(cards: list[dict[str, Any]]) -> str:
    rows = [_evidence_completeness_row(card) for card in cards]
    if not rows:
        return ""
    source_keys = ["markers", "marker_db", "model", "reference", "qc", "llm"]
    complete_count = sum(1 for row in rows if all(row["sources"][key] for key in source_keys))
    meta = f"{complete_count}/{len(rows)} clusters have all evidence sources"
    header = "".join(f"<th>{html.escape(label)}</th>" for label in ["Cluster", "Markers", "Marker DB", "Model", "Reference", "QC", "LLM"])
    body = "".join(_evidence_completeness_html(row) for row in rows)
    return f"""
    <section class="evidence-completeness">
      <div class="section-header">
        <h2>Evidence completeness</h2>
        <span class="muted">{html.escape(meta)}</span>
      </div>
      <div class="completeness-wrap">
        <table class="completeness-table">
          <thead><tr>{header}</tr></thead>
          <tbody>{body}</tbody>
        </table>
      </div>
    </section>
    """


def _evidence_completeness_row(card: dict[str, Any]) -> dict[str, Any]:
    evidence = card.get("evidence", {})
    reasoning = card.get("reasoning", {})
    references = evidence.get("references") or []
    sources = {
        "markers": bool(evidence.get("markers")),
        "marker_db": any(isinstance(ref, dict) and ref.get("ref_id") == "builtin" for ref in references),
        "model": bool(evidence.get("models")),
        "reference": any(isinstance(ref, dict) and ref.get("ref_id") != "builtin" for ref in references),
        "qc": bool(evidence.get("qc") or evidence.get("qc_warnings")),
        "llm": reasoning.get("summary_source") == "llm",
    }
    return {
        "cluster_id": str(card.get("cluster_id", "")),
        "decision": str(card.get("decision", "")),
        "sources": sources,
    }


def _evidence_completeness_html(row: dict[str, Any]) -> str:
    cluster_id = str(row["cluster_id"])
    sources = row["sources"]
    cells = "".join(_completeness_cell(bool(sources[key])) for key in ["markers", "marker_db", "model", "reference", "qc", "llm"])
    return (
        f"<tr>"
        f'<th><a href="#cluster-{html.escape(cluster_id)}">Cluster {html.escape(cluster_id)}</a></th>'
        f"{cells}"
        f"</tr>"
    )


def _completeness_cell(available: bool) -> str:
    label = "Present" if available else "Missing"
    css = "is-present" if available else "is-missing"
    symbol = "OK" if available else "NA"
    return f'<td><span class="completeness-dot {css}" title="{label}">{symbol}</span></td>'


# ── Reference match evidence ─────────────────────────────────────────────────


def _reference_match_section(cards: list[dict[str, Any]]) -> str:
    matrix = _reference_match_matrix(cards)
    if not matrix:
        return ""

    clusters = [str(card.get("cluster_id", "")) for card in cards]
    labels = [str(row["label"]) for row in matrix]
    z_values: list[list[float | None]] = []
    hover_text: list[list[str]] = []
    for row in matrix:
        label = str(row["label"])
        z_row: list[float | None] = []
        hover_row: list[str] = []
        for cluster_id in clusters:
            match = row["values"].get(cluster_id)
            if not isinstance(match, dict):
                z_row.append(None)
                hover_row.append(f"Reference label: {label}<br>Cluster: {cluster_id}<br>No reference match")
                continue
            jaccard = _optional_number(match.get("jaccard", match.get("similarity")))
            ref_id = str(match.get("ref_id") or match.get("reference") or "")
            shared = match.get("n_shared")
            if jaccard is None:
                z_row.append(None)
                hover_row.append(f"Reference label: {label}<br>Cluster: {cluster_id}<br>No reference score")
            else:
                z_row.append(jaccard)
                shared_text = f"<br>Shared genes: {shared}" if isinstance(shared, (int, float)) else ""
                hover_row.append(f"Reference: {ref_id}<br>Label: {label}<br>Cluster: {cluster_id}<br>Jaccard: {jaccard:.3f}{shared_text}")
        z_values.append(z_row)
        hover_text.append(hover_row)

    trace = {
        "type": "heatmap",
        "x": [f"Cluster {cluster_id}" for cluster_id in clusters],
        "y": labels,
        "z": z_values,
        "text": hover_text,
        "hovertemplate": "%{text}<extra></extra>",
        "zmin": 0,
        "zmax": max(0.2, max((value for row in z_values for value in row if isinstance(value, (int, float))), default=0.0)),
        "colorscale": [
            [0.0, "#f7fbff"],
            [0.25, "#deebf7"],
            [0.5, "#9ecae1"],
            [0.75, "#3182bd"],
            [1.0, "#08519c"],
        ],
        "colorbar": {
            "title": {"text": "Jaccard", "side": "right"},
            "len": 0.82,
            "thickness": 14,
            "outlinewidth": 0,
        },
        "xgap": 1,
        "ygap": 1,
    }
    height = max(280, min(720, 120 + len(labels) * 24))
    layout = {
        "height": height,
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "#ffffff",
        "margin": {"l": 132, "r": 66, "t": 10, "b": 76},
        "xaxis": {"tickangle": -35, "showgrid": False, "zeroline": False, "ticks": "", "title": {"text": ""}},
        "yaxis": {"autorange": "reversed", "showgrid": False, "zeroline": False, "ticks": "", "title": {"text": ""}},
        "font": {"family": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", "size": 12, "color": "#253447"},
    }
    config = {"responsive": True, "displaylogo": False}

    return f"""
    <section class="reference-section">
      <div class="section-header">
        <h2>Reference match matrix</h2>
        <span class="muted">External references · clusters × labels</span>
      </div>
      <div class="reference-plot-wrap">
        <div id="reference-heatmap-loading" class="reference-plot-loading">Loading reference match matrix&hellip; (requires internet access)</div>
        <div id="reference-heatmap" style="width:100%;height:{height}px"></div>
      </div>
      <script>
      window.scauditReferenceHeatmap = {{
        trace: {json.dumps(trace)},
        layout: {json.dumps(layout)},
        config: {json.dumps(config)}
      }};
      window.scauditRenderReferenceHeatmap = function() {{
        if (window.scauditReferenceHeatmapRendered) {{ return; }}
        window.scauditReferenceHeatmapRendered = true;
        var loading = document.getElementById('reference-heatmap-loading');
        if (loading) {{ loading.style.display = 'none'; }}
        Plotly.newPlot('reference-heatmap', [window.scauditReferenceHeatmap.trace], window.scauditReferenceHeatmap.layout, window.scauditReferenceHeatmap.config);
      }};
      if (window.Plotly) {{ window.scauditRenderReferenceHeatmap(); }}
      </script>
    </section>
    """


def _reference_match_matrix(cards: list[dict[str, Any]], *, max_labels: int = 40) -> list[dict[str, Any]]:
    labels: list[str] = []
    values_by_label: dict[str, dict[str, dict[str, Any]]] = {}
    for card in cards:
        cluster_id = str(card.get("cluster_id", ""))
        evidence = card.get("evidence", {})
        references = evidence.get("references") or []
        for match in references:
            if not isinstance(match, dict) or match.get("ref_id") == "builtin":
                continue
            label = str(match.get("label") or "")
            if not label:
                continue
            key = f"{match.get('ref_id', 'ref')}:{label}"
            if key not in values_by_label:
                labels.append(key)
                values_by_label[key] = {}
            values_by_label[key][cluster_id] = match
    return [{"label": label, "values": values_by_label[label]} for label in labels[:max_labels]]


# ── Marker expression evidence ───────────────────────────────────────────────


def _marker_expression_section(cards: list[dict[str, Any]]) -> str:
    matrix = _marker_heatmap_matrix(cards)
    if not matrix:
        return ""

    clusters = [str(card.get("cluster_id", "")) for card in cards]
    z_values: list[list[float | None]] = []
    hover_text: list[list[str]] = []
    finite_values = [
        abs(value)
        for row in matrix
        for value in row["values"].values()
        if isinstance(value, (int, float)) and math.isfinite(value)
    ]
    max_abs = max(finite_values, default=1.0)
    if max_abs <= 0:
        max_abs = 1.0

    for row in matrix:
        gene = str(row["gene"])
        z_row: list[float | None] = []
        hover_row: list[str] = []
        for cluster_id in clusters:
            value = row["values"].get(cluster_id)
            if value is None or not math.isfinite(value):
                z_row.append(None)
                hover_row.append(f"Gene: {gene}<br>Cluster: {cluster_id}<br>No marker evidence")
            else:
                z_row.append(value)
                hover_row.append(f"Gene: {gene}<br>Cluster: {cluster_id}<br>log2FC: {value:+.2f}")
        z_values.append(z_row)
        hover_text.append(hover_row)

    genes = [str(row["gene"]) for row in matrix]
    trace = {
        "type": "heatmap",
        "x": [f"Cluster {cluster_id}" for cluster_id in clusters],
        "y": genes,
        "z": z_values,
        "text": hover_text,
        "hovertemplate": "%{text}<extra></extra>",
        "zmin": -max_abs,
        "zmax": max_abs,
        "zmid": 0,
        "colorscale": [
            [0.0, "#2166ac"],
            [0.35, "#d1e5f0"],
            [0.5, "#f7f7f7"],
            [0.65, "#fddbc7"],
            [1.0, "#b2182b"],
        ],
        "colorbar": {
            "title": {"text": "log2FC", "side": "right"},
            "len": 0.82,
            "thickness": 14,
            "outlinewidth": 0,
        },
        "xgap": 1,
        "ygap": 1,
    }
    height = max(340, min(860, 120 + len(genes) * 18))
    layout = {
        "height": height,
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "#ffffff",
        "margin": {"l": 92, "r": 66, "t": 10, "b": 76},
        "xaxis": {
            "side": "bottom",
            "tickangle": -35,
            "showgrid": False,
            "zeroline": False,
            "ticks": "",
            "title": {"text": ""},
        },
        "yaxis": {
            "autorange": "reversed",
            "showgrid": False,
            "zeroline": False,
            "ticks": "",
            "title": {"text": ""},
        },
        "font": {"family": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", "size": 12, "color": "#253447"},
    }
    config = {"responsive": True, "displaylogo": False}

    return f"""
    <section class="marker-section">
      <div class="section-header">
        <h2>Marker expression evidence</h2>
        <span class="muted">Top mentioned genes · log2FC heatmap</span>
      </div>
      <div class="marker-plot-wrap">
        <div id="marker-heatmap-loading" class="marker-plot-loading">Loading marker heatmap&hellip; (requires internet access)</div>
        <div id="marker-heatmap" style="width:100%;height:{height}px"></div>
      </div>
      <script>
      window.scauditMarkerHeatmap = {{
        trace: {json.dumps(trace)},
        layout: {json.dumps(layout)},
        config: {json.dumps(config)}
      }};
      window.scauditRenderMarkerHeatmap = function() {{
        if (window.scauditMarkerHeatmapRendered) {{ return; }}
        window.scauditMarkerHeatmapRendered = true;
        var loading = document.getElementById('marker-heatmap-loading');
        if (loading) {{ loading.style.display = 'none'; }}
        Plotly.newPlot('marker-heatmap', [window.scauditMarkerHeatmap.trace], window.scauditMarkerHeatmap.layout, window.scauditMarkerHeatmap.config);
      }};
      if (window.Plotly) {{ window.scauditRenderMarkerHeatmap(); }}
      </script>
    </section>
    """


def _marker_heatmap_matrix(cards: list[dict[str, Any]], *, per_cluster: int = 5, max_genes: int = 40) -> list[dict[str, Any]]:
    genes: list[str] = []
    values_by_gene: dict[str, dict[str, float]] = {}
    for card in cards:
        cluster_id = str(card.get("cluster_id", ""))
        markers = _marker_dicts(card.get("evidence", {}).get("markers") or [])[:per_cluster]
        for marker in markers:
            gene = str(marker.get("gene") or "")
            value = _marker_log2fc(marker)
            if not gene or value is None:
                continue
            if gene not in values_by_gene:
                values_by_gene[gene] = {}
                genes.append(gene)
            values_by_gene[gene][cluster_id] = value

    return [{"gene": gene, "values": values_by_gene[gene]} for gene in genes[:max_genes]]


# ── Review HTML ───────────────────────────────────────────────────────────────


def _write_review_html(path: Path, cards: list[dict[str, Any]]) -> None:
    n_attention = sum(1 for c in cards if c.get("decision") in _NEEDS_ATTENTION)

    if cards:
        rows = "\n".join(_review_row(c) for c in cards)
        subtitle = f"{len(cards)} clusters"
        if n_attention:
            subtitle += f" · {n_attention} need attention"
        table_html = f"""
        <p class="instructions">
          Make your decisions below. When done, click
          <strong>Download review_table.csv</strong> then run:<br>
          <code>scaudit review import review_table.csv --run results/</code>
        </p>
        <div class="table-wrap">
          <table id="review-table">
            <thead>
              <tr>
                <th>Cluster</th>
                <th>Proposed label</th>
                <th>scaudit decision</th>
                <th>Your decision</th>
                <th>New label</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
        <div class="review-actions">
          <button class="btn-primary" onclick="downloadCSV()">
            Download review_table.csv
          </button>
        </div>
        """
    else:
        subtitle = "No clusters yet"
        table_html = "<p>No annotation cards have been generated yet. Run <code>scaudit run</code> first.</p>"

    body = f"""
    <section class="hero">
      <p class="eyebrow">Human review</p>
      <h1>Review table</h1>
      <p>{html.escape(subtitle)}</p>
    </section>
    <section>{table_html}</section>
    """

    _write_page(
        path,
        title="scaudit — review table",
        body=body,
        back_link=("report.html", "← Back to report"),
        extra_js=_REVIEW_JS,
    )


def _review_row(card: dict[str, Any]) -> str:
    cluster_id = html.escape(str(card.get("cluster_id", "")))
    proposed = html.escape(str(card.get("proposed_label") or ""))
    decision = str(card.get("decision", ""))
    confidence = str(card.get("confidence", {}).get("overall", ""))
    badge = _badge(decision)
    is_accepted = decision == "Accepted"
    selected_accept = "selected" if is_accepted else ""
    selected_ambiguous = "selected" if decision == "Ambiguous" else ""
    selected_unknown = "selected" if decision == "Unknown" else ""
    return (
        f'<tr data-cluster="{cluster_id}" data-proposed="{proposed}" '
        f'data-decision="{html.escape(decision)}" data-confidence="{html.escape(confidence)}">'
        f"<td>{cluster_id}</td>"
        f"<td>{proposed or '<em>pending</em>'}</td>"
        f"<td>{badge}</td>"
        f"<td>"
        f'<select class="review-action" onchange="toggleLabel(this)">'
        f'<option value="accepted" {selected_accept}>Accept</option>'
        f'<option value="changed">Change to...</option>'
        f'<option value="ambiguous" {selected_ambiguous}>Mark ambiguous</option>'
        f'<option value="unknown" {selected_unknown}>Mark unknown</option>'
        f"</select>"
        f"</td>"
        f'<td><input type="text" class="review-label" placeholder="New label..." style="visibility:hidden"></td>'
        f'<td><input type="text" class="review-note" placeholder="Note..."></td>'
        f"</tr>"
    )


# ── Cluster list ──────────────────────────────────────────────────────────────


def _cluster_list(cards: list[dict[str, Any]]) -> str:
    if not cards:
        return ""
    n_attention = sum(1 for c in cards if c.get("decision") in _NEEDS_ATTENTION)
    meta = f"{len(cards)} total"
    if n_attention:
        meta += f" · {n_attention} need attention"
    items = "\n".join(_cluster_card(c) for c in cards)
    return f"""
    <section>
      <div class="section-header">
        <h2>Clusters</h2>
        <span class="muted">{html.escape(meta)}</span>
      </div>
      {items}
    </section>
    """


def _cluster_card(card: dict[str, Any]) -> str:
    cluster_id = str(card.get("cluster_id", ""))
    proposed = str(card.get("proposed_label") or "")
    decision = str(card.get("decision", ""))
    confidence = card.get("confidence", {})
    overall = str(confidence.get("overall") or "—")
    lineage = str(confidence.get("lineage") or "—")
    subtype = str(confidence.get("subtype") or "—")
    provenance = card.get("provenance", {})
    cell_count = provenance.get("cell_count")
    reasoning = card.get("reasoning", {})
    summary = str(reasoning.get("summary") or "")
    summary_source = str(reasoning.get("summary_source") or "")
    summary_model = str(reasoning.get("summary_model") or "")
    supports = reasoning.get("supports") or []
    contradictions = reasoning.get("contradictions") or []
    uncertainties = reasoning.get("uncertainties") or []
    suggestions = reasoning.get("validation_suggestions") or []
    evidence = card.get("evidence", {})
    markers = evidence.get("markers") or []
    marker_signatures = evidence.get("marker_signatures") or []
    models = evidence.get("models") or []
    references = evidence.get("references") or []
    qc_metrics = evidence.get("qc") or {}
    composition = evidence.get("composition") or {}
    qc_warnings = evidence.get("qc_warnings") or []

    is_open = decision in _NEEDS_ATTENTION
    open_attr = " open" if is_open else ""
    badge = _badge(decision)
    cell_meta = f" · {cell_count:,} cells" if isinstance(cell_count, int) else ""

    body_parts: list[str] = []

    # ── Summary ──
    if summary:
        summary_badge = ""
        if summary_source == "llm":
            title = "Generated by LLM" if not summary_model else f"Generated by LLM model {summary_model}"
            summary_badge = f'<span class="summary-badge" title="{html.escape(title)}">LLM-generated</span>'
        body_parts.append(f'<p class="card-summary">{summary_badge}{html.escape(summary)}</p>')

    # ── Confidence ──
    conf_items = [("Lineage", lineage), ("Subtype", subtype), ("Overall", overall)]
    conf_html = "".join(
        f'<span class="conf-item">'
        f'<span class="conf-label">{k}</span>'
        f'<span class="conf-value conf-{html.escape(v.lower())}">{html.escape(v)}</span>'
        f"</span>"
        for k, v in conf_items
    )
    body_parts.append(f'<div class="conf-row">{conf_html}</div>')

    evidence_stack = _cluster_evidence_stack(
        markers=markers,
        marker_signatures=marker_signatures,
        models=models,
        references=references,
        qc_metrics=qc_metrics,
        composition=composition,
        qc_warnings=qc_warnings,
        reasoning=reasoning,
    )
    if evidence_stack:
        body_parts.append(evidence_stack)

    marker_bars = _marker_bar_block(markers)
    if marker_bars:
        body_parts.append(marker_bars)

    # ── Reasoning block ──
    r_parts: list[str] = []
    if supports:
        r_parts.append(_rblock("Supports", supports, "rblock-support"))
    if contradictions:
        r_parts.append(_rblock("Contradictions", contradictions, "rblock-conflict"))
    if uncertainties:
        r_parts.append(_rblock("Uncertain", uncertainties, "rblock-uncertain"))
    if suggestions:
        r_parts.append(_rblock("Suggested validation", suggestions, "rblock-suggest"))

    if r_parts:
        body_parts.append(
            f'<div class="card-block">'
            f'<p class="block-title">Reasoning</p>'
            f'{"".join(r_parts)}'
            f"</div>"
        )

    card_body = "\n".join(body_parts)
    proposed_label_html = f"· <strong>{html.escape(proposed)}</strong>" if proposed and proposed != "pending" else ""

    return (
        f'<details class="cluster-card" data-decision="{html.escape(decision)}"{open_attr} '
        f'id="cluster-{html.escape(cluster_id)}">\n'
        f"  <summary>\n"
        f"    {badge}\n"
        f"    <span class=\"cluster-label\">Cluster {html.escape(cluster_id)} {proposed_label_html}</span>\n"
        f"    <span class=\"cluster-meta\">{html.escape(overall)} confidence{html.escape(cell_meta)}</span>\n"
        f"  </summary>\n"
        f'  <div class="cluster-body">{card_body}</div>\n'
        f"</details>"
    )


def _cluster_evidence_stack(
    *,
    markers: list[Any],
    marker_signatures: list[Any],
    models: list[Any],
    references: list[Any],
    qc_metrics: Any,
    composition: Any,
    qc_warnings: list[Any],
    reasoning: dict[str, Any],
) -> str:
    layers = [
        _marker_evidence_layer(markers, marker_signatures, references),
        _reference_evidence_layer(references),
        _model_evidence_layer(models),
        _ontology_evidence_layer(),
        _llm_evidence_layer(reasoning),
        _qc_evidence_layer(qc_metrics, composition, qc_warnings),
    ]
    layer_html = "".join(layer for layer in layers if layer)
    if not layer_html:
        return ""
    return (
        f'<div class="card-block evidence-stack-block">'
        f'<p class="block-title">Evidence stack</p>'
        f'<div class="cluster-evidence-stack">{layer_html}</div>'
        f"</div>"
    )


def _evidence_layer(title: str, purpose: str, tool: str, rows: list[tuple[str, str]], *, status: str = "Active") -> str:
    rows_html = "".join(f"<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>" for k, v in rows)
    status_class = "is-active" if status == "Active" else "is-planned" if status == "Planned" else "is-missing"
    return (
        f'<section class="evidence-layer">'
        f'<div class="evidence-layer-head">'
        f'<h4>{html.escape(title)}</h4>'
        f'<span class="stack-status {status_class}">{html.escape(status)}</span>'
        f"</div>"
        f'<p class="layer-purpose">{html.escape(purpose)}</p>'
        f'<p class="layer-tool">{html.escape(tool)}</p>'
        f'<dl class="ev-list">{rows_html}</dl>'
        f"</section>"
    )


def _marker_evidence_layer(markers: list[Any], marker_signatures: list[Any], references: list[Any]) -> str:
    rows: list[tuple[str, str]] = []
    marker_dicts = _marker_dicts(markers)
    if marker_dicts:
        strong = [marker for marker in marker_dicts if _marker_strength_label(marker) == "strong"]
        moderate = [marker for marker in marker_dicts if _marker_strength_label(marker) == "moderate"]
        weak = [marker for marker in marker_dicts if _marker_strength_label(marker) == "weak"]
        rows.append(("Marker rule", "Strong: log2FC > 1 and padj < 0.01; moderate: log2FC > 0.5 and padj < 0.05"))
        rows.append(("Strength summary", f"{len(strong)} strong, {len(moderate)} moderate, {len(weak)} weak among top {len(marker_dicts)} markers"))
        rows.append(("Top statistics", _format_marker_statistics(marker_dicts[:6])))
    signature_rows = _format_marker_signatures(marker_signatures)
    if signature_rows:
        rows.append(("Signature scoring", signature_rows))
    builtin = [r for r in references if isinstance(r, dict) and r.get("ref_id") == "builtin"]
    if builtin:
        parts = []
        for r in builtin[:3]:
            lbl = str(r.get("label") or "")
            j = r.get("jaccard")
            j_str = f" ({j:.2f})" if isinstance(j, (int, float)) else ""
            shared = r.get("n_shared")
            shared_str = f", {shared} shared genes" if isinstance(shared, (int, float)) else ""
            parts.append(f"{lbl}{j_str}{shared_str}")
        rows.append(("Marker-set overlap", ", ".join(parts)))
    return _evidence_layer(
        "Marker-based evidence",
        "Biological interpretability",
        "Scanpy rank_genes_groups; built-in marker DB",
        rows or [("Status", "No marker evidence available for this cluster.")],
        status="Active" if rows else "Missing",
    )


def _format_marker_signatures(marker_signatures: list[Any]) -> str:
    parts = []
    for signature in marker_signatures[:3]:
        if not isinstance(signature, dict):
            continue
        label = str(signature.get("label") or "")
        coverage = _optional_number(signature.get("coverage"))
        overlap = _optional_number(signature.get("overlap_score"))
        matched = signature.get("matched_genes") or []
        matched_text = ", ".join(str(gene) for gene in matched[:5])
        if not label:
            continue
        metric_parts = []
        if coverage is not None:
            metric_parts.append(f"coverage {coverage:.0%}")
        if overlap is not None:
            metric_parts.append(f"overlap {overlap:.2f}")
        if matched_text:
            metric_parts.append(f"matched: {matched_text}")
        parts.append(f"{label} ({'; '.join(metric_parts)})")
    return "; ".join(parts)


def _format_marker_statistics(markers: list[dict[str, Any]]) -> str:
    parts = []
    for marker in markers:
        gene = str(marker.get("gene") or "")
        log2fc = _marker_log2fc(marker)
        score = _optional_number(marker.get("score"))
        pval = _optional_number(marker.get("pval_adj", marker.get("pvalue_adj")))
        if not gene:
            continue
        fields = []
        if log2fc is not None:
            fields.append(f"log2FC {log2fc:+.2f}")
        if pval is not None:
            fields.append(f"padj {_format_pvalue(pval)}")
        if score is not None:
            fields.append(f"score {score:.2f}")
        strength = _marker_strength_label(marker)
        fields.append(strength)
        parts.append(f"{gene} ({', '.join(fields)})")
    return "; ".join(parts)


def _marker_strength_label(marker: dict[str, Any]) -> str:
    pval = _optional_number(marker.get("pval_adj", marker.get("pvalue_adj")))
    log2fc = _marker_log2fc(marker)
    score = _optional_number(marker.get("score"))
    if pval is not None and pval >= 0.05:
        return "weak"
    if log2fc is None:
        return "moderate" if score is not None and score > 0 else "weak"
    if log2fc > 1.0 and (pval is None or pval < 0.01):
        return "strong"
    if log2fc > 0.5 and (pval is None or pval < 0.05):
        return "moderate"
    return "weak"


def _reference_evidence_layer(references: list[Any]) -> str:
    external = [r for r in references if isinstance(r, dict) and r.get("ref_id") != "builtin"]
    rows = []
    for r in external:
        ref_id = str(r.get("ref_id") or r.get("reference") or r.get("name") or "ref")
        lbl = str(r.get("label") or "")
        j = r.get("jaccard") or r.get("similarity")
        j_str = f" (J={j:.2f})" if isinstance(j, (int, float)) else ""
        rows.append((ref_id, f"{lbl}{j_str}"))
    return _evidence_layer(
        "Reference-based mapping",
        "Biological grounding",
        "Local/reference h5ad matching; public reference registry",
        rows or [("Status", "No external reference match available for this cluster.")],
        status="Active" if rows else "Missing",
    )


def _model_evidence_layer(models: list[Any]) -> str:
    rows = []
    for m in models:
        if isinstance(m, dict):
            name = str(m.get("model") or m.get("name") or "model")
            lbl = str(m.get("label") or "")
            prob = m.get("probability") or m.get("score")
            prob_str = f" ({prob:.0%})" if isinstance(prob, (int, float)) else ""
            rows.append((name, f"{lbl}{prob_str}"))
    return _evidence_layer(
        "Model-based prediction",
        "Statistical inference",
        "CellTypist; future scVI/scANVI adapters",
        rows or [("Status", "No model prediction available for this cluster.")],
        status="Active" if rows else "Missing",
    )


def _ontology_evidence_layer() -> str:
    return _evidence_layer(
        "Ontology reasoning",
        "Hierarchical consistency",
        "Planned Cell Ontology layer",
        [("Status", "Not active yet; planned for lineage/subtype consistency checks.")],
        status="Planned",
    )


def _llm_evidence_layer(reasoning: dict[str, Any]) -> str:
    source = str(reasoning.get("summary_source") or "")
    model = str(reasoning.get("summary_model") or "")
    summary = str(reasoning.get("summary") or "")
    rows = []
    if source == "llm":
        rows.append(("Model", model or "configured LLM"))
        rows.append(("Summary", summary))
    return _evidence_layer(
        "LLM explanation",
        "Human-readable interpretation",
        "OpenAI-compatible or Anthropic provider; explanation-only",
        rows or [("Status", "No LLM-generated explanation available for this cluster.")],
        status="Active" if rows else "Missing",
    )


def _qc_evidence_layer(qc_metrics: Any, composition: Any, qc_warnings: list[Any]) -> str:
    rows = []
    qc_line = _format_qc_metrics(qc_metrics)
    if qc_line:
        rows.append(("QC metrics", qc_line))
    composition_line = _format_composition(composition)
    if composition_line:
        rows.append(("Composition", composition_line))
    if qc_warnings:
        rows.append(("QC flags", "; ".join(str(w) for w in qc_warnings)))
    return _evidence_layer(
        "QC and artifact evidence",
        "Safety and artifact detection",
        "AnnData obs QC fields; sample/batch composition checks",
        rows or [("Status", "No QC or composition evidence available for this cluster.")],
        status="Active" if rows else "Missing",
    )


def _format_qc_metrics(qc_metrics: Any) -> str:
    if not isinstance(qc_metrics, dict):
        return ""
    labels = {
        "n_genes": "genes",
        "total_counts": "counts",
        "pct_counts_mt": "mito %",
        "doublet_score": "doublet",
    }
    parts = []
    for key in ("n_genes", "total_counts", "pct_counts_mt", "doublet_score"):
        metric = qc_metrics.get(key)
        if not isinstance(metric, dict):
            continue
        mean = metric.get("mean")
        median = metric.get("median")
        if not isinstance(mean, (int, float)) or not isinstance(median, (int, float)):
            continue
        parts.append(f"{labels[key]} median {median:g}, mean {mean:g}")
    return "; ".join(parts)


def _format_composition(composition: Any) -> str:
    if not isinstance(composition, dict):
        return ""
    parts = []
    for key in ("sample", "batch"):
        value = composition.get(key)
        if not isinstance(value, dict):
            continue
        dominant = str(value.get("dominant") or "")
        fraction = value.get("fraction")
        total = value.get("total")
        if not dominant or not isinstance(fraction, (int, float)):
            continue
        total_text = f", n={total}" if isinstance(total, int) else ""
        parts.append(f"{key} {dominant} {fraction:.0%}{total_text}")
    return "; ".join(parts)


def _marker_bar_block(markers: list[Any]) -> str:
    rows = _marker_dicts(markers)[:8]
    if not rows:
        return ""

    values = [_marker_log2fc(row) for row in rows]
    max_value = max((abs(value) for value in values if value is not None and math.isfinite(value)), default=0.0)
    if max_value <= 0:
        max_value = 1.0

    row_html = "".join(_marker_bar_row(row, max_value) for row in rows)
    if not row_html:
        return ""

    return (
        f'<div class="card-block marker-bars-block">'
        f'<p class="block-title">Marker expression</p>'
        f'<div class="marker-bars" role="table" aria-label="Marker expression log2FC">{row_html}</div>'
        f"</div>"
    )


def _marker_bar_row(marker: dict[str, Any], max_value: float) -> str:
    gene = str(marker.get("gene") or "")
    value = _marker_log2fc(marker)
    if not gene or value is None or not math.isfinite(value):
        return ""

    score = _optional_number(marker.get("score"))
    pval = _optional_number(marker.get("pval_adj", marker.get("pvalue_adj")))
    width = max(4.0, min(abs(value) / max_value, 1.0) * 100)
    bar_class = "marker-bar-positive" if value >= 0 else "marker-bar-negative"
    score_text = f"score {score:.2f}" if score is not None else ""
    pval_text = f"padj {_format_pvalue(pval)}" if pval is not None else ""
    meta = " · ".join(part for part in [f"log2FC {value:+.2f}", score_text, pval_text] if part)
    return (
        f'<div class="marker-bar-row" role="row">'
        f'<span class="marker-gene" role="cell">{html.escape(gene)}</span>'
        f'<span class="marker-bar-track" role="cell">'
        f'<span class="marker-bar {bar_class}" style="width:{width:.1f}%"></span>'
        f"</span>"
        f'<span class="marker-stat" role="cell">{html.escape(meta)}</span>'
        f"</div>"
    )


def _marker_dicts(markers: list[Any]) -> list[dict[str, Any]]:
    return [marker for marker in markers if isinstance(marker, dict) and marker.get("gene")]


def _marker_log2fc(marker: dict[str, Any]) -> float | None:
    return _optional_number(marker.get("log2fc", marker.get("logfoldchange")))


def _optional_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        try:
            number = float(str(value))
        except (TypeError, ValueError):
            return None
    return number if math.isfinite(number) else None


def _format_pvalue(value: float) -> str:
    if value == 0:
        return "<1e-300"
    if value < 0.001:
        return f"{value:.1e}"
    return f"{value:.3f}"


def _rblock(label: str, items: list[Any], css_class: str) -> str:
    items_html = "".join(f"<li>{html.escape(str(s))}</li>" for s in items)
    return (
        f'<div class="rblock {css_class}">'
        f'<p class="rblock-label">{html.escape(label)}</p>'
        f"<ul>{items_html}</ul>"
        f"</div>"
    )


# ── Attention panel ───────────────────────────────────────────────────────────


def _attention_panel(attention: list[dict[str, Any]]) -> str:
    items = ""
    for card in attention:
        cluster_id = str(card.get("cluster_id", ""))
        proposed = str(card.get("proposed_label") or "pending")
        decision = str(card.get("decision", ""))
        badge = _badge(decision)
        reasoning = card.get("reasoning", {})
        summary = str(reasoning.get("summary") or "")
        short = summary[:80] + "…" if len(summary) > 80 else summary
        items += (
            f"<li>"
            f'<a href="#cluster-{html.escape(cluster_id)}">Cluster {html.escape(cluster_id)}</a>'
            f" {badge} {html.escape(proposed)}"
            f'{f" — <span class=muted>{html.escape(short)}</span>" if short else ""}'
            f"</li>\n"
        )
    return f"""
    <section class="attention-panel">
      <p class="eyebrow">Needs attention</p>
      <ul>{items}</ul>
    </section>
    """


# ── Methods section ───────────────────────────────────────────────────────────


def _methods_section(diagnosis: dict[str, Any]) -> str:
    obs_keys = diagnosis.get("obs_keys") or []
    var_preview = diagnosis.get("var_names_preview") or []
    cluster_key = diagnosis.get("cluster_key") or "—"
    n_obs = diagnosis.get("n_obs") or "—"
    n_vars = diagnosis.get("n_vars") or "—"

    obs_html = ", ".join(html.escape(str(k)) for k in obs_keys) or "—"
    var_html = ", ".join(html.escape(str(v)) for v in var_preview[:5]) or "—"
    if len(var_preview) > 5:
        var_html += ", …"

    return f"""
    <details class="methods-section">
      <summary>Methods &amp; Reproducibility</summary>
      <div class="methods-body">
        <h3>Dataset</h3>
        <table class="info-table">
          <tr><td>Path</td><td><code>{html.escape(str(diagnosis.get("path") or "—"))}</code></td></tr>
          <tr><td>Cells</td><td>{html.escape(str(n_obs))}</td></tr>
          <tr><td>Genes</td><td>{html.escape(str(n_vars))}</td></tr>
          <tr><td>Cluster key</td><td><code>{html.escape(cluster_key)}</code></td></tr>
          <tr><td>Obs keys</td><td>{obs_html}</td></tr>
          <tr><td>Gene name preview</td><td>{var_html}</td></tr>
        </table>
        <h3>Methods status</h3>
        <p>Marker evidence, model evidence, and reference evidence are pending future milestones.</p>
        <h3>Reproducibility</h3>
        <p>See <code>../reproducibility.json</code> for the full machine-readable run record.</p>
      </div>
    </details>
    """


# ── Helpers ───────────────────────────────────────────────────────────────────


def _decision_counts(cards: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for card in cards:
        d = str(card.get("decision", ""))
        counts[d] = counts.get(d, 0) + 1
    return counts


def _decision_pill(label: str, count: int) -> str:
    cls = _BADGE_CLASS.get(label, "badge-unknown")
    return f'<span class="pill {html.escape(cls)}">{html.escape(str(count))} {html.escape(label)}</span>'


def _badge(decision: str) -> str:
    cls = _BADGE_CLASS.get(decision, "badge-unknown")
    return f'<span class="badge {html.escape(cls)}">{html.escape(decision)}</span>'


def _metric(label: str, value: object, *, highlight: bool = False) -> str:
    hl = " metric-highlight" if highlight else ""
    return (
        f'<div class="metric{hl}">'
        f"<span>{html.escape(label)}</span>"
        f"<strong>{html.escape(str(value))}</strong>"
        f"</div>"
    )


def _warning_list(warnings: list[str]) -> str:
    items = "\n".join(f"<li>{html.escape(str(w))}</li>" for w in warnings)
    return f'<section class="warning-panel"><ul>{items}</ul></section>'


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


# ── Page shell ────────────────────────────────────────────────────────────────


def _write_page(
    path: Path,
    title: str,
    body: str,
    back_link: tuple[str, str] | None,
    extra_js: str = "",
) -> None:
    nav_html = ""
    if back_link:
        href, label = back_link
        nav_html = f'<a href="{html.escape(href)}" class="nav-link">{html.escape(label)}</a>'
    github_html = (
        f'<a href="{html.escape(_GITHUB_URL)}" class="nav-link github-link" '
        f'target="_blank" rel="noopener noreferrer" aria-label="Open scaudit on GitHub">'
        f'{_GITHUB_MARK}<span>GitHub</span></a>'
    )

    path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>{_CSS}</style>
</head>
<body>
  <header>
    <a class="brand" href="{html.escape(_GITHUB_URL)}" target="_blank" rel="noopener noreferrer" aria-label="scaudit on GitHub">
      {_LOGO_MARK}
      <span class="logo">scaudit</span>
    </a>
    <nav class="nav-actions" aria-label="Report links">
      {nav_html}
      {github_html}
    </nav>
  </header>
  <main>{body}</main>
  {"<script>" + extra_js + "</script>" if extra_js else ""}
</body>
</html>
""",
        encoding="utf-8",
    )


# ── Styles ────────────────────────────────────────────────────────────────────

_CSS = """
  :root {
    --navy:    #071936;
    --blue:    #2c62c3;
    --teal:    #0e8f94;
    --green:   #2a9d5c;
    --purple:  #6e40c9;
    --orange:  #c9600a;
    --red:     #c0392b;
    --border:  #dce4f0;
    --muted:   #5d6b7c;
    --bg:      #f2f5fb;
    --card:    #ffffff;
    --shadow:  0 1px 3px rgba(7,25,54,0.07), 0 1px 2px rgba(7,25,54,0.04);
  }
  *, *::before, *::after { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--navy);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 15px;
    line-height: 1.6;
  }
  a { color: var(--blue); }

  /* ── Header ── */
  header {
    background: var(--card);
    border-bottom: 1px solid var(--border);
    padding: 10px 32px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    position: sticky;
    top: 0;
    z-index: 20;
    box-shadow: var(--shadow);
  }
  .brand {
    display: inline-flex;
    align-items: center;
    gap: 9px;
    color: var(--navy);
    text-decoration: none;
    min-width: 0;
  }
  .brand:hover .logo { color: var(--blue); }
  .logo-mark {
    width: 34px;
    height: 34px;
    flex: 0 0 auto;
  }
  .logo { font-weight: 800; font-size: 17px; letter-spacing: -0.3px; color: var(--navy); }
  .nav-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    flex-wrap: wrap;
  }
  .nav-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    color: var(--blue);
    text-decoration: none;
    padding: 6px 14px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--card);
    transition: background 0.1s;
  }
  .nav-link:hover { background: var(--bg); }
  .github-link {
    color: var(--navy);
  }
  .github-mark {
    width: 16px;
    height: 16px;
    flex: 0 0 auto;
  }
  @media (max-width: 560px) {
    header { padding: 10px 16px; }
    .logo { font-size: 16px; }
    .logo-mark { width: 30px; height: 30px; }
    .nav-link { padding: 5px 10px; }
  }

  /* ── Layout ── */
  main { max-width: 920px; margin: 0 auto; padding: 28px 24px 72px; }
  h1 { font-size: 26px; font-weight: 800; margin: 6px 0 12px; letter-spacing: -0.3px; }
  h2 { font-size: 16px; font-weight: 700; margin: 0 0 14px; }
  h3 { font-size: 12px; font-weight: 700; margin: 18px 0 8px; color: var(--muted);
       text-transform: uppercase; letter-spacing: 0.06em; }
  .eyebrow {
    font-size: 11px; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--teal); margin: 0 0 4px;
  }
  section, .hero {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 22px 24px;
    margin-bottom: 16px;
    box-shadow: var(--shadow);
  }
  .hero { padding: 24px 26px; }
  .dataset-path { font-size: 13px; color: var(--muted); margin: 4px 0 12px; }
  .decision-summary { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
  .section-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 14px; }
  .muted { color: var(--muted); font-size: 13px; }
  code { background: #eef2f9; padding: 2px 5px; border-radius: 4px; font-size: 12px; font-family: "SF Mono", "Fira Code", monospace; }

  /* ── Metrics ── */
  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 12px;
    margin-bottom: 16px;
  }
  .metric {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px 18px;
    box-shadow: var(--shadow);
  }
  .metric-highlight { border-color: var(--orange); }
  .metric span { display: block; font-size: 11px; color: var(--muted); font-weight: 700;
                 text-transform: uppercase; letter-spacing: 0.06em; }
  .metric strong { display: block; font-size: 28px; font-weight: 800; margin-top: 4px; }
  .metric-highlight strong { color: var(--orange); }

  /* ── UMAP section ── */
  .umap-section { padding: 20px 24px; }
  .umap-section .section-header { margin-bottom: 12px; }
  .umap-tabs {
    position: absolute;
    top: 10px;
    right: 10px;
    z-index: 3;
    display: flex;
    gap: 4px;
    padding: 4px;
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(7, 25, 54, 0.08);
  }
  .umap-tab {
    border: 0;
    border-radius: 6px;
    background: transparent;
    color: var(--muted);
    font-size: 12px;
    font-weight: 700;
    padding: 6px 9px;
    cursor: pointer;
  }
  .umap-tab:hover { background: #eef2f9; color: var(--navy); }
  .umap-tab.is-active { background: var(--navy); color: white; }

  /* ── Evidence stack overview ── */
  .evidence-stack-section {
    padding: 20px 24px;
  }
  .evidence-stack-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 10px;
  }
  .evidence-stack-card {
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 14px;
    background: #fbfcff;
  }
  .stack-card-head,
  .evidence-layer-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 8px;
  }
  .evidence-stack-card h3,
  .evidence-layer h4 {
    margin: 0;
    color: var(--navy);
    font-size: 13px;
    font-weight: 800;
    text-transform: none;
    letter-spacing: 0;
  }
  .stack-status {
    flex: 0 0 auto;
    border-radius: 999px;
    padding: 2px 7px;
    font-size: 10px;
    font-weight: 800;
    line-height: 1.4;
  }
  .stack-status.is-active { background: #e3f5ec; color: #1a6b3c; }
  .stack-status.is-missing { background: #eef0f4; color: var(--muted); }
  .stack-status.is-planned { background: #fff3e0; color: #b45309; }
  .stack-purpose {
    margin: 6px 0 8px;
    color: var(--teal);
    font-size: 12px;
    font-weight: 700;
  }
  .stack-meta {
    display: grid;
    grid-template-columns: 88px 1fr;
    gap: 5px 10px;
    margin: 0;
    font-size: 12px;
  }
  .stack-meta dt {
    color: var(--muted);
    font-weight: 700;
  }
  .stack-meta dd {
    margin: 0;
    color: var(--navy);
    line-height: 1.4;
  }

  /* ── Evidence completeness ── */
  .evidence-completeness {
    padding: 20px 24px;
  }
  .completeness-wrap {
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: 8px;
  }
  .completeness-table {
    width: 100%;
    min-width: 640px;
    border-collapse: collapse;
    font-size: 12px;
  }
  .completeness-table th,
  .completeness-table td {
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
    text-align: center;
    white-space: nowrap;
  }
  .completeness-table tr:last-child th,
  .completeness-table tr:last-child td { border-bottom: none; }
  .completeness-table thead th {
    background: #f7f9fc;
    color: var(--muted);
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .completeness-table tbody th {
    text-align: left;
    font-weight: 700;
  }
  .completeness-table tbody th a {
    color: var(--navy);
    text-decoration: none;
  }
  .completeness-table tbody th a:hover { color: var(--blue); text-decoration: underline; }
  .completeness-dot {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 20px;
    border-radius: 999px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.03em;
  }
  .completeness-dot.is-present { background: #e3f5ec; color: #1a6b3c; }
  .completeness-dot.is-missing { background: #eef0f4; color: var(--muted); }

  /* ── Reference match matrix ── */
  .reference-section {
    margin-bottom: 16px;
  }
  .reference-plot-wrap {
    position: relative;
    min-height: 280px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--card);
    box-shadow: var(--shadow);
    overflow: hidden;
  }
  .reference-plot-loading {
    position: absolute;
    inset: 0;
    z-index: 2;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--card);
    color: var(--navy);
    font-size: 13px;
  }

  /* ── Marker expression overview ── */
  .marker-section {
    margin-bottom: 16px;
  }
  .marker-plot-wrap {
    position: relative;
    min-height: 340px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--card);
    box-shadow: var(--shadow);
    overflow: hidden;
  }
  .marker-plot-loading {
    position: absolute;
    inset: 0;
    z-index: 2;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--card);
    color: var(--navy);
    font-size: 13px;
  }

  /* ── Attention panel ── */
  .attention-panel {
    background: #fffaf2;
    border: 1px solid #f0c46a;
    border-radius: 10px;
    padding: 18px 22px;
    margin-bottom: 16px;
    box-shadow: var(--shadow);
  }
  .attention-panel ul { margin: 8px 0 0; padding-left: 0; list-style: none; }
  .attention-panel li { padding: 6px 0; border-bottom: 1px solid #f0d9a0; font-size: 14px; }
  .attention-panel li:last-child { border-bottom: none; }
  .attention-panel a { color: var(--navy); font-weight: 700; text-decoration: none; }
  .attention-panel a:hover { color: var(--blue); text-decoration: underline; }

  /* ── Warning panel ── */
  .warning-panel {
    background: #fffaf2;
    border: 1px solid #f0c46a;
    border-radius: 10px;
    padding: 14px 20px;
    margin-bottom: 16px;
    box-shadow: var(--shadow);
  }
  .warning-panel ul { margin: 0; padding-left: 18px; font-size: 13px; }

  /* ── Badges and pills ── */
  .badge {
    display: inline-block; font-size: 11px; font-weight: 700;
    padding: 2px 8px; border-radius: 99px; white-space: nowrap; flex-shrink: 0;
  }
  .pill {
    display: inline-block; font-size: 12px; font-weight: 700;
    padding: 3px 11px; border-radius: 99px;
  }
  .badge-accepted,  .pill.badge-accepted  { background: #e3f5ec; color: #1a6b3c; }
  .badge-ambiguous, .pill.badge-ambiguous { background: #fff3e0; color: #b45309; }
  .badge-unknown,   .pill.badge-unknown   { background: #eef0f4; color: var(--muted); }
  .badge-review,    .pill.badge-review    { background: #fff0e6; color: #c9600a; }
  .badge-artifact,  .pill.badge-artifact  { background: #fde8e8; color: var(--red); }

  /* ── Cluster cards ── */
  .cluster-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-left: 3px solid var(--border);
    border-radius: 8px;
    margin-bottom: 8px;
    overflow: hidden;
    box-shadow: var(--shadow);
  }
  .cluster-card[data-decision="Accepted"]        { border-left-color: var(--green); }
  .cluster-card[data-decision="Needs review"]    { border-left-color: var(--orange); }
  .cluster-card[data-decision="Ambiguous"]       { border-left-color: #d97706; }
  .cluster-card[data-decision="Unknown"]         { border-left-color: var(--muted); }
  .cluster-card[data-decision="Artifact warning"]{ border-left-color: var(--red); }

  .cluster-card summary {
    display: flex; align-items: center; gap: 10px;
    padding: 12px 16px;
    cursor: pointer; user-select: none; list-style: none;
  }
  .cluster-card summary::-webkit-details-marker { display: none; }
  .cluster-card summary::before {
    content: "▶"; font-size: 9px; color: var(--muted);
    margin-right: 2px; transition: transform 0.15s; flex-shrink: 0;
  }
  .cluster-card[open] > summary::before { transform: rotate(90deg); }
  .cluster-card summary:hover { background: #fafbfd; }

  .cluster-label { font-size: 14px; font-weight: 600; flex: 1; }
  .cluster-meta  { font-size: 12px; color: var(--muted); white-space: nowrap; }

  /* ── Cluster card body ── */
  .cluster-body {
    padding: 14px 20px 18px 42px;
    border-top: 1px solid var(--border);
    font-size: 13.5px;
  }
  .card-summary {
    color: var(--muted);
    margin: 0 0 12px;
    font-size: 13px;
    line-height: 1.5;
  }
  .summary-badge {
    display: inline-flex;
    align-items: center;
    margin-right: 8px;
    padding: 2px 7px;
    border: 1px solid #c7d2fe;
    border-radius: 999px;
    background: #eef2ff;
    color: #3730a3;
    font-size: 11px;
    font-weight: 700;
    line-height: 1.2;
    white-space: nowrap;
  }

  /* Confidence row */
  .conf-row { display: flex; gap: 20px; margin: 0 0 4px; }
  .conf-item { display: flex; flex-direction: column; }
  .conf-label {
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.07em; color: var(--muted);
  }
  .conf-value { font-size: 13px; font-weight: 700; margin-top: 1px; }
  .conf-high    { color: var(--green); }
  .conf-medium  { color: var(--orange); }
  .conf-low     { color: var(--red); }
  .conf-unknown { color: var(--muted); }
  .conf-—       { color: var(--muted); }

  /* Evidence block */
  .card-block {
    margin-top: 14px;
    padding-top: 12px;
    border-top: 1px solid var(--border);
  }
  .block-title {
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.08em; color: var(--muted); margin: 0 0 8px;
  }
  .ev-list {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 5px 14px;
    margin: 0;
  }
  .ev-list dt {
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.06em; color: var(--muted);
    white-space: nowrap; padding-top: 1px;
  }
  .ev-list dd {
    margin: 0; font-size: 13px; line-height: 1.5;
    word-break: break-word;
  }
  .evidence-stack-block {
    overflow: hidden;
  }
  .cluster-evidence-stack {
    display: grid;
    gap: 8px;
  }
  .evidence-layer {
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 12px;
    background: #fbfcff;
  }
  .layer-purpose {
    margin: 4px 0 2px;
    color: var(--teal);
    font-size: 12px;
    font-weight: 700;
  }
  .layer-tool {
    margin: 0 0 8px;
    color: var(--muted);
    font-size: 12px;
  }
  .marker-bars-block {
    overflow: hidden;
  }
  .marker-bars {
    display: grid;
    gap: 6px;
  }
  .marker-bar-row {
    display: grid;
    grid-template-columns: minmax(68px, 110px) minmax(90px, 1fr) minmax(135px, auto);
    gap: 10px;
    align-items: center;
    min-height: 22px;
  }
  .marker-gene {
    color: var(--navy);
    font-size: 12px;
    font-weight: 700;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .marker-bar-track {
    display: block;
    height: 7px;
    border-radius: 999px;
    background: #edf1f7;
    overflow: hidden;
  }
  .marker-bar {
    display: block;
    height: 100%;
    border-radius: inherit;
  }
  .marker-bar-positive { background: var(--green); }
  .marker-bar-negative { background: var(--red); }
  .marker-stat {
    color: var(--muted);
    font-size: 12px;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  @media (max-width: 720px) {
    .marker-bar-row {
      grid-template-columns: minmax(64px, 88px) minmax(70px, 1fr);
      gap: 6px 8px;
    }
    .marker-stat {
      grid-column: 2;
      white-space: normal;
    }
  }

  /* Reasoning blocks */
  .rblock {
    margin: 6px 0;
    padding: 8px 12px;
    border-radius: 6px;
    border-left: 3px solid var(--border);
    background: var(--bg);
    font-size: 13px;
  }
  .rblock ul { margin: 4px 0 0; padding-left: 16px; }
  .rblock li { margin: 2px 0; line-height: 1.5; }
  .rblock-label {
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.07em; color: var(--muted); margin: 0 0 4px;
  }
  .rblock-support  { border-left-color: var(--green);  background: #f2fbf5; }
  .rblock-conflict { border-left-color: var(--orange); background: #fff8f0; }
  .rblock-uncertain{ border-left-color: var(--muted);  background: var(--bg); }
  .rblock-suggest  { border-left-color: var(--blue);   background: #f0f5ff; }

  /* ── Methods section ── */
  .methods-section {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    margin-top: 16px;
    overflow: hidden;
    box-shadow: var(--shadow);
  }
  .methods-section > summary {
    padding: 15px 22px; cursor: pointer; font-weight: 700; font-size: 14px;
    color: var(--muted); user-select: none; list-style: none;
    display: flex; align-items: center; gap: 8px;
  }
  .methods-section > summary::-webkit-details-marker { display: none; }
  .methods-section > summary::before { content: "▶"; font-size: 9px; }
  .methods-section[open] > summary::before { transform: rotate(90deg); }
  .methods-body { padding: 4px 22px 20px; border-top: 1px solid var(--border); }
  .info-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .info-table td { padding: 6px 8px; border-bottom: 1px solid var(--border); }
  .info-table td:first-child { color: var(--muted); font-weight: 600; width: 140px; }

  /* ── Review table ── */
  .instructions { font-size: 13px; color: var(--muted); margin: 0 0 18px; line-height: 1.7; }
  .table-wrap { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th {
    text-align: left; padding: 8px 10px;
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.06em; color: var(--muted);
    border-bottom: 2px solid var(--border); white-space: nowrap;
  }
  td { padding: 9px 10px; border-bottom: 1px solid var(--border); vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  select.review-action {
    border: 1px solid var(--border); border-radius: 5px;
    padding: 4px 8px; font-size: 13px; background: var(--card);
    cursor: pointer; width: 100%;
  }
  input.review-label, input.review-note {
    border: 1px solid var(--border); border-radius: 5px;
    padding: 4px 8px; font-size: 13px; width: 100%;
  }
  .review-actions { margin-top: 20px; display: flex; align-items: center; gap: 16px; }
  .btn-primary {
    background: var(--navy); color: white; border: none;
    padding: 10px 20px; border-radius: 7px;
    font-size: 14px; font-weight: 700; cursor: pointer; letter-spacing: 0.01em;
  }
  .btn-primary:hover { background: #0f2a4e; }
"""

_REVIEW_JS = """
function toggleLabel(select) {
  var row = select.closest('tr');
  var input = row.querySelector('.review-label');
  input.style.visibility = select.value === 'changed' ? 'visible' : 'hidden';
  if (select.value !== 'changed') input.value = '';
}

function downloadCSV() {
  var header = 'cluster_id,proposed_label,decision,confidence,review_status,reviewed_label,reviewer_note';
  var rows = Array.from(document.querySelectorAll('#review-table tbody tr')).map(function(row) {
    var action = row.querySelector('.review-action').value;
    var proposed = row.dataset.proposed || '';
    var reviewedLabel = action === 'changed'
      ? (row.querySelector('.review-label').value || '')
      : (action === 'accepted' ? proposed : '');
    var note = row.querySelector('.review-note').value || '';
    return [
      row.dataset.cluster || '',
      proposed,
      row.dataset.decision || '',
      row.dataset.confidence || '',
      action,
      reviewedLabel,
      note
    ].map(function(v) { return '"' + String(v).replace(/"/g, '""') + '"'; }).join(',');
  });
  var csv = [header].concat(rows).join('\\n');
  var a = document.createElement('a');
  a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv);
  a.download = 'review_table.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}
"""
