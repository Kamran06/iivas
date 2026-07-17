# IIVAS — Project Blueprint (Section 1)

*Institutional Investor Voting Alignment Score: architecture, research framework, methodology, and engineering design.*

---

## 1.1 Objectives

The project has one scientific objective and three engineering objectives.

**Scientific.** Construct a transparent, reproducible metric, the Institutional Investor Voting Alignment Score (IIVAS), that quantifies the degree to which a large asset manager supports company management when it votes on shareholder and management proposals, and to do so separately for governance, executive-compensation, and ESG proposals. The metric must be defensible to a finance audience: every component must map to a construct in the stewardship and agency-theory literature, and every transformation must be documented.

**Engineering.** (i) Build an automated, rate-compliant acquisition layer for SEC Form N-PX filings; (ii) parse heterogeneous filing formats into one normalized relational schema; and (iii) deliver an analytics and dashboard layer that lets a non-technical reader answer each research question interactively.

The project is scoped to three filers (Vanguard, BlackRock, State Street) over fiscal proxy years 2019–2024. The scope is deliberately narrow so the analysis is finishable and verifiable; the architecture is built so that adding filers or years is a configuration change, not a code change.

## 1.2 Research framework

The work sits at the intersection of corporate governance and institutional investment. The conceptual chain is: ownership concentration in passive managers → limited ability to exit → reliance on voice (voting) as the stewardship mechanism → observable voting records in N-PX → measurable preferences. IIVAS operationalises the last link.

The unit of analysis is the **vote**: one (investor, company, proposal, year) record with a categorical outcome (For / Against / Abstain / Withhold) and the management recommendation. Research questions are answered at three levels of aggregation:

- **Investor level** (RQ1–3, primary RQ): aggregate support rates and IIVAS components per manager.
- **Cross-sectional** (RQ4–5): support rates conditioned on industry and company size (market-cap quintile).
- **Longitudinal** (RQ6): support rates per year, with trend tests.
- **Predictive** (RQ7): a supervised model of `support_management` on company and proposal features, with SHAP attribution.

The design is descriptive and predictive, not causal. We are careful throughout the documentation to frame findings as associations, because filing selection, classification error, and unobserved engagement (private "behind-the-scenes" stewardship) all threaten causal interpretation (see `PROJECT_EVALUATION.md`).

## 1.3 Methodology

The methodology is a seven-stage pipeline, each stage idempotent and independently runnable.

1. **Acquire.** Resolve each filer's CIK, pull its submission index from EDGAR's JSON API, filter to N-PX, and download the filing documents to `data/raw/`. (Section 2.)
2. **Parse.** Convert N-PX XML/HTML into a long-format `votes` dataframe. Handle both the legacy free-text layout and the post-2024 structured schema. (Section 2.)
3. **Clean.** Standardise issuer names, resolve duplicate votes (re-filed amendments), normalise outcome and recommendation codes, impute or flag missing fields. (Section 4.)
4. **Classify.** Tag each proposal into one of five categories using a deterministic rule layer first, then a TF-IDF + logistic-regression model for the residual. (Section 5.)
5. **Persist.** Load the cleaned, classified records into the normalized PostgreSQL schema. (Section 3.)
6. **Score.** Compute Governance, Compensation, ESG, and Management-Alignment sub-scores and the composite IIVAS. (Section 6.)
7. **Analyse & explain.** EDA, publication-quality visualisation, predictive modelling, and SHAP explainability. (Sections 7–10.)

Outputs feed two dashboards (Section 11): a Power BI report for executive consumption and a self-contained HTML/Plotly dashboard for portfolio reviewers without a Power BI licence.

## 1.4 Data pipeline (logical view)

```
                ┌──────────────────────────────────────────────────────┐
                │                    SEC EDGAR                           │
                │  data.sec.gov/submissions  +  /Archives/edgar/data     │
                └───────────────┬──────────────────────────────────────┘
                                │  HTTPS (rate-limited, User-Agent set)
                                ▼
   ┌────────────────┐   raw XML/HTML   ┌────────────────┐  long df  ┌──────────────┐
   │ edgar_         │ ───────────────▶ │ npx_parser.py  │ ────────▶ │ clean_votes  │
   │ downloader.py  │   data/raw/      │ (lxml/bs4)     │           │ .py          │
   └────────────────┘                  └────────────────┘           └──────┬───────┘
                                                                            │ tidy votes
                                                                            ▼
                                            ┌───────────────────────────────────────┐
                                            │ classification (rule_based + ml)        │
                                            └──────────────────┬──────────────────────┘
                                                               │ categorized votes
                              ┌────────────────────────────────┼───────────────────────────┐
                              ▼                                 ▼                           ▼
                     ┌────────────────┐               ┌────────────────┐          ┌──────────────────┐
                     │ load_to_db.py  │──PostgreSQL──▶│ metrics/iivas  │          │ modeling/        │
                     │ (SQLAlchemy)   │   (6 tables)  │ .py            │          │ train + shap     │
                     └────────────────┘               └───────┬────────┘          └────────┬─────────┘
                                                              │ scores                     │ preds/shap
                                                              ▼                            ▼
                                                  ┌───────────────────────────────────────────────┐
                                                  │  Dashboards: Power BI (.pbix) + Plotly (.html)  │
                                                  └───────────────────────────────────────────────┘
```

## 1.5 Technology stack

| Layer | Tools | Rationale |
|---|---|---|
| Language | Python 3.11, SQL | Standard for analytics; SQL for set-based aggregation |
| Acquisition | `requests`, `sec-edgar-downloader`, `edgartools` | EDGAR JSON API + convenience wrappers |
| Parsing | `lxml`, `beautifulsoup4`, `pandas` | XML/HTML robustness + tidy frames |
| Storage | PostgreSQL 15, `SQLAlchemy`, `psycopg2` | ACID relational store, normalized schema |
| NLP / classify | `scikit-learn` (TF-IDF, LogisticRegression), `nltk` | Lightweight, interpretable text model |
| ML | `scikit-learn`, `xgboost`, `imbalanced-learn` | Linear baseline → tree ensembles |
| Explainability | `shap` | Model-agnostic Shapley attributions |
| Visualisation | `matplotlib`, `seaborn`, `plotly` | Static (paper) + interactive (dashboard) |
| BI | Power BI Desktop + DAX | Executive dashboard; industry-standard |
| QA / tooling | `pytest`, `black`, `ruff`, `python-dotenv` | Tests, formatting, linting, secrets |
| Repro | `requirements.txt`, `config.yaml`, fixed `random_seed` | Deterministic re-runs |

## 1.6 Folder structure

See the tree in `README.md` §3. Design principles: (a) `src/` is an importable package so every stage runs as `python -m src.<module>`; (b) `config/config.yaml` is the only place parameters live; (c) `data/` holds the raw→interim→processed progression and is git-ignored; (d) `docs/` carries the narrative deliverables; (e) `sql/` is plain, version-controlled DDL so the schema is reviewable in a PR.

## 1.7 Database structure

A normalized (3NF) star-leaning schema with the `votes` table as the central fact and four dimensions plus one aggregate table:

- `investors` (dimension) — the filers.
- `companies` (dimension) — issuers being voted on, with a foreign key to `industries`.
- `industries` (dimension) — SIC/GICS sector lookup.
- `proposals` (dimension) — proposal text, sponsor, category, and management recommendation.
- `votes` (fact) — one row per cast vote, foreign keys to investor / company / proposal / year.
- `yearly_statistics` (aggregate) — pre-computed per-investor-per-year support rates and IIVAS components, refreshed by the scoring stage so the dashboard reads fast.

Full DDL, keys, and indexing in Section 3 (`sql/` and `docs/ER_DIAGRAM.md`).

## 1.8 Dashboard structure

Two parallel surfaces fed from the same processed tables.

**Power BI (7 pages):** Executive Summary → Investor Rankings → ESG Analysis → Compensation Analysis → Governance Analysis → Prediction Engine → Methodology. Detailed layout, visual choices, KPI cards, DAX measures, and interaction flow in `docs/POWER_BI_DASHBOARD.md` (Section 11).

**Plotly/HTML:** a single self-contained `dashboard/iivas_dashboard.html` mirroring the headline views (rankings, category radar, time trend, industry heatmap) so reviewers can interact without a Power BI licence.

## 1.9 GitHub repository structure & conventions

- **Branching:** `main` (protected) + short-lived feature branches; PRs require the test suite to pass.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`).
- **CI (suggested):** GitHub Actions running `ruff`, `black --check`, and `pytest` on push.
- **Docs:** every `src/` subpackage maps to a numbered section in `docs/`, so a reviewer can trace any deliverable from the spec to the code.
- **Reproducibility:** pinned `requirements.txt`, a fixed seed, and a documented run order in the README make the project re-runnable end-to-end.
- **Data hygiene:** no data committed; only code, schema, and small report artefacts. License and a data-ethics note clarify that all inputs are public.
