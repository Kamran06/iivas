"""
Filer discovery — enumerate the actual N-PX filer CIKs per fund family.

Why this exists
---------------
Full N-PX voting records are filed by the registered investment companies
(fund trusts), not by the parent asset manager. Verified examples:
CIK 0000102909 is "VANGUARD GROUP INC" (the adviser — a 13F filer, not the
fund votes) and 0000093751 is "STATE STREET CORP" (the holding company).
Each family files through many trusts (Vanguard Index Funds, iShares Trust,
SPDR trusts, ...), so hardcoding one CIK per manager silently misses most of
the voting universe.

Approach
--------
EDGAR publishes quarterly form indexes listing EVERY filing:
    https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{q}/form.idx
Each line: Form Type | Company Name | CIK | Date Filed | File Name.
We scan the windows around the N-PX season (Q3 for the 31-Aug deadline, plus
Q1 for amendments), keep rows where form is N-PX or N-PX/A, and match company
names against the per-family regex patterns in config. The result — a mapping
family -> [{cik, company_name}] — is written to data/interim/filers_resolved.json
and merged with the seed_ciks from config. edgar_downloader consumes this file.

Run:  python -m src.data_acquisition.filer_discovery
"""
from __future__ import annotations

import json
import re
import time

import requests

from src.config_loader import CONFIG, path

HEADERS = {"User-Agent": CONFIG["sec"]["user_agent"]}
_SLEEP = 1.0 / max(CONFIG["sec"]["rate_limit_per_sec"], 1)
IDX_URL = "https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{q}/form.idx"
FORMS = {"N-PX", "N-PX/A"}


def _get(url: str) -> str:
    for attempt in range(4):
        resp = requests.get(url, headers=HEADERS, timeout=60)
        if resp.status_code == 200:
            time.sleep(_SLEEP)
            return resp.text
        if resp.status_code in (403, 429):
            time.sleep(2 ** attempt)
            continue
        resp.raise_for_status()
    raise RuntimeError(f"Failed to fetch {url}")


def parse_form_idx(text: str) -> list[dict]:
    """
    Parse the fixed-width-ish form.idx. Columns are separated by 2+ spaces;
    we split defensively and validate the CIK is numeric.
    """
    rows: list[dict] = []
    started = False
    for line in text.splitlines():
        if line.startswith("Form Type"):
            started = True
            continue
        if not started or not line.strip() or set(line.strip()) == {"-"}:
            continue
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) < 5:
            continue
        form, company, cik, date_filed, file_name = parts[0], parts[1], parts[2], parts[3], parts[4]
        if form not in FORMS or not cik.isdigit():
            continue
        rows.append({"form": form, "company": company, "cik": cik.zfill(10),
                     "date_filed": date_filed, "file_name": file_name})
    return rows


def discover() -> dict[str, list[dict]]:
    from datetime import date as _date
    start = CONFIG["sec"]["start_year"]
    end = max(CONFIG["sec"]["end_year"], _date.today().year)  # self-extending
    npx_rows: list[dict] = []
    # Q3 catches the 31-Aug season; Q1 sweeps amendments/late filings.
    for year in range(start, end + 1):
        for q in (1, 3):
            url = IDX_URL.format(year=year, q=q)
            try:
                npx_rows.extend(parse_form_idx(_get(url)))
                print(f"  indexed {year} QTR{q}: cumulative N-PX rows {len(npx_rows):,}")
            except Exception as exc:  # noqa: BLE001
                print(f"  [warn] {year} QTR{q}: {exc}")

    resolved: dict[str, list[dict]] = {}
    for filer in CONFIG["filers"]:
        pats = [re.compile(p) for p in filer["name_patterns"]]
        seen: dict[str, str] = {}
        for row in npx_rows:
            if any(p.search(row["company"]) for p in pats):
                seen.setdefault(row["cik"], row["company"])
        for cik in filer.get("seed_ciks", []):
            seen.setdefault(cik.zfill(10), f"(seed) {filer['name']}")
        resolved[filer["name"]] = [{"cik": c, "company_name": n} for c, n in sorted(seen.items())]
        print(f"[{filer['name']}] {len(resolved[filer['name']])} filer CIK(s) resolved")
    return resolved


def run() -> None:
    resolved = discover()
    out = path("interim") / "filers_resolved.json"
    out.write_text(json.dumps(resolved, indent=2))
    total = sum(len(v) for v in resolved.values())
    print(f"\nWrote {total} resolved filer entities -> {out}")
    if total == 0:
        print("[error] No filers resolved — check network/User-Agent before proceeding.")


if __name__ == "__main__":
    run()
