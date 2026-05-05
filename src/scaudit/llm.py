from __future__ import annotations

import importlib.util
import json
import os
import urllib.request
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
    provider: str = "",
    base_url: str = "",
    api_key_env: str = "",
    model: str = "",
    temperature: float = 0,
) -> list[dict[str, Any]]:
    """Replace reasoning.summary with an LLM-generated narrative for each card.

    Supports Anthropic and OpenAI-compatible chat completion endpoints.
    Skips silently if the provider client cannot be configured.
    Cards with decision=="Accepted" and high confidence still get updated summaries.

    Returns the same list mutated in-place (also returned for chaining).
    """
    resolved_provider = (provider or os.environ.get("SCAUDIT_LLM_PROVIDER", "") or "anthropic").lower()
    resolved_model = model or os.environ.get("SCAUDIT_LLM_MODEL", "") or _default_model(resolved_provider)
    key = api_key or _api_key_from_env(api_key_env, resolved_provider)
    if not key:
        return annotation_cards

    try:
        client = _build_client(resolved_provider, key, base_url)
    except Exception:  # pragma: no cover
        return annotation_cards

    for card in annotation_cards:
        try:
            summary = _generate_summary(client, card, resolved_model, temperature)
            if summary:
                reasoning = card.setdefault("reasoning", {})
                reasoning["summary"] = summary
                reasoning["summary_source"] = "llm"
                reasoning["summary_provider"] = resolved_provider
                reasoning["summary_model"] = resolved_model
        except Exception:  # pragma: no cover - API errors should never crash the pipeline
            continue

    return annotation_cards


def _default_model(provider: str) -> str:
    if provider in {"openai", "openai-compatible"}:
        return "gpt-4o-mini"
    return "claude-haiku-4-5-20251001"


def _api_key_from_env(api_key_env: str, provider: str) -> str:
    candidates = []
    if api_key_env:
        candidates.append(api_key_env)
    candidates.append("SCAUDIT_LLM_API_KEY")
    if provider in {"openai", "openai-compatible"}:
        candidates.append("OPENAI_API_KEY")
    else:
        candidates.append("ANTHROPIC_API_KEY")
    for name in candidates:
        value = os.environ.get(name, "")
        if value:
            return value
    return ""


def _build_client(provider: str, api_key: str, base_url: str) -> Any:
    if provider in {"openai", "openai-compatible"}:
        return OpenAICompatibleClient(
            api_key=api_key,
            base_url=base_url or os.environ.get("SCAUDIT_LLM_BASE_URL", "") or "https://api.openai.com/v1",
        )
    if importlib.util.find_spec("anthropic") is None:
        raise RuntimeError("anthropic SDK is not installed")
    import anthropic

    return AnthropicClient(anthropic.Anthropic(api_key=api_key))


class AnthropicClient:
    def __init__(self, client: Any) -> None:
        self.client = client

    def complete(self, *, model: str, system: str, prompt: str, temperature: float) -> str:
        message = self.client.messages.create(
            model=model,
            max_tokens=120,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip() if message.content else ""


class OpenAICompatibleClient:
    def __init__(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def complete(self, *, model: str, system: str, prompt: str, temperature: float) -> str:
        payload = {
            "model": model,
            "temperature": temperature,
            "max_tokens": 120,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
        choices = data.get("choices") or []
        if not choices:
            return ""
        return str(choices[0].get("message", {}).get("content", "")).strip()


def _generate_summary(client: Any, card: dict[str, Any], model: str, temperature: float) -> str | None:
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

    text = client.complete(
        model=model,
        system=_SYSTEM_PROMPT,
        prompt=prompt,
        temperature=temperature,
    )
    return text or None
