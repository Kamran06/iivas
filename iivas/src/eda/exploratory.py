"""
Section 7 — Exploratory Data Analysis.

Produces the descriptive tables that answer RQ1-RQ6 and feed the
visualisation layer. Reads data/interim/votes_classified.parquet, writes
tidy CSVs to data/processed/ that both plots.py and the dashboards consume.

Covered:
  * descriptive statistics (counts, coverage, missingness)
  * voting outcome distributions
  * support rate by investor x category   (RQ1-3)
  * support rate by investor x sector      (RQ4)
  * support rate by investor x market-cap  (RQ5)
  * support rate by investor x year + trend test (RQ6)
  * ESG and compensation specific cuts
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from src.io_utils import read_df, write_df
from src.config_loader import path


def descriptive_stats(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame({
        "n_votes": df.groupby("filer").size(),
        "n_defined": df.groupby("filer")["support_management"].apply(lambda s: s.notna().sum()),
        "support_rate": df.groupby("filer")["support_management"].mean(),
        "n_companies": df.groupby("filer")["issuer_std"].nunique(),
        "years": df.groupby("filer")["filing_year"].nunique(),
    })
    out["support_rate"] = out["support_rate"].round(4)
    return out.reset_index()


def support_by(df: pd.DataFrame, col: str) -> pd.DataFrame:
    g = (df.dropna(subset=["support_management"])
           .groupby(["filer", col])
           .agg(n_votes=("support_management", "size"),
                support_rate=("support_management", "mean"))
           .reset_index())
    g["support_rate"] = g["support_rate"].round(4)
    return g


def trend_test(df: pd.DataFrame) -> pd.DataFrame:
    """Linear trend of yearly support rate per investor (RQ6)."""
    rows = []
    by_year = support_by(df, "filing_year")
    for filer, g in by_year.groupby("filer"):
        g = g.sort_values("filing_year")
        if len(g) >= 3:
            slope, intercept, r, p, se = stats.linregress(g["filing_year"], g["support_rate"])
            rows.append({"filer": filer, "slope_per_year": round(slope, 5),
                         "r_squared": round(r**2, 3), "p_value": round(p, 4),
                         "direction": "rising" if slope > 0 else "falling"})
    return pd.DataFrame(rows)


def esg_shareholder_cut(df: pd.DataFrame) -> pd.DataFrame:
    """
    Support for ESG *shareholder* proposals specifically (RQ2). Here a
    manager voting 'For' a shareholder ESG proposal is the substantive ESG-
    supportive action, independent of management's recommendation.
    """
    esg = df[df["category"] == "ESG"].copy()
    esg_sh = esg[esg.get("proposal_sponsor", "").astype(str).str.contains("Share", case=False, na=False)]
    base = esg_sh if len(esg_sh) else esg  # fall back if sponsor unparsed
    base = base.assign(voted_for=(base["vote_cast"] == "For").astype(float))
    g = (base.groupby("filer")
             .agg(n=("voted_for", "size"), esg_for_rate=("voted_for", "mean"))
             .reset_index())
    g["esg_for_rate"] = g["esg_for_rate"].round(4)
    return g


def run() -> None:
    interim, processed = path("interim"), path("processed")
    df = read_df(interim / "votes_classified.parquet")

    tables = {
        "eda_descriptive.csv": descriptive_stats(df),
        "eda_outcome_distribution.csv": (
            df.groupby(["filer", "vote_cast"]).size()
              .rename("n").reset_index()),
        "eda_support_by_category.csv": support_by(df, "category"),
        "eda_support_by_year.csv": support_by(df, "filing_year"),
        "eda_trend_test.csv": trend_test(df),
        "eda_esg_shareholder.csv": esg_shareholder_cut(df),
    }
    for name, tbl in tables.items():
        tbl.to_csv(processed / name, index=False)
        print(f"  wrote {name}  ({len(tbl)} rows)")

    print("\nDescriptive stats:")
    print(tables["eda_descriptive.csv"].to_string(index=False))


if __name__ == "__main__":
    run()
