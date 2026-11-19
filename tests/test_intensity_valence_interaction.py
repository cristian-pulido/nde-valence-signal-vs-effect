"""Focused statistical and isolation checks for the standalone exploration."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests

from nde_analysis.analysis.intensity_valence_interaction import (
    CENTERED, INTENSITY, INTERACTION, _fit_pair, analyze, fdr_ten,
)
from nde_analysis.preprocess.transform import preprocess_data

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def real_analysis():
    prep = preprocess_data(pd.read_csv(ROOT / "../../DATA/data_for_model.csv"))
    saved = pd.read_csv(ROOT / "outputs/latest/main/tables/lci_adjusted_full_models.csv")
    return prep, analyze(prep, saved)


def test_existing_baselines_and_matched_samples(real_analysis):
    _, result = real_analysis
    assert len(result.results) == 10
    assert result.baseline_validation.passed.all()
    assert result.results.identical_model_samples.all()
    assert (result.results.status == "ok").all()
    np.testing.assert_array_equal(result.results.n, result.unadjusted.n)
    assert (result.results.delta_r2 >= -1e-12).all()
    np.testing.assert_allclose(result.results.interaction_q,
                               multipletests(result.results.interaction_p, method="fdr_bh")[1])
    # All numeric inference and uncertainty must be finite for this dataset.
    cols = ["interaction_beta", "interaction_ci_low", "interaction_ci_high",
            "interaction_p", "interaction_q", "interaction_hc3_p", "delta_r2"]
    assert np.isfinite(result.results[cols]).all().all()


def test_independent_formula_confirms_raw_units_and_direction(real_analysis):
    _, result = real_analysis
    for _, row in result.results.iterrows():
        data = result.samples[row.outcome]
        # Independent Patsy interaction expansion uses the uncentered RAW score.
        context = [c for c in data if c.startswith("death_context_nature_")]
        formula = (f"Q('{row.outcome_column}') ~ {INTENSITY} * valence_binary + "
                   "age_first_NDE + CTQ_IM_SCORE + education_ord + dx_prior_NDE_Yes + "
                   "sex_Male + " + " + ".join(context))
        fit = smf.ols(formula, data=data).fit()
        term = f"{INTENSITY}:valence_binary"
        np.testing.assert_allclose(row.interaction_beta, fit.params[term], atol=1e-11)
        np.testing.assert_allclose([row.interaction_ci_low, row.interaction_ci_high],
                                   fit.conf_int().loc[term], atol=1e-10)
        np.testing.assert_allclose(row.interaction_p, fit.pvalues[term], atol=1e-10)
        np.testing.assert_allclose(row.slope_positive-row.slope_nonpositive,
                                   row.interaction_beta, atol=1e-11)


def test_synthetic_interaction_and_single_complete_case_selection():
    rng = np.random.default_rng(42)
    n = 120
    intensity = rng.normal(10, 3, n)
    group = np.tile([0, 1], n//2)
    data = pd.DataFrame({INTENSITY: intensity, CENTERED: intensity-intensity.mean(),
                         "valence_binary": group, "covariate": rng.normal(size=n)})
    data["outcome"] = 1 + .05*data[CENTERED] + .4*group - .03*data[CENTERED]*group + .2*data.covariate
    data.loc[0, "outcome"] = np.nan
    data.loc[1, "covariate"] = np.nan
    used = data.dropna()
    baseline, model = _fit_pair(used, "outcome", ["valence_binary", CENTERED, "covariate"], 30)
    assert baseline.nobs == model.nobs == n-2
    assert list(baseline.model.data.row_labels) == list(model.model.data.row_labels)
    assert np.isclose(model.params[INTERACTION], -.03, atol=1e-12)


def test_guard_against_rank_deficiency_and_no_group_support():
    data = pd.DataFrame({INTENSITY: np.arange(40), CENTERED: np.arange(40)-19.5,
                         "valence_binary": np.tile([0, 1], 20), "outcome": np.arange(40),
                         "constant_covariate": np.ones(40)})
    with pytest.raises(ValueError, match="rank deficient"):
        _fit_pair(data, "outcome", ["valence_binary", CENTERED, "constant_covariate"], 30)
    data["valence_binary"] = 1
    with pytest.raises(ValueError, match="Both valence groups"):
        _fit_pair(data, "outcome", ["valence_binary", CENTERED], 30)


def test_fdr_preserves_ten_hypotheses_when_one_is_not_estimable():
    data = pd.DataFrame({"p": [.005] + [.2]*8 + [np.nan]})
    result = fdr_ten(data, "p", "q")
    assert np.isclose(result.q.iloc[0], .05)
    assert pd.isna(result.q.iloc[-1])


def test_main_output_paths_are_rejected():
    spec = importlib.util.spec_from_file_location(
        "interaction_runner", ROOT / "scripts/run_intensity_valence_interaction.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    for path in (ROOT / "outputs/latest/main", ROOT / "outputs/latest/main/nested",
                 ROOT / "outputs/exploratory", ROOT / "README.md"):
        with pytest.raises(ValueError, match="dedicated directory"):
            runner.safe_output_dir(path)
    assert runner.safe_output_dir(ROOT / "outputs/exploratory/test") == ROOT / "outputs/exploratory/test"
