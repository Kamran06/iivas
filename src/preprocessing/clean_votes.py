"""
Section 4 — data cleaning & preprocessing.

Takes data/interim/votes_raw.parquet (from npx_parser) and produces
data/interim/votes_clean.parquet with:
  * normalized vote outcomes and management recommendations,
  * a derived support_management target,
  * standardized issuer names,
  * de-duplicated re-filed votes,
  * explicit missing-value handling and a data-quality report.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from src.io_utils import read_df, write_df
from src.config_loader import path

# --- value normalisation maps ---------------------------------------------
VOTE_MAP = {
    "for": "For", "f": "For", "yes": "For", "1": "For",
    "against": "Against", "a": "Against", "no": "Against", "0": "Against",
    "abstain": "Abstain", "abs": "Abstain",
    "withhold": "Withhold", "withheld": "Withhold",
}
MGMT_MAP = {
    "for": "For", "f": "For", "yes": "For",
    "against": "Against", "a": "Against", "no": "Against",
    "none": "None", "n/a": "None", "": "None",
}
# N-PX voteSource uses ISSUER/SHAREHOLDER (real filings, verified run #3).
SPONSOR_MAP = {
    "issuer": "Management", "management": "Management",
    "shareholder": "Shareholder", "security holder": "Shareholder",
    "shareholder proposal": "Shareholder",
}


def _norm_token(value, mapping, default=None):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return default
    key = str(value).strip().lower()
    return mapping.get(key, default)


def standardize_issuer(name) -> str | None:
    """Uppercase, strip legal suffixes and punctuation for entity matching."""
    if name is None or (isinstance(name, float) and np.isnan(name)):
        return None
    s = str(name).upper()
    s = re.sub(r"[.,]", " ", s)
    s = re.sub(r"\b(INC|CORP|CORPORATION|CO|LTD|LLC|PLC|THE|COMPANY|GROUP|HOLDINGS?)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def derive_support(row) -> int | float:
    """
    support_management = 1 if the cast vote matches the management
    recommendation, 0 if it opposes it, NaN if undefined (abstain, no rec).
    """
    vote, rec = row["vote_cast"], row["management_recommendation"]
    if rec not in ("For", "Against") or vote not in ("For", "Against"):
        return np.nan
    return int(vote == rec)


def run() -> None:
    interim = path("interim")
    df = read_df(interim / "votes_raw.parquet")
    n0 = len(df)
    report = {"rows_in": n0}

    # 1) Normalise categorical tokens.
    df["vote_cast"] = df["vote_cast"].map(lambda v: _norm_token(v, VOTE_MAP, "Other"))
    df["management_recommendation"] = df["management_recommendation"].map(
        lambda v: _norm_token(v, MGMT_MAP, "None")
    )
    df["proposal_sponsor"] = df["proposal_sponsor"].map(
        lambda v: _norm_token(v, SPONSOR_MAP, None)
    )

    # 2) Standardise issuer names (new column kept alongside the original).
    df["issuer_std"] = df["issuer_name"].map(standardize_issuer)

    # 3) Normalise proposal text (collapse whitespace, strip, lowercase copy
    #    for classification; keep original for display).
    df["proposal_text"] = df["proposal_text"].fillna("").astype(str).str.strip()
    df["proposal_text_norm"] = (
        df["proposal_text"].str.lower().str.replace(r"\s+", " ", regex=True)
    )

    # 4) Drop rows with no usable proposal text or no issuer.
    before = len(df)
    df = df[(df["proposal_text"].str.len() > 0) & df["issuer_std"].notna()].copy()
    report["dropped_empty"] = before - len(df)

    # 5) Derive the supervised target.
    df["support_management"] = df.apply(derive_support, axis=1)

    # 6) De-duplicate. N-PX amendments (N-PX/A) re-report votes already filed.
    #    CRITICAL: filing_year MUST be part of the key — recurring proposals
    #    ("Elect Director X" voted For in 2023 AND 2024) are distinct votes,
    #    not duplicates. Within a year, keep the last accession (amendments
    #    supersede originals).
    key = ["filer", "filing_year", "issuer_std", "proposal_text_norm", "vote_cast"]
    before = len(df)
    df = (
        df.sort_values(["filing_year", "accession"])
        .drop_duplicates(subset=key, keep="last")
        .reset_index(drop=True)
    )
    report["dropped_duplicates"] = before - len(df)

    # 7) Missing-value handling: shares_voted -> numeric, NaN allowed;
    #    ticker/cusip left NULL (joined later if available).
    df["shares_voted"] = pd.to_numeric(df["shares_voted"], errors="coerce")

    report["rows_out"] = len(df)
    report["support_defined_pct"] = round(df["support_management"].notna().mean() * 100, 2)

    out = interim / "votes_clean.parquet"
    write_df(df, out)
    print("Cleaning report:", report)
    print(f"Wrote {len(df):,} clean rows -> {out}")


if __name__ == "__main__":
    run()
