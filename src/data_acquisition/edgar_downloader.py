"""
Section 2 — SEC EDGAR acquisition layer.

Downloads Form N-PX filings for the filers and years configured in
config/config.yaml.

Data source
-----------
The SEC's Electronic Data Gathering, Analysis, and Retrieval system (EDGAR)
publishes every registrant's filing history as JSON at
    https://data.sec.gov/submissions/CIK##########.json
and the filing documents under
    https://www.sec.gov/Archives/edgar/data/<cik>/<accession-no-dashes>/

Access methods used here (belt and braces):
  1. The native JSON submissions API via `requests` (primary; no extra deps).
  2. `sec-edgar-downloader` as a convenience fallback for bulk pulls.
  3. `edgartools` for high-level access when iterating interactively.

Compliance
----------
EDGAR's fair-access policy REQUIRES a descriptive User-Agent containing a
contact email and limits clients to 10 requests/second. We set the header
from config and sleep to stay under the ceiling. Violations return HTTP 403
and can lead to an IP block.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

from src.config_loader import CONFIG, path

SUBMISSIONS_URL = CONFIG["sec"]["base_submissions_url"]
HEADERS = {"User-Agent": CONFIG["sec"]["user_agent"]}
RATE = CONFIG["sec"]["rate_limit_per_sec"]
FORM = CONFIG["sec"]["form_type"]
from datetime import date as _date
START = CONFIG["sec"]["start_year"]
# Self-extending window: scheduled future runs automatically include
# the current filing year without config edits.
END = max(CONFIG["sec"]["end_year"], _date.today().year)
_SLEEP = 1.0 / max(RATE, 1)


def _get(url: str) -> requests.Response:
    """Rate-limited GET with retry/backoff and a compliant header."""
    for attempt in range(4):
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            time.sleep(_SLEEP)
            return resp
        if resp.status_code in (403, 429):
            wait = 2 ** attempt
            print(f"  [warn] {resp.status_code} on {url} — backing off {wait}s")
            time.sleep(wait)
            continue
        resp.raise_for_status()
    raise RuntimeError(f"Failed to fetch {url} after retries")


def fetch_submissions(cik: str) -> dict:
    """Return the parsed submissions JSON for a 10-digit zero-padded CIK."""
    url = SUBMISSIONS_URL.format(cik=cik.zfill(10))
    return _get(url).json()


def list_npx_accessions(submissions: dict) -> list[dict]:
    """
    Extract N-PX filings within the configured year window.

    The 'recent' block is column-oriented (parallel arrays). For filers with
    long histories EDGAR splits older filings into additional files listed
    under submissions['filings']['files']; production code should page through
    those too. We read 'recent' here, which covers the 2019-2024 window.
    """
    recent = submissions["filings"]["recent"]
    rows = zip(
        recent["form"],
        recent["accessionNumber"],
        recent["filingDate"],
        recent["primaryDocument"],
    )
    out = []
    for form, accession, fdate, primary_doc in rows:
        # Accept amendments too (N-PX/A); dedup happens downstream.
        if form not in (FORM, f"{FORM}/A"):
            continue
        year = int(fdate[:4])
        if not (START <= year <= END):
            continue
        out.append(
            {
                "accession": accession,
                "accession_nodash": accession.replace("-", ""),
                "filing_date": fdate,
                "year": year,
                "primary_document": primary_doc,
            }
        )
    return out


def _pick_vote_document(cik_int: str, accession_nodash: str, primary: str) -> str:
    """
    Return the filename of the document that actually contains the votes.

    Verified against live filings (run #4): for structured N-PX,
    'primary_doc.xml' is only the COVER PAGE (registrant info, signatures);
    the proxy vote table is a separate exhibit XML in the same accession
    folder — the same pattern as 13F's infotable. We list the accession via
    index.json and prefer (a) XMLs whose name suggests a vote table, then
    (b) the largest other XML, falling back to the primary document.
    """
    import re as _re

    base = CONFIG["sec"]["archives_base"]
    try:
        idx = _get(f"{base}/{cik_int}/{accession_nodash}/index.json").json()
        items = idx.get("directory", {}).get("item", [])
        xmls = [i for i in items
                if str(i.get("name", "")).lower().endswith(".xml")
                and i.get("name") != primary]
        if xmls:
            named = [i for i in xmls
                     if _re.search(r"vote|table|npx|infotable", str(i["name"]), _re.I)]
            pool = named or xmls
            def _size(i):
                try: return int(i.get("size") or 0)
                except (TypeError, ValueError): return 0
            return max(pool, key=_size)["name"]
    except Exception as exc:  # noqa: BLE001 — fall back to the cover doc
        print(f"    [warn] index.json fallback ({exc})")
    return primary


def download_filing(cik: str, filing: dict, dest: Path) -> Path:
    """Download the vote-table document for one filing. Returns the path."""
    cik_int = str(int(cik))  # archives path uses the un-padded integer CIK
    base = CONFIG["sec"]["archives_base"]
    # Strip EDGAR's XSL-viewer prefix ('xslN-PX_X01/...') to get the raw doc.
    primary = filing["primary_document"].split("/")[-1]
    doc = _pick_vote_document(cik_int, filing["accession_nodash"], primary)
    url = f"{base}/{cik_int}/{filing['accession_nodash']}/{doc}"
    resp = _get(url)
    safe_name = f"{cik.zfill(10)}_{filing['accession']}_{doc}".replace("/", "_")
    out_path = dest / safe_name
    out_path.write_bytes(resp.content)
    return out_path


def _load_resolved_filers() -> dict[str, list[str]]:
    """
    Return {family_name: [cik, ...]} from filers_resolved.json (produced by
    filer_discovery.py). Falls back to config seed_ciks with a loud warning,
    because N-PX is filed by many fund trusts per family and seeds alone
    under-cover the voting universe.
    """
    import json as _json

    resolved_path = path("interim") / "filers_resolved.json"
    if resolved_path.exists():
        resolved = _json.loads(resolved_path.read_text())
        return {fam: [e["cik"] for e in entities] for fam, entities in resolved.items()}

    print("[warn] filers_resolved.json not found — run "
          "`python -m src.data_acquisition.filer_discovery` first. "
          "Falling back to config seed_ciks (coverage will be PARTIAL).")
    return {f["name"]: [c.zfill(10) for c in f.get("seed_ciks", [])]
            for f in CONFIG["filers"]}


def run() -> None:
    raw_dir = path("raw")
    manifest = []
    families = _load_resolved_filers()
    for name, ciks in families.items():
        if not ciks:
            print(f"[{name}] no CIKs resolved — skipping (run filer_discovery).")
            continue
        filer_dir = raw_dir / name.replace(" ", "_")
        filer_dir.mkdir(parents=True, exist_ok=True)
        for cik in ciks:
            print(f"[{name}] CIK {cik} — fetching submission index…")
            try:
                subs = fetch_submissions(cik)
            except Exception as exc:  # noqa: BLE001
                print(f"  [error] could not fetch submissions: {exc}")
                continue
            filings = list_npx_accessions(subs)
            print(f"  found {len(filings)} {FORM} filings in {START}-{END}")
            for f in filings:
                try:
                    p = download_filing(cik, f, filer_dir)
                    manifest.append({"filer": name, "cik": cik, **f, "local_path": str(p)})
                    print(f"    saved {p.name}")
                except Exception as exc:  # noqa: BLE001
                    print(f"    [error] {f['accession']}: {exc}")

    # A manifest makes the parse stage deterministic and auditable.
    manifest_path = raw_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"\nManifest written: {manifest_path} ({len(manifest)} filings)")


if __name__ == "__main__":
    run()
