# Methods

This document captures a paper-style or technical white-paper style Methods section for scaudit. It formalizes the annotation task as evidence aggregation and decision-making rather than direct classification.

## 1. Problem Formulation

Given a single-cell RNA-seq dataset:

```math
X \in \mathbb{R}^{n \times p}
```

where `n` is the number of cells and `p` is the number of genes.

Optional cluster labels are defined as:

```math
c(i) \in \{1,\dots,K\}
```

for example Leiden clusters.

The goal is to assign a cell type label to each cell or cluster `k`:

```math
y_k \in \mathcal{Y}
```

while also producing an **interpretable and auditable evidence structure** `E_k` and a final decision `D_k`.

We define annotation as a tuple:

```math
A_k = (E_k, R_k, D_k)
```

where:

- `E_k`: multi-source evidence.
- `R_k`: reasoning process.
- `D_k`: final decision.

## 2. Data Preprocessing

Input data is normalized and transformed:

```math
X' = \log(1 + \mathrm{Normalize}(X))
```

Highly variable genes are selected:

```math
X^{HVG} = \mathrm{SelectHVG}(X')
```

Dimensionality reduction is performed:

```math
Z = \mathrm{PCA}(X^{HVG}) \in \mathbb{R}^{n \times d}
```

If needed, a neighborhood graph is constructed and clustering is performed:

```math
G = \mathrm{kNN}(Z), \quad c = \mathrm{Cluster}(G)
```

## 3. Reference Selection

Given metadata:

```math
m = (\mathrm{species}, \mathrm{tissue}, \mathrm{disease}, \mathrm{technology})
```

scaudit selects a subset `\mathcal{R}^*` from a reference library `\mathcal{R}`.

For each reference `r \in \mathcal{R}`, define a scoring function:

```math
S(r \mid X) = \alpha S_{\mathrm{meta}} + \beta S_{\mathrm{gene}} + \gamma S_{\mathrm{embed}}
```

where:

- `S_meta`: metadata match, including species, tissue, and disease.
- `S_gene`: gene overlap ratio.
- `S_embed`: embedding similarity, for example PCA or scVI latent similarity.

Gene overlap is defined as:

```math
S_{\mathrm{gene}} = \frac{|G_X \cap G_r|}{|G_X|}
```

References are selected as:

```math
\mathcal{R}^* = \mathrm{Top}\text{-}k \{ S(r \mid X) \}
```

## 4. Evidence Construction

For each cluster `k`, scaudit constructs a multi-modal evidence set:

```math
E_k = \{ E_k^{\mathrm{marker}}, E_k^{\mathrm{ref}}, E_k^{\mathrm{model}}, E_k^{\mathrm{ontology}} \}
```

## 4.1 Marker-Based Evidence

Differential expression is computed as:

```math
\Delta_{k,g} = \log \frac{\mu_{k,g} + \epsilon}{\mu_{\neg k,g} + \epsilon}
```

The top marker set is selected as:

```math
M_k = \{ g \mid \Delta_{k,g} > \tau \}
```

Marker score is defined as:

```math
S_{\mathrm{marker}}(y \mid k) = \frac{1}{|M_y|} \sum_{g \in M_y} \mathbf{1}(g \in M_k)
```

## 4.2 Reference-Based Evidence

The query embedding `Z` is projected into a reference latent space:

```math
Z_r = f_r(X)
```

Similarity, such as cosine similarity, is computed as:

```math
S_{\mathrm{ref}}(y \mid k) = \frac{1}{|k|} \sum_{i \in k} \max_{j \in r_y} \cos(Z_i, Z_j)
```

where `r_y` is the set of cells labeled as `y` in the reference.

## 4.3 Model-Based Evidence

For each model `m`, prediction probabilities are obtained:

```math
P_m(y \mid i)
```

Cluster-level aggregation is defined as:

```math
S_{\mathrm{model}}(y \mid k) = \frac{1}{|k|} \sum_{i \in k} P_m(y \mid i)
```

Multi-model aggregation is defined as:

```math
S_{\mathrm{model}}^{\mathrm{agg}}(y \mid k) = \sum_m w_m S_{\mathrm{model}}(y \mid k)
```

## 4.4 Ontology-Based Evidence

Given an ontology graph `\mathcal{O}`, parent-child relationships are defined as:

```math
y_{\mathrm{parent}} = \mathrm{Parent}(y)
```

Hierarchical consistency is computed as:

```math
S_{\mathrm{onto}}(y \mid k) = \mathbf{1}(\mathrm{consistent\ across\ levels})
```

## 5. Evidence Fusion

Multi-source evidence is integrated as:

```math
S(y \mid k) =
w_1 S_{\mathrm{marker}} +
w_2 S_{\mathrm{ref}} +
w_3 S_{\mathrm{model}}^{\mathrm{agg}} +
w_4 S_{\mathrm{onto}}
```

The candidate label is selected as:

```math
\hat{y}_k = \arg\max_y S(y \mid k)
```

## 6. Uncertainty Quantification

### 6.1 Model Disagreement

```math
U_{\mathrm{model}} = 1 - \max_y S_{\mathrm{model}}^{\mathrm{agg}}(y \mid k)
```

### 6.2 Reference Distance

```math
U_{\mathrm{ref}} = 1 - \max_y S_{\mathrm{ref}}(y \mid k)
```

### 6.3 Marker Inconsistency

```math
U_{\mathrm{marker}} = 1 - S_{\mathrm{marker}}(\hat{y}_k \mid k)
```

Total uncertainty is defined as:

```math
U_k = \lambda_1 U_{\mathrm{model}} + \lambda_2 U_{\mathrm{ref}} + \lambda_3 U_{\mathrm{marker}}
```

## 7. Decision Rule

The final decision is:

```math
D_k =
\begin{cases}
\mathrm{Accepted} & \mathrm{if}\ S(\hat{y}_k) > \tau_1 \land U_k < \delta_1 \\
\mathrm{Ambiguous} & \mathrm{if}\ S(\hat{y}_k) > \tau_2 \\
\mathrm{Unknown} & \mathrm{if}\ U_k > \delta_2 \\
\mathrm{Needs\ review} & \mathrm{otherwise}
\end{cases}
```

## 8. LLM-Assisted Reasoning

Given structured evidence `E_k`, construct an input:

```math
I_k = \mathrm{Serialize}(E_k)
```

The LLM output is:

```math
R_k = \mathrm{LLM}(I_k)
```

The LLM does not directly generate labels. It is used only for:

- Evidence summarization.
- Contradiction detection.
- Explanation generation.

## 9. Annotation Record

Each cluster's final output is:

```math
A_k = (E_k, R_k, D_k)
```

It is stored as:

```json
{
  "cluster": "k",
  "label": "y_hat",
  "scores": {},
  "uncertainty": "U_k",
  "evidence": {},
  "reasoning": "...",
  "decision": "Accepted/Ambiguous/Unknown"
}
```

## 10. Pipeline Summary

```text
Input X
-> Preprocessing
-> Reference selection
-> Evidence computation
-> Evidence fusion
-> Uncertainty estimation
-> Decision
-> LLM explanation
-> Output annotation records
```

## Core Methods Statement

```text
We formalize single-cell annotation as an evidence aggregation and decision problem,
rather than a direct classification task.
```
