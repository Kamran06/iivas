"""
Section 6 — IIVAS metric computation.

Computes, per investor (and per investor-year), four sub-scores and the
composite IIVAS:

    Governance Score      G  = management-support rate on Board Governance
    Compensation Score    C  = management-support rate on Executive Compensation
    ESG Score             E  = management-support rate on ESG proposals
    Mgmt Alignment Score  M  = overall management-support rate (all categories)

Each rate r in [0,1] is mapped to a 0-100 score. The composite is a weighted
mean of the four 0-100 sub-scores using config.iivas_weights.

    IIVAS = 100 * ( w_g*G + w_c*C + w_e*E + w_m*M ) / 100
          =        ( w_g*G + w_c*C + w_e*E + w_m*M )     (since G..M already 0-100)

Interpretation: HIGH IIVAS = consistently votes WITH management (low
challenge / high alignment). LOW IIVAS = frequently challenges management.

Full derivation, normalization options, and academic justification:
docs/METHODOLOGY.md.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.io_utils import read_df, write_df
from src.config_loader import CONFIG, path

W = CONFIG["iivas_weights"]
CATEGORY_TO_SCORE = {
    "Board Governance": "governance",
    "Executive Compensation": "compensation",
    "ESG": "esg",
}


def _support_rate(frame: pd.DataFrame) -> float:
    """Mean of support_management over defined votes; NaN if none defined."""
    s = frame["support_management"].dropna()
    return float(s.mean()) if len(s) else np.nan


def compute_scores(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    """Return a frame of sub-scores + composite for each group."""
    records = []
    for keys, g in df.groupby(group_cols):
        keys = keys if isinstance(keys, tuple) else (keys,)
        row = dict(zip(group_cols, keys))

        rates = {
            "governance": _support_rate(g[g["category"] == "Board Governance"]),
            "compensation": _support_rate(g[g["category"] == "Executive Compensation"]),
            "esg": _support_rate(g[g["category"] == "ESG"]),
            "management_alignment": _support_rate(g),
        }
        row["total_votes"] = int(g["support_management"].notna().sum())
        for k, r in rates.items():
            row[f"{k}_support_rate"] = r
            row[f"{k}_score"] = np.nan if np.isnan(r) else round(r * 100, 2)

        # Composite: weighted mean over available sub-scores (re-normalise
        # weights when a category has no votes, so missing categories do not
        # silently drag the score toward zero).
        comp_terms, weight_sum = 0.0, 0.0
        for comp, w in W.items():
            score = row[f"{comp}_score"]
            if score is not None and not (isinstance(score, float) and np.isnan(score)):
                comp_terms += w * score
                weight_sum += w
        row["iivas_composite"] = round(comp_terms / weight_sum, 2) if weight_sum else np.nan
        records.append(row)
    return pd.DataFrame(records)


def run() -> None:
    interim, processed = path("interim"), path("processed")
    df = read_df(interim / "votes_classified.parquet")

    overall = compute_scores(df, ["filer"]).sort_values("iivas_composite", ascending=False)
    by_year = compute_scores(df, ["filer", "filing_year"])
    by_sector = compute_scores(df, ["filer"])  # placeholder; sector join done in EDA

    overall.to_csv(processed / "iivas_overall.csv", index=False)
    by_year.to_csv(processed / "iivas_by_year.csv", index=False)

    print("=== IIVAS (overall) ===")
    cols = ["filer", "governance_score", "compensation_score", "esg_score",
            "management_alignment_score", "iivas_composite"]
    print(overall[cols].to_string(index=False))
    print(f"\nWrote scores -> {processed}")

    # Optionally refresh yearly_statistics in PostgreSQL.
    try:
        from src.database.db_connection import get_engine
        eng = get_engine()
        with eng.begin() as conn:
            inv_map = pd.read_sql("SELECT investor_id, investor_name FROM investors", conn)
            merged = by_year.merge(inv_map, left_on="filer", right_on="investor_name", how="inner")
            for _, r in merged.iterrows():
                conn.exec_driver_sql("""
                    INSERT INTO yearly_statistics
                        (investor_id, stat_year, total_votes,
                         governance_support_rate, compensation_support_rate,
                         esg_support_rate, management_alignment_rate,
                         governance_score, compensation_score, esg_score,
                         management_alignment_score, iivas_composite)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (investor_id, stat_year) DO UPDATE SET
                        total_votes = EXCLUDED.total_votes,
                        iivas_composite = EXCLUDED.iivas_composite
                """, (
                    int(r["investor_id"]), int(r["filing_year"]), int(r["total_votes"]),
                    r["governance_support_rate"], r["compensation_support_rate"],
                    r["esg_support_rate"], r["management_alignment_support_rate"],
                    r["governance_score"], r["compensation_score"], r["esg_score"],
                    r["management_alignment_score"], r["iivas_composite"],
                ))
        print("yearly_statistics refreshed in PostgreSQL.")
    except Exception as exc:  # noqa: BLE001
        print(f"[info] skipped DB refresh ({exc}). CSV outputs still written.")


if __name__ == "__main__":
    run()
