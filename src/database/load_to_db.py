"""
Load the cleaned, classified votes into the normalized PostgreSQL schema.

Strategy: upsert the dimensions (investors, industries, companies, proposals)
to obtain surrogate keys, then bulk-insert the fact rows. Uses ON CONFLICT to
stay idempotent so the loader can be re-run safely.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy import text

from src.config_loader import path
from src.database.db_connection import get_engine

BUCKETS = ["Mega", "Large", "Mid", "Small", "Micro"]


def _bucket(mktcap) -> str | None:
    if mktcap is None or (isinstance(mktcap, float) and np.isnan(mktcap)):
        return None
    b = mktcap / 1e9
    if b >= 200: return "Mega"
    if b >= 10:  return "Large"
    if b >= 2:   return "Mid"
    if b >= 0.3: return "Small"
    return "Micro"


def _upsert_returning(conn, sql: str, params: dict) -> int:
    return conn.execute(text(sql), params).scalar_one()


def run() -> None:
    df = pd.read_parquet(path("interim") / "votes_classified.parquet")
    engine = get_engine()

    with engine.begin() as conn:
        # --- investors ---
        inv_ids: dict[str, int] = {}
        for (name, cik), _ in df.groupby(["filer", "cik"]):
            inv_ids[name] = _upsert_returning(conn, """
                INSERT INTO investors (cik, investor_name)
                VALUES (:cik, :name)
                ON CONFLICT (cik) DO UPDATE SET investor_name = EXCLUDED.investor_name
                RETURNING investor_id
            """, {"cik": str(cik).zfill(10), "name": name})

        # --- companies (industry left NULL here; enrich separately) ---
        comp_ids: dict[str, int] = {}
        comp_keys = df[["issuer_std", "issuer_name", "cusip", "ticker"]].drop_duplicates("issuer_std")
        for _, r in comp_keys.iterrows():
            comp_ids[r["issuer_std"]] = _upsert_returning(conn, """
                INSERT INTO companies (company_name, cusip, ticker, market_cap_bucket)
                VALUES (:name, :cusip, :ticker, :bucket)
                ON CONFLICT (company_name, cusip) DO UPDATE SET ticker = EXCLUDED.ticker
                RETURNING company_id
            """, {
                "name": r["issuer_name"] or r["issuer_std"],
                "cusip": r["cusip"],
                "ticker": r["ticker"],
                "bucket": None,
            })

        # --- proposals ---
        prop_keys = df.drop_duplicates(
            subset=["issuer_std", "proposal_text_norm", "filing_year"]
        )
        prop_ids: dict[tuple, int] = {}
        for _, r in prop_keys.iterrows():
            key = (r["issuer_std"], r["proposal_text_norm"], int(r["filing_year"]))
            prop_ids[key] = _upsert_returning(conn, """
                INSERT INTO proposals
                    (company_id, proposal_year, proposal_text, proposal_sponsor,
                     category, classification_method, management_recommendation)
                VALUES (:company_id, :year, :text, :sponsor, :category, :method, :mgmt)
                RETURNING proposal_id
            """, {
                "company_id": comp_ids[r["issuer_std"]],
                "year": int(r["filing_year"]),
                "text": r["proposal_text"],
                "sponsor": r.get("proposal_sponsor"),
                "category": r["category"],
                "method": r.get("classification_method"),
                "mgmt": r["management_recommendation"] if r["management_recommendation"] in ("For", "Against", "None") else None,
            })

        # --- votes (fact): chunked executemany, not per-row round-trips.
        #     A full Big-Three pull is millions of rows; row-by-row inserts
        #     against a remote (Supabase) host would take hours.
        vote_sql = text("""
            INSERT INTO votes
                (investor_id, company_id, proposal_id, vote_year, accession,
                 vote_cast, shares_voted, support_management)
            VALUES (:inv, :comp, :prop, :year, :acc, :vote, :shares, :sm)
            ON CONFLICT (investor_id, proposal_id, accession) DO NOTHING
        """)
        params: list[dict] = []
        for r in df.itertuples(index=False):
            rd = r._asdict()
            key = (rd["issuer_std"], rd["proposal_text_norm"], int(rd["filing_year"]))
            sm = rd["support_management"]
            params.append({
                "inv": inv_ids[rd["filer"]],
                "comp": comp_ids[rd["issuer_std"]],
                "prop": prop_ids[key],
                "year": int(rd["filing_year"]),
                "acc": rd.get("accession"),
                "vote": rd["vote_cast"] if rd["vote_cast"] in ("For","Against","Abstain","Withhold","Other") else None,
                "shares": None if pd.isna(rd["shares_voted"]) else float(rd["shares_voted"]),
                "sm": None if pd.isna(sm) else int(sm),
            })

        CHUNK = 5000
        n = 0
        for i in range(0, len(params), CHUNK):
            conn.execute(vote_sql, params[i:i + CHUNK])   # executemany
            n += len(params[i:i + CHUNK])
            if n % 50000 < CHUNK:
                print(f"  ...{n:,} vote rows staged")
    print(f"Loaded {n:,} vote rows into PostgreSQL.")


if __name__ == "__main__":
    run()
