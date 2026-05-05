from __future__ import annotations

import importlib.util
import json
import os
from typing import Any


_SYSTEM_PROMPT = """\
You are an expert in single-cell RNA-seq biology assisting with cluster annotation.
You receive structured evidence for a cell cluster and write a concise scientific summary.

Rules you MUST follow:
- Ground every claim in the provided evidence. Invent nothing.
- Never override the scaudit decision or confidence level.
- Acknowledge uncertainty when evidence is weak or conflicting.
- Use precise cell biology language (lineage names, marker gene symbols).
- Keep the summary under 60 words.
- Output ONLY the summary text — no JSON, no headings, no preamble.
"""

_USER_TEMPLATE = """\
Cluster {cluster_id} ({cell_count} cells)
Decision: {decision}
Confidence: lineage={lineage}, subtype={subtype}, overall={overall}

Marker genes (top, log2FC-filtered):
{marker_list}

Model evidence:
{model_evidence}

Reference / DB matches:
{ref_evidence}

Reasoning so far:
Supports: {supports}
Uncertainties: {uncertainties}
Contradictions: {contradictions}

Write a single-paragraph summary for the annotation card.
"""


def enrich_cards_with_llm(
    annotation_cards: list[dict[str, Any]],
    api_key: str | None = None,
    model: str = "claude-haiku-4-5-20251001",
) -> list[dict[str, Any]]:
    """Replace reasoning.summary with a Claude-generated narrative for each card.

    Skips silently if the anthropic SDK is not installed or no API key is available.
    Cards with decision=="Accepted" and high confidence still get updated summaries.

    Returns the same list mutated in-place (also returned for chaining).
    """
    if importlib.util.find_spec("anthropic") is None:
        return annotation_cards

    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return annotation_cards

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
    except Exception:  # pragma: no cover
        return annotation_cards

    for card in annotation_cards:
        try:
            summary = _generate_summary(client, card, model)
            if summary:
                card.setdefault("reasoning", {})["summary"] = summary
        except Exception:  # pragma: no cover - API errors should never crash the pipeline
            continue

    return annotation_cards


def _generate_summary(client: Any, card: dict[str, Any], model: str) -> str | None:
    cluster_id = str(card.get("cluster_id", ""))
    decision = str(card.get("decision", ""))
    confidence = card.get("confidence", {})
    provenance = card.get("provenance", {})
    evidence = card.get("evidence", {})
    reasoning = card.get("reasoning", {})

    markers = evidence.get("markers") or []
    marker_list = (
        ", ".join(f"{m['gene']} (log2FC {m['log2fc']:+.2f})" for m in markers[:8] if isinstance(m, dict))
        or "none computed"
    )

    model_ev = evidence.get("models") or []
    model_evidence = (
        "; ".join(
            f"{m.get('model','model')}: {m.get('label','')} ({m.get('probability', m.get('score', 0)):.0%})"
            for m in model_ev
            if isinstance(m, dict)
        )
        or "none"
    )

    refs = evidence.get("references") or []
    builtin = [r for r in refs if isinstance(r, dict) and r.get("ref_id") == "builtin"]
    external = [r for r in refs if isinstance(r, dict) and r.get("ref_id") != "builtin"]
    ref_parts: list[str] = []
    if builtin:
        ref_parts.append("Marker DB: " + ", ".join(f"{r['label']} (J={r['jaccard']:.2f})" for r in builtin[:3]))
    if external:
        ref_parts.append("References: " + ", ".join(f"{r['ref_id']}:{r['label']}" for r in external[:2]))
    ref_evidence = "; ".join(ref_parts) or "none"

    prompt = _USER_TEMPLATE.format(
        cluster_id=cluster_id,
        cell_count=provenance.get("cell_count", "?"),
        decision=decision,
        lineage=confidence.get("lineage", "unknown"),
        subtype=confidence.get("subtype", "unknown"),
        overall=confidence.get("overall", "unknown"),
        marker_list=marker_list,
        model_evidence=model_evidence,
        ref_evidence=ref_evidence,
        supports="; ".join(reasoning.get("supports") or []) or "none",
        uncertainties="; ".join(reasoning.get("uncertainties") or []) or "none",
        contradictions="; ".join(reasoning.get("contradictions") or []) or "none",
    )

    message = client.messages.create(
        model=model,
        max_tokens=120,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    text = message.content[0].text.strip() if message.content else ""
    return text or None
