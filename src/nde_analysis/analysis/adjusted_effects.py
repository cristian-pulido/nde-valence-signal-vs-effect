from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import chi2

from nde_analysis.analysis.multiple_testing import add_fdr_columns


@dataclass
class OutcomeModelResult:
    full_table: pd.DataFrame
    covariates_only_table: pd.DataFrame
    comparison_table: pd.DataFrame


def _center_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col in out.columns:
            out[f"{col}_c"] = out[col] - out[col].mean(skipna=True)
    return out


def _fit_ols(df: pd.DataFrame, y_col: str, x_cols: list[str]):
    use = df[[y_col] + x_cols].dropna().copy()
    if len(use) == 0:
        return None, use
    X = sm.add_constant(use[x_cols], has_constant="add")
    y = use[y_col]
    return sm.OLS(y, X).fit(), use


def _extract_table(
    model,
    outcome_label: str,
    target_term: str | None,
    n: int,
) -> dict:
    conf = model.conf_int()
    intercept_low, intercept_high = conf.loc["const"]
    row = {
        "outcome": outcome_label,
        "intercept": model.params["const"],
        "intercept_ci_low": intercept_low,
        "intercept_ci_high": intercept_high,
        "intercept_p_value": model.pvalues["const"],
        "r2": model.rsquared,
        "aic": model.aic,
        "bic": model.bic,
        "n": n,
    }
    if target_term and target_term in model.params.index:
        low, high = conf.loc[target_term]
        row.update(
            {
                "effect": model.params[target_term],
                "effect_ci_low": low,
                "effect_ci_high": high,
                "effect_p_value": model.pvalues[target_term],
            }
        )
    else:
        row.update(
            {
                "effect": np.nan,
                "effect_ci_low": np.nan,
                "effect_ci_high": np.nan,
                "effect_p_value": np.nan,
            }
        )
    return row


def run_outcome_models(
    model_df: pd.DataFrame,
    outcomes: list[str],
    outcome_labels: dict[str, str],
    continuous_covariates: list[str],
    categorical_covariates: list[str],
    include_valence: bool,
    min_n: int,
) -> pd.DataFrame:
    centered = _center_columns(model_df, continuous_covariates)
    centered_covars = [
        f"{c}_c" for c in continuous_covariates if f"{c}_c" in centered.columns
    ]
    x_cols = centered_covars + [
        c for c in categorical_covariates if c in centered.columns
    ]
    if include_valence:
        x_cols = ["valence_binary"] + x_cols

    rows: list[dict] = []
    for out in outcomes:
        label = outcome_labels.get(out, out)
        model, used = _fit_ols(centered, out, x_cols)
        if model is None or len(used) < min_n:
            continue
        rows.append(
            _extract_table(
                model=model,
                outcome_label=label,
                target_term="valence_binary" if include_valence else None,
                n=len(used),
            )
        )

    out = pd.DataFrame(rows)
    out = add_fdr_columns(out, p_col="intercept_p_value")
    out = add_fdr_columns(out, p_col="effect_p_value")
    return out


def compare_full_vs_covariates(
    model_df: pd.DataFrame,
    outcomes: list[str],
    outcome_labels: dict[str, str],
    continuous_covariates: list[str],
    categorical_covariates: list[str],
    min_n: int,
) -> OutcomeModelResult:
    full = run_outcome_models(
        model_df=model_df,
        outcomes=outcomes,
        outcome_labels=outcome_labels,
        continuous_covariates=continuous_covariates,
        categorical_covariates=categorical_covariates,
        include_valence=True,
        min_n=min_n,
    )

    cov_only = run_outcome_models(
        model_df=model_df,
        outcomes=outcomes,
        outcome_labels=outcome_labels,
        continuous_covariates=continuous_covariates,
        categorical_covariates=categorical_covariates,
        include_valence=False,
        min_n=min_n,
    )

    merged = full.merge(
        cov_only,
        on="outcome",
        suffixes=("_full", "_cov_only"),
    )

    if not merged.empty:
        merged["delta_r2"] = merged["r2_full"] - merged["r2_cov_only"]
        merged["delta_aic"] = merged["aic_full"] - merged["aic_cov_only"]
        merged["delta_bic"] = merged["bic_full"] - merged["bic_cov_only"]

        # Approximate LR test using RSS-based relation is not ideal in OLS tables,
        # so we provide a simple nested-model comparison via F test from full model.
        # Here, infer additional value of valence from its own p-value in full model.
        if "effect_p_value_fdr_full" in merged.columns:
            merged["valence_adds_signal"] = merged["effect_p_value_fdr_full"] < 0.05
            sort_col = "effect_p_value_fdr_full"
        else:
            merged["valence_adds_signal"] = merged["effect_p_value_full"] < 0.05
            sort_col = "effect_p_value_full"
        merged["interpretation"] = merged.apply(
            lambda r: (
                "Valence adds explanatory value beyond covariates after FDR correction."
                if r["valence_adds_signal"]
                else "Valence does not add clear explanatory value beyond covariates after FDR correction."
            ),
            axis=1,
        )
    else:
        sort_col = "effect_p_value_full"

    return OutcomeModelResult(
        full_table=full.sort_values("effect_p_value_fdr", na_position="last"),
        covariates_only_table=cov_only.sort_values("outcome"),
        comparison_table=merged.sort_values(sort_col, na_position="last"),
    )
