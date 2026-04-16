from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def require_columns(
    df: pd.DataFrame, columns: Iterable[str], context: str = ""
) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        prefix = f"{context}: " if context else ""
        raise ValueError(f"{prefix}missing required columns: {missing}")
