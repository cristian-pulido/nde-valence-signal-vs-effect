import numpy as np
import pandas as pd

from nde_analysis.analysis.bayesian_rank_sum import run_bayesian_rank_sum


def _toy_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "valence_binary": [1, 1, 1, 1, 0, 0, 0, 0],
            "LCI_Appreciation of Life": [1.0, 1.2, 0.8, 1.1, 0.7, 0.8, 0.6, 0.5],
            "LCI_Self-Acceptance": [0.4, np.nan, 0.2, 0.3, 0.1, -0.1, np.nan, 0.0],
        }
    )


def test_run_bayesian_rank_sum_columns_and_rows():
    df = _toy_df()
    variables = [
        "LCI_Appreciation of Life",
        "LCI_Self-Acceptance",
    ]
    out = run_bayesian_rank_sum(
        df=df,
        variables=variables,
        group_col="valence_binary",
        n_iter=900,
        burn=300,
        seed=11,
    )

    expected_cols = {
        "variable",
        "domain",
        "n_positive",
        "n_non_positive",
        "bf01",
        "bf10",
        "rank_biserial",
        "delta_posterior_median",
        "delta_ci_low",
        "delta_ci_high",
        "interpretation",
    }
    assert set(out.columns) == expected_cols
    assert out.shape[0] == len(variables)


def test_run_bayesian_rank_sum_deterministic_given_seed():
    df = _toy_df()
    variables = ["LCI_Appreciation of Life", "LCI_Self-Acceptance"]
    out_1 = run_bayesian_rank_sum(
        df=df,
        variables=variables,
        group_col="valence_binary",
        n_iter=800,
        burn=250,
        seed=123,
    )
    out_2 = run_bayesian_rank_sum(
        df=df,
        variables=variables,
        group_col="valence_binary",
        n_iter=800,
        burn=250,
        seed=123,
    )

    pd.testing.assert_frame_equal(out_1, out_2)


def test_fixed_n_complete_case_has_constant_group_sizes():
    df = _toy_df()
    group_col = "valence_binary"
    variables = [
        "LCI_Appreciation of Life",
        "LCI_Self-Acceptance",
    ]

    fixed_df = df[[group_col] + variables].dropna(axis=0)
    out = run_bayesian_rank_sum(
        df=fixed_df,
        variables=variables,
        group_col=group_col,
        n_iter=700,
        burn=250,
        seed=7,
    )

    assert out["n_positive"].nunique() == 1
    assert out["n_non_positive"].nunique() == 1
