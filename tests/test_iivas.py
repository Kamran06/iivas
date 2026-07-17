"""
Unit tests for the deterministic, data-independent parts of the pipeline:
the rule-based classifier, issuer standardisation, support derivation, and
the IIVAS scoring maths. These run without any SEC download or database.

    pytest -q
"""
import numpy as np
import pandas as pd

from src.classification.rule_based import classify_text
from src.preprocessing.clean_votes import standardize_issuer, derive_support
from src.metrics.iivas import compute_scores


def test_classify_compensation():
    assert classify_text("advisory vote on executive compensation") == "Executive Compensation"
    assert classify_text("approve say-on-pay") == "Executive Compensation"


def test_classify_esg():
    assert classify_text("report on greenhouse gas emissions and climate risk") == "ESG"
    assert classify_text("adopt diversity equity and inclusion targets") == "ESG"


def test_classify_governance_and_rights():
    assert classify_text("elect director jane doe") == "Board Governance"
    assert classify_text("adopt proxy access bylaw") == "Shareholder Rights"


def test_classify_other():
    assert classify_text("approve the minutes of the prior meeting") == "Other"


def test_standardize_issuer_strips_suffixes():
    assert standardize_issuer("Apple Inc.") == "APPLE"
    assert standardize_issuer("The Coca-Cola Company") == "COCA-COLA"


def test_derive_support():
    assert derive_support({"vote_cast": "For", "management_recommendation": "For"}) == 1
    assert derive_support({"vote_cast": "Against", "management_recommendation": "For"}) == 0
    assert np.isnan(derive_support({"vote_cast": "Abstain", "management_recommendation": "For"}))


def test_compute_scores_basic():
    df = pd.DataFrame({
        "filer": ["X"] * 4,
        "category": ["Board Governance", "ESG", "Executive Compensation", "ESG"],
        "support_management": [1, 0, 1, 1],
    })
    out = compute_scores(df, ["filer"])
    row = out.iloc[0]
    assert row["governance_score"] == 100.0          # 1/1
    assert row["esg_score"] == 50.0                   # 1/2
    assert row["compensation_score"] == 100.0         # 1/1
    assert 0 <= row["iivas_composite"] <= 100
