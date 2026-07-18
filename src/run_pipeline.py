"""
End-to-end pipeline orchestrator.

Runs every stage in order:
    acquire -> parse -> clean -> classify (rule + ml) -> load -> score

Usage
-----
    python -m src.run_pipeline                # full run
    python -m src.run_pipeline --skip-acquire # reuse already-downloaded raw filings
    python -m src.run_pipeline --no-db        # stop before the DB load/score (dry run)

This is the entry point the scheduled GitHub Actions workflow calls twice a
year. Each stage is idempotent, so a re-run is safe.
"""
from __future__ import annotations

import argparse
import sys
import time


def _stage(label: str, fn) -> None:
    print(f"\n{'='*70}\n▶ {label}\n{'='*70}", flush=True)
    t0 = time.time()
    fn()
    print(f"✔ {label} done in {time.time()-t0:,.1f}s", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the full IIVAS pipeline.")
    ap.add_argument("--skip-acquire", action="store_true",
                    help="reuse existing data/raw filings instead of downloading")
    ap.add_argument("--no-db", action="store_true",
                    help="stop before the PostgreSQL load and score stages")
    args = ap.parse_args()

    # Imported lazily so --help works without heavy deps installed.
    from src.data_acquisition import edgar_downloader, filer_discovery, npx_parser
    from src.preprocessing import clean_votes
    from src.classification import rule_based, ml_classifier

    from src.config_loader import CONFIG
    flagship = CONFIG["sec"].get("scope_mode", "flagship") == "flagship"

    if not args.skip_acquire:
        if flagship:
            print("Flagship scope — skipping full filer discovery.")
        else:
            _stage("1/9 Resolve N-PX filer CIKs per family", filer_discovery.run)
        _stage("2/9 Acquire N-PX filings from SEC EDGAR", edgar_downloader.run)
    else:
        print("Skipping discovery + acquisition (using existing data/raw).")

    _stage("3/9 Parse filings", npx_parser.run)
    _stage("4/9 Clean & deduplicate", clean_votes.run)
    _stage("5/9 Classify proposals (rules)", rule_based.run)
    _stage("6/9 Classify proposals (NLP residual)", ml_classifier.run)

    if args.no_db:
        print("\n--no-db set: skipping DB load and scoring. Pipeline stopped.")
        return 0

    from src.database import load_to_db
    from src.metrics import iivas
    _stage("7/9 Load into PostgreSQL (Supabase)", load_to_db.run)
    _stage("8/9 Compute IIVAS & refresh yearly_statistics", iivas.run)

    # EDA + figures are non-fatal: a plotting failure should not sink a
    # scheduled refresh whose main job is the DB load.
    def _analytics():
        from src.eda import exploratory
        from src.visualization import plots
        exploratory.run()
        plots.run()
    try:
        _stage("9/9 EDA tables + figures", _analytics)
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] analytics stage failed (non-fatal): {exc}")

    print("\n🎉 Pipeline complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
