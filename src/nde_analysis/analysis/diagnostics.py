from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from scipy.stats import chi2_contingency, mannwhitneyu

from nde_analysis.analysis.multiple_testing import add_fdr_columns


@dataclass
class CovariateDiagnostics:
    overlap_df: pd.DataFrame
    overall_table: pd.DataFrame
    overall_categorical_table: pd.DataFrame
    summary_table: pd.DataFrame
    balance_table: pd.DataFrame
    sex_summary: pd.DataFrame


def build_covariate_diagnostics(
    analysis_df: pd.DataFrame,
    analysis_pretransform_df: pd.DataFrame | None = None,
    complete_case: bool = False,
) -> CovariateDiagnostics:
    overlap_vars = [
        "age",
        "CTQ_IM_SCORE",
        "ADHD_SCALE",
        "ERQ_reappraisal",
        "ERQ_suppression",
        "education_ord",
    ]

    df_overlap = analysis_df[["valence_binary", "sex_Male"] + overlap_vars].copy()
    if complete_case:
        required = ["valence_binary", "sex_Male"] + overlap_vars
        keep_index = df_overlap.dropna(subset=required).index
        df_overlap = df_overlap.loc[keep_index].copy()
    df_overlap["valence"] = df_overlap["valence_binary"].map(
        {1: "Positive", 0: "Non-positive"}
    )

    source = (
        analysis_pretransform_df
        if analysis_pretransform_df is not None
        else analysis_df
    )
    if complete_case:
        source = source.loc[df_overlap.index].copy()
    overall_rows: list[dict] = []
    for var in overlap_vars:
        series = pd.to_numeric(source[var], errors="coerce").dropna()
        if len(series) == 0:
            continue
        overall_rows.append(
            {
                "variable": var,
                "n": len(series),
                "mean": series.mean(),
                "std": series.std(ddof=1),
            }
        )
    overall_table = pd.DataFrame(overall_rows)

    sex_series = pd.to_numeric(source["sex_Male"], errors="coerce").dropna()
    if len(sex_series) > 0:
        proportions = sex_series.value_counts(normalize=True)
        top_value = int(proportions.index[0])
        top_label = "Male" if top_value == 1 else "Female/other baseline"
        overall_categorical_table = pd.DataFrame(
            [
                {
                    "variable": "sex_Male",
                    "top_category": top_label,
                    "top_pct": 100 * proportions.iloc[0],
                    "n": len(sex_series),
                }
            ]
        )
    else:
        overall_categorical_table = pd.DataFrame(
            columns=["variable", "top_category", "top_pct", "n"]
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
    balance_table = add_fdr_columns(pd.DataFrame(balance_rows), p_col="p_value")
    balance_table = balance_table.sort_values("p_value_fdr", na_position="last")

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
        overall_table=overall_table,
        overall_categorical_table=overall_categorical_table,
        summary_table=summary_table,
        balance_table=balance_table,
        sex_summary=sex_summary,
    )
