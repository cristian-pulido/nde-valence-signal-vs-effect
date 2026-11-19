"""Standalone exploratory interaction models; never called by the main pipeline.

The covariate lists mirror run_post_effects_pipeline in cli.py. Preprocessing,
LCI scoring and the baseline fitter are reused, rather than reconstructed.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

from nde_analysis.analysis.adjusted_effects import _center_columns, run_outcome_models
from nde_analysis.analysis.multiple_testing import add_fdr_columns
from nde_analysis.preprocess.mappings import normalize_display_label

INTENSITY = "greyson_total_no_affective"
CENTERED = f"{INTENSITY}_c"
INTERACTION = "intensity_x_positive"
CONTINUOUS = [
    "age_first_NDE", "CTQ_IM_SCORE", "education_ord", INTENSITY,
    "dx_prior_NDE_Yes",
]


@dataclass
class InteractionAnalysis:
    results: pd.DataFrame
    unadjusted: pd.DataFrame
    feasibility: pd.DataFrame
    influence: pd.DataFrame
    coefficients: pd.DataFrame
    baseline_validation: pd.DataFrame
    fits: dict
    samples: dict
    intensity_center: float


def domain_label(outcome: str) -> str:
    return normalize_display_label(outcome).removeprefix("LCI_")


def fdr_ten(table: pd.DataFrame, p_col: str, q_col: str) -> pd.DataFrame:
    """Keep the prespecified family size if an outcome cannot be estimated.

    Non-estimable hypotheses conservatively enter correction as p=1, but their
    reported p and q remain missing. Never silently shrink the ten-domain family.
    """
    work = table.copy()
    work["_family_p"] = work[p_col].fillna(1.0)
    work = add_fdr_columns(work, "_family_p", q_col, "_reject")
    work.loc[work[p_col].isna(), q_col] = np.nan
    return work.drop(columns=["_family_p", "_reject"])


def describe_sample(data: pd.DataFrame, outcome: str) -> list[dict]:
    groups = [data.loc[data.valence_binary == v, INTENSITY] for v in (0, 1)]
    lower = max(g.min() for g in groups)
    upper = min(g.max() for g in groups)
    common_values = set(groups[0].dropna()) & set(groups[1].dropna())
    rows = []
    for value, group in zip((0, 1), groups):
        rows.append({
            "outcome": outcome, "valence": "Positive" if value else "Non-positive",
            "n": len(group), "mean": group.mean(), "sd": group.std(),
            "min": group.min(), "q25": group.quantile(.25),
            "median": group.median(), "q75": group.quantile(.75), "max": group.max(),
            "unique_values": group.nunique(), "overlap_min": lower,
            "overlap_max": upper, "n_in_overlap_range": group.between(lower, upper).sum(),
            "n_outside_overlap_range": (~group.between(lower, upper)).sum(),
            "n_shared_discrete_values": len(common_values),
        })
    return rows


def _summary(baseline, model, used: pd.DataFrame) -> dict:
    j = model.model.exog_names.index(INTERACTION)
    robust = model.get_robustcov_results(cov_type="HC3", use_t=True)
    low, high = model.conf_int().loc[INTERACTION]
    f_stat, f_p, df_diff = model.compare_f_test(baseline)
    if not np.isclose(f_p, model.pvalues[INTERACTION], atol=1e-10, rtol=1e-8):
        raise AssertionError("Nested F test and interaction t test disagree")
    if not np.array_equal(baseline.model.data.row_labels, model.model.data.row_labels):
        raise AssertionError("Nested models use different participants")
    if model.rsquared < baseline.rsquared - 1e-12:
        raise AssertionError("Nested model reduced R squared")
    slopes = {}
    for group, include_interaction in (("nonpositive", False), ("positive", True)):
        weights = np.zeros(len(model.params))
        weights[model.model.exog_names.index(CENTERED)] = 1
        if include_interaction:
            weights[j] = 1
        test = model.t_test(weights)
        ci = test.conf_int()[0]
        slopes.update({f"slope_{group}": float(np.asarray(test.effect).item()),
                       f"slope_{group}_ci_low": ci[0], f"slope_{group}_ci_high": ci[1]})
    return {
        "status": "ok", "interaction_beta": model.params[INTERACTION],
        "interaction_ci_low": low, "interaction_ci_high": high,
        "interaction_p": model.pvalues[INTERACTION],
        "interaction_hc3_ci_low": robust.conf_int()[j, 0],
        "interaction_hc3_ci_high": robust.conf_int()[j, 1],
        "interaction_hc3_p": robust.pvalues[j],
        "baseline_r2": baseline.rsquared, "interaction_r2": model.rsquared,
        "delta_r2": model.rsquared - baseline.rsquared,
        "nested_f": f_stat, "nested_f_p": f_p, "nested_df_difference": df_diff,
        "identical_model_samples": True, "residual_df": model.df_resid,
        "design_rank": np.linalg.matrix_rank(model.model.exog),
        "design_columns": len(model.params), "condition_number": model.condition_number,
        "residual_rmse": np.sqrt(model.mse_resid), **slopes,
    }


def _fit_pair(used: pd.DataFrame, outcome: str, predictors: list[str], min_n: int):
    if len(used) < min_n:
        raise ValueError(f"N={len(used)} is below the existing minimum of {min_n}")
    if used.valence_binary.nunique() != 2:
        raise ValueError("Both valence groups are required")
    if any(len(g) < 2 or g[INTENSITY].nunique() < 2
           for _, g in used.groupby("valence_binary")):
        raise ValueError("At least two distinct intensity values per group are required")
    x0 = sm.add_constant(used[predictors], has_constant="add")
    x1 = x0.assign(**{INTERACTION: used[CENTERED] * used.valence_binary})
    if np.linalg.matrix_rank(x1) != x1.shape[1]:
        raise ValueError("Interaction design is rank deficient; no reliable coefficient")
    if len(used) <= x1.shape[1] + 1:
        raise ValueError("Insufficient residual degrees of freedom for diagnostics")
    baseline = sm.OLS(used[outcome], x0, missing="raise").fit()
    model = sm.OLS(used[outcome], x1, missing="raise").fit()
    return baseline, model


def influence_checks(model, outcome: str, used: pd.DataFrame) -> tuple[dict, list[dict]]:
    """Single-case deletion checks retain all observations in the reported model."""
    influence = model.get_influence()
    n, k = model.model.exog.shape
    j = model.model.exog_names.index(INTERACTION)
    cooks = influence.cooks_distance[0]
    leverage = influence.hat_matrix_diag
    dfbetas = influence.dfbetas[:, j]
    records = []
    for i in range(n):
        keep = np.arange(n) != i
        x = model.model.exog[keep]
        rank_ok = np.linalg.matrix_rank(x) == k
        deleted = sm.OLS(model.model.endog[keep], x).fit() if rank_ok else None
        records.append({
            "outcome": domain_label(outcome),
            "input_data_row": int(used.index[i]) + 1,
            "valence": "Positive" if used.valence_binary.iloc[i] else "Non-positive",
            "intensity": used[INTENSITY].iloc[i], "cooks_distance": cooks[i],
            "leverage": leverage[i], "interaction_dfbetas": dfbetas[i],
            "cooks_flag": bool(cooks[i] > 4 / n),
            "leverage_flag": bool(leverage[i] > 2 * k / n),
            "interaction_dfbetas_flag": bool(abs(dfbetas[i]) > 2 / np.sqrt(n)),
            "loo_full_rank": rank_ok,
            "loo_interaction_beta": deleted.params[j] if deleted is not None else np.nan,
            "loo_interaction_p": deleted.pvalues[j] if deleted is not None else np.nan,
        })
    deleted = pd.DataFrame(records)
    betas = deleted.loo_interaction_beta
    stats = {
        "max_cooks_distance": np.max(cooks), "n_cooks_gt_4_over_n": np.sum(cooks > 4/n),
        "max_leverage": np.max(leverage), "n_leverage_gt_2k_over_n": np.sum(leverage > 2*k/n),
        "max_abs_interaction_dfbetas": np.max(abs(dfbetas)),
        "n_interaction_dfbetas_gt_2_over_sqrt_n": np.sum(abs(dfbetas) > 2/np.sqrt(n)),
        "loo_beta_min": betas.min(), "loo_beta_max": betas.max(),
        "loo_p_min": deleted.loo_interaction_p.min(),
        "loo_p_max": deleted.loo_interaction_p.max(),
        "loo_sign_changes": int((np.sign(betas.dropna()) != np.sign(model.params[INTERACTION])).sum()),
        "loo_rank_failures": int((~deleted.loo_full_rank).sum()),
    }
    return stats, records


def baseline_validation(reference: pd.DataFrame, saved: pd.DataFrame,
                        fitted_baselines: dict) -> pd.DataFrame:
    """Check every saved numeric field, then verify raw-unit reparameterization."""
    if set(reference.outcome) != set(saved.outcome):
        raise ValueError("Existing and reproduced baseline outcomes differ")
    checks = []
    existing = saved.set_index("outcome")
    for _, row in reference.iterrows():
        for metric in reference.select_dtypes(include="number").columns:
            before, now = existing.loc[row.outcome, metric], row[metric]
            checks.append({"outcome": row.outcome, "comparison": "saved_vs_existing_fitter",
                           "metric": metric, "reference": before, "reproduced": now,
                           "absolute_difference": abs(before-now),
                           "passed": bool(np.isclose(before, now, atol=1e-8, rtol=1e-8))})
        new = fitted_baselines.get(row.outcome)
        if new is not None:
            for metric, now in {"n": new.nobs, "r2": new.rsquared,
                                "intercept": new.params["const"],
                                "effect": new.params["valence_binary"],
                                "effect_p_value": new.pvalues["valence_binary"],
                                "aic": new.aic, "bic": new.bic}.items():
                before = row[metric]
                checks.append({"outcome": row.outcome, "comparison": "existing_vs_raw_centered_baseline",
                               "metric": metric, "reference": before, "reproduced": now,
                               "absolute_difference": abs(before-now),
                               "passed": bool(np.isclose(before, now, atol=1e-8, rtol=1e-8))})
    return pd.DataFrame(checks)


def analyze(prep, saved_baseline: pd.DataFrame, min_n: int = 30) -> InteractionAnalysis:
    if len(prep.lci_score_cols) != 10:
        raise ValueError("This exploration prespecifies exactly ten LCI-R outcomes")
    if not prep.analysis_df.index.is_unique:
        raise ValueError("Participant rows must have a unique index")
    original = prep.analysis_df.join(prep.lci_df[prep.lci_score_cols]).copy()
    categorical = ["sex_Male"] + sorted(
        c for c in prep.analysis_df if c.startswith("death_context_nature_"))
    for c in CONTINUOUS + categorical + ["valence_binary"]:
        original[c] = pd.to_numeric(original[c], errors="coerce")
    reference = run_outcome_models(
        original, prep.lci_score_cols, {c: domain_label(c) for c in prep.lci_score_cols},
        CONTINUOUS, categorical, True, min_n)
    frame = original.copy()
    # The existing preprocessing z-scores intensity; its saved pretransform
    # snapshot provides the SAME score in original points, without rescoring.
    frame[INTENSITY] = pd.to_numeric(prep.analysis_pretransform_df[INTENSITY], errors="coerce")
    if np.isinf(frame.select_dtypes(include="number").to_numpy()).any():
        raise ValueError("Infinite input values prevent equivalent baseline estimation")
    frame = _center_columns(frame, CONTINUOUS)
    predictors = ["valence_binary"] + [f"{c}_c" for c in CONTINUOUS] + categorical
    rows, unadjusted, feasibility, diagnostics, coefficients = [], [], [], [], []
    fits, samples, baselines = {}, {}, {}
    for outcome in prep.lci_score_cols:
        label = domain_label(outcome)
        required = [outcome] + predictors + [INTENSITY]
        # One complete-case selection precedes both nested fits and sensitivity.
        used = frame.loc[frame[required].notna().all(axis=1)].copy()
        row = {"outcome": label, "outcome_column": outcome, "n": len(used),
               "n_positive": int((used.valence_binary == 1).sum()),
               "n_nonpositive": int((used.valence_binary == 0).sum()),
               "n_mixed": int((used.valence == "Mixed").sum()),
               "n_negative": int((used.valence == "Negative").sum()),
               "n_missing_outcome": int(frame[outcome].isna().sum()),
               "n_missing_predictors": int(frame[predictors].isna().any(axis=1).sum()),
               "n_excluded_complete_case": len(frame)-len(used),
               "intensity_center": frame[INTENSITY].mean(),
               "status": "not_estimated", "interaction_p": np.nan,
               "interaction_hc3_p": np.nan}
        feasibility.extend(describe_sample(used, label))
        try:
            baseline, model = _fit_pair(used, outcome, predictors, min_n)
        except (ValueError, np.linalg.LinAlgError) as error:
            row["status"] = str(error)
            rows.append(row)
            unadjusted.append({**row, "status": "not_estimated_on_adjusted_sample"})
            continue
        row.update(_summary(baseline, model, used))
        influence_stats, records = influence_checks(model, outcome, used)
        row.update(influence_stats)
        diagnostics.extend(records)
        baselines[label], fits[label], samples[label] = baseline, model, used
        for kind, fitted in (("baseline", baseline), ("interaction", model)):
            for term, beta in fitted.params.items():
                low, high = fitted.conf_int().loc[term]
                coefficients.append({"outcome": label, "model": kind, "term": term,
                                     "beta": beta, "ci_low": low, "ci_high": high,
                                     "p": fitted.pvalues[term], "n": len(used)})
        u0, u1 = _fit_pair(used, outcome, ["valence_binary", CENTERED], min_n)
        unadjusted.append({**{k: row[k] for k in (
            "outcome", "n", "n_positive", "n_nonpositive", "intensity_center")},
                           **_summary(u0, u1, used)})
        rows.append(row)
    results = fdr_ten(pd.DataFrame(rows), "interaction_p", "interaction_q")
    results = fdr_ten(results, "interaction_hc3_p", "interaction_hc3_q")
    unadj = fdr_ten(pd.DataFrame(unadjusted), "interaction_p", "interaction_q")
    validation = baseline_validation(reference, saved_baseline, baselines)
    return InteractionAnalysis(results, unadj, pd.DataFrame(feasibility),
                               pd.DataFrame(diagnostics), pd.DataFrame(coefficients),
                               validation, fits, samples, frame[INTENSITY].mean())
