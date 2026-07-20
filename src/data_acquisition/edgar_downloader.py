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


def _scan_block(block: dict, out: list[dict]) -> None:
    """Append in-window N-PX rows from one column-oriented filings block."""
    rows = zip(block.get("form", []), block.get("accessionNumber", []),
               block.get("filingDate", []), block.get("primaryDocument", []))
    for form, accession, fdate, primary_doc in rows:
        if form not in (FORM, f"{FORM}/A"):  # amendments included; dedup later
            continue
        year = int(fdate[:4])
        if not (START <= year <= END):
            continue
        out.append({
            "accession": accession,
            "accession_nodash": accession.replace("-", ""),
            "filing_date": fdate, "year": year,
            "primary_document": primary_doc,
        })


def list_npx_accessions(submissions: dict) -> list[dict]:
    """
    Extract in-window N-PX filings, paging through EDGAR's older submission
    files when needed.

    The 'recent' block only holds the last ~1000 filings. High-volume fund
    trusts (SPDR, iShares) file so many NPORT/497/485 documents that their
    annual N-PX ages out of 'recent' into the additional files listed under
    filings.files[].name. We scan 'recent' first, then only fetch older
    pages while they can still contain filings in our year window (their
    filingTo date is >= START), so we never over-download.
    """
    out: list[dict] = []
    _scan_block(submissions["filings"]["recent"], out)

    cik_padded = str(submissions.get("cik", "")).zfill(10)
    for f in submissions["filings"].get("files", []):
        try:
            if int(str(f.get("filingTo", "9999"))[:4]) < START:
                continue  # this page is entirely older than our window
        except ValueError:
            pass
        try:
            page = _get(f"https://data.sec.gov/submissions/{f['name']}").json()
            _scan_block(page, out)
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] paging {f.get('name')}: {exc}")
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
    Return {family_name: [cik, ...]} to acquire.

    scope_mode == 'flagship' (default): one verified representative trust per
    manager from config — fast and free-tier-friendly. Otherwise use the full
    discovered universe from filers_resolved.json (hours), falling back to
    config seed_ciks.
    """
    import json as _json

    if CONFIG["sec"].get("scope_mode", "flagship") == "flagship":
        fam = {f["name"]: [f["flagship_cik"].zfill(10)]
               for f in CONFIG["filers"] if f.get("flagship_cik")}
        print(f"[scope] flagship mode — {len(fam)} trust(s): "
              + ", ".join(f'{k}={v[0]}' for k, v in fam.items()))
        return fam

    cap = CONFIG["sec"].get("max_ciks_per_family")
    resolved_path = path("interim") / "filers_resolved.json"
    if resolved_path.exists():
        resolved = _json.loads(resolved_path.read_text())
        fam = {f: [e["cik"] for e in ent] for f, ent in resolved.items()}
        if cap:
            # Keep the flagship first (if present), then fill up to the cap so
            # coverage widens beyond one trust without an unbounded pull.
            flag = {x["name"]: x.get("flagship_cik") for x in CONFIG["filers"]}
            for f in fam:
                fc = (flag.get(f) or "").zfill(10)
                ordered = ([fc] if fc in fam[f] else []) + [c for c in fam[f] if c != fc]
                fam[f] = ordered[:cap]
            print(f"[scope] discover mode — capped at {cap} trust(s)/family: "
                  + ", ".join(f"{k}={len(v)}" for k, v in fam.items()))
        return fam
    print("[warn] filers_resolved.json not found — falling back to seed_ciks.")
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
            cap = CONFIG["sec"].get("max_filings_per_cik")
            if cap:
                # Newest first, so the cap keeps the most recent seasons.
                filings = sorted(filings, key=lambda x: x["filing_date"],
                                 reverse=True)[:cap]
            print(f"  found {len(filings)} {FORM} filings in {START}-{END} "
                  f"(capped at {cap})" if cap else
                  f"  found {len(filings)} {FORM} filings in {START}-{END}")
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
