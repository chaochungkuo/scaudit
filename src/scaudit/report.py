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
    <script async src="{_PLOTLY_CDN}" onload="scauditRenderUMAP()"></script>
    <script>
    window.scauditUMAPTraces = {trace_sets_json};
    window.scauditUMAPLayout = {layout_json};
    window.scauditUMAPConfig = {config_json};
    window.scauditRenderUMAP = function() {{
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


# ── Marker expression evidence ───────────────────────────────────────────────


def _marker_expression_section(cards: list[dict[str, Any]]) -> str:
    matrix = _marker_heatmap_matrix(cards)
    if not matrix:
        return ""

    clusters = [str(card.get("cluster_id", "")) for card in cards]
    max_abs = max(
        abs(value)
        for row in matrix
        for value in row["values"].values()
        if isinstance(value, (int, float)) and math.isfinite(value)
    )
    if max_abs <= 0:
        max_abs = 1.0

    header_cells = "".join(f"<th>Cluster {html.escape(cluster_id)}</th>" for cluster_id in clusters)
    rows = []
    for row in matrix:
        gene = str(row["gene"])
        cells = []
        for cluster_id in clusters:
            value = row["values"].get(cluster_id)
            cells.append(_marker_heatmap_cell(value, max_abs))
        rows.append(f"<tr><th>{html.escape(gene)}</th>{''.join(cells)}</tr>")

    return f"""
    <section class="marker-section">
      <div class="section-header">
        <h2>Marker expression evidence</h2>
        <span class="muted">Top mentioned genes · log2FC heatmap</span>
      </div>
      <div class="marker-heatmap-wrap">
        <table class="marker-heatmap">
          <thead><tr><th>Gene</th>{header_cells}</tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
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


def _marker_heatmap_cell(value: float | None, max_abs: float) -> str:
    if value is None or not math.isfinite(value):
        return '<td class="marker-empty">—</td>'
    ratio = min(abs(value) / max_abs, 1.0)
    alpha = 0.12 + (0.66 * ratio)
    color = f"rgba(42, 157, 92, {alpha:.2f})" if value >= 0 else f"rgba(192, 57, 43, {alpha:.2f})"
    return (
        f'<td class="marker-heat" style="background:{color}" '
        f'title="log2FC {value:+.2f}">{value:+.2f}</td>'
    )


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
    models = evidence.get("models") or []
    references = evidence.get("references") or []
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

    # ── Evidence block ──
    ev_rows: list[tuple[str, str]] = []
    if markers:
        names = ", ".join(str(m.get("gene") or m) if isinstance(m, dict) else str(m) for m in markers[:10])
        ev_rows.append(("Markers", names))
    if models:
        lines = []
        for m in models:
            if isinstance(m, dict):
                name = str(m.get("model") or m.get("name") or "model")
                lbl = str(m.get("label") or "")
                prob = m.get("probability") or m.get("score")
                prob_str = f" ({prob:.0%})" if isinstance(prob, (int, float)) else ""
                lines.append(f"{name}: {lbl}{prob_str}")
        if lines:
            ev_rows.append(("Models", ", ".join(lines)))
    if references:
        builtin = [r for r in references if isinstance(r, dict) and r.get("ref_id") == "builtin"]
        external = [r for r in references if isinstance(r, dict) and r.get("ref_id") != "builtin"]
        if builtin:
            parts = []
            for r in builtin[:3]:
                lbl = str(r.get("label") or "")
                j = r.get("jaccard")
                j_str = f" ({j:.2f})" if isinstance(j, (int, float)) else ""
                parts.append(f"{lbl}{j_str}")
            ev_rows.append(("Marker DB", ", ".join(parts)))
        if external:
            ref_lines = []
            for r in external:
                ref_id = str(r.get("ref_id") or r.get("reference") or r.get("name") or "ref")
                lbl = str(r.get("label") or "")
                j = r.get("jaccard") or r.get("similarity")
                j_str = f" (J={j:.2f})" if isinstance(j, (int, float)) else ""
                ref_lines.append(f"{ref_id}:{lbl}{j_str}")
            ev_rows.append(("References", ", ".join(ref_lines)))
    if qc_warnings:
        ev_rows.append(("QC flags", "; ".join(str(w) for w in qc_warnings)))

    if ev_rows:
        dl_html = "".join(
            f"<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>" for k, v in ev_rows
        )
        body_parts.append(
            f'<div class="card-block">'
            f'<p class="block-title">Evidence</p>'
            f'<dl class="ev-list">{dl_html}</dl>'
            f"</div>"
        )

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
    <span class="logo">scaudit</span>
    {nav_html}
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
    padding: 13px 32px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: sticky;
    top: 0;
    z-index: 20;
    box-shadow: var(--shadow);
  }
  .logo { font-weight: 800; font-size: 17px; letter-spacing: -0.3px; color: var(--navy); }
  .nav-link {
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

  /* ── Marker expression overview ── */
  .marker-section {
    margin-bottom: 16px;
  }
  .marker-heatmap-wrap {
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--card);
    box-shadow: var(--shadow);
  }
  .marker-heatmap {
    width: 100%;
    min-width: 680px;
    border-collapse: collapse;
    font-size: 12px;
  }
  .marker-heatmap th,
  .marker-heatmap td {
    border-bottom: 1px solid var(--border);
    border-right: 1px solid var(--border);
    padding: 7px 9px;
    text-align: center;
    white-space: nowrap;
  }
  .marker-heatmap th {
    background: #f7f9fc;
    color: var(--muted);
    font-weight: 700;
  }
  .marker-heatmap tbody th {
    color: var(--navy);
    text-align: left;
    position: sticky;
    left: 0;
    z-index: 1;
  }
  .marker-heatmap tr:last-child th,
  .marker-heatmap tr:last-child td { border-bottom: none; }
  .marker-heat,
  .marker-empty {
    font-variant-numeric: tabular-nums;
    color: var(--navy);
  }
  .marker-empty {
    background: #fafbfd;
    color: var(--muted);
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
