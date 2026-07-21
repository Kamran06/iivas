"""
Section 6 (v3) - IIVAS metric, redefined around CONTESTED votes, plus four
supporting cuts requested to get more mileage out of the same dataset.

The v1 metric averaged "support for management" over all proposals. But ~99%
of proxy votes are routine management items that every investor rubber-stamps
~99% of the time, so that average is a base rate that hides all cross-manager
variation. The real behavioural signal lives in SHAREHOLDER-SPONSORED proposals
- the contested ones management recommends against - where a manager must
actually choose a side.

This module reports, on shareholder proposals only (the pipeline keeps only
those when analysis.shareholder_only is set):

  Shareholder Support Rate  = share of votes cast FOR the shareholder proposal
  IIVAS alignment (0-100)   = 100 * (1 - Shareholder Support Rate)
                              higher = more management-aligned / less dissenting

Seven cuts are written to data/processed:
  iivas_overall.csv          - per manager, all their shareholder votes
  iivas_by_category.csv      - per manager x proposal category (primary lens)
  iivas_matched.csv          - per manager on proposals ALL managers voted on
  iivas_by_year.csv          - per manager x filing year (2024 vs 2025)
  iivas_agreement_matrix.csv - pairwise manager agreement %, loosened key
  iivas_agreement_n.csv      - shared-proposal counts backing the matrix above
  iivas_director_dissent.csv - director-election dissent rate per manager
                                (pre-scope: director elections are almost
                                always management-sponsored, so they're not
                                in the shareholder-only contested set at all;
                                this reads a separate feed ml_classifier.py
                                persists before applying that scope)

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


def _agreement_matrix(d: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pairwise manager agreement on the loosened matched-sample key.

    Unlike iivas_matched.csv (which requires a prop_key to be shared by ALL
    managers), this compares every PAIR of managers on whatever prop_keys
    they both have, so two managers can still be compared even when a third
    manager never filed on that issuer/category/year. Values are averaged
    within a (filer, prop_key) group first, since the loosened key can
    occasionally merge more than one real proposal per filer (documented
    over-merge limitation); agreement is then 1 - the absolute gap between
    each pair's average support, expressed as a percentage.
    """
    piv = d.pivot_table(index="prop_key", columns="filer",
                         values="for_shareholder", aggfunc="mean")
    filers = list(piv.columns)
    agree = pd.DataFrame(index=filers, columns=filers, dtype=float)
    n_shared = pd.DataFrame(index=filers, columns=filers, dtype="Int64")
    for a in filers:
        for b in filers:
            if a == b:
                n_shared.loc[a, b] = int(piv[a].notna().sum())
                agree.loc[a, b] = 100.0
                continue
            both = piv[[a, b]].dropna()
            n_shared.loc[a, b] = len(both)
            agree.loc[a, b] = (100 * (1 - (both[a] - both[b]).abs()).mean()
                               if len(both) else np.nan)
    return agree.round(1), n_shared


def _director_dissent(interim) -> pd.DataFrame | None:
    """Director-election dissent rate per manager (Against + Withhold).

    Reads the pre-scope director_elections.parquet feed persisted by
    ml_classifier.py, since director elections are almost always
    management-sponsored and would otherwise be dropped entirely by
    shareholder_only before reaching this module. Returns None if that feed
    doesn't exist yet (older pipeline run) or is empty.
    """
    try:
        de = read_df(interim / "director_elections.parquet")
    except FileNotFoundError:
        return None
    if de is None or de.empty or "vote_cast" not in de.columns:
        return None
    de = de[de["vote_cast"].isin(["For", "Against", "Withhold"])].copy()
    if de.empty:
        return None
    de["dissent"] = (de["vote_cast"] != "For").astype(int)
    g = (de.groupby("filer")
           .agg(director_votes=("dissent", "size"),
                dissent_rate=("dissent", "mean"))
           .reset_index())
    g["dissent_rate_pct"] = (100 * g["dissent_rate"]).round(1)
    return g.drop(columns="dissent_rate").sort_values(
        "dissent_rate_pct", ascending=False)


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

    # 4) By filing year (2024 vs 2025 - a before/after, not a trend line;
    #    only two N-PX seasons are in scope).
    by_year = _rate_table(d, ["filer", "filing_year"])
    by_year.to_csv(processed / "iivas_by_year.csv", index=False)
    year_grid = by_year.pivot(index="filer", columns="filing_year",
                              values="shareholder_support_pct")

    # 5) Pairwise manager agreement matrix (loosened key, pairwise-shared).
    agree, n_shared = _agreement_matrix(d)
    agree.to_csv(processed / "iivas_agreement_matrix.csv")
    n_shared.to_csv(processed / "iivas_agreement_n.csv")

    # 6) Director-election dissent (pre-scope feed; may be None on older runs).
    dissent = _director_dissent(interim)
    if dissent is not None:
        dissent.to_csv(processed / "iivas_director_dissent.csv", index=False)

    print("=== Shareholder support % by proposal TYPE (manager x category) ===")
    print(pct_grid.round(1).to_string())
    print("\n=== N contested votes per cell (manager x category) ===")
    print(n_grid.to_string())
    print("\n=== Shareholder Support Rate — all contested votes (own pool) ===")
    print(overall.to_string(index=False))
    print(f"\n=== Matched sample (robustness only): {len(shared_keys):,} proposals "
          f"voted by all {n_filers} managers ===")
    print(matched_tbl.to_string(index=False))
    print("\n=== Shareholder support % by filing year (manager x year) ===")
    print(year_grid.round(1).to_string())
    print("\n=== Pairwise manager agreement % (loosened key, pairwise-shared votes) ===")
    print(agree.to_string())
    print("\n=== N shared proposals backing the agreement matrix (per pair) ===")
    print(n_shared.to_string())
    if dissent is not None:
        print("\n=== Director-election dissent rate (Against+Withhold), pre-scope, all sponsors ===")
        print(dissent.to_string(index=False))
    else:
        print("\n[director dissent] director_elections.parquet not found or empty — "
              "run the classification stage with the updated ml_classifier.py first.")
    print(f"\nWrote overall / by-category / matched / by-year / agreement / dissent -> {processed}")


if __name__ == "__main__":
    run()
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
