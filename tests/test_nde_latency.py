"""Focused age-quality, model-equivalence and isolation checks."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests

from nde_analysis.analysis.nde_latency import (
    FIRST, LATENCY, LATENCY_C, SURVEY, _fdr, analyze_latency, audit_ages, fit_ols,
)
from nde_analysis.preprocess.transform import preprocess_data

ROOT = Path(__file__).resolve().parents[1]


def test_age_join_preserves_cohort_and_unmatched_records():
    cohort = pd.DataFrame({"response_id": ["001", "002", "003"], "age_first_NDE": [20, 30, 40]})
    age = pd.DataFrame({"response_id": ["002", "001", "999"], "age": [60, 45, 80]})
    check = audit_ages(cohort, age)
    assert not check.issues
    assert check.merged.response_id.tolist() == ["001", "002", "003"]
    assert check.merged[LATENCY].iloc[:2].tolist() == [25, 30]
    assert pd.isna(check.merged[LATENCY].iloc[2])
    counts = check.diagnostics.set_index("check")["count"]
    assert counts.unmatched_modeling_participants == counts.age_file_only_participants == 1
    # Validation never changes the supplied input frames.
    assert "_original_index" not in cohort and LATENCY not in cohort


@pytest.mark.parametrize("field,bad", [("age", -1), ("age", 150), ("age", np.inf),
                                       ("age_first_NDE", -1), ("age", "unknown")])
def test_implausible_or_invalid_age_stops_modeling(field, bad):
    cohort = pd.DataFrame({"response_id": ["a"], "age_first_NDE": [20]})
    ages = pd.DataFrame({"response_id": ["a"], "age": [60]})
    data = cohort if field == "age_first_NDE" else ages
    data[field] = data[field].astype(object)
    data.loc[0, field] = bad
    check = audit_ages(cohort, ages)
    assert check.issues
    with pytest.raises(ValueError, match="Age audit must pass"):
        analyze_latency(None, check, None)


def test_negative_difference_is_rejected_but_zero_and_fractional_ages_are_retained():
    cohort = pd.DataFrame({"response_id": ["a", "b"], "age_first_NDE": [60., 20.5]})
    age = pd.DataFrame({"response_id": ["a", "b"], "age": [59., 20.5]})
    check = audit_ages(cohort, age)
    assert check.issues
    assert check.diagnostics.set_index("check").loc["negative_latency", "count"] == 1
    age.loc[0, "age"] = 60
    check = audit_ages(cohort, age)
    assert not check.issues
    assert check.merged[LATENCY].tolist() == [0, 0]


@pytest.mark.parametrize("ids", [["a", "a"], ["a", None], ["a", " "]])
def test_missing_or_duplicate_identifiers_prevent_a_merge(ids):
    cohort = pd.DataFrame({"response_id": ["a", "b"], "age_first_NDE": [20, 30]})
    ages = pd.DataFrame({"response_id": ids, "age": [40, 50]})
    check = audit_ages(cohort, ages)
    assert check.issues and check.merged is None


@pytest.fixture(scope="module")
def real_result():
    cohort = pd.read_csv(ROOT/"../../DATA/data_for_model.csv", dtype={"response_id": "string"})
    ages = pd.read_csv(ROOT/"../../DATA/data_age.csv", dtype={"response_id": "string"})
    audit = audit_ages(cohort, ages)
    prep = preprocess_data(cohort)
    saved = pd.read_csv(ROOT/"outputs/latest/main/tables/lci_adjusted_full_models.csv")
    return prep, audit, saved, analyze_latency(prep, audit, saved)


def test_actual_baselines_samples_fdr_and_parameterization(real_result):
    _, audit, _, result = real_result
    assert not audit.issues
    np.testing.assert_allclose(audit.merged.age,
                               audit.merged.age_first_NDE+audit.merged[LATENCY], atol=1e-12)
    assert len(result.results) == 10
    assert (result.results.status=="ok").all()
    assert result.baseline_validation.passed.all()
    assert result.parameterization.passed.all()
    assert result.results.identical_model_samples.all()
    assert (result.results.delta_r2>=-1e-12).all()
    np.testing.assert_allclose(result.results.latency_q,
                               multipletests(result.results.latency_p, method="fdr_bh")[1])
    for name in ("results", "coefficients", "baseline_validation", "parameterization", "vif",
                 "descriptions", "correlations"):
        assert not {"response_id", "input_data_row", "participant_id"} & set(getattr(result, name).columns)


def test_independent_formula_matches_latency_and_original_predictors(real_result):
    _, _, _, result = real_result
    data = result.eligible
    context = [c for c in data if c.startswith("death_context_nature_")]
    for _, row in result.results.iterrows():
        outcome = next(k for k in data if k.startswith("LCI_") and
                       k.removeprefix("LCI_").replace("Material Achievements", "Worldly Achievement") == row.outcome)
        model = smf.ols(f"Q('{outcome}') ~ {LATENCY} + age_first_NDE_raw + greyson_total_no_affective + "
                        "valence_binary + CTQ_IM_SCORE + education_ord + dx_prior_NDE_Yes + sex_Male + "+
                        " + ".join(context), data=data).fit()
        np.testing.assert_allclose(row.latency_beta, model.params[LATENCY], atol=1e-11)
        np.testing.assert_allclose([row.latency_ci_low, row.latency_ci_high],
                                   model.conf_int().loc[LATENCY], atol=1e-10)
        np.testing.assert_allclose(row.latency_p, model.pvalues[LATENCY], atol=1e-10)
        np.testing.assert_allclose(row.m1_intensity_beta, model.params["greyson_total_no_affective"], atol=1e-10)
        np.testing.assert_allclose(row.m1_valence_beta, model.params["valence_binary"], atol=1e-10)


def test_missing_age_uses_the_same_smaller_complete_case_samples(real_result):
    prep, audit, saved, _ = real_result
    changed = audit.merged.copy()
    changed.loc[changed.index[0], ["age", LATENCY]] = np.nan
    altered_audit = type(audit)(changed, audit.diagnostics, audit.ages, [])
    result = analyze_latency(prep, altered_audit, saved)
    assert (result.results.n==121).all()
    assert result.results.identical_model_samples.all()
    assert result.baseline_validation.passed.all()
    assert result.parameterization.passed.all()


def test_three_dependent_temporal_variables_are_explicitly_rejected():
    data = pd.DataFrame({FIRST: np.arange(40), SURVEY: np.arange(40)+20,
                         LATENCY_C: np.ones(40)*20, "outcome": np.arange(40)})
    with pytest.raises(ValueError, match="Never include"):
        fit_ols(data, "outcome", [FIRST, SURVEY, LATENCY_C], 30)


def test_nonestimable_domain_does_not_shrink_the_ten_test_family():
    corrected = _fdr(pd.DataFrame({"p": [.005]+[.2]*8+[np.nan]}), "p", "q")
    assert np.isclose(corrected.q.iloc[0], .05)
    assert pd.isna(corrected.q.iloc[-1])


def test_output_guard_protects_main_and_parent_directories():
    spec = importlib.util.spec_from_file_location("latency_runner", ROOT/"scripts/run_nde_latency.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    for path in (ROOT/"outputs/latest/main", ROOT/"outputs/latest/main/new", ROOT/"outputs/exploratory", ROOT):
        with pytest.raises(ValueError, match="dedicated output directory"):
            runner.safe_output(path)
    assert runner.safe_output(ROOT/"outputs/exploratory/nde_latency") == ROOT/"outputs/exploratory/nde_latency"
