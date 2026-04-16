import pandas as pd

from nde_analysis.preprocess.transform import preprocess_data


def test_preprocess_creates_core_fields():
    df = pd.read_csv("../../DATA/data_for_model.csv")
    out = preprocess_data(df)
    assert "valence_binary" in out.analysis_df.columns
    assert "ERQ_reappraisal" in out.analysis_df.columns
    assert "ERQ_suppression" in out.analysis_df.columns
    assert len(out.lci_score_cols) > 0
