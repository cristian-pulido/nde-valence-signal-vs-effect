from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import statsmodels.api as sm
from scipy.stats import chi2

from nde_analysis.analysis.statistics import odds_ratio_table


@dataclass
class ValenceModelResults:
    model1: any
    model2: any
    model3: any
    table_m1: pd.DataFrame
    table_m2: pd.DataFrame
    table_m3: pd.DataFrame
    fit_table: pd.DataFrame
    sample_table: pd.DataFrame
    model3_predictions: pd.DataFrame


def _fit_logit(df: pd.DataFrame, outcome: str, predictors: list[str]):
    use = df[[outcome] + predictors].dropna().copy()
    X = sm.add_constant(use[predictors])
    y = use[outcome]
    model = sm.Logit(y, X).fit(disp=False)
    return model, use


def run_valence_models(analysis_df: pd.DataFrame) -> ValenceModelResults:
    model1_vars = ["age", "education_ord", "sex_Male"]
    model2_vars = model1_vars + [
        "CTQ_IM_SCORE",
        "ADHD_SCALE",
        "ERQ_reappraisal",
        "ERQ_suppression",
    ]
    model3_vars = model2_vars + ["greyson_total_no_affective"]

    m1, d1 = _fit_logit(analysis_df, "valence_binary", model1_vars)
    m2, d2 = _fit_logit(analysis_df, "valence_binary", model2_vars)
    m3, d3 = _fit_logit(analysis_df, "valence_binary", model3_vars)

    label_map = {
        "age": "Age",
        "education_ord": "Education",
        "sex_Male": "Sex (Male vs non-male)",
        "CTQ_IM_SCORE": "CTQ Emotional Abuse",
        "ADHD_SCALE": "ADHD",
        "ERQ_reappraisal": "ERQ Reappraisal",
        "ERQ_suppression": "ERQ Suppression",
        "greyson_total_no_affective": "Greyson (non-affective)",
    }

    t1 = odds_ratio_table(m1, label_map)
    t2 = odds_ratio_table(m2, label_map)
    t3 = odds_ratio_table(m3, label_map)

    lr_21 = 2 * (m2.llf - m1.llf)
    lr_32 = 2 * (m3.llf - m2.llf)
    fit_table = pd.DataFrame(
        [
            {
                "comparison": "Model 2 vs Model 1",
                "lr_stat": lr_21,
                "df_diff": m2.df_model - m1.df_model,
                "p_value": chi2.sf(lr_21, m2.df_model - m1.df_model),
            },
            {
                "comparison": "Model 3 vs Model 2",
                "lr_stat": lr_32,
                "df_diff": m3.df_model - m2.df_model,
                "p_value": chi2.sf(lr_32, m3.df_model - m2.df_model),
            },
        ]
    )

    sample_table = pd.DataFrame(
        [
            {"model": "Model 1", "n": len(d1), "pseudo_r2": m1.prsquared},
            {"model": "Model 2", "n": len(d2), "pseudo_r2": m2.prsquared},
            {"model": "Model 3", "n": len(d3), "pseudo_r2": m3.prsquared},
        ]
    )

    d3_pred = d3.copy()
    d3_pred["pred_prob"] = m3.predict(sm.add_constant(d3[model3_vars]))

    return ValenceModelResults(
        model1=m1,
        model2=m2,
        model3=m3,
        table_m1=t1,
        table_m2=t2,
        table_m3=t3,
        fit_table=fit_table,
        sample_table=sample_table,
        model3_predictions=d3_pred,
    )
