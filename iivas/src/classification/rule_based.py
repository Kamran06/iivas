"""
Section 5 — rule-based proposal classifier.

Deterministic first pass that assigns each proposal to one of:
  ESG, Executive Compensation, Board Governance, Shareholder Rights, Other.

Rationale: a large share of N-PX proposals are boilerplate ("Elect Director
X", "Ratify auditors", "Advisory vote on executive compensation"). Keyword
rules classify these with near-perfect precision and zero training data, and
the residual ambiguous text is handed to the ML classifier (ml_classifier.py).
The ordering of rules matters: more specific categories are tested first.
"""
from __future__ import annotations

import re

import pandas as pd

from src.io_utils import read_df, write_df
from src.config_loader import path

# Ordered (category, compiled-pattern) rules. First match wins.
_RULES: list[tuple[str, re.Pattern]] = [
    ("Executive Compensation", re.compile(
        r"\b(say[\s-]?on[\s-]?pay|executive compensation|advisory vote on (named )?"
        r"executive|compensation of (the )?named executive|golden parachute|"
        r"equity incentive plan|stock option plan|omnibus (stock|incentive)|"
        r"clawback|pay[\s-]?ratio|severance)\b", re.I)),

    ("ESG", re.compile(
        r"\b(climate|emission|greenhouse|carbon|net[\s-]?zero|environmental|"
        r"sustainab|diversity|equity and inclusion|\bdei\b|human rights|"
        r"political (contribution|spending|lobbying)|lobbying|deforestation|"
        r"water|plastic|gender pay|racial equity|civil rights audit|"
        r"social|esg)\b", re.I)),

    ("Board Governance", re.compile(
        r"\b(elect(ion)? of director|elect director|re[\s-]?elect|"
        r"declassif|classified board|board (independence|diversity|size)|"
        r"separate (the roles of )?chair|independent chair|lead director|"
        r"ratif\w* .*(auditor|accounting firm)|audit committee|"
        r"director nominee)\b", re.I)),

    ("Shareholder Rights", re.compile(
        r"\b(proxy access|special meeting|written consent|"
        r"supermajority|poison pill|rights plan|cumulative voting|"
        r"majority voting|one share one vote|dual[\s-]?class|"
        r"call a special meeting|right to act by written consent)\b", re.I)),
]

CATEGORIES = ["ESG", "Executive Compensation", "Board Governance",
              "Shareholder Rights", "Other"]


def classify_text(text: str) -> str:
    """Return the first matching category, else 'Other'."""
    if not text:
        return "Other"
    for category, pattern in _RULES:
        if pattern.search(text):
            return category
    return "Other"


def run() -> None:
    interim = path("interim")
    df = read_df(interim / "votes_clean.parquet")
    df["category"] = df["proposal_text_norm"].map(classify_text)
    df["classification_method"] = "rule"

    coverage = (df["category"] != "Other").mean()
    print("Rule-based category distribution:")
    print(df["category"].value_counts())
    print(f"Non-'Other' coverage: {coverage:.1%}")

    out = interim / "votes_classified_rule.parquet"
    write_df(df, out)
    print(f"Wrote {len(df):,} rows -> {out}")


if __name__ == "__main__":
    run()
