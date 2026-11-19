"""Independent, provisional first-NDE latency exploration.

No main-pipeline call sites are changed. The supplied age-field definitions and
their link to the evaluated NDE cannot be verified from available local data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, skew, spearmanr
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

from nde_analysis.analysis.adjusted_effects import _center_columns, run_outcome_models
from nde_analysis.analysis.multiple_testing import add_fdr_columns
from nde_analysis.preprocess.mappings import normalize_display_label

INTENSITY = "greyson_total_no_affective_c"
FIRST = "age_first_NDE_c"
SURVEY = "age_at_survey_c"
LATENCY = "latency_first_NDE_proxy"
LATENCY_C = f"{LATENCY}_c"
# Match the original adjusted specification in cli.py, without an interaction.
CONTINUOUS = ["age_first_NDE", "CTQ_IM_SCORE", "education_ord",
              "greyson_total_no_affective", "dx_prior_NDE_Yes"]


def label(outcome: str) -> str:
    return normalize_display_label(outcome).removeprefix("LCI_")


@dataclass
class AgeAudit:
    merged: pd.DataFrame | None
    diagnostics: pd.DataFrame
    ages: pd.DataFrame
    issues: list[str] = field(default_factory=list)


@dataclass
class LatencyAnalysis:
    results: pd.DataFrame
    coefficients: pd.DataFrame
    baseline_validation: pd.DataFrame
    parameterization: pd.DataFrame
    vif: pd.DataFrame
    descriptions: pd.DataFrame
    correlations: pd.DataFrame
    fits: dict
    eligible: pd.DataFrame


def describe(series: pd.Series) -> dict:
    s = series.dropna()
    q1, q3 = s.quantile(.25), s.quantile(.75)
    lower, upper = q1-1.5*(q3-q1), q3+1.5*(q3-q1)
    return {"n": len(s), "mean": s.mean(), "sd": s.std(), "median": s.median(),
            "q25": q1, "q75": q3, "min": s.min(), "max": s.max(),
            "skewness": skew(s, bias=False) if len(s) >= 3 and s.nunique() > 1 else np.nan,
            "iqr_fence_low": lower, "iqr_fence_high": upper,
            "n_outside_iqr_fences": int(((s<lower)|(s>upper)).sum()),
            "n_zero": int((s==0).sum())}


def audit_ages(cohort: pd.DataFrame, ages: pd.DataFrame) -> AgeAudit:
    """Validate BEFORE subtraction/modeling; no silent record loss or imputation.

    Ages >100 are review flags, not exclusions. Negative ages, ages >120 and
    negative differences halt modeling pending verification. These are explicit
    operational screens, not claims of validated questionnaire eligibility.
    """
    required = [(cohort, ["response_id", "age_first_NDE"]),
                (ages, ["response_id", "age"])]
    for data, columns in required:
        if missing := set(columns)-set(data.columns):
            raise ValueError(f"Missing age-validation columns: {sorted(missing)}")
    if not cohort.index.is_unique:
        raise ValueError("Modeling cohort must have a unique row index")
    issues, checks, summaries = [], [], []
    copies = [cohort.copy(), ages.copy()]
    for source, data, column in zip(("modeling_cohort", "age_file"), copies,
                                    ("age_first_NDE", "age")):
        data["response_id"] = data.response_id.astype("string")
        missing_id = data.response_id.isna() | data.response_id.str.strip().eq("").fillna(False)
        duplicates = data.response_id.duplicated(keep=False) & ~missing_id
        checks.extend([{"check": f"{source}_rows", "count": len(data)},
                       {"check": f"{source}_missing_ids", "count": int(missing_id.sum())},
                       {"check": f"{source}_duplicate_id_rows", "count": int(duplicates.sum())}])
        if missing_id.any() or duplicates.any():
            issues.append(f"{source}: missing or duplicate identifiers prevent a one-to-one join")
        original = data[column]
        numeric = pd.to_numeric(original, errors="coerce")
        nonfinite = numeric.notna() & ~np.isfinite(numeric)
        nonnumeric = original.notna() & numeric.isna()
        finite = numeric.where(np.isfinite(numeric))
        summaries.append({"source": source, "variable": column, **describe(finite),
                          "n_missing_input": int(original.isna().sum()),
                          "n_nonnumeric": int(nonnumeric.sum()), "n_nonfinite": int(nonfinite.sum()),
                          "n_negative": int((finite<0).sum()), "n_over_100_review": int((finite>100).sum()),
                          "n_over_120_requires_verification": int((finite>120).sum()),
                          "n_fractional": int((finite.dropna()%1!=0).sum()),
                          "n_current_under_18_review": int((finite<18).sum()) if column == "age" else 0})
        data[column] = finite
        if nonnumeric.any() or nonfinite.any() or (finite<0).any() or (finite>120).any():
            issues.append(f"{source}: nonnumeric, nonfinite, negative or >120 ages require verification")
    if any("identifiers" in problem for problem in issues):
        return AgeAudit(None, pd.DataFrame(checks), pd.DataFrame(summaries), issues)
    original, age_data = copies
    original["_original_index"] = original.index
    joined = original.merge(age_data[["response_id", "age"]], on="response_id", how="left",
                            validate="one_to_one", indicator=True, sort=False).set_index("_original_index")
    joined.index.name = cohort.index.name
    if not joined.index.equals(cohort.index):
        raise AssertionError("Left join changed modeling-cohort order")
    joined[LATENCY] = joined.age-joined.age_first_NDE
    negative = joined[LATENCY] < 0
    checks.extend([
        {"check": "matched_modeling_participants", "count": int((joined._merge=="both").sum())},
        {"check": "unmatched_modeling_participants", "count": int((joined._merge=="left_only").sum())},
        {"check": "age_file_only_participants", "count": int((~age_data.response_id.isin(original.response_id)).sum())},
        {"check": "first_age_exceeds_current_age", "count": int(negative.sum())},
        {"check": "negative_latency", "count": int(negative.sum())},
        {"check": "zero_latency", "count": int((joined[LATENCY]==0).sum())},
        {"check": "missing_latency", "count": int(joined[LATENCY].isna().sum())},
        {"check": "available_latency", "count": int(joined[LATENCY].notna().sum())},
    ])
    if negative.any():
        issues.append("Age at first NDE exceeds supplied current age; negative latency requires verification")
    return AgeAudit(joined, pd.DataFrame(checks), pd.DataFrame(summaries), issues)


def _fdr(table: pd.DataFrame, p_col: str, q_col: str) -> pd.DataFrame:
    work = table.copy()
    work["_family_p"] = work[p_col].fillna(1)
    work = add_fdr_columns(work, "_family_p", q_col, "_reject")
    work.loc[work[p_col].isna(), q_col] = np.nan
    return work.drop(columns=["_family_p", "_reject"])


def fit_ols(data: pd.DataFrame, outcome: str, terms: list[str], min_n: int):
    if all(term in terms for term in (FIRST, SURVEY, LATENCY_C)):
        raise ValueError("Never include current age, first-NDE age and their difference together")
    x = sm.add_constant(data[terms], has_constant="add")
    if len(data) < min_n or len(data) <= x.shape[1]+1:
        raise ValueError("Insufficient sample size or residual degrees of freedom")
    if np.linalg.matrix_rank(x) != x.shape[1]:
        raise ValueError("Rank-deficient model design; estimation withheld")
    return sm.OLS(data[outcome], x, missing="raise").fit()


def _term(model, term: str, prefix: str) -> dict:
    low, high = model.conf_int().loc[term]
    return {f"{prefix}_beta": model.params[term], f"{prefix}_ci_low": low,
            f"{prefix}_ci_high": high, f"{prefix}_p": model.pvalues[term]}


def _influence_summary(model) -> dict:
    """Aggregate only: no IDs, ages, row indices or per-person diagnostics exported."""
    inf = model.get_influence()
    n, k = model.model.exog.shape
    j = model.model.exog_names.index(LATENCY_C)
    cooks, leverage, db = inf.cooks_distance[0], inf.hat_matrix_diag, inf.dfbetas[:, j]
    betas, pvalues, rank_failures = [], [], 0
    intensity_changes, valence_changes = [], []
    i_idx = model.model.exog_names.index(INTENSITY)
    v_idx = model.model.exog_names.index("valence_binary")
    for i in range(n):
        keep = np.arange(n) != i
        x = model.model.exog[keep]
        if np.linalg.matrix_rank(x) != k:
            rank_failures += 1
            continue
        deleted = sm.OLS(model.model.endog[keep], x).fit()
        betas.append(deleted.params[j])
        pvalues.append(deleted.pvalues[j])
        intensity_changes.append(abs(deleted.params[i_idx]-model.params[INTENSITY]))
        valence_changes.append(abs(deleted.params[v_idx]-model.params["valence_binary"]))
    return {"max_cooks_distance": float(np.max(cooks)), "n_cooks_gt_4_over_n": int((cooks>4/n).sum()),
            "max_leverage": float(np.max(leverage)), "n_leverage_gt_2k_over_n": int((leverage>2*k/n).sum()),
            "max_abs_latency_dfbetas": float(np.max(abs(db))),
            "n_latency_dfbetas_gt_2_over_sqrt_n": int((abs(db)>2/np.sqrt(n)).sum()),
            "loo_latency_beta_min": min(betas, default=np.nan),
            "loo_latency_beta_max": max(betas, default=np.nan),
            "loo_latency_p_min": min(pvalues, default=np.nan), "loo_latency_p_max": max(pvalues, default=np.nan),
            "loo_latency_sign_changes": int((np.sign(betas)!=np.sign(model.params[LATENCY_C])).sum()),
            "loo_rank_failures": rank_failures,
            "loo_max_abs_intensity_beta_change": max(intensity_changes, default=np.nan),
            "loo_max_abs_valence_beta_change": max(valence_changes, default=np.nan)}


def _validate_baseline(original_frame, prep, categorical, saved):
    reference = run_outcome_models(original_frame, prep.lci_score_cols,
                                  {c: label(c) for c in prep.lci_score_cols},
                                  CONTINUOUS, categorical, True, 1)
    if set(reference.outcome) != set(saved.outcome):
        raise ValueError("Saved and reproduced baseline domains differ")
    checks = []
    saved = saved.set_index("outcome")
    for _, row in reference.iterrows():
        for metric in reference.select_dtypes(include="number").columns:
            before, now = saved.loc[row.outcome, metric], row[metric]
            checks.append({"outcome": row.outcome, "comparison": "saved_vs_original_fitter",
                           "metric": metric, "reference": before, "reproduced": now,
                           "absolute_difference": abs(before-now),
                           "passed": bool(np.isclose(before, now, atol=1e-8, rtol=1e-8))})
    return checks


def analyze_latency(prep, audit: AgeAudit, saved_baseline: pd.DataFrame, min_n: int = 30) -> LatencyAnalysis:
    if audit.issues or audit.merged is None:
        raise ValueError("Age audit must pass before any model is fit")
    if len(prep.lci_score_cols) != 10:
        raise ValueError("The intended FDR family contains ten LCI-R domains")
    merged = audit.merged.loc[prep.analysis_df.index]
    original = prep.analysis_df.join(prep.lci_df[prep.lci_score_cols])
    categorical = ["sex_Male"] + sorted(c for c in original if c.startswith("death_context_nature_"))
    for c in CONTINUOUS+categorical+["valence_binary"]:
        original[c] = pd.to_numeric(original[c], errors="coerce")
    checks = _validate_baseline(original, prep, categorical, saved_baseline)
    frame = original.copy()
    frame[LATENCY] = merged[LATENCY]
    frame["age_at_survey"] = merged.age
    frame["age_first_NDE_raw"] = merged.age_first_NDE
    frame["intensity_raw"] = prep.analysis_pretransform_df.greyson_total_no_affective
    if np.isinf(frame.select_dtypes(include="number").to_numpy()).any():
        raise ValueError("Infinite predictor or outcome values prevent reliable estimation")
    frame = _center_columns(frame, CONTINUOUS+[LATENCY, "age_at_survey"])
    base_terms = ["valence_binary"]+[f"{c}_c" for c in CONTINUOUS]+categorical
    terms = base_terms+[LATENCY_C]
    m2_terms = [c for c in terms if c != FIRST]+[SURVEY]
    rows, coefs, param_checks, vifs, fits = [], [], [], [], {}
    for outcome in prep.lci_score_cols:
        # One intersection is selected before both nested models and M2.
        required = [outcome]+terms+[SURVEY]
        used = frame.loc[frame[required].notna().all(axis=1)].copy()
        row = {"outcome": label(outcome), "n": len(used),
               "n_positive": int((used.valence_binary==1).sum()),
               "n_nonpositive": int((used.valence_binary==0).sum()),
               "n_missing_outcome": int(frame[outcome].isna().sum()),
               "n_missing_covariates": int(frame[base_terms].isna().any(axis=1).sum()),
               "n_missing_latency": int(frame[LATENCY_C].isna().sum()),
               "n_excluded_complete_case": len(frame)-len(used),
               "status": "not_estimated", "latency_p": np.nan, "latency_hc3_p": np.nan}
        # Schema remains explicit even if a domain cannot be fit.
        for model_name in ("m0", "m1"):
            for predictor in ("intensity", "valence"):
                row[f"{model_name}_{predictor}_p"] = np.nan
        try:
            m0 = fit_ols(used, outcome, base_terms, min_n)
            m1 = fit_ols(used, outcome, terms, min_n)
            m2 = fit_ols(used, outcome, m2_terms, min_n)
        except (ValueError, np.linalg.LinAlgError) as error:
            row["status"] = str(error)
            rows.append(row)
            continue
        row.update({"status": "ok", **_term(m1, LATENCY_C, "latency")})
        for name, model in (("m0", m0), ("m1", m1)):
            row.update(_term(model, INTENSITY, f"{name}_intensity"))
            row.update(_term(model, "valence_binary", f"{name}_valence"))
            for term in model.params.index:
                low, high = model.conf_int().loc[term]
                coefs.append({"outcome": label(outcome), "model": name.upper(), "term": term,
                              "beta": model.params[term], "ci_low": low, "ci_high": high,
                              "p": model.pvalues[term], "n": len(used)})
        robust = m1.get_robustcov_results(cov_type="HC3", use_t=True)
        j = m1.model.exog_names.index(LATENCY_C)
        f_stat, f_p, df_diff = m1.compare_f_test(m0)
        assert np.isclose(f_p, m1.pvalues[LATENCY_C], atol=1e-10, rtol=1e-8)
        assert np.array_equal(m0.model.data.row_labels, m1.model.data.row_labels)
        assert m1.rsquared >= m0.rsquared-1e-12
        row.update({"m0_r2": m0.rsquared, "m1_r2": m1.rsquared,
                    "delta_r2": m1.rsquared-m0.rsquared, "nested_f": f_stat,
                    "nested_f_p": f_p, "nested_df_difference": df_diff,
                    "identical_model_samples": True,
                    "latency_hc3_ci_low": robust.conf_int()[j, 0],
                    "latency_hc3_ci_high": robust.conf_int()[j, 1],
                    "latency_hc3_p": robust.pvalues[j],
                    "design_rank": np.linalg.matrix_rank(m1.model.exog),
                    "design_columns": len(m1.params), "residual_df": m1.df_resid,
                    "condition_number": m1.condition_number,
                    "latency_center": frame[LATENCY].mean(),
                    "survey_age_center": frame.age_at_survey.mean()})
        for suffix in ("beta", "ci_low", "ci_high"):
            row[f"latency_per_decade_{suffix}"] = 10*row[f"latency_{suffix}"]
        for predictor in ("intensity", "valence"):
            row[f"{predictor}_beta_change"] = row[f"m1_{predictor}_beta"]-row[f"m0_{predictor}_beta"]
            row[f"{predictor}_sign_changed"] = np.sign(row[f"m1_{predictor}_beta"]) != np.sign(row[f"m0_{predictor}_beta"])
        row.update(_influence_summary(m1))
        # M2 has an identical column space, not an independent sensitivity test.
        fit_difference = float(np.max(abs(m1.fittedvalues-m2.fittedvalues)))
        first_sd = float(prep.analysis_pretransform_df.age_first_NDE.std(ddof=0))
        check = {"outcome": label(outcome), "n": len(used),
                 "max_abs_fitted_difference": fit_difference,
                 "abs_r2_difference": abs(m1.rsquared-m2.rsquared),
                 "abs_aic_difference": abs(m1.aic-m2.aic),
                 "abs_bic_difference": abs(m1.bic-m2.bic),
                 "m2_survey_age_beta": m2.params[SURVEY],
                 "expected_m2_survey_age_beta": m1.params[FIRST]/first_sd,
                 "m2_latency_beta": m2.params[LATENCY_C],
                 "expected_m2_latency_beta": m1.params[LATENCY_C]-m1.params[FIRST]/first_sd}
        check["passed"] = bool(fit_difference<1e-9 and np.isclose(m1.rsquared, m2.rsquared, atol=1e-10)
                                and np.isclose(m1.aic, m2.aic, atol=1e-9, rtol=1e-9)
                                and np.isclose(m1.bic, m2.bic, atol=1e-9, rtol=1e-9)
                                and np.isclose(check["m2_survey_age_beta"], check["expected_m2_survey_age_beta"], atol=1e-10)
                                and np.isclose(check["m2_latency_beta"], check["expected_m2_latency_beta"], atol=1e-10))
        param_checks.append(check)
        # Independently reproduce the matched M0 with the original fitter.
        ref = run_outcome_models(original.loc[used.index], [outcome], {outcome: label(outcome)},
                                 CONTINUOUS, categorical, True, min_n).iloc[0]
        for metric, now in {"n": m0.nobs, "r2": m0.rsquared, "effect": m0.params["valence_binary"],
                            "effect_p_value": m0.pvalues["valence_binary"], "aic": m0.aic,
                            "bic": m0.bic}.items():
            before = ref[metric]
            checks.append({"outcome": label(outcome), "comparison": "matched_m0_vs_original_fitter",
                           "metric": metric, "reference": before, "reproduced": now,
                           "absolute_difference": abs(before-now),
                           "passed": bool(np.isclose(before, now, atol=1e-8, rtol=1e-8))})
        for model_name, model in (("M0", m0), ("M1", m1), ("M2", m2)):
            for i, term in enumerate(model.model.exog_names):
                if term != "const":
                    vifs.append({"outcome": label(outcome), "model": model_name, "term": term,
                                 "vif": variance_inflation_factor(model.model.exog, i)})
        fits[label(outcome)] = {"M0": m0, "M1": m1, "M2": m2}
        rows.append(row)
    table = pd.DataFrame(rows)
    for p, q in [("latency_p", "latency_q"), ("latency_hc3_p", "latency_hc3_q")]+[
        (f"{m}_{pred}_p", f"{m}_{pred}_q") for m in ("m0", "m1") for pred in ("intensity", "valence")]:
        table = _fdr(table, p, q)
    descriptions = [{"group": "All eligible", **describe(frame[LATENCY])}]
    for val, group in frame.groupby("valence_binary"):
        descriptions.append({"group": "Positive" if val else "Non-positive", **describe(group[LATENCY])})
    for val, group in frame.groupby("valence"):
        descriptions.append({"group": f"Original valence: {val}", **describe(group[LATENCY])})
    correlations = []
    for a, b in combinations(["age_at_survey", "age_first_NDE_raw", LATENCY, "intensity_raw"], 2):
        use = frame[[a, b]].dropna()
        correlations.append({"variable_1": a, "variable_2": b, "n": len(use),
                             "pearson_r": pearsonr(use[a], use[b]).statistic,
                             "spearman_rho": spearmanr(use[a], use[b]).statistic})
    return LatencyAnalysis(table, pd.DataFrame(coefs), pd.DataFrame(checks), pd.DataFrame(param_checks),
                           pd.DataFrame(vifs), pd.DataFrame(descriptions), pd.DataFrame(correlations), fits, frame)
