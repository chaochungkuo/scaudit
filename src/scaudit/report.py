from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def render_draft_report(report_dir: Path, diagnosis_path: Path, annotation_cards_path: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    clusters_dir = report_dir / "clusters"
    clusters_dir.mkdir(parents=True, exist_ok=True)

    diagnosis = _read_json(diagnosis_path, {})
    annotation_cards = _read_json(annotation_cards_path, [])
    index_path = report_dir / "index.html"

    _write_page(
        index_path,
        "scaudit annotation audit",
        f"""
        <section class="hero">
          <p class="eyebrow">Draft annotation audit</p>
          <h1>scaudit report</h1>
          <p>{_dataset_summary(diagnosis)}</p>
        </section>
        <section class="grid">
          {_metric_card("Cells", diagnosis.get("n_obs", "unknown"))}
          {_metric_card("Genes", diagnosis.get("n_vars", "unknown"))}
          {_metric_card("Clusters", diagnosis.get("cluster_count", "unknown"))}
          {_metric_card("Annotation cards", len(annotation_cards))}
        </section>
        <section>
          <h2>Navigation</h2>
          <nav class="cards">
            <a href="annotation.html">Annotation summary</a>
            <a href="clusters/index.html">Cluster reports</a>
            <a href="methods.html">Methods</a>
            <a href="reproducibility.html">Reproducibility</a>
          </nav>
        </section>
        <section>
          <h2>Warnings</h2>
          {_warning_list(diagnosis.get("warnings", []))}
        </section>
        """,
    )
    _write_page(
        report_dir / "annotation.html",
        "Annotation summary",
        f"""
        <section>
          <p class="eyebrow">Draft</p>
          <h1>Annotation summary</h1>
          <p>Marker evidence and decision assignment will populate this page in the next milestones.</p>
          {_annotation_table(annotation_cards)}
        </section>
        """,
    )
    for card in annotation_cards:
        _write_cluster_page(clusters_dir, card)
    _write_page(
        clusters_dir / "index.html",
        "Cluster reports",
        f"""
        <section>
          <p class="eyebrow">Cluster-level audit</p>
          <h1>Cluster reports</h1>
          {_cluster_index(annotation_cards)}
        </section>
        """,
        prefix="../",
    )
    _write_page(
        report_dir / "methods.html",
        "Methods",
        """
        <section>
          <p class="eyebrow">Methods</p>
          <h1>Methods</h1>
          <p>This draft run created the audit output structure. Dataset diagnosis is active; marker evidence is pending.</p>
        </section>
        """,
    )
    _write_page(
        report_dir / "reproducibility.html",
        "Reproducibility",
        """
        <section>
          <p class="eyebrow">Run record</p>
          <h1>Reproducibility</h1>
          <p>See <code>../reproducibility.json</code> for the current machine-readable run record.</p>
        </section>
        """,
    )
    return index_path


def render_final_report(report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    index_path = report_dir / "index.html"
    _write_page(
        index_path,
        "scaudit final report",
        """
        <section class="hero">
          <p class="eyebrow">Final annotation audit</p>
          <h1>scaudit final report</h1>
          <p>This final report skeleton confirms that final outputs were created.</p>
        </section>
        <section>
          <h2>Outputs</h2>
          <ul>
            <li><code>final_annotation_cards.json</code></li>
            <li><code>final_annotation_summary.csv</code></li>
            <li><code>review_audit.json</code></li>
            <li><code>reproducibility.json</code></li>
          </ul>
        </section>
        """,
    )
    return index_path


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _dataset_summary(diagnosis: dict[str, Any]) -> str:
    path = html.escape(str(diagnosis.get("path", "unknown")))
    return f"Dataset: <code>{path}</code>"


def _metric_card(label: str, value: object) -> str:
    return f'<div class="metric"><span>{html.escape(label)}</span><strong>{html.escape(str(value))}</strong></div>'


def _warning_list(warnings: list[str]) -> str:
    if not warnings:
        return "<p>No warnings.</p>"
    items = "\n".join(f"<li>{html.escape(str(warning))}</li>" for warning in warnings)
    return f"<ul>{items}</ul>"


def _annotation_table(annotation_cards: list[dict[str, Any]]) -> str:
    if not annotation_cards:
        return "<p>No cluster annotation cards were generated yet.</p>"
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(card.get('cluster_id', '')))}</td>"
        f"<td>{html.escape(str(card.get('proposed_label') or ''))}</td>"
        f"<td>{html.escape(str(card.get('decision', '')))}</td>"
        f"<td>{html.escape(str(card.get('confidence', {}).get('overall', '')))}</td>"
        "</tr>"
        for card in annotation_cards
    )
    return (
        "<table><thead><tr><th>Cluster</th><th>Proposed label</th><th>Decision</th><th>Confidence</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def _cluster_index(annotation_cards: list[dict[str, Any]]) -> str:
    if not annotation_cards:
        return "<p>No clusters available yet. Provide a readable .h5ad and cluster key to generate cluster pages.</p>"
    links = "\n".join(
        f'<li><a href="cluster_{html.escape(str(card.get("cluster_id", "")))}.html">'
        f'Cluster {html.escape(str(card.get("cluster_id", "")))}</a> '
        f'<span>{html.escape(str(card.get("decision", "")))}</span></li>'
        for card in annotation_cards
    )
    return f"<ul>{links}</ul>"


def _write_cluster_page(clusters_dir: Path, card: dict[str, Any]) -> None:
    cluster_id = str(card.get("cluster_id", "unknown"))
    safe_cluster_id = "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in cluster_id)
    confidence = card.get("confidence", {})
    provenance = card.get("provenance", {})
    _write_page(
        clusters_dir / f"cluster_{safe_cluster_id}.html",
        f"Cluster {cluster_id}",
        f"""
        <section class="hero">
          <p class="eyebrow">Cluster annotation card</p>
          <h1>Cluster {html.escape(cluster_id)}</h1>
          <p>Decision: <strong>{html.escape(str(card.get("decision", "")))}</strong></p>
        </section>
        <section class="grid">
          {_metric_card("Proposed label", card.get("proposed_label") or "pending")}
          {_metric_card("Overall confidence", confidence.get("overall", "unknown"))}
          {_metric_card("Lineage confidence", confidence.get("lineage", "unknown"))}
          {_metric_card("Cell count", provenance.get("cell_count", "unknown"))}
        </section>
        <section>
          <h2>Evidence</h2>
          <p>Marker, model, reference, and ontology evidence are pending.</p>
        </section>
        """,
        prefix="../",
    )


def _write_page(path: Path, title: str, body: str, prefix: str = "") -> None:
    path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --navy: #071936;
      --blue: #2f67c8;
      --teal: #129a9f;
      --green: #38a86b;
      --purple: #7446a8;
      --border: #d8e0ec;
      --muted: #5d6b7c;
      --bg: #f7f9fc;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--navy);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    header {{
      background: white;
      border-bottom: 1px solid var(--border);
      padding: 18px 32px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    header a {{
      color: var(--navy);
      text-decoration: none;
      font-weight: 700;
    }}
    main {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 32px;
    }}
    .eyebrow {{
      color: var(--teal);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .hero, section {{
      background: white;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 24px;
      margin-bottom: 20px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
      background: transparent;
      border: 0;
      padding: 0;
    }}
    .metric {{
      background: white;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 18px;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 13px;
    }}
    .metric strong {{
      display: block;
      font-size: 28px;
      margin-top: 6px;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
    }}
    .cards a {{
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px;
      color: var(--navy);
      text-decoration: none;
      font-weight: 700;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
    }}
    th, td {{
      border-bottom: 1px solid var(--border);
      padding: 10px;
      text-align: left;
    }}
    th {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }}
    code {{
      background: #eef3f8;
      padding: 2px 5px;
      border-radius: 4px;
    }}
  </style>
</head>
<body>
  <header>
    <a href="{prefix}index.html">scaudit</a>
    <nav>
      <a href="{prefix}annotation.html">Annotation</a>
      <a href="{prefix}clusters/index.html">Clusters</a>
      <a href="{prefix}methods.html">Methods</a>
      <a href="{prefix}reproducibility.html">Reproducibility</a>
    </nav>
  </header>
  <main>
    {body}
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )
