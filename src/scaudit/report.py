from __future__ import annotations

import html
import json
import math
import os
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


def render_draft_report(
    report_dir: Path,
    diagnosis_path: Path,
    annotation_cards_path: Path,
    provider_index_path: Path | None = None,
) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    diagnosis = _read_json(diagnosis_path, {})
    cards = _read_json(annotation_cards_path, [])
    provider_index = _read_json(provider_index_path, {}) if provider_index_path else {}
    report_path = report_dir / "report.html"
    review_path = report_dir / "review.html"
    _write_report_html(report_path, diagnosis, cards, final=False, provider_index=provider_index, provider_index_path=provider_index_path)
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
    path: Path,
    diagnosis: dict[str, Any],
    cards: list[dict[str, Any]],
    *,
    final: bool,
    provider_index: dict[str, Any] | None = None,
    provider_index_path: Path | None = None,
) -> None:
    label = "Final annotation audit" if final else "Draft annotation audit"
    n_cells = diagnosis.get("n_obs") or "—"
    n_genes = diagnosis.get("n_vars") or "—"
    n_clusters = diagnosis.get("cluster_count") or len(cards) or "—"
    dataset_path = diagnosis.get("path") or "—"
    warnings = diagnosis.get("warnings") or []

    counts = _decision_counts(cards)
    attention = [c for c in cards if c.get("decision") in _NEEDS_ATTENTION]

    overview_html = _run_overview_section(diagnosis, cards, attention)
    umap_html = _umap_section(cards, diagnosis) if cards else ""
    workflow_html = _workflow_section(provider_index or {})
    provider_html = _provider_status_table(path.parent, provider_index or {}, provider_index_path) if provider_index else ""
    cross_provider_html = _cross_provider_summary_section(path.parent, provider_index or {}, provider_index_path) if provider_index else ""
    priority_html = _review_priorities_section(cards)
    artifacts_html = _artifact_navigation_section(path.parent, provider_index or {}, provider_index_path)
    warning_html = _warning_list(warnings) if warnings else ""
    methods_html = _methods_section(diagnosis)

    body = f"""
    <nav class="report-toc" aria-label="Report navigation">
      <a href="#overview">Overview</a>
      <a href="#cluster-overview">UMAP</a>
      <a href="#workflow">Workflow</a>
      <a href="#providers">Providers</a>
      <a href="#cross-provider">Comparison</a>
      <a href="#review-priorities">Review</a>
      <a href="#artifacts">Artifacts</a>
      <a href="#methods">Methods</a>
    </nav>
    <section class="hero audit-hero">
      <p class="eyebrow">{html.escape(label)}</p>
      <h1>scaudit report</h1>
      <p class="dataset-path">Dataset: <code>{html.escape(str(dataset_path))}</code></p>
      <div class="decision-summary">
        {"".join(_decision_pill(lbl, count) for lbl, count in counts.items() if count > 0)}
      </div>
    </section>
    {overview_html}
    {umap_html}
    {workflow_html}
    {provider_html}
    {cross_provider_html}
    {priority_html}
    {artifacts_html}
    {warning_html}
    {methods_html}
    """

    _write_page(path, title="scaudit report", body=body, back_link=("review.html", "Review table →"))


# ── UMAP overview ─────────────────────────────────────────────────────────────


def _provider_reports_section(report_dir: Path, provider_index: dict[str, Any], provider_index_path: Path | None) -> str:
    providers = provider_index.get("providers") if isinstance(provider_index, dict) else []
    if not isinstance(providers, list) or not providers:
        return ""
    output_dir = provider_index_path.parent.parent if provider_index_path else report_dir.parent
    cards = []
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        name = html.escape(str(provider.get("name") or provider.get("id") or "Provider report"))
        purpose = html.escape(str(provider.get("purpose") or ""))
        status = html.escape(str(provider.get("status") or "unknown"))
        top_finding = html.escape(str(provider.get("top_finding") or "No top finding reported."))
        warning_count = len(provider.get("warnings") or [])
        html_target = str(provider.get("html") or "")
        json_target = str(provider.get("json") or "")
        html_href = _relative_report_link(report_dir, output_dir / html_target) if html_target else ""
        json_href = _relative_report_link(report_dir, output_dir / json_target) if json_target else ""
        warning_text = f"{warning_count} warning{'s' if warning_count != 1 else ''}" if warning_count else "No warnings"
        actions = []
        if html_href:
            actions.append(f'<a href="{html.escape(html_href)}">Open focused report</a>')
        if json_href:
            actions.append(f'<a href="{html.escape(json_href)}">Evidence JSON</a>')
        cards.append(
            f"""
            <article class="provider-card">
              <div class="provider-card-head">
                <h3>{name}</h3>
                <span class="provider-status">{status}</span>
              </div>
              <p class="provider-purpose">{purpose}</p>
              <p class="provider-finding">{top_finding}</p>
              <p class="provider-warning">{html.escape(warning_text)}</p>
              <div class="provider-actions">{"".join(actions)}</div>
            </article>
            """
        )
    if not cards:
        return ""
    return f"""
    <section class="provider-reports-section">
      <div class="section-header">
        <h2>Focused evidence reports</h2>
        <span class="muted">Bird's-eye links to runnable qmd provider reports</span>
      </div>
      <div class="provider-grid">{"".join(cards)}</div>
    </section>
    """


def _run_overview_section(diagnosis: dict[str, Any], cards: list[dict[str, Any]], attention: list[dict[str, Any]]) -> str:
    metrics = (
        _metric("Cells", diagnosis.get("n_obs") or "—")
        + _metric("Genes", diagnosis.get("n_vars") or "—")
        + _metric("Clusters", diagnosis.get("cluster_count") or len(cards) or "—")
        + _metric("Needs attention", len(attention), highlight=len(attention) > 0)
    )
    rows = [
        ("Species", diagnosis.get("species") or "—"),
        ("Tissue", diagnosis.get("tissue") or "—"),
        ("Cluster key", diagnosis.get("cluster_key") or "—"),
        ("Gene ID type", diagnosis.get("gene_id_type") or "—"),
    ]
    row_html = "".join(f"<tr><th>{html.escape(label)}</th><td>{html.escape(str(value))}</td></tr>" for label, value in rows)
    return f"""
    <section id="overview" class="audit-section overview-section">
      <div class="section-header">
        <h2>Run overview</h2>
        <span class="muted">Dataset and review scope</span>
      </div>
      <div class="metrics-grid compact-metrics">{metrics}</div>
      <table class="info-table overview-table"><tbody>{row_html}</tbody></table>
    </section>
    """


def _workflow_section(provider_index: dict[str, Any]) -> str:
    providers = provider_index.get("providers") if isinstance(provider_index, dict) else []
    if not isinstance(providers, list):
        providers = []
    active_ids = {str(provider.get("id")) for provider in providers if isinstance(provider, dict)}
    steps = [
        ("1", "Raw markers", "Rank genes per cluster and summarize marker strength.", "marker_based" in active_ids),
        ("2", "Marker databases", "Compare cluster markers with curated and user-defined marker databases.", any(pid in active_ids for pid in ("cellmarker", "panglaodb", "user_markers"))),
        ("3", "Human review", "Route ambiguous or weak marker evidence to reviewer action.", True),
    ]
    step_html = "".join(_workflow_step(*step) for step in steps)
    return f"""
    <section id="workflow" class="audit-section workflow-section">
      <div class="section-header">
        <h2>Evidence workflow</h2>
        <span class="muted">What each stage contributes</span>
      </div>
      <div class="workflow-steps">{step_html}</div>
    </section>
    """


def _workflow_step(number: str, title: str, text: str, active: bool) -> str:
    state = "Active" if active else "Not configured"
    css = "is-active" if active else "is-muted"
    return (
        f'<article class="workflow-step {css}">'
        f'<span class="workflow-number">{html.escape(number)}</span>'
        f'<div><h3>{html.escape(title)}</h3><p>{html.escape(text)}</p><span>{html.escape(state)}</span></div>'
        f"</article>"
    )


def _provider_status_table(report_dir: Path, provider_index: dict[str, Any], provider_index_path: Path | None) -> str:
    providers = provider_index.get("providers") if isinstance(provider_index, dict) else []
    if not isinstance(providers, list) or not providers:
        return ""
    output_dir = provider_index_path.parent.parent if provider_index_path else report_dir.parent
    rows = []
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        provider_id = str(provider.get("id") or "")
        name = str(provider.get("name") or provider_id or "Provider")
        status = str(provider.get("status") or "unknown")
        purpose = str(provider.get("purpose") or "")
        finding = str(provider.get("top_finding") or "")
        warning_count = len(provider.get("warnings") or [])
        html_target = str(provider.get("html") or "")
        json_target = str(provider.get("json") or "")
        html_href = _relative_report_link(report_dir, output_dir / html_target) if html_target else ""
        json_href = _relative_report_link(report_dir, output_dir / json_target) if json_target else ""
        links = []
        if html_href:
            links.append(f'<a href="{html.escape(html_href)}">Report</a>')
        if json_href:
            links.append(f'<a href="{html.escape(json_href)}">JSON</a>')
        rows.append(
            "<tr>"
            f"<td><strong>{html.escape(name)}</strong><br><span class=\"muted\">{html.escape(purpose)}</span></td>"
            f"<td>{_status_badge(status)}</td>"
            f"<td>{html.escape(finding)}</td>"
            f"<td>{html.escape(str(warning_count))}</td>"
            f"<td>{' · '.join(links)}</td>"
            "</tr>"
        )
    return f"""
    <section id="providers" class="audit-section provider-status-section">
      <div class="section-header">
        <h2>Provider status</h2>
        <span class="muted">Focused reports hold method-level detail</span>
      </div>
      <div class="table-wrap">
        <table class="audit-table provider-status-table">
          <thead><tr><th>Provider</th><th>Status</th><th>Top finding</th><th>Warnings</th><th>Open</th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    </section>
    """


def _status_badge(status: str) -> str:
    normalized = status.lower().strip() or "unknown"
    return f'<span class="status-badge status-{html.escape(normalized)}">{html.escape(status)}</span>'


def _cross_provider_summary_section(report_dir: Path, provider_index: dict[str, Any], provider_index_path: Path | None) -> str:
    summary = provider_index.get("cross_provider_summary") if isinstance(provider_index, dict) else {}
    rows = summary.get("rows") if isinstance(summary, dict) else []
    if not isinstance(rows, list) or not rows:
        return ""
    csv_href = ""
    if provider_index_path and isinstance(summary, dict) and summary.get("path"):
        csv_href = _relative_report_link(report_dir, provider_index_path.parent.parent / str(summary.get("path")))
    body = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        body.append(
            "<tr>"
            f"<td>Cluster {html.escape(str(row.get('cluster_id', '')))}</td>"
            f"<td>{_provider_label_cell(row.get('marker_based_label'), row.get('marker_based_score'))}</td>"
            f"<td>{_provider_label_cell(row.get('cellmarker_label'), row.get('cellmarker_score'), row.get('cellmarker_confidence'))}</td>"
            f"<td>{_provider_label_cell(row.get('panglaodb_label'), row.get('panglaodb_score'), row.get('panglaodb_confidence'))}</td>"
            f"<td>{_provider_label_cell(row.get('user_markers_label'), row.get('user_markers_score'), row.get('user_markers_confidence'))}</td>"
            f"<td>{_agreement_badge(str(row.get('agreement') or 'insufficient'))}</td>"
            f"<td>{html.escape(str(row.get('action') or 'Review'))}</td>"
            "</tr>"
        )
    link = f'<a href="{html.escape(csv_href)}">CSV</a>' if csv_href else ""
    return f"""
    <section id="cross-provider" class="audit-section cross-provider-section">
      <div class="section-header">
        <h2>Cross-provider summary</h2>
        <span class="muted">Cluster-level comparison across marker-based and database evidence {link}</span>
      </div>
      <div class="table-wrap">
        <table class="audit-table cross-provider-table">
          <thead><tr><th>Cluster</th><th>Marker-based</th><th>CellMarker</th><th>PanglaoDB</th><th>User markers</th><th>Agreement</th><th>Action</th></tr></thead>
          <tbody>{''.join(body)}</tbody>
        </table>
      </div>
    </section>
    """


def _provider_label_cell(label: Any, score: Any, confidence: Any = "") -> str:
    label_text = str(label or "").strip()
    if not label_text:
        return '<span class="muted">Missing</span>'
    meta = []
    if str(score or "").strip():
        meta.append(f"score {score}")
    if str(confidence or "").strip():
        meta.append(str(confidence))
    meta_html = f'<br><span class="muted">{html.escape("; ".join(meta))}</span>' if meta else ""
    return f"<strong>{html.escape(label_text)}</strong>{meta_html}"


def _agreement_badge(agreement: str) -> str:
    normalized = agreement.lower().strip() or "insufficient"
    labels = {
        "high": "High",
        "lineage": "Lineage",
        "mixed": "Mixed",
        "insufficient": "Insufficient",
    }
    return f'<span class="agreement-badge agreement-{html.escape(normalized)}">{html.escape(labels.get(normalized, agreement))}</span>'


def _review_priorities_section(cards: list[dict[str, Any]]) -> str:
    if not cards:
        return ""
    rows = []
    for card in cards:
        cluster_id = str(card.get("cluster_id", ""))
        proposed = str(card.get("proposed_label") or "pending")
        decision = str(card.get("decision") or "")
        confidence = card.get("confidence", {})
        overall = str(confidence.get("overall") or "—")
        evidence = card.get("evidence", {})
        markers = evidence.get("markers") or []
        marker_text = _top_marker_text(markers)
        reasoning = card.get("reasoning", {})
        uncertainties = reasoning.get("uncertainties") or []
        action = _review_action(card)
        rows.append(
            "<tr>"
            f'<td><a href="review.html">Cluster {html.escape(cluster_id)}</a></td>'
            f"<td>{html.escape(proposed)}</td>"
            f"<td>{_badge(decision)}</td>"
            f"<td>{html.escape(overall)}</td>"
            f"<td>{html.escape(marker_text)}</td>"
            f"<td>{html.escape('; '.join(map(str, uncertainties[:2])) or '—')}</td>"
            f"<td>{html.escape(action)}</td>"
            "</tr>"
        )
    return f"""
    <section id="review-priorities" class="audit-section review-priority-section">
      <div class="section-header">
        <h2>Review priorities</h2>
        <span class="muted">Cluster-level routing for human review</span>
      </div>
      <div class="table-wrap">
        <table class="audit-table review-table">
          <thead><tr><th>Cluster</th><th>Label</th><th>Decision</th><th>Confidence</th><th>Top markers</th><th>Uncertainty</th><th>Next action</th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    </section>
    """


def _top_marker_text(markers: list[Any], limit: int = 4) -> str:
    marker_dicts = _marker_dicts(markers)
    genes = [str(marker.get("gene") or "") for marker in marker_dicts if marker.get("gene")]
    return ", ".join(genes[:limit]) if genes else "—"


def _review_action(card: dict[str, Any]) -> str:
    decision = str(card.get("decision") or "")
    if decision == "Accepted":
        return "Confirm or finalize"
    if decision == "Ambiguous":
        return "Compare provider reports"
    if decision == "Artifact warning":
        return "Inspect QC and cluster composition"
    if decision == "Unknown":
        return "Check marker evidence"
    return "Review label and supporting evidence"


def _artifact_navigation_section(report_dir: Path, provider_index: dict[str, Any], provider_index_path: Path | None) -> str:
    output_dir = provider_index_path.parent.parent if provider_index_path else report_dir.parent
    links = [
        ("Review table", "review.html", "Editable browser table for human decisions."),
    ]
    if provider_index_path:
        links.append(("Provider index", _relative_report_link(report_dir, provider_index_path), "Machine-readable list of focused reports."))
    providers = provider_index.get("providers") if isinstance(provider_index, dict) else []
    if isinstance(providers, list):
        for provider in providers:
            if not isinstance(provider, dict):
                continue
            html_target = str(provider.get("html") or "")
            if html_target:
                links.append((str(provider.get("name") or provider.get("id")), _relative_report_link(report_dir, output_dir / html_target), str(provider.get("purpose") or "")))
    items = "".join(
        f'<li><a href="{html.escape(href)}">{html.escape(label)}</a><span>{html.escape(desc)}</span></li>'
        for label, href, desc in links
    )
    return f"""
    <section id="artifacts" class="audit-section artifact-section">
      <div class="section-header">
        <h2>Artifacts and detail pages</h2>
        <span class="muted">Open focused evidence pages when needed</span>
      </div>
      <ul class="artifact-list">{items}</ul>
    </section>
    """


def _relative_report_link(report_dir: Path, target: Path) -> str:
    return os.path.relpath(target, report_dir)


def _umap_section(cards: list[dict[str, Any]], diagnosis: dict[str, Any]) -> str:
    umap_coords = diagnosis.get("umap_coords") or {}
    has_real = bool(umap_coords)
    subtitle = "Interactive · hover for details" + ("" if has_real else " · placeholder layout")
    plotly_html = _umap_plotly(cards, umap_coords)
    return f"""
    <section id="cluster-overview" class="umap-section audit-section">
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
            "tools": "Scanpy rank_genes_groups; built-in marker signature scoring",
            "outputs": "DE markers, log2FC, padj, signature coverage/overlap",
            "authority": "Can support labels and confidence",
            "available": any(card.get("evidence", {}).get("markers") for card in cards),
        },
        {
            "layer": "Marker database evidence",
            "purpose": "Curated and user-defined marker support",
            "tools": "Built-in marker DB; CellMarker; PanglaoDB; user marker CSV/TSV",
            "outputs": "Marker-set overlaps, matched genes, coverage/Jaccard scores, confidence buckets",
            "authority": "Can support labels and expose database disagreement",
            "available": any(card.get("evidence", {}).get("references") for card in cards),
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
    status = "Active" if row["available"] else "Missing"
    status_class = "is-active" if row["available"] else "is-missing"
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
    source_keys = ["markers", "marker_db", "qc", "llm"]
    complete_count = sum(1 for row in rows if all(row["sources"][key] for key in source_keys))
    meta = f"{complete_count}/{len(rows)} clusters have all evidence sources"
    header = "".join(f"<th>{html.escape(label)}</th>" for label in ["Cluster", "Markers", "Marker DB", "QC", "LLM"])
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
    cells = "".join(_completeness_cell(bool(sources[key])) for key in ["markers", "marker_db", "qc", "llm"])
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
        "Scanpy rank_genes_groups; built-in marker signatures",
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
    <details class="methods-section" id="methods">
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

  .report-toc {
    position: sticky;
    top: 56px;
    z-index: 10;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    align-items: center;
    margin: -8px 0 16px;
    padding: 8px 0;
    background: rgba(242, 245, 251, 0.94);
    backdrop-filter: blur(6px);
  }
  .report-toc a {
    display: inline-flex;
    align-items: center;
    min-height: 30px;
    padding: 5px 10px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: #fff;
    color: var(--navy);
    font-size: 12px;
    font-weight: 700;
    text-decoration: none;
  }
  .report-toc a:hover { color: var(--blue); border-color: #b9c7dc; }
  .audit-hero {
    box-shadow: none;
    border-radius: 8px;
  }
  .audit-section {
    border-radius: 8px;
    box-shadow: none;
  }
  .overview-table th { width: 150px; }
  .compact-metrics .metric {
    box-shadow: none;
    border-radius: 8px;
    padding: 12px 14px;
  }
  .compact-metrics .metric strong { font-size: 24px; }
  .workflow-steps {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 10px;
  }
  .workflow-step {
    display: grid;
    grid-template-columns: 34px minmax(0, 1fr);
    gap: 10px;
    padding: 12px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: #fbfcff;
  }
  .workflow-step.is-muted { opacity: 0.68; }
  .workflow-number {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 999px;
    background: var(--navy);
    color: #fff;
    font-size: 12px;
    font-weight: 800;
  }
  .workflow-step.is-muted .workflow-number { background: #9aa7b8; }
  .workflow-step h3 {
    margin: 0 0 3px;
    color: var(--navy);
    font-size: 13px;
    letter-spacing: 0;
    text-transform: none;
  }
  .workflow-step p {
    margin: 0;
    color: var(--muted);
    font-size: 12px;
    line-height: 1.45;
  }
  .workflow-step span:not(.workflow-number) {
    display: inline-block;
    margin-top: 6px;
    color: var(--teal);
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .workflow-step.is-muted span:not(.workflow-number) { color: var(--muted); }
  .table-wrap {
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: 8px;
  }
  .audit-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    background: #fff;
  }
  .audit-table th,
  .audit-table td {
    padding: 9px 10px;
    border-bottom: 1px solid #e7edf5;
    vertical-align: top;
    text-align: left;
  }
  .audit-table tbody tr:last-child td { border-bottom: 0; }
  .audit-table th {
    background: #f6f8fc;
    color: var(--navy);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .status-badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border: 1px solid var(--border);
    border-radius: 999px;
    color: var(--muted);
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
  }
  .status-success { color: var(--green); border-color: #b9dfc8; background: #f1fbf5; }
  .status-warning { color: var(--orange); border-color: #f1d0ad; background: #fff8ef; }
  .status-skipped,
  .status-missing { color: var(--muted); background: #f7f9fc; }
  .agreement-badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
  }
  .agreement-high { color: var(--green); background: #e3f5ec; }
  .agreement-lineage { color: var(--blue); background: #eef4ff; }
  .agreement-mixed { color: var(--orange); background: #fff3e0; }
  .agreement-insufficient { color: var(--muted); background: #eef0f4; }
  .cross-provider-table td:nth-child(2),
  .cross-provider-table td:nth-child(3),
  .cross-provider-table td:nth-child(4),
  .cross-provider-table td:nth-child(5) {
    min-width: 150px;
  }
  .artifact-list {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 10px;
    padding: 0;
    margin: 0;
    list-style: none;
  }
  .artifact-list li {
    padding: 12px 14px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: #fbfcff;
  }
  .artifact-list a {
    display: block;
    font-weight: 800;
    text-decoration: none;
  }
  .artifact-list span {
    display: block;
    margin-top: 3px;
    color: var(--muted);
    font-size: 12px;
  }

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

  /* ── Focused provider reports ── */
  .provider-reports-section { padding: 20px 24px; }
  .provider-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 12px;
  }
  .provider-card {
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 16px;
    background: #fbfcff;
  }
  .provider-card-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }
  .provider-card h3 {
    margin: 0;
    color: var(--navy);
    font-size: 13px;
    letter-spacing: 0;
    text-transform: none;
  }
  .provider-status {
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 2px 8px;
    color: var(--muted);
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
  }
  .provider-purpose,
  .provider-warning {
    color: var(--muted);
    font-size: 12px;
    margin: 6px 0 0;
  }
  .provider-finding {
    margin: 8px 0 0;
    font-size: 13px;
  }
  .provider-actions {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 10px;
    font-size: 13px;
    font-weight: 600;
  }

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
