# IIVAS — Critical Evaluation (Section 15)

An honest assessment, written as a thesis examiner would expect. The goal is
to pre-empt the questions an admissions committee or finance professor will
ask.

## Strengths

- **Reproducibility.** A single config file, pinned dependencies, a fixed
  random seed, plain SQL DDL, and a documented run order mean the entire
  pipeline can be re-executed and audited end to end. Each stage is idempotent.
- **Transparent metric.** Unlike proprietary stewardship ratings, every IIVAS
  component, weight, and transformation is documented with academic
  justification and is recomputable by a third party.
- **Defensible engineering.** Normalized 3NF schema, a hybrid (rules + NLP)
  classifier that trades nothing on interpretability, a proper linear baseline
  before tree ensembles, cross-validated tuning, and SHAP explainability rather
  than black-box importances.
- **Theory-grounded.** Each sub-score maps to a specific construct in agency
  and stewardship theory, so the numbers carry meaning, not just signal.
- **Two-surface delivery.** A Power BI report for practitioners and a
  licence-free interactive web dashboard for reviewers.

## Limitations

- **Three filers only.** With N = 3 managers, cross-sectional inference is
  descriptive, not statistical. Rankings are interpretable; significance tests
  across managers are not meaningful at this N.
- **Voting is not stewardship.** N-PX captures public votes but not private
  "behind-the-scenes" engagement, which the Big Three say is their primary
  channel. A high IIVAS may understate genuine influence exercised privately.
- **Classification error.** Even a hybrid classifier mislabels a minority of
  proposals; category-level scores inherit that error. The confidence
  threshold mitigates but does not eliminate it.
- **"Support management" is not "good governance."** Alignment is a behavioural
  measure, not a normative one. Supporting management can be the value-
  maximising vote; opposing it can be misguided. IIVAS measures behaviour, and
  the documentation is careful never to equate high alignment with bad
  stewardship.
- **ESG ambiguity.** Supporting management on an ESG item can mean opposing an
  ESG shareholder proposal. The project separates these, but any single "ESG
  score" remains a simplification.

## Data-quality concerns

- **Format heterogeneity.** Pre-2024 N-PX filings are inconsistent free-text /
  HTML; the parser is best-effort and will miss or mis-extract some rows. The
  post-2024 structured schema is far cleaner, so coverage and reliability
  improve sharply from 2024 onward, an analyst must report this asymmetry.
- **Entity resolution.** Issuer names are standardised heuristically; without a
  CUSIP/ticker crosswalk some companies may fragment or merge incorrectly,
  affecting company-level and sector cuts.
- **Filer/CIK scope.** Each manager files under multiple series/entity CIKs;
  the configured CIKs must be verified to capture the full voting universe
  before publication, or coverage will be understated.
- **External joins.** Market cap and GICS sector are not in N-PX and must be
  joined from an external source; gaps there propagate to RQ4/RQ5.

## Selection bias

- **Disclosure selection.** Only votes that must be disclosed appear; voting on
  certain holdings or via securities-lending recall decisions may be uneven.
- **Survivorship / coverage.** Companies that delist mid-window contribute
  partial histories, which can bias time trends if not handled.
- **Class imbalance.** Management-support votes vastly outnumber dissents;
  models use class weighting and report F1/ROC-AUC rather than accuracy to
  avoid the majority-class trap, but rare-class precision remains the binding
  constraint.

## Future research opportunities

- **Causal identification.** Exploit index reconstitutions (Russell 1000/2000
  cutoff) as quasi-exogenous variation in ownership to move from association to
  effect, following the Appel-Gormley-Keim design.
- **Recommendation joins.** Where licensing permits, join ISS/Glass Lewis
  recommendations to separate manager preference from proxy-advisor herding.
- **Transformer classifier.** Replace TF-IDF with a fine-tuned domain model for
  proposal text to lift category precision.
- **Broader panel.** Add active managers and mid-size passive funds to enable
  real cross-sectional statistics.
- **Incremental refresh.** Move from batch to a scheduled, EDGAR-daily-index-
  driven incremental load.

## Recommendations for publication-quality improvement

1. Verify and document the complete set of entity CIKs per manager; report
   coverage explicitly.
2. Add a CUSIP/ticker-based entity-resolution step with a manual audit sample.
3. Report a weight-sensitivity analysis (and a PCA-derived alternative) for the
   IIVAS composite.
4. Hand-label a stratified sample of proposals to measure and report classifier
   precision/recall per category.
5. Restrict the headline analysis to the 2024+ structured-filing window for
   reliability, and treat earlier years as a supplementary, caveated trend.
6. Add unit tests for the parser against fixture filings and a CI workflow.
