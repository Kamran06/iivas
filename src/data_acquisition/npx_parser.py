"""
Section 2 — N-PX parsing workflow.

Converts downloaded N-PX documents into a tidy long-format votes table:
one row per (filer, issuer, proposal, vote).

Two layouts are handled:
  * Post-2024 structured N-PX XML (the SEC's voteTable schema), where each
    <proxyVoteTable>/<voteRecord> carries issuerName, cusip, voteCategory,
    proposal text, managementRecommendation, and how the shares were voted.
  * Legacy HTML/free-text N-PX, where votes appear in tables; we fall back to
    pandas.read_html and a column-mapping heuristic.

The parser is intentionally defensive: filing formats vary across filers and
years, so every field is read with a getter that tolerates missing nodes and
records a NULL rather than crashing the run.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from lxml import etree

from src.io_utils import read_df, write_df
from src.config_loader import path

# Canonical output columns for the votes long table.
COLUMNS = [
    "filer", "cik", "filing_year", "accession",
    "issuer_name", "cusip", "ticker",
    "proposal_id", "proposal_text", "proposal_sponsor",
    "management_recommendation", "vote_cast", "shares_voted",
]


def _xtext(node, tag: str, ns: dict | None = None) -> str | None:
    """Return stripped text of the first child <tag> or None."""
    found = node.find(tag, ns) if ns else node.find(tag)
    if found is None or found.text is None:
        return None
    return found.text.strip()


def parse_structured_xml(content: bytes, meta: dict) -> list[dict]:
    """
    Parse the post-2024 structured N-PX voteTable XML.

    Real-world layout (verified against live 2024/2025 filings in run #3):
    issuer-level fields live on a parent <proxyTable> element; the nested
    <voteRecord> carries only how the shares were voted:

        <proxyVoteTable>
          <proxyTable>
            <issuerName>… <cusip>… <voteDescription>… <voteSource>…
            <vote><voteRecord>
              <howVoted>… <sharesVoted>… <managementRecommendation>…
            </voteRecord></vote>
          </proxyTable>
        </proxyVoteTable>

    A flat all-fields-on-voteRecord layout is kept as a fallback for variant
    filings and our test fixtures.
    """
    rows: list[dict] = []
    try:
        root = etree.fromstring(content)
    except etree.XMLSyntaxError:
        return rows

    # Namespaces vary; strip them so tag lookups are namespace-agnostic.
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]

    def _row(issuer, cusip, ticker, text, sponsor, mgmt, vote_cast, shares):
        return {
            **meta,
            "issuer_name": issuer, "cusip": cusip, "ticker": ticker,
            "proposal_id": None, "proposal_text": text,
            "proposal_sponsor": sponsor, "management_recommendation": mgmt,
            "vote_cast": vote_cast, "shares_voted": shares,
        }

    tables = list(root.iter("proxyTable"))
    if tables:
        for t in tables:
            issuer = _xtext(t, "issuerName")
            cusip = _xtext(t, "cusip")
            ticker = _xtext(t, "symbol") or _xtext(t, "ticker") or _xtext(t, "isin")
            text = _xtext(t, "voteDescription") or _xtext(t, "proposalText")
            sponsor = _xtext(t, "voteSource")
            mgmt_tbl = _xtext(t, "managementRecommendation")
            shares_tbl = _xtext(t, "sharesVoted")
            recs = list(t.iter("voteRecord"))
            if recs:
                for rec in recs:
                    rows.append(_row(
                        issuer, cusip, ticker, text, sponsor,
                        _xtext(rec, "managementRecommendation") or mgmt_tbl,
                        _xtext(rec, "howVoted") or _xtext(rec, "vote"),
                        _xtext(rec, "sharesVoted") or shares_tbl))
            else:  # some filers report the vote at table level
                rows.append(_row(issuer, cusip, ticker, text, sponsor,
                                 mgmt_tbl, _xtext(t, "howVoted"), shares_tbl))
        return rows

    # Fallback: flat layout with everything on voteRecord.
    for rec in root.iter("voteRecord"):
        rows.append(_row(
            _xtext(rec, "issuerName"), _xtext(rec, "cusip"),
            _xtext(rec, "ticker") or _xtext(rec, "isin"),
            _xtext(rec, "voteDescription") or _xtext(rec, "proposalText"),
            _xtext(rec, "voteSource") or _xtext(rec, "proposalSponsor"),
            _xtext(rec, "managementRecommendation"),
            _xtext(rec, "howVoted") or _xtext(rec, "vote"),
            _xtext(rec, "sharesVoted") or _xtext(rec, "votedShares")))
    return rows


def parse_legacy_html(content: bytes, meta: dict) -> list[dict]:
    """Best-effort parse of legacy free-text / HTML N-PX filings."""
    rows: list[dict] = []
    try:
        tables = pd.read_html(content)
    except Exception:  # noqa: BLE001 — no tables, bad markup, or missing
        return rows     # optional parser dep: skip this filing, never crash
                        # a multi-hour run over one document.

    # Heuristic: keep tables that look like vote tables (have a 'proposal'
    # and a 'vote' column after normalising headers).
    for tbl in tables:
        cols = {str(c).strip().lower(): c for c in tbl.columns}
        prop_col = next((cols[c] for c in cols if "proposal" in c or "description" in c), None)
        vote_col = next((cols[c] for c in cols if "vote" in c or "cast" in c), None)
        if prop_col is None or vote_col is None:
            continue
        mgmt_col = next((cols[c] for c in cols if "management" in c or "recommend" in c), None)
        issuer_col = next((cols[c] for c in cols if "issuer" in c or "company" in c), None)
        for _, r in tbl.iterrows():
            rows.append(
                {
                    **meta,
                    "issuer_name": (str(r[issuer_col]) if issuer_col else None),
                    "cusip": None,
                    "ticker": None,
                    "proposal_id": None,
                    "proposal_text": str(r[prop_col]),
                    "proposal_sponsor": None,
                    "management_recommendation": (str(r[mgmt_col]) if mgmt_col else None),
                    "vote_cast": str(r[vote_col]),
                    "shares_voted": None,
                }
            )
    return rows


def parse_file(local_path: Path, meta: dict) -> list[dict]:
    content = local_path.read_bytes()
    head = content.lstrip()[:200].lower()
    if head.startswith(b"<?xml") or b"<edgarsubmission" in head or b"<voterecord" in content[:5000].lower():
        rows = parse_structured_xml(content, meta)
        if rows:
            return rows
    # Fall back to HTML/table parsing.
    return parse_legacy_html(content, meta)


def run() -> None:
    raw_dir = path("raw")
    interim_dir = path("interim")
    manifest_path = raw_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            "manifest.json not found — run edgar_downloader first."
        )

    manifest = json.loads(manifest_path.read_text())
    all_rows: list[dict] = []
    for entry in manifest:
        meta = {
            "filer": entry["filer"],
            "cik": entry["cik"],
            "filing_year": entry["year"],
            "accession": entry["accession"],
        }
        p = Path(entry["local_path"])
        if not p.exists():
            continue
        rows = parse_file(p, meta)
        print(f"  {entry['filer']} {entry['accession']}: {len(rows)} vote rows")
        all_rows.extend(rows)

    df = pd.DataFrame(all_rows, columns=COLUMNS)
    out = interim_dir / "votes_raw.parquet"
    write_df(df, out)
    print(f"\nParsed {len(df):,} vote rows -> {out}")


if __name__ == "__main__":
    run()
