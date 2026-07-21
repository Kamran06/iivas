"""
Section 5 -- rule-based proposal classifier.

Deterministic first pass that assigns each proposal to one of:
  ESG, Executive Compensation, Board Governance, Shareholder Rights, Other.

Rationale: a large share of N-PX proposals are boilerplate ("Elect Director
X", "Ratify auditors", "Advisory vote on executive compensation"). Keyword
rules classify these with near-perfect precision and zero training data, and
the residual ambiguous text is handed to the ML classifier (ml_classifier.py).
The ordering of rules matters: more specific categories are tested first.

2026-07 update: merged in a manual keyword->category pass the project owner
did by hand (election/director, auditor ratification, equity incentive
plans, expanded E&S terms, and management-governance boilerplate like
merger/bylaw/charter/adjourn/share issuance). The owner's pass used a finer
6-bucket taxonomy (splitting off Election-of-Director and Auditor-Ratification
as their own categories, and tagging governance items Mgmt vs SH); per
project decision those are folded into the existing 4 categories rather than
expanding the schema, since proposal_sponsor already carries the Mgmt/SH
split independently and the by-type grid is built around 4 columns. A few of
the owner's broadest single-word entries (bare "equity", "stock", "amend",
"incentive") were intentionally not added verbatim: they are common enough
in unrelated proposal text that they would trade recall for a real drop in
precision. They're captured instead as bounded phrases below.

Also fixed a pre-existing bug: several stem patterns (e.g. "declassif",
"sustainab", "adjourn") sat inside a single \b(...)\b alternation, so the
trailing \b required a word boundary immediately after the stem, which
fails for real words like "declassification" or "sustainability" where a
suffix follows. Fixed by appending \w* to stems so they absorb any suffix
before the boundary check.
"""
from __future__ import annotations

import re

import pandas as pd

from src.io_utils import read_df, write_df
from src.config_loader import path

# Ordered (category, compiled-pattern) rules. First match wins.
_RULES: list[tuple[str, re.Pattern]] = [
    ("Executive Compensation", re.compile(
        r"\b(say[\s-]?on[\s-]?pay|executive compensation|executive pay|"
        r"advisory vote on (named )?executive|"
        r"compensation of (the )?named executive|"
        r"executive\w*.{0,25}compensation\w*|compensation\w*.{0,25}executive\w*|"
        r"golden parachute|"
        r"equity incentive plan\w*|equity incentive|stock option\w*|"
        r"stock incentive plan\w*|omnibus (stock|incentive)\w*|"
        r"repricing|clawback\w*|pay[\s-]?ratio|severance\w*)\b", re.I)),

    ("ESG", re.compile(
        r"\b(climate|emission\w*|greenhouse|carbon|net[\s-]?zero|environmental|"
        r"sustainab\w*|diversity|equity and inclusion|\bdei\b|human rights|"
        r"political (contribution|spending|lobbying)\w*|lobbying|deforestation|"
        r"water|plastic\w*|gender pay|racial equity|civil rights audit\w*|"
        r"social|esg|food waste|health care|regenerative agriculture|"
        r"greenwash\w*|discriminat\w*|disabilit\w*)\b", re.I)),

    ("Board Governance", re.compile(
        r"\b(elect\w*.{0,25}\bdirector\w*|re[\s-]?elect\w*|"
        r"director nominee\w*|declassif\w*|classified board\w*|"
        r"board (independence|diversity|size|structure)\w*|"
        r"separate (the roles of )?chair\w*|independent chair\w*|lead director\w*|"
        r"ratif\w* .*(auditor|accounting firm)\w*|accounting firm\w*|"
        r"audit committee\w*|"
        r"adjourn\w*|bylaw\w*|by[\s-]?law\w*|charter|merger\w*|"
        r"scheme of arrangement\w*|"
        r"authorized share capital|ordinary share issuance\w*|share issuance\w*|"
        r"share repurchase\w*|renewal of share purchase\w*|"
        r"receipt of reports and accounts|other business)\b", re.I)),

    ("Shareholder Rights", re.compile(
        r"\b(proxy access|special meeting\w*|written consent\w*|"
        r"supermajority|poison pill\w*|rights plan\w*|cumulative voting|"
        r"majority voting|one share one vote\w*|dual[\s-]?class|"
        r"call a special meeting\w*|right to act by written consent\w*)\b", re.I)),
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
