from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from scipy.stats import mannwhitneyu, wilcoxon

from nde_analysis.analysis.multiple_testing import add_fdr_columns
from nde_analysis.preprocess.mappings import MCQ_COLS, MCQ_ITEM_LABELS, MCQ_VALUE_LABELS


@dataclass
class MCQResults:
    global_table: pd.DataFrame
    by_valence_table: pd.DataFrame
    response_distribution: pd.DataFrame
    long_df: pd.DataFrame


def run_mcq_analyses(mcq_df: pd.DataFrame) -> MCQResults:
    global_rows: list[dict] = []
    by_valence_rows: list[dict] = []

    for col in MCQ_COLS:
        series = mcq_df[col].dropna()
        if len(series) > 0:
            _, p = wilcoxon(series)
            global_rows.append(
                {
                    "item": MCQ_ITEM_LABELS[col],
                    "median": series.median(),
                    "mean": series.mean(),
                    "p_value": p,
                    "n": len(series),
                }
            )

        pos = mcq_df.loc[mcq_df["valence_binary"] == 1, col].dropna()
        non = mcq_df.loc[mcq_df["valence_binary"] == 0, col].dropna()
        if len(pos) > 0 and len(non) > 0:
            _, p2 = mannwhitneyu(pos, non, alternative="two-sided")
            by_valence_rows.append(
                {
                    "item": MCQ_ITEM_LABELS[col],
                    "mean_positive": pos.mean(),
                    "mean_non_positive": non.mean(),
                    "median_positive": pos.median(),
                    "median_non_positive": non.median(),
                    "p_value": p2,
                    "n_positive": len(pos),
                    "n_non_positive": len(non),
                }
            )

    long_df = (
        mcq_df.melt(
            id_vars=["valence_binary"],
            value_vars=MCQ_COLS,
            var_name="item",
            value_name="score",
        )
        .dropna()
        .copy()
    )
    long_df["item"] = long_df["item"].map(MCQ_ITEM_LABELS)
    long_df["valence"] = long_df["valence_binary"].map(
        {1: "Positive", 0: "Non-positive"}
    )
    long_df["response"] = long_df["score"].map(MCQ_VALUE_LABELS)

    dist = (
        long_df.groupby(["item", "valence", "score", "response"])
        .size()
        .reset_index(name="n")
    )
    dist["pct"] = dist.groupby(["item", "valence"])["n"].transform(
        lambda x: 100 * x / x.sum()
    )

    global_table = add_fdr_columns(pd.DataFrame(global_rows), p_col="p_value")
    by_valence_table = add_fdr_columns(pd.DataFrame(by_valence_rows), p_col="p_value")

    return MCQResults(
        global_table=global_table.sort_values("p_value_fdr", na_position="last"),
        by_valence_table=by_valence_table.sort_values(
            "p_value_fdr", na_position="last"
        ),
        response_distribution=dist,
        long_df=long_df,
    )
