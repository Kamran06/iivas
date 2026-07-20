"""
Section 6 (v2) — IIVAS metric, redefined around CONTESTED votes.

The v1 metric averaged "support for management" over all proposals. But ~99%
of proxy votes are routine management items that every investor rubber-stamps
~99% of the time, so that average is a base rate that hides all cross-manager
variation. The real behavioural signal lives in SHAREHOLDER-SPONSORED proposals
— the contested ones management recommends against — where a manager must
actually choose a side.

This module therefore reports, on shareholder proposals only (the pipeline now
keeps only those when analysis.shareholder_only is set):

  Shareholder Support Rate  = share of votes cast FOR the shareholder proposal
  IIVAS alignment (0-100)   = 100 * (1 - Shareholder Support Rate)
                              higher = more management-aligned / less dissenting

Three cuts are written:
  iivas_overall.csv    — per manager, all their shareholder votes
  iivas_by_category.csv— per manager x proposal category
  iivas_matched.csv    — per manager on the IDENTICAL proposals every manager
                         voted on (the fair, apples-to-apples comparison that
                         removes fund-coverage differences)

Full rationale: docs/METHODOLOGY.md and docs/RESULTS.md.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.io_utils import read_df, write_df
from src.config_loader import path


def _prep(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["vote_cast"].isin(["For", "Against"])].copy()
    d["for_shareholder"] = (d["vote_cast"] == "For").astype(int)
    d["prop_key"] = (d["issuer_std"].astype(str) + "|"
                     + d["proposal_text_norm"].astype(str) + "|"
                     + d["filing_year"].astype(str))
    return d


def _rate_table(d: pd.DataFrame, group) -> pd.DataFrame:
    g = (d.groupby(group)
           .agg(contested_votes=("for_shareholder", "size"),
                shareholder_support=("for_shareholder", "mean"))
           .reset_index())
    g["shareholder_support_pct"] = (100 * g["shareholder_support"]).round(1)
    g["iivas_alignment"] = (100 * (1 - g["shareholder_support"])).round(1)
    return g.drop(columns="shareholder_support")


def run() -> None:
    interim, processed = path("interim"), path("processed")
    df = read_df(interim / "votes_classified.parquet")
    if df.empty:
        raise SystemExit("[fatal] no classified votes — nothing to score.")

    d = _prep(df)
    if d.empty:
        raise SystemExit("[fatal] no For/Against shareholder votes to score.")

    # 1) Overall, per manager.
    overall = _rate_table(d, "filer").sort_values(
        "shareholder_support_pct", ascending=False)
    overall.to_csv(processed / "iivas_overall.csv", index=False)

    # 2) Per manager x category (ESG, Governance, Shareholder Rights, ...).
    bycat = _rate_table(d, ["filer", "category"])
    bycat.to_csv(processed / "iivas_by_category.csv", index=False)

    # 3) Matched sample: proposals every manager voted on (apples-to-apples).
    n_filers = d["filer"].nunique()
    per_key = d.groupby("prop_key")["filer"].nunique()
    shared_keys = set(per_key[per_key == n_filers].index)
    matched = d[d["prop_key"].isin(shared_keys)]
    matched_tbl = _rate_table(matched, "filer").sort_values(
        "shareholder_support_pct", ascending=False) if len(matched) else overall.iloc[0:0]
    matched_tbl.to_csv(processed / "iivas_matched.csv", index=False)

    print("=== Shareholder Support Rate — all contested votes ===")
    print(overall.to_string(index=False))
    print(f"\n=== Matched sample: {len(shared_keys):,} proposals voted by all "
          f"{n_filers} managers ===")
    print(matched_tbl.to_string(index=False))
    print(f"\nWrote overall / by-category / matched -> {processed}")


if __name__ == "__main__":
    run()
