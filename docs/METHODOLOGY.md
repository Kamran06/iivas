# IIVAS — Metric Design & Methodology (Section 6)

This document defines the Institutional Investor Voting Alignment Score
(IIVAS), its four sub-scores, the mathematics, the normalization choices, the
interpretation framework, and the academic justification for each component.

---

## 6.1 Construct

IIVAS measures **management alignment**: the degree to which an asset manager
votes *with* company management rather than challenging it. We measure this
through proxy votes because, for large index managers that cannot sell, the
vote is the observable expression of stewardship preference (Hirschman's
*voice* rather than *exit*; Hirschman, 1970).

A vote is coded **aligned** (`support_management = 1`) when the cast vote
matches the management recommendation, **opposing** (`= 0`) when it differs,
and **undefined** (`NULL`) when no recommendation exists or the manager
abstained/withheld. Undefined votes are excluded from rate denominators so the
metric reflects decisions where alignment is actually meaningful.

## 6.2 Variable definitions

| Symbol | Definition |
|---|---|
| $V_{i,k}$ | set of defined votes by investor $i$ in category $k$ |
| $a_{v}$ | alignment indicator for vote $v$: $a_v = 1$ if cast = management rec, else $0$ |
| $r_{i,k}$ | management-support rate of investor $i$ in category $k$: $r_{i,k} = \frac{1}{|V_{i,k}|}\sum_{v \in V_{i,k}} a_v$ |
| $G_i, C_i, E_i$ | sub-scores for Board Governance, Executive Compensation, ESG |
| $M_i$ | overall management-alignment sub-score (all categories) |
| $w_g, w_c, w_e, w_m$ | composite weights (config: 0.30 / 0.25 / 0.25 / 0.20) |

## 6.3 Sub-scores

Each category support rate $r_{i,k} \in [0,1]$ is mapped linearly to a 0–100 scale:

$$ G_i = 100\, r_{i,\text{Governance}}, \quad C_i = 100\, r_{i,\text{Compensation}}, \quad E_i = 100\, r_{i,\text{ESG}} $$

$$ M_i = 100\, r_{i,\text{all}} = 100 \cdot \frac{1}{|V_i|}\sum_{v \in V_i} a_v $$

A score of 100 means the manager always sided with management in that
category; 0 means it always opposed.

## 6.4 Composite

$$ \text{IIVAS}_i = \frac{w_g G_i + w_c C_i + w_e E_i + w_m M_i}{w_g + w_c + w_e + w_m} $$

With the default weights summing to 1.0 the denominator is 1; the explicit
denominator matters for **graceful degradation**: if a manager has no votes in
a category that year, that term and its weight are dropped and the remaining
weights renormalised, so a missing category does not bias the composite toward
zero. This is implemented in `src/metrics/iivas.py::compute_scores`.

### Weight justification
- **Governance (0.30)** carries the most weight because director elections and
  auditor ratification are the highest-volume, highest-stakes recurring votes
  and are the classic locus of the agency conflict (Jensen & Meckling, 1976).
- **Compensation (0.25)** and **ESG (0.25)** are equally weighted: say-on-pay
  and ESG shareholder proposals are the two arenas where the Big Three most
  visibly diverge from each other, so they carry strong discriminating power.
- **Management alignment (0.20)** is a lower-weight stabiliser capturing the
  base-rate tendency across *all* proposals, smoothing categories with thin
  samples.

The weights are configurable; `docs/PROJECT_EVALUATION.md` discusses a
sensitivity analysis and an unsupervised (PCA) alternative for setting them.

## 6.5 Normalization

Two normalization layers are offered:

1. **Scale normalization (default):** rates → 0–100, already comparable across
   managers because all face roughly the same proposal universe.
2. **Cross-sectional z-normalization (optional, for ranking emphasis):**
   $z_{i} = (\text{IIVAS}_i - \overline{\text{IIVAS}}) / \sigma_{\text{IIVAS}}$,
   which expresses each manager relative to the panel mean. With only three
   filers the z-form is presented for interpretation, not inference.

## 6.6 Interpretation framework

| IIVAS band | Reading |
|---|---|
| 80–100 | Strongly management-aligned; rarely dissents (typical of passive default-support posture) |
| 60–80 | Generally supportive; selective dissent on specific categories |
| 40–60 | Balanced / contested; meaningful challenge on at least one category |
| < 40 | Frequently challenges management; activist-leaning voting posture |

Because the three managers are all large and passive, observed scores tend to
cluster high; the **category sub-scores and their spread** are usually more
informative than the composite. A low ESG sub-score alongside a high
governance sub-score, for example, signals a manager that defers to management
on board matters but pushes back on ESG shareholder proposals.

## 6.7 Mapping to research questions
- **RQ1 (most pro-management):** highest $M_i$.
- **RQ2 (most ESG-supportive of shareholder ESG proposals):** lowest $E_i$ on
  *management* recommendations is ambiguous, so ESG is additionally reported as
  support-for-shareholder-ESG-proposals (a separate cut in EDA) to avoid the
  trap where "supporting management" on an ESG item can mean *opposing* an ESG
  shareholder proposal. This nuance is documented in EDA and the evaluation.
- **RQ3 (most likely to oppose compensation):** lowest $C_i$.
- **RQ4–6:** $r_{i,k}$ recomputed within sector / market-cap bucket / year.

## 6.8 References (selected)
- Hirschman, A. O. (1970). *Exit, Voice, and Loyalty.* Harvard UP.
- Jensen, M., & Meckling, W. (1976). Theory of the firm. *J. Financial Economics*.
- Bebchuk, L., & Hirst, S. (2019). Index funds and the future of corporate governance. *Columbia Law Review*.
- Appel, I., Gormley, T., & Keim, D. (2016). Passive investors, not passive owners. *J. Financial Economics*.
