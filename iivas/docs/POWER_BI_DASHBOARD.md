# IIVAS — Power BI Dashboard Specification (Section 11)

A 7-page Power BI report built directly on the PostgreSQL `public` schema
(import mode, or DirectQuery against `v_votes_enriched`). A licence-free
interactive mirror ships as `dashboard/iivas_dashboard.html`.

## Data model in Power BI
Import the dimension tables (`investors`, `companies`, `industries`,
`proposals`), the fact (`votes`), and `yearly_statistics`. Relationships mirror
the SQL foreign keys (single-direction, one-to-many from each dimension to
`votes`). Mark `proposals[category]` and `companies[market_cap_bucket]` as the
primary slicer fields. Create a disconnected `Year` table for the timeline.

---

## Page 1 — Executive Summary
**Goal:** one-screen answer to "who aligns with management, and how has it
moved?"

- **KPI cards (top row):** IIVAS composite per manager (3 cards), each with a
  trend sparkline and YoY delta.
- **Bar chart:** IIVAS composite ranking (sorted).
- **Line chart:** management-support rate by year, one line per manager.
- **Card:** total votes analysed; date range.
- **Slicers:** Year range, Proposal category.

## Page 2 — Investor Rankings
- **Matrix:** rows = managers, columns = the four sub-scores + composite,
  conditional-formatting data bars.
- **Clustered bar:** support rate by manager within selected category.
- **Decomposition tree:** support rate broken down by category → sponsor →
  sector (drill path).

## Page 3 — ESG Analysis
- **KPI cards:** ESG management-support rate and ESG *shareholder-proposal*
  support rate per manager (the two are distinct; see methodology §6.7).
- **Stacked column:** ESG vote outcomes (For/Against/Abstain) by manager.
- **Line:** ESG support trend by year.
- **Table:** top 20 ESG proposals by share count with each manager's vote.

## Page 4 — Compensation Analysis
- **KPI cards:** say-on-pay support rate per manager.
- **Clustered bar:** compensation support by manager × market-cap bucket (RQ5).
- **Scatter:** compensation support rate vs. company size.
- **Line:** compensation support trend by year.

## Page 5 — Governance Analysis
- **KPI cards:** director-election support rate per manager.
- **Heatmap (matrix w/ colour):** governance support by manager × sector (RQ4).
- **Bar:** support on shareholder-rights proposals (proxy access, special
  meeting) per manager.

## Page 6 — Prediction Engine
- **What-if parameters:** Investor, Sector, Market-cap bucket, Category, Year.
- **Card:** predicted probability of `support_management` (from a scored table
  produced by `train_models` and written back to the DB, or via a Power BI
  Python/AzureML scoring step).
- **Bar:** top SHAP drivers for the selected scenario (from
  `shap_importance_*.csv`).
- **Gauge:** model ROC-AUC (from `model_leaderboard.csv`).

## Page 7 — Methodology
Text + image page summarising the IIVAS formula, weights, data source, and
limitations. Embed the radar and Sankey figures. Link to the GitHub repo.

---

## DAX measures

```DAX
-- Defined votes only (denominator for all rates)
Defined Votes =
CALCULATE ( COUNTROWS ( votes ), NOT ISBLANK ( votes[support_management] ) )

-- Overall management-support rate (Management Alignment, 0-1)
Mgmt Support Rate =
DIVIDE (
    CALCULATE ( SUM ( votes[support_management] ), NOT ISBLANK ( votes[support_management] ) ),
    [Defined Votes]
)

-- Category-scoped support rate (respects the page/slicer category filter)
Category Support Rate =
DIVIDE (
    CALCULATE ( SUM ( votes[support_management] ), NOT ISBLANK ( votes[support_management] ) ),
    [Defined Votes]
)

-- Sub-scores on the 0-100 scale
Governance Score =
CALCULATE ( [Category Support Rate] * 100, proposals[category] = "Board Governance" )

Compensation Score =
CALCULATE ( [Category Support Rate] * 100, proposals[category] = "Executive Compensation" )

ESG Score =
CALCULATE ( [Category Support Rate] * 100, proposals[category] = "ESG" )

Mgmt Alignment Score = [Mgmt Support Rate] * 100

-- Composite with config weights (0.30/0.25/0.25/0.20)
IIVAS Composite =
VAR g = [Governance Score]   VAR c = [Compensation Score]
VAR e = [ESG Score]          VAR m = [Mgmt Alignment Score]
RETURN 0.30*g + 0.25*c + 0.25*e + 0.20*m

-- Year-over-year delta for KPI cards
IIVAS YoY =
VAR cur = [IIVAS Composite]
VAR prev =
    CALCULATE ( [IIVAS Composite], DATEADD ( 'Year'[Year], -1, YEAR ) )
RETURN cur - prev

-- ESG shareholder-proposal support (substantive ESG support, RQ2)
ESG Shareholder For Rate =
CALCULATE (
    DIVIDE (
        CALCULATE ( COUNTROWS ( votes ), votes[vote_cast] = "For" ),
        COUNTROWS ( votes )
    ),
    proposals[category] = "ESG",
    proposals[proposal_sponsor] = "Shareholder"
)
```

## User interaction flow
Landing on **Executive Summary**, the reader sets a Year range and (optionally)
a category; KPI cards and trend update via cross-filtering. Clicking a
manager's bar cross-highlights every other page through the shared data model.
**Prediction Engine** is parameter-driven rather than filter-driven so the
reader can pose counterfactual scenarios. **Methodology** is static reference.

## Visual-selection rationale
KPI cards for the few headline numbers; bars for cross-manager comparison
(position is the most accurate visual encoding); lines for time; a colour
matrix/heatmap for the two-way manager×sector cut; decomposition tree for
guided drill-down; radar reserved for the four-axis profile where shape
comparison is the point.
