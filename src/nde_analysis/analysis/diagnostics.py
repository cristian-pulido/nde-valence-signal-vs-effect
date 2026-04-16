from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from scipy.stats import chi2_contingency, mannwhitneyu


@dataclass
class CovariateDiagnostics:
    overlap_df: pd.DataFrame
    summary_table: pd.DataFrame
    balance_table: pd.DataFrame
    sex_summary: pd.DataFrame


def build_covariate_diagnostics(analysis_df: pd.DataFrame) -> CovariateDiagnostics:
    overlap_vars = [
        "age",
        "CTQ_IM_SCORE",
        "ADHD_SCALE",
        "ERQ_reappraisal",
        "ERQ_suppression",
        "education_ord",
    ]

    df_overlap = analysis_df[["valence_binary", "sex_Male"] + overlap_vars].copy()
    df_overlap["valence"] = df_overlap["valence_binary"].map(
        {1: "Positive", 0: "Non-positive"}
    )

    summary_rows: list[pd.DataFrame] = []
    for var in overlap_vars:
        agg = (
            df_overlap.groupby("valence")[var]
            .agg(["count", "mean", "std", "median", "min", "max"])
            .reset_index()
        )
        agg["variable"] = var
        summary_rows.append(agg)
    summary_table = pd.concat(summary_rows, ignore_index=True)
    summary_table = summary_table[
        ["variable", "valence", "count", "mean", "std", "median", "min", "max"]
    ]

    balance_rows: list[dict] = []
    for var in overlap_vars:
        g_pos = df_overlap.loc[df_overlap["valence_binary"] == 1, var].dropna()
        g_non = df_overlap.loc[df_overlap["valence_binary"] == 0, var].dropna()
        if len(g_pos) > 0 and len(g_non) > 0:
            _, p_value = mannwhitneyu(g_pos, g_non, alternative="two-sided")
            balance_rows.append(
                {
                    "variable": var,
                    "type": "continuous/ordinal",
                    "p_value": p_value,
                    "mean_positive": g_pos.mean(),
                    "mean_non_positive": g_non.mean(),
                }
            )

    tab = pd.crosstab(df_overlap["valence"], df_overlap["sex_Male"])
    _, sex_p, _, _ = chi2_contingency(tab)
    balance_rows.append(
        {
            "variable": "sex_Male",
            "type": "categorical",
            "p_value": sex_p,
            "mean_positive": df_overlap.loc[
                df_overlap["valence_binary"] == 1, "sex_Male"
            ].mean(),
            "mean_non_positive": df_overlap.loc[
                df_overlap["valence_binary"] == 0, "sex_Male"
            ].mean(),
        }
    )
    balance_table = pd.DataFrame(balance_rows).sort_values("p_value")

    sex_summary = (
        df_overlap.groupby("valence")["sex_Male"]
        .value_counts(normalize=True)
        .rename("proportion")
        .reset_index()
    )
    sex_summary["sex_label"] = sex_summary["sex_Male"].map(
        {0: "Female/other baseline", 1: "Male"}
    )

    return CovariateDiagnostics(
        overlap_df=df_overlap,
        summary_table=summary_table,
        balance_table=balance_table,
        sex_summary=sex_summary,
    )
