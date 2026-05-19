import pandas as pd
import pytest

from nde_analysis.preprocess.transform import (
    preprocess_collinearity_data,
    preprocess_data,
)


def test_preprocess_creates_core_fields():
    df = pd.read_csv("../../DATA/data_for_model.csv")
    required = {
        "ADHD_SCALE",
        "age",
        "ERQ_01",
        "ERQ_02",
        "ERQ_03",
        "ERQ_04",
        "ERQ_05",
        "ERQ_06",
        "ERQ_07",
        "ERQ_08",
        "ERQ_09",
        "ERQ_10",
    }
    if not required.issubset(df.columns):
        pytest.skip("Dataset does not contain full valence/post-effects input columns")
    out = preprocess_data(df)
    assert "valence_binary" in out.analysis_df.columns
    assert "ERQ_reappraisal" in out.analysis_df.columns
    assert "ERQ_suppression" in out.analysis_df.columns
    assert len(out.lci_score_cols) > 0


def test_preprocess_collinearity_creates_expected_fields():
    df = pd.read_csv("../../DATA/data_for_model.csv")
    out = preprocess_collinearity_data(df)
    for col in [
        "valence_binary",
        "education_ord",
        "sex_Male",
        "age_first_NDE",
        "dx_prior_NDE",
        "dx_prior_NDE_specify",
    ]:
        assert col in out.columns
