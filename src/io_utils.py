"""
Table IO with graceful degradation.

Parquet (via pyarrow) is the preferred interchange format between pipeline
stages: typed, compressed, fast. But requiring pyarrow makes the pipeline
brittle on minimal environments, so these helpers fall back to CSV when
pyarrow is unavailable. Stage code always passes the .parquet path; the
helpers transparently substitute .csv when needed.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

try:
    import pyarrow  # noqa: F401
    HAS_PARQUET = True
except ImportError:
    HAS_PARQUET = False


def write_df(df: pd.DataFrame, path: Path) -> Path:
    path = Path(path)
    if HAS_PARQUET and path.suffix == ".parquet":
        df.to_parquet(path, index=False)
        return path
    alt = path.with_suffix(".csv")
    df.to_csv(alt, index=False)
    if not HAS_PARQUET and path.suffix == ".parquet":
        print(f"  [io] pyarrow unavailable — wrote CSV fallback {alt.name}")
    return alt


def read_df(path: Path) -> pd.DataFrame:
    path = Path(path)
    if path.exists() and path.suffix == ".parquet" and HAS_PARQUET:
        return pd.read_parquet(path)
    alt = path.with_suffix(".csv")
    if alt.exists():
        return pd.read_csv(alt)
    if path.exists():  # parquet exists but no pyarrow
        raise ImportError(
            f"{path.name} is parquet but pyarrow is not installed; "
            f"pip install pyarrow or re-run the producing stage."
        )
    raise FileNotFoundError(f"Neither {path.name} nor {alt.name} exists — run the earlier stage first.")
