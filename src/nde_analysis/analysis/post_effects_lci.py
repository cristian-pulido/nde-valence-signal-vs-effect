from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from scipy.stats import mannwhitneyu, wilcoxon

from nde_analysis.preprocess.mappings import LCI_SECTIONS


@dataclass
class LCIResults:
    global_table: pd.DataFrame
    by_valence_table: pd.DataFrame
    missingness_table: pd.DataFrame
    long_df: pd.DataFrame


def run_lci_analyses(lci_df: pd.DataFrame, lci_score_cols: list[str]) -> LCIResults:
    global_rows: list[dict] = []
    by_valence_rows: list[dict] = []

    for col in lci_score_cols:
        series = lci_df[col].dropna()
        if len(series) > 0:
            _, p = wilcoxon(series)
            global_rows.append(
                {
                    "category": col.replace("LCI_", ""),
                    "median": series.median(),
                    "mean": series.mean(),
                    "p_value": p,
                    "n": len(series),
                }
            )

        pos = lci_df.loc[lci_df["valence_binary"] == 1, col].dropna()
        non = lci_df.loc[lci_df["valence_binary"] == 0, col].dropna()
        if len(pos) > 0 and len(non) > 0:
            _, p2 = mannwhitneyu(pos, non, alternative="two-sided")
            by_valence_rows.append(
                {
                    "category": col.replace("LCI_", ""),
                    "mean_positive": pos.mean(),
                    "mean_non_positive": non.mean(),
                    "median_positive": pos.median(),
                    "median_non_positive": non.median(),
                    "p_value": p2,
                    "n_positive": len(pos),
                    "n_non_positive": len(non),
                }
            )

    missing = pd.DataFrame(
        {
            "category": [c.replace("LCI_", "") for c in lci_score_cols],
            "missing_fraction": [lci_df[c].isna().mean() for c in lci_score_cols],
        }
    ).sort_values("missing_fraction", ascending=False)

    long_df = (
        lci_df.melt(
            id_vars=["valence_binary"],
            value_vars=lci_score_cols,
            var_name="category",
            value_name="score",
        )
        .dropna()
        .copy()
    )
    long_df["category"] = long_df["category"].str.replace("LCI_", "", regex=False)
    long_df["valence"] = long_df["valence_binary"].map(
        {1: "Positive", 0: "Non-positive"}
    )

    return LCIResults(
        global_table=pd.DataFrame(global_rows).sort_values("p_value"),
        by_valence_table=pd.DataFrame(by_valence_rows).sort_values("p_value"),
        missingness_table=missing,
        long_df=long_df,
    )


def lci_score_columns() -> list[str]:
    return [f"LCI_{section}" for section in LCI_SECTIONS.keys()]
