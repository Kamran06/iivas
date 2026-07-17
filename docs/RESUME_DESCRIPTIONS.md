# IIVAS — Portfolio & Application Copy (Section 13)

Reusable descriptions for a CV, LinkedIn, and a graduate statement of purpose.
Edit the bracketed figures after a real data run.

---

## 1. One-line resume bullet

> Built IIVAS, an end-to-end Python/SQL pipeline that scores Vanguard, BlackRock, and State Street on proxy-voting alignment using SEC N-PX filings, with NLP proposal classification, ML prediction (ROC-AUC [0.8x]), SHAP explainability, and Power BI/Plotly dashboards.

## 2. Three-line resume project description

> **Institutional Investor Voting Alignment Score (IIVAS)** — independent research project.
> Designed and implemented a reproducible analytics pipeline that ingests SEC Form N-PX proxy-voting filings, normalizes them into a PostgreSQL schema, and classifies proposals (ESG, compensation, governance, shareholder rights) with a hybrid rule-based + TF-IDF model.
> Engineered a proprietary stewardship metric, trained Logistic Regression / Random Forest / XGBoost models to predict management-support votes, explained drivers with SHAP, and delivered a 7-page Power BI dashboard plus an interactive web dashboard.

## 3. LinkedIn project description

> **Institutional Investor Voting Alignment Score (IIVAS)**
>
> How differently do the "Big Three" asset managers, Vanguard, BlackRock, and State Street, vote on the proposals that shape corporate America? I built a full data-science project to answer that from public SEC Form N-PX filings.
>
> The pipeline automatically downloads filings from SEC EDGAR (rate-limited, compliant), parses heterogeneous XML/HTML into a normalized PostgreSQL database, and classifies every proposal into ESG, executive compensation, board governance, or shareholder rights using a hybrid rule-based + NLP (TF-IDF / logistic regression) classifier.
>
> On top of that I designed IIVAS, a transparent 0–100 composite measuring how often each manager aligns with company management, decomposed into governance, compensation, and ESG sub-scores with documented weights and academic justification. I then trained and tuned three ML models (Logistic Regression, Random Forest, XGBoost) to predict vote outcomes, used SHAP to surface the drivers, and shipped both a Power BI report and a self-contained interactive web dashboard.
>
> Tech: Python (pandas, scikit-learn, XGBoost, SHAP, Plotly), SQL/PostgreSQL, Power BI. All code, schema, and documentation are open-source on GitHub.
>
> #DataScience #CorporateGovernance #ESG #FinanceAnalytics #Python #MachineLearning

## 4. Graduate-school statement-of-purpose paragraph

> My interest in [Business/Finance/Data] Analytics crystallised while building the Institutional Investor Voting Alignment Score, a project I pursued to understand how the largest asset managers exercise their growing influence over public companies. Working only from public SEC Form N-PX filings, I built an end-to-end pipeline, automated data acquisition, a normalized relational database, NLP-based proposal classification, a purpose-designed stewardship metric grounded in agency and stewardship theory, predictive modelling, and explainable-AI analysis, and presented the results through interactive dashboards. The project taught me to move fluently between the technical (handling messy, inconsistently formatted regulatory filings; tuning and validating models) and the conceptual (translating governance theory into a defensible quantitative construct, and being disciplined about the line between description and causal claims). It is exactly this combination, rigorous data engineering in service of substantive questions in finance and governance, that I hope to deepen in your programme, where I aim to extend the work toward causal identification and a broader panel of institutional investors.
