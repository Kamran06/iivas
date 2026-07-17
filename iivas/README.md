# Institutional Investor Voting Alignment Score (IIVAS)

**Measuring stewardship and governance preferences of large asset managers from SEC Form N-PX proxy-voting disclosures.**

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Data: SEC EDGAR](https://img.shields.io/badge/data-SEC%20EDGAR%20(public)-orange.svg)](https://www.sec.gov/edgar)

---

## 1. Overview

Institutional investors are now the dominant owners of US public equity. The "Big Three" passive managers, **Vanguard, BlackRock, and State Street**, together vote on a large share of US corporate proposals every proxy season. Because index funds cannot exit a position, *voice* (voting) is their primary stewardship channel. Since 2003 the SEC has required these managers to disclose every vote on **Form N-PX**, and since the 2024 reporting cycle in a structured, machine-readable format.

This project builds a reproducible pipeline that downloads N-PX filings from SEC EDGAR, parses them into a normalized PostgreSQL database, classifies each proposal (ESG / Executive Compensation / Board Governance / Shareholder Rights / Other), and computes a proprietary **Institutional Investor Voting Alignment Score (IIVAS)** that ranks managers on how often they support versus challenge management. A machine-learning layer then predicts vote outcomes and a SHAP layer explains the drivers.

### Primary research question
> Can institutional investors be systematically ranked according to their voting behaviour on corporate governance, executive compensation, and ESG proposals?

### Secondary questions
1. Which manager most often supports management recommendations?
2. Which manager is most supportive of ESG proposals?
3. Which manager most often opposes executive-compensation proposals?
4. Do voting patterns vary by industry?
5. Do voting patterns vary by company size?
6. Have voting patterns changed over time?
7. Can voting behaviour be predicted from company and proposal characteristics?

---

## 2. Key features

- **Automated SEC EDGAR acquisition** with rate-limiting and a compliant `User-Agent` (`requests`, `sec-edgar-downloader`, `edgartools`).
- **Robust N-PX XML parsing** that handles both legacy free-text and the post-2024 structured schema (`lxml`, `beautifulsoup4`).
- **Normalized 6-table PostgreSQL schema** (investors, companies, proposals, votes, industries, yearly_statistics) with keys and indexes.
- **Hybrid proposal classifier**: deterministic rule layer + TF-IDF / logistic-regression NLP fallback.
- **IIVAS metric**: Governance, Compensation, ESG, and Management-Alignment sub-scores combined into a normalized composite.
- **Predictive modelling**: Logistic Regression, Random Forest, XGBoost with cross-validation and hyperparameter tuning.
- **Explainability**: SHAP global and local attributions.
- **Dashboards**: a 7-page Power BI specification (DAX included) **and** a self-contained interactive Plotly/HTML dashboard you can open in any browser.

---

## 3. Repository structure

```
iivas/
├── README.md                  ← this file
├── LICENSE                    ← MIT
├── requirements.txt
├── .gitignore
├── config/
│   └── config.yaml            ← single source of truth for all parameters
├── docs/
│   ├── PROJECT_BLUEPRINT.md   ← §1 architecture & methodology
│   ├── METHODOLOGY.md         ← §6 IIVAS formulas + academic justification
│   ├── ER_DIAGRAM.md          ← §3 database design narrative
│   ├── POWER_BI_DASHBOARD.md  ← §11 dashboard spec + DAX
│   ├── ACADEMIC_DISCUSSION.md ← §12 theory & contribution
│   ├── RESUME_DESCRIPTIONS.md ← §13 portfolio copy
│   └── PROJECT_EVALUATION.md  ← §15 strengths, limitations, future work
├── sql/
│   ├── 01_create_tables.sql
│   ├── 02_indexes.sql
│   └── 03_views.sql
├── src/
│   ├── data_acquisition/      ← §2 edgar_downloader.py, npx_parser.py
│   ├── database/              ← db_connection.py, load_to_db.py
│   ├── preprocessing/         ← §4 clean_votes.py
│   ├── classification/        ← §5 rule_based.py, ml_classifier.py
│   ├── metrics/               ← §6 iivas.py
│   ├── eda/                   ← §7 exploratory.py
│   ├── visualization/         ← §8 plots.py
│   └── modeling/              ← §9/§10 features.py, train_models.py, shap_analysis.py
├── dashboard/
│   └── iivas_dashboard.html   ← working interactive dashboard
├── notebooks/                 ← optional analysis notebooks
├── tests/
│   └── test_iivas.py
└── data/                      ← raw / interim / processed (git-ignored)
```

---

## 4. Installation

```bash
# 1. Clone
git clone https://github.com/<your-handle>/iivas.git
cd iivas

# 2. Create an isolated environment
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (One-off) download NLTK stopwords used by the classifier
python -c "import nltk; nltk.download('stopwords'); nltk.download('punkt')"

# 5. Provision PostgreSQL (local example)
createdb iivas
psql -d iivas -f sql/01_create_tables.sql
psql -d iivas -f sql/02_indexes.sql
psql -d iivas -f sql/03_views.sql

# 6. Configure secrets
cp .env.example .env                 # then edit DB_* values
#   Also edit config/config.yaml -> sec.user_agent with YOUR name + email.
```

> **SEC compliance:** EDGAR requires a descriptive `User-Agent` containing a contact email and enforces a 10 requests/second ceiling. Set this in `config/config.yaml` before running any acquisition step or requests will return HTTP 403.

---

## 5. Usage

The pipeline is modular; run stages in order or call them from an orchestrator.

```bash
# Stage 1 – download N-PX filings for the configured filers/years
python -m src.data_acquisition.edgar_downloader

# Stage 2 – parse the downloaded XML into a tidy votes table
python -m src.data_acquisition.npx_parser

# Stage 3 – clean & deduplicate
python -m src.preprocessing.clean_votes

# Stage 4 – classify proposals
python -m src.classification.rule_based            # deterministic first pass
python -m src.classification.ml_classifier         # TF-IDF model for residual "Other"

# Stage 5 – load to PostgreSQL
python -m src.database.load_to_db

# Stage 6 – compute IIVAS
python -m src.metrics.iivas

# Stage 7 – EDA + figures
python -m src.eda.exploratory
python -m src.visualization.plots

# Stage 8 – modelling + explainability
python -m src.modeling.train_models
python -m src.modeling.shap_analysis
```

Open `dashboard/iivas_dashboard.html` directly in a browser for the interactive view, or open `iivas.pbix` in Power BI Desktop after pointing it at the PostgreSQL `public` schema (see `docs/POWER_BI_DASHBOARD.md`).

---

## 6. Methodology (summary)

IIVAS is a 0–100 composite of four normalized sub-scores. Higher = more aligned with (supportive of) management.

```
IIVAS = 100 × ( w_g·G + w_c·C + w_e·E + w_m·M )
```

where G, C, E are management-support rates on Governance, Compensation, and ESG proposals respectively, and M is the overall management-alignment rate. Default weights (0.30 / 0.25 / 0.25 / 0.20) and full derivations, normalization, and academic justification are in [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

---

## 7. Results

> Populate after a production run. The repository ships the full analysis code; results depend on the filing window you download. Suggested artefacts to commit to `reports/`:
> - IIVAS ranking table (overall and by category) for Vanguard / BlackRock / State Street.
> - Time-series of management-support rates 2019–2024.
> - Industry and market-cap breakdowns.
> - Model leaderboard (AUC / F1) and SHAP summary plot.

---

## 8. Future improvements

- Extend beyond the Big Three to a broader panel of filers for cross-sectional contrast.
- Add NLP-based proposal *outcome* sentiment and ISS/Glass Lewis recommendation joins (where licensing permits).
- Move from a batch pipeline to an incremental, scheduled refresh keyed on EDGAR's daily index.
- Replace TF-IDF with a fine-tuned transformer classifier for proposal text.
- Add causal-inference robustness (e.g., entropy-balancing) before any behavioural claims.

See [`docs/PROJECT_EVALUATION.md`](docs/PROJECT_EVALUATION.md) for a critical assessment.

---

## 9. Data & ethics

All inputs are **public** SEC Form N-PX filings retrieved from EDGAR. No confidential, proprietary, or personal data is used or redistributed. This project is for research and educational purposes and is **not** investment advice.

## 10. Citation

```bibtex
@misc{iivas2026,
  title  = {Institutional Investor Voting Alignment Score (IIVAS)},
  author = {Your Name},
  year   = {2026},
  note   = {https://github.com/<your-handle>/iivas}
}
```

## License
MIT — see [LICENSE](LICENSE).
