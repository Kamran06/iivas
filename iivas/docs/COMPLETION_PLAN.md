# IIVAS — Completion Plan (single runbook)

Everything left to take this from "code + framework" to a finished, portfolio-
ready project, in order. Each task lists what to do, the command or file, and
how you know it worked ("done when"). Check them off top to bottom.

---

## Phase 0 — Local setup (≈20 min)
- [ ] **0.1 Clone & environment.** `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
  Done when `pip check` reports no broken requirements.
- [ ] **0.2 NLTK data.** `python -c "import nltk; nltk.download('stopwords'); nltk.download('punkt')"`
  Done when it prints `True`.
- [ ] **0.3 Run the tests.** `python -m pytest -q`
  Done when all tests pass (validates the classifier + IIVAS maths).

## Phase 1 — Data source integrity (≈1 hr) — DO THIS FIRST, it gates everything
> Status update (2026-07 audit): entity identities were verified against the
> SEC submissions API. The originally configured CIKs were the WRONG entities
> for full voting records (0000102909 = Vanguard Group Inc, the adviser;
> 0000093751 = State Street Corp, the holding company; 0001761055 =
> BlackRock ETF Trust, one trust among many). Full N-PX voting is filed by
> the fund registrants (trusts), many per family. The repo now ships
> `src/data_acquisition/filer_discovery.py`, which enumerates actual N-PX
> filer CIKs per family from EDGAR's quarterly form indexes.
- [ ] **1.1 Run filer discovery.** `python -m src.data_acquisition.filer_discovery`
  Done when `data/interim/filers_resolved.json` lists a plausible set of
  trusts per family (expect dozens, e.g. Vanguard Index Funds, iShares Trust,
  SPDR trusts). Spot-check 3 CIKs on EDGAR.
- [ ] **1.2 Set your User-Agent.** Put a real name + email in `.env` `SEC_USER_AGENT`.
  Done when a test fetch returns HTTP 200, not 403.
- [ ] **1.3 Decide scope.** A full multi-trust, multi-year pull is millions of
  rows and exceeds Supabase's free tier. Recommended: `start_year: 2024`
  (structured filings only) for the headline analysis. Done when config
  reflects a deliberate scope choice.
- [ ] **1.4 Smoke-test acquisition on ONE trust/year** before a full pull.
  Done when files land in `data/raw/<Filer>/` and `manifest.json` is written.

## Phase 2 — Database (Supabase) (≈30 min)
- [ ] **2.1 Create the Supabase project** and copy the connection URI. (`docs/SUPABASE_SETUP.md` Part 1.)
- [ ] **2.2 Create schema** by running `sql/01`, `sql/02`, `sql/03` in the SQL editor or via psql.
  Done when `investors, companies, industries, proposals, votes, yearly_statistics` exist.
- [ ] **2.3 Wire `.env`** with `DATABASE_URL`; test the connection helper.
  Done when the `get_engine().connect()` check prints connected.

## Phase 3 — Full pipeline run (≈1 hr, mostly download time)
- [ ] **3.1 Run end to end.** `python -m src.run_pipeline`
  Done when stage 7 prints "Pipeline complete" and `data/processed/iivas_overall.csv` exists.
- [ ] **3.2 Sanity-check the parse.** Spot-check 10 rows of `votes_clean.parquet`
  against the original filing text; confirm outcomes/recommendations look right.
  Done when the sample matches the source filings.
- [ ] **3.3 Load check in Supabase.** `SELECT investor_name, COUNT(*) FROM votes v JOIN investors i USING(investor_id) GROUP BY 1;`
  Done when each manager has a plausible vote count.

## Phase 4 — Data quality & enrichment (≈2–4 hrs) — raises it from "runs" to "credible"
- [ ] **4.1 Entity resolution.** Add a CUSIP/ticker crosswalk so issuers don't
  fragment; audit a stratified sample of company names. (Improves RQ4/RQ5.)
- [ ] **4.2 Join market cap + GICS sector** into `companies` (external source of
  your choice), then set `market_cap_bucket`. Done when RQ4/RQ5 cuts are non-empty.
- [ ] **4.3 Classifier audit.** Hand-label ~200 stratified proposals; measure
  precision/recall per category; adjust rules/threshold. Record the numbers in
  `docs/PROJECT_EVALUATION.md`. Done when per-category precision is reported.
- [ ] **4.4 Restrict the headline window to 2024+** (structured filings) for
  reliability; treat earlier years as a caveated supplementary trend.

## Phase 5 — Analysis, modelling, results (≈2–3 hrs)
- [ ] **5.1 EDA + figures.** `python -m src.eda.exploratory && python -m src.visualization.plots`
  Done when `reports/figures/` has the bar, heatmap, radar, trend, Sankey.
- [ ] **5.2 Train + tune models.** `python -m src.modeling.train_models`
  Done when `model_leaderboard.csv` and `models/best_model.joblib` exist.
- [ ] **5.3 SHAP.** `python -m src.modeling.shap_analysis`
  Done when `shap_summary_*.png` and `shap_importance_*.csv` are produced.
- [ ] **5.4 Write up findings.** Fill the README "Results" section and answer
  RQ1–RQ7 with the actual numbers + one figure each. Done when Results is populated.

## Phase 6 — Dashboards (≈1–2 hrs)
- [ ] **6.1 HTML dashboard.** Replace the placeholder `DATA` object in
  `dashboard/iivas_dashboard.html` with real `data/processed` values; remove the
  demo banner. Done when it shows real scores.
- [ ] **6.2 Power BI (optional).** Connect to Supabase, build the 7 pages and DAX
  from `docs/POWER_BI_DASHBOARD.md`, save `iivas.pbix`.

## Phase 7 — Automation (≈30 min)
- [ ] **7.1 Push to GitHub.** Done when the repo is up with CI green.
- [ ] **7.2 Add secrets** `DATABASE_URL` and `SEC_USER_AGENT` (repo Settings).
- [ ] **7.3 Test the workflow** via Actions -> Run workflow; confirm Supabase
  updates. It then auto-runs 1 Mar & 1 Sep. Done when a manual run succeeds.

## Phase 8 — Portfolio polish (≈1–2 hrs)
- [ ] **8.1 Add a CI badge, screenshots** of the dashboard/figures to the README.
- [ ] **8.2 Weight-sensitivity note.** Report how IIVAS moves under alternative
  weights (and a PCA-derived alternative) in `docs/METHODOLOGY.md`.
- [ ] **8.3 Final proofread** of all `docs/`; confirm every claim is
  description, not unsupported causation.
- [ ] **8.4 Tag a release** `v1.0`; drop the repo link into your CV / LinkedIn /
  SOP using the copy in `docs/RESUME_DESCRIPTIONS.md`.

---

### Critical path (if short on time)
1.1 → 1.2 → 2.1–2.3 → 3.1 → 4.2 → 5.1–5.4 → 6.1 → 7.1–7.3.
Phases 4.1/4.3 and 8 are quality multipliers; skip only under deadline pressure
and note the gaps in the evaluation doc.

### Definition of done
The workflow runs unattended, Supabase holds verified votes for all three
managers, the README reports real RQ1–RQ7 answers with figures, the dashboard
shows live numbers, and every limitation is documented.
