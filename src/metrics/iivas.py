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
    # Loosened matched-sample key. The SAME contested proposal is usually
    # worded slightly differently in each manager's N-PX, so exact-text
    # matching under-counts true matches and shrinks the matched sample. We
    # instead treat proposals of the same TYPE (category) at the same issuer
    # in the same year as the same contested item. This materially grows the
    # matched sample; the cost is occasionally merging two distinct same-type
    # proposals at one issuer-year (rare, and flagged as a known limitation).
    d["prop_key"] = (d["issuer_std"].astype(str) + "|"
                     + d["category"].astype(str) + "|"
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
    #    This is the PRIMARY lens: how each institution votes on each TYPE of
    #    contested proposal. Far higher N than the exact-proposal matched cut,
    #    and it maps directly onto the research questions (most ESG-supportive,
    #    opposes executive pay, etc.). Matched (below) is kept only as a
    #    strict robustness check.
    bycat = _rate_table(d, ["filer", "category"])
    bycat.to_csv(processed / "iivas_by_category.csv", index=False)
    pct_grid = bycat.pivot(index="filer", columns="category",
                           values="shareholder_support_pct")
    n_grid = (bycat.pivot(index="filer", columns="category",
                          values="contested_votes")
              .fillna(0).astype(int))

    # 3) Matched sample: proposals every manager voted on (apples-to-apples).
    n_filers = d["filer"].nunique()
    per_key = d.groupby("prop_key")["filer"].nunique()
    shared_keys = set(per_key[per_key == n_filers].index)
    matched = d[d["prop_key"].isin(shared_keys)]
    matched_tbl = _rate_table(matched, "filer").sort_values(
        "shareholder_support_pct", ascending=False) if len(matched) else overall.iloc[0:0]
    matched_tbl.to_csv(processed / "iivas_matched.csv", index=False)

    print("=== Shareholder support % by proposal TYPE (manager x category) ===")
    print(pct_grid.round(1).to_string())
    print("\n=== N contested votes per cell (manager x category) ===")
    print(n_grid.to_string())
    print("\n=== Shareholder Support Rate — all contested votes (own pool) ===")
    print(overall.to_string(index=False))
    print(f"\n=== Matched sample (robustness only): {len(shared_keys):,} proposals "
          f"voted by all {n_filers} managers ===")
    print(matched_tbl.to_string(index=False))
    print(f"\nWrote overall / by-category / matched -> {processed}")


if __name__ == "__main__":
    run()
