from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests


def add_fdr_columns(
    df: pd.DataFrame,
    p_col: str,
    p_fdr_col: str | None = None,
    reject_col: str | None = None,
    alpha: float = 0.05,
) -> pd.DataFrame:
    if df.empty or p_col not in df.columns:
        return df

    p_fdr_col = p_fdr_col or f"{p_col}_fdr"
    reject_col = reject_col or f"{p_col}_fdr_reject"

    out = df.copy()
    pvals = pd.to_numeric(out[p_col], errors="coerce")
    valid = pvals.notna()

    out[p_fdr_col] = np.nan
    out[reject_col] = False
    if valid.any():
        reject, pvals_corr, _, _ = multipletests(
            pvals.loc[valid],
            alpha=alpha,
            method="fdr_bh",
        )
        out.loc[valid, p_fdr_col] = pvals_corr
        out.loc[valid, reject_col] = reject

    return out
