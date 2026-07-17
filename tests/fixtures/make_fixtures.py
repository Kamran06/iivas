"""
Build a small, clearly-synthetic N-PX fixture set for integration testing.

These files mimic the post-2024 structured N-PX voteRecord XML layout so the
full pipeline (parse -> clean -> classify -> score) can be exercised without
network access. Issuer names are real large-cap companies (public knowledge),
but EVERY VOTE VALUE IS INVENTED for testing. Never present fixture-derived
scores as findings.

Deliberately exercised edge cases:
  * an N-PX/A amendment duplicating votes from the original filing
    (same filer/year -> must dedupe),
  * the same recurring proposal in two different years
    (must NOT dedupe across years),
  * an Abstain vote (support_management must be NULL),
  * all five proposal categories.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

VOTE = """  <voteRecord>
    <issuerName>{issuer}</issuerName>
    <cusip>{cusip}</cusip>
    <voteDescription>{desc}</voteDescription>
    <voteSource>{sponsor}</voteSource>
    <managementRecommendation>{mgmt}</managementRecommendation>
    <howVoted>{voted}</howVoted>
    <sharesVoted>{shares}</sharesVoted>
  </voteRecord>
"""

def wrap(records: str) -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<edgarSubmission>\n<proxyVoteTable>\n{records}</proxyVoteTable>\n</edgarSubmission>\n'


def v(issuer, cusip, desc, sponsor, mgmt, voted, shares="1000000"):
    return VOTE.format(issuer=issuer, cusip=cusip, desc=desc, sponsor=sponsor,
                       mgmt=mgmt, voted=voted, shares=shares)


def build() -> None:
    filings = {
        # ---- Vanguard 2024 original -------------------------------------
        ("Vanguard", "0000036405", 2024, "TEST-VG-2024-01"): wrap(
            v("Apple Inc", "037833100", "Elect Director Arthur Levinson", "Management", "For", "For")
            + v("Apple Inc", "037833100", "Advisory vote on executive compensation (say-on-pay)", "Management", "For", "For")
            + v("Apple Inc", "037833100", "Report on climate change and greenhouse gas reduction targets", "Shareholder", "Against", "Against")
            + v("Exxon Mobil Corp", "30231G102", "Adopt proxy access bylaw", "Shareholder", "Against", "For")
            + v("Exxon Mobil Corp", "30231G102", "Ratify PricewaterhouseCoopers as auditors", "Management", "For", "Abstain")
        ),
        # ---- Vanguard 2024 amendment: repeats 2 votes (dedup within year)
        ("Vanguard", "0000036405", 2024, "TEST-VG-2024-01A"): wrap(
            v("Apple Inc", "037833100", "Elect Director Arthur Levinson", "Management", "For", "For")
            + v("Apple Inc", "037833100", "Advisory vote on executive compensation (say-on-pay)", "Management", "For", "For")
        ),
        # ---- Vanguard 2025: recurring proposal (must survive dedup) -----
        ("Vanguard", "0000036405", 2025, "TEST-VG-2025-01"): wrap(
            v("Apple Inc", "037833100", "Elect Director Arthur Levinson", "Management", "For", "For")
            + v("Apple Inc", "037833100", "Advisory vote on executive compensation (say-on-pay)", "Management", "For", "Against")
        ),
        # ---- BlackRock 2024 ---------------------------------------------
        ("BlackRock", "0001100663", 2024, "TEST-BR-2024-01"): wrap(
            v("Microsoft Corp", "594918104", "Elect Director Satya Nadella", "Management", "For", "For")
            + v("Microsoft Corp", "594918104", "Advisory vote on executive compensation", "Management", "For", "Against")
            + v("Chevron Corp", "166764100", "Report on human rights due diligence", "Shareholder", "Against", "For")
            + v("Chevron Corp", "166764100", "Eliminate supermajority voting requirement", "Shareholder", "Against", "Against")
        ),
        # ---- State Street 2024 ------------------------------------------
        ("State Street", "0000999999", 2024, "TEST-SS-2024-01"): wrap(
            v("Amazon.com Inc", "023135106", "Elect Director Jeffrey Blackburn", "Management", "For", "For")
            + v("Amazon.com Inc", "023135106", "Approve omnibus stock incentive plan", "Management", "For", "For")
            + v("Amazon.com Inc", "023135106", "Report on political contributions and lobbying", "Shareholder", "Against", "Against")
            + v("Amazon.com Inc", "023135106", "Approve the minutes of the prior meeting", "Management", "For", "For")
        ),
    }

    raw_dir = HERE / "raw"
    raw_dir.mkdir(exist_ok=True)
    manifest = []
    for (filer, cik, year, accession), xml in filings.items():
        fn = raw_dir / f"{cik}_{accession}.xml"
        fn.write_text(xml)
        manifest.append({
            "filer": filer, "cik": cik, "year": year, "accession": accession,
            "accession_nodash": accession.replace("-", ""),
            "filing_date": f"{year}-08-30", "primary_document": fn.name,
            "local_path": str(fn),
        })
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Fixture built: {len(manifest)} filings, {sum(x.count('<voteRecord>') for x in filings.values())} vote records")


if __name__ == "__main__":
    build()
