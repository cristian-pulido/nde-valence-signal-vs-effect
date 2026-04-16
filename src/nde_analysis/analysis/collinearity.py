from __future__ import annotations

import pandas as pd
from statsmodels.stats.outliers_influence import variance_inflation_factor


def compute_vif_table(df: pd.DataFrame, predictors: list[str]) -> pd.DataFrame:
    use = df[predictors].dropna().copy()
    use = use.astype(float)

    vif_df = pd.DataFrame(
        {
            "predictor": use.columns,
            "vif": [
                variance_inflation_factor(use.values, i) for i in range(use.shape[1])
            ],
        }
    )

    def _label(v: float) -> str:
        if v < 2:
            return "Low"
        if v < 5:
            return "Moderate"
        return "High"

    vif_df["collinearity"] = vif_df["vif"].apply(_label)
    return vif_df.sort_values("vif", ascending=False).reset_index(drop=True)
