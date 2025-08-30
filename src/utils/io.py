from __future__ import annotations
import pandas as pd
from pathlib import Path

def ensure_parent(path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

def read_csv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)

def write_csv(df, path: str | Path) -> None:
    ensure_parent(path)
    df.to_csv(path, index=False)