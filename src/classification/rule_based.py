"""
Section 5 — rule-based proposal classifier.

Deterministic first pass that assigns each proposal to one of the project
owner's 7 categories:
  Election of director proposals, Auditor ratification proposals,
  Equity incentive plans, Executive comp proposals,
  Environmental & social SHP proposals, Governance-related proposals (Mgmt),
  Governance-related proposals (SH), Other.

Rationale: a large share of N-PX proposals are boilerplate ("Elect Director
X", "Ratify auditors", "Advisory vote on executive compensation"). Keyword
rules classify these with near-perfect precision and zero training data, and
the residual ambiguous text is handed to the ML classifier (ml_classifier.py).
The ordering of rules matters: first match wins, so more specific categories
are tested before broad catch-alls.

2026-07 update (v2): replaced the prior 4-category schema (ESG / Executive
Compensation / Board Governance / Shareholder Rights) with the owner's full
7-category taxonomy, used verbatim this time (including the broad single-word
entries — bare "director", "equity", "stock", "amend", "compensation" — that
were deliberately left out of the v1 merge). The owner explicitly split
Governance-related proposals into Mgmt vs SH sub-categories per keyword,
which is followed literally below rather than inferred from
proposal_sponsor.

Known precision trade-off, flagged rather than silently accepted: several of
the owner's keywords are single common words ("director", "stock", "equity",
"compensation") that appear inside a lot of unrelated proposal text (e.g.
"board of directors" inside a bylaw amendment, "common stock" inside a
governance item). Because rule order is first-match-wins and these live in
early, high-priority categories (Election of director, Equity incentive
plans), they will pull some proposals that are really Governance-related
boilerplate into those buckets. This is the owner's taxonomy applied as
given, not a bug — but it means Election of director / Equity incentive
counts should be read as upper bounds, not precise.
"""
from __future__ import annotations

import re

import pandas as pd

from src.io_utils import read_df, write_df
from src.config_loader import path

# Ordered (category, compiled-pattern) rules. First match wins.
_RULES: list[tuple[str, re.Pattern]] = [
    ("Election of director proposals", re.compile(
        r"\b(elect\w*|director\w*)\b", re.I)),

    ("Auditor ratification proposals", re.compile(
        r"\b(auditor\w*|ratif\w*|accounting firm\w*)\b", re.I)),

    ("Equity incentive plans", re.compile(
        r"\b(equity\w*|stock option\w*|incentive\w*|repricing|stock plan\w*|"
        r"stock\w*|share increase\w*)\b", re.I)),

    ("Executive comp proposals", re.compile(
        r"\b(compensation\w*|say[\s-]?on[\s-]?pay|executive pay)\b", re.I)),

    ("Environmental & social SHP proposals", re.compile(
        r"\b(environment\w*|climate|social|sustainab\w*|esg|human rights|"
        r"food waste|health care|greenhouse gas\w*|regenerative agriculture|"
        r"plastic packaging|greenwash\w*|diversity and inclusion|"
        r"emission reduction goal\w*|discriminat\w*|disabilit\w*)\b", re.I)),

    ("Governance-related proposals (SH)", re.compile(
        r"\b(special shareholder meeting\w*)\b", re.I)),

    ("Governance-related proposals (Mgmt)", re.compile(
        r"\b(adjourn\w*|bylaw\w*|by[\s-]?law provision\w*|charter\w*|"
        r"board structure\w*|declassif\w*|merger\w*|"
        r"authorized share capital\w*|ordinary share issuance\w*|"
        r"renewal of share purchase\w*|amend\w*|scheme of arrangement\w*|"
        r"share repurchase\w*|receipt of reports and accounts|"
        r"share issuance\w*|other business|financial statement\w*)\b", re.I)),
]

CATEGORIES = [
    "Election of director proposals",
    "Auditor ratification proposals",
    "Equity incentive plans",
    "Executive comp proposals",
    "Environmental & social SHP proposals",
    "Governance-related proposals (SH)",
    "Governance-related proposals (Mgmt)",
    "Other",
]


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
