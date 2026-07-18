"""
Load the cleaned, classified votes into the normalized PostgreSQL schema.

Bulk, set-based, idempotent. The key to speed over a remote (Supabase) pooler
is psycopg2's execute_values, which packs many rows into a SINGLE multi-row
INSERT statement per page. SQLAlchemy/psycopg2 `executemany` secretly loops one
round-trip per row, which made earlier versions crawl for tens of minutes on
~165k rows; execute_values does the same load in seconds.

Idempotency: companies use UNIQUE(company_name, cusip); proposals get a
deterministic natural key `proposal_uid` (added here via an IF NOT EXISTS
migration) with a unique index so re-runs de-duplicate rather than pile up.
"""
from __future__ import annotations

import hashlib

import pandas as pd
from psycopg2.extras import execute_values

from src.config_loader import path
from src.database.db_connection import get_engine

PAGE = 2000


def _uid(issuer_std: str, text_norm: str, year: int) -> str:
    return hashlib.md5(f"{issuer_std}|{text_norm}|{year}".encode()).hexdigest()


def _none(v):
    return None if (v is None or (isinstance(v, float) and pd.isna(v))) else v


def run() -> None:
    df = pd.read_parquet(path("interim") / "votes_classified.parquet")
    df["proposal_uid"] = [
        _uid(a, b, int(c)) for a, b, c in
        zip(df["issuer_std"], df["proposal_text_norm"], df["filing_year"])
    ]

    raw = get_engine().raw_connection()
    try:
        cur = raw.cursor()

        # Idempotency migration for proposals' natural key.
        cur.execute("ALTER TABLE proposals ADD COLUMN IF NOT EXISTS proposal_uid VARCHAR(32)")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_proposals_uid ON proposals (proposal_uid)")

        # --- investors ---
        inv = [(str(c).zfill(10), n) for (n, c), _ in df.groupby(["filer", "cik"])]
        execute_values(cur,
            "INSERT INTO investors (cik, investor_name) VALUES %s "
            "ON CONFLICT (cik) DO UPDATE SET investor_name = EXCLUDED.investor_name",
            inv, page_size=PAGE)
        cur.execute("SELECT investor_id, investor_name FROM investors")
        inv_ids = {n: i for i, n in cur.fetchall()}

        # --- companies ---
        ck = df.drop_duplicates("issuer_std")[["issuer_std", "issuer_name", "cusip", "ticker"]]
        comp = [((r.issuer_name or r.issuer_std), _none(r.cusip), _none(r.ticker))
                for r in ck.itertuples(index=False)]
        execute_values(cur,
            "INSERT INTO companies (company_name, cusip, ticker) VALUES %s "
            "ON CONFLICT (company_name, cusip) DO UPDATE SET ticker = EXCLUDED.ticker",
            comp, page_size=PAGE)
        cur.execute("SELECT company_id, company_name FROM companies")
        name_to_id = {n: i for i, n in cur.fetchall()}
        comp_ids = {r.issuer_std: name_to_id.get(r.issuer_name or r.issuer_std)
                    for r in ck.itertuples(index=False)}

        # --- proposals ---
        pk = df.drop_duplicates("proposal_uid")
        props = []
        for r in pk.itertuples(index=False):
            d = r._asdict()
            mgmt = d["management_recommendation"]
            sp = d.get("proposal_sponsor")
            props.append((
                d["proposal_uid"], comp_ids[d["issuer_std"]], int(d["filing_year"]),
                d["proposal_text"],
                sp if sp in ("Management", "Shareholder") else None,
                d["category"], d.get("classification_method"),
                mgmt if mgmt in ("For", "Against", "None") else None,
            ))
        execute_values(cur,
            "INSERT INTO proposals (proposal_uid, company_id, proposal_year, "
            "proposal_text, proposal_sponsor, category, classification_method, "
            "management_recommendation) VALUES %s ON CONFLICT (proposal_uid) DO NOTHING",
            props, page_size=PAGE)
        cur.execute("SELECT proposal_id, proposal_uid FROM proposals WHERE proposal_uid IS NOT NULL")
        prop_ids = {u: i for i, u in cur.fetchall()}

        # --- votes (fact) ---
        votes = []
        for r in df.itertuples(index=False):
            d = r._asdict()
            sm = d["support_management"]
            votes.append((
                inv_ids[d["filer"]], comp_ids[d["issuer_std"]], prop_ids[d["proposal_uid"]],
                int(d["filing_year"]), _none(d.get("accession")),
                d["vote_cast"] if d["vote_cast"] in
                ("For", "Against", "Abstain", "Withhold", "Other") else None,
                None if pd.isna(d["shares_voted"]) else float(d["shares_voted"]),
                None if pd.isna(sm) else int(sm),
            ))
        execute_values(cur,
            "INSERT INTO votes (investor_id, company_id, proposal_id, vote_year, "
            "accession, vote_cast, shares_voted, support_management) VALUES %s "
            "ON CONFLICT (investor_id, proposal_id, accession) DO NOTHING",
            votes, page_size=5000)

        raw.commit()
    finally:
        raw.close()

    print(f"Loaded {len(votes):,} votes ({len(props):,} proposals, "
          f"{len(comp):,} companies) into PostgreSQL.")


if __name__ == "__main__":
    run()
