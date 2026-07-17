"""
Section 9 — feature engineering for the support_management classifier.

Builds the modelling matrix from the classified votes. Features:
  * investor              (categorical)
  * gics_sector / industry(categorical; NULL-safe)
  * market_cap_bucket     (ordinal categorical)
  * proposal category     (categorical)
  * year                  (numeric)
  * proposal_sponsor      (categorical: Management/Shareholder)
  * text length & a few proposal-characteristic flags (numeric/binary)

Returns X (DataFrame), y (Series), and a ColumnTransformer-ready spec.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.io_utils import read_df, write_df
from src.config_loader import path

CATEGORICAL = ["filer", "category", "proposal_sponsor", "market_cap_bucket", "gics_sector"]
NUMERIC = ["filing_year", "text_len", "is_shareholder_proposal", "mentions_climate", "mentions_pay"]


def build_matrix() -> tuple[pd.DataFrame, pd.Series, dict]:
    df = read_df(path("interim") / "votes_classified.parquet")
    df = df.dropna(subset=["support_management"]).copy()
    df["support_management"] = df["support_management"].astype(int)

    # Columns that may be absent depending on enrichment; default safely.
    for col, default in [("gics_sector", "Unknown"),
                         ("market_cap_bucket", "Unknown"),
                         ("proposal_sponsor", "Unknown")]:
        if col not in df.columns:
            df[col] = default
        df[col] = df[col].fillna(default).astype(str)

    # Engineered proposal-characteristic features.
    txt = df["proposal_text_norm"].fillna("")
    df["text_len"] = txt.str.len()
    df["is_shareholder_proposal"] = df["proposal_sponsor"].str.contains("share", case=False).astype(int)
    df["mentions_climate"] = txt.str.contains(r"climate|carbon|emission", regex=True).astype(int)
    df["mentions_pay"] = txt.str.contains(r"compensation|say.?on.?pay|pay", regex=True).astype(int)
    df["filing_year"] = pd.to_numeric(df["filing_year"], errors="coerce").fillna(0).astype(int)

    feature_cols = [c for c in CATEGORICAL + NUMERIC if c in df.columns]
    X = df[feature_cols].copy()
    y = df["support_management"]
    spec = {"categorical": [c for c in CATEGORICAL if c in X.columns],
            "numeric": [c for c in NUMERIC if c in X.columns]}
    return X, y, spec
