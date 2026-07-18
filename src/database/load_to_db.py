"""
Load the cleaned, classified votes into the normalized PostgreSQL schema.

Set-based and idempotent. Earlier versions upserted companies and proposals
one row at a time with a RETURNING round-trip each — fine locally, but tens of
thousands of round-trips over a remote (Supabase) pooler made the load the
slowest stage by far. This version batches every insert and reads surrogate
keys back with a single SELECT per dimension.

Idempotency: companies use their existing UNIQUE(company_name, cusip);
proposals get a deterministic natural key `proposal_uid` (added here via an
"IF NOT EXISTS" migration) so re-runs de-duplicate instead of piling up rows.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
from sqlalchemy import text

from src.config_loader import path
from src.database.db_connection import get_engine

CHUNK = 5000


def _uid(issuer_std: str, text_norm: str, year: int) -> str:
    return hashlib.md5(f"{issuer_std}|{text_norm}|{year}".encode()).hexdigest()


def _executemany(conn, sql: str, rows: list[dict]) -> None:
    stmt = text(sql)
    for i in range(0, len(rows), CHUNK):
        conn.execute(stmt, rows[i:i + CHUNK])


def run() -> None:
    df = pd.read_parquet(path("interim") / "votes_classified.parquet")
    df["proposal_uid"] = [
        _uid(a, b, int(c)) for a, b, c in
        zip(df["issuer_std"], df["proposal_text_norm"], df["filing_year"])
    ]
    engine = get_engine()

    with engine.begin() as conn:
        # One-time idempotency migration: natural key + unique index on proposals.
        conn.execute(text(
            "ALTER TABLE proposals ADD COLUMN IF NOT EXISTS proposal_uid VARCHAR(32)"))
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_proposals_uid "
            "ON proposals (proposal_uid)"))

        # --- investors ---
        inv_rows = [{"cik": str(c).zfill(10), "name": n}
                    for (n, c), _ in df.groupby(["filer", "cik"])]
        _executemany(conn, """
            INSERT INTO investors (cik, investor_name) VALUES (:cik, :name)
            ON CONFLICT (cik) DO UPDATE SET investor_name = EXCLUDED.investor_name
        """, inv_rows)
        inv_ids = {n: i for i, n in conn.execute(
            text("SELECT investor_id, investor_name FROM investors")).all()}

        # --- companies ---
        comp_keys = df.drop_duplicates("issuer_std")[
            ["issuer_std", "issuer_name", "cusip", "ticker"]]
        comp_rows = [{"name": (r.issuer_name or r.issuer_std),
                      "cusip": r.cusip, "ticker": r.ticker}
                     for r in comp_keys.itertuples(index=False)]
        _executemany(conn, """
            INSERT INTO companies (company_name, cusip, ticker)
            VALUES (:name, :cusip, :ticker)
            ON CONFLICT (company_name, cusip) DO UPDATE SET ticker = EXCLUDED.ticker
        """, comp_rows)
        # Map issuer_std -> company_id via the same name we inserted under.
        name_to_id = {n: i for i, n in conn.execute(
            text("SELECT company_id, company_name FROM companies")).all()}
        comp_ids = {r.issuer_std: name_to_id.get(r.issuer_name or r.issuer_std)
                    for r in comp_keys.itertuples(index=False)}

        # --- proposals ---
        prop_keys = df.drop_duplicates("proposal_uid")
        prop_rows = []
        for r in prop_keys.itertuples(index=False):
            rd = r._asdict()
            mgmt = rd["management_recommendation"]
            prop_rows.append({
                "uid": rd["proposal_uid"],
                "company_id": comp_ids[rd["issuer_std"]],
                "year": int(rd["filing_year"]),
                "text": rd["proposal_text"],
                "sponsor": rd.get("proposal_sponsor")
                if rd.get("proposal_sponsor") in ("Management", "Shareholder") else None,
                "category": rd["category"],
                "method": rd.get("classification_method"),
                "mgmt": mgmt if mgmt in ("For", "Against", "None") else None,
            })
        _executemany(conn, """
            INSERT INTO proposals
                (proposal_uid, company_id, proposal_year, proposal_text,
                 proposal_sponsor, category, classification_method,
                 management_recommendation)
            VALUES (:uid, :company_id, :year, :text, :sponsor, :category,
                    :method, :mgmt)
            ON CONFLICT (proposal_uid) DO NOTHING
        """, prop_rows)
        prop_ids = {u: i for i, u in conn.execute(
            text("SELECT proposal_id, proposal_uid FROM proposals "
                 "WHERE proposal_uid IS NOT NULL")).all()}

        # --- votes (fact) ---
        vote_rows = []
        for r in df.itertuples(index=False):
            rd = r._asdict()
            sm = rd["support_management"]
            vote_rows.append({
                "inv": inv_ids[rd["filer"]],
                "comp": comp_ids[rd["issuer_std"]],
                "prop": prop_ids[rd["proposal_uid"]],
                "year": int(rd["filing_year"]),
                "acc": rd.get("accession"),
                "vote": rd["vote_cast"] if rd["vote_cast"] in
                ("For", "Against", "Abstain", "Withhold", "Other") else None,
                "shares": None if pd.isna(rd["shares_voted"]) else float(rd["shares_voted"]),
                "sm": None if pd.isna(sm) else int(sm),
            })
        _executemany(conn, """
            INSERT INTO votes
                (investor_id, company_id, proposal_id, vote_year, accession,
                 vote_cast, shares_voted, support_management)
            VALUES (:inv, :comp, :prop, :year, :acc, :vote, :shares, :sm)
            ON CONFLICT (investor_id, proposal_id, accession) DO NOTHING
        """, vote_rows)

    print(f"Loaded {len(vote_rows):,} vote rows "
          f"({len(prop_rows):,} proposals, {len(comp_rows):,} companies) "
          f"into PostgreSQL.")


if __name__ == "__main__":
    run()
