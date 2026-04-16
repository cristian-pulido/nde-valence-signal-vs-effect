import pandas as pd

from nde_analysis.analysis.valence_models import run_valence_models
from nde_analysis.preprocess.transform import preprocess_data


def test_valence_models_run():
    df = pd.read_csv("../../DATA/data_for_model.csv")
    prep = preprocess_data(df)
    out = run_valence_models(prep.analysis_df)
    assert not out.table_m1.empty
    assert not out.table_m2.empty
    assert not out.table_m3.empty
