# Design Philosophy

## 1. Annotation Is Not a Prediction

Most tools output a label. scaudit outputs a **decision backed by evidence**.

```text
Label -> Evidence -> Reasoning -> Decision
```

Every annotation must answer:

- Why is this label assigned?
- What evidence supports it?
- When should it not be trusted?

## 2. No Black Boxes

scaudit avoids hiding complexity behind models.

Instead, it exposes the full annotation process:

- Which references were used.
- Which models contributed.
- Which markers support or contradict the result.

The user should always be able to trace **how a conclusion was reached**.

## 3. Multiple Methods, One Coherent View

Single-cell annotation is inherently uncertain and context-dependent. No single method is sufficient.

scaudit integrates:

- **Marker-based evidence** for biological interpretability.
- **Reference-based mapping** for biological grounding.
- **Model-based predictions** for statistical inference.
- **Ontology-aware reasoning** for hierarchical consistency.

These are unified into a single, structured representation.

## 4. Embrace Uncertainty

Ambiguity is not a failure. It is biological reality.

scaudit explicitly represents:

- Conflicting signals.
- Low-confidence assignments.
- Potential novel or disease-specific states.

Rather than forcing a label, it highlights **what is known and what is not**.

## 5. Human-in-the-Loop, Not Human-Replaced

scaudit is designed to assist expert reasoning, not replace it.

It provides:

- Structured evidence.
- Suggested interpretations.
- Alternative hypotheses.

Final interpretation remains transparent and editable.

## 6. LLM as Reasoning Layer, Not Oracle

Large language models are used to:

- Summarize evidence.
- Explain decisions.
- Detect contradictions.
- Suggest validation strategies.

They are constrained by structured inputs and **never act as the sole source of truth**.

## 7. Reproducibility by Design

Every annotation is fully traceable:

- Reference versions.
- Model configurations.
- Parameters.
- Evidence records.

scaudit ensures that results are **auditable, reproducible, and publication-ready**.
