from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from nde_analysis.preprocess.mappings import (
    CORE_MODEL_COLS,
    EDUCATION_MAP,
    ERQ_COLS,
    ERQ_LIKERT_MAP,
    ERQ_REAPPRAISAL_ITEMS,
    ERQ_SUPPRESSION_ITEMS,
    LCI_MAP,
    LCI_SECTIONS,
    VALENCE_MAP,
)
from nde_analysis.utils.validation import require_columns


@dataclass
class PreprocessedData:
    raw_df: pd.DataFrame
    analysis_df: pd.DataFrame
    analysis_pretransform_df: pd.DataFrame
    lci_df: pd.DataFrame
    lci_score_cols: list[str]


def _zscore(series: pd.Series) -> pd.Series:
    if series.dropna().empty:
        return series
    sd = series.std(ddof=0)
    if sd == 0 or pd.isna(sd):
        return series * 0.0
    return (series - series.mean()) / sd


def preprocess_data(
    df: pd.DataFrame, lci_min_valid_fraction: float = 0.5
) -> PreprocessedData:
    data = df.copy()

    if "TO_DROP" in data.columns:
        data = data.loc[~data["TO_DROP"].fillna(False)].copy()

    lci_cols = sorted({c for cols in LCI_SECTIONS.values() for c in cols})
    needed = CORE_MODEL_COLS + ERQ_COLS + lci_cols
    require_columns(data, needed, context="preprocess")

    # Keep valid valence classes and derive binary target.
    data = data[data["valence"].isin(["Positive", "Mixed", "Negative"])].copy()
    data["valence_binary"] = data["valence"].map(VALENCE_MAP)

    # ERQ mapping and scores.
    data[ERQ_COLS] = data[ERQ_COLS].replace("Missing", np.nan)
    for col in ERQ_COLS:
        data[col] = pd.to_numeric(
            data[col].apply(lambda v: ERQ_LIKERT_MAP.get(v, v)), errors="coerce"
        )

    data["ERQ_reappraisal"] = data[ERQ_REAPPRAISAL_ITEMS].mean(axis=1)
    data["ERQ_suppression"] = data[ERQ_SUPPRESSION_ITEMS].mean(axis=1)

    # Demographic encoding.
    data["education_ord"] = data["education"].map(EDUCATION_MAP)
    data["sex_Male"] = (data["sex"].astype(str).str.lower() == "male").astype(int)

    analysis_cols = [
        "valence",
        "valence_binary",
        "age",
        "sex_Male",
        "education_ord",
        "CTQ_IM_SCORE",
        "ADHD_SCALE",
        "ERQ_reappraisal",
        "ERQ_suppression",
        "greyson_total_no_affective",
    ]

    # Numeric normalization for valence models.
    to_standardize = [
        "age",
        "ADHD_SCALE",
        "ERQ_reappraisal",
        "ERQ_suppression",
        "greyson_total_no_affective",
        "CTQ_PA_SCORE",
        "CTQ_SA_SCORE",
        "CTQ_EN_SCORE",
        "CTQ_PN_SCORE",
    ]
    for col in to_standardize:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    # Snapshot before z-score transformation for descriptive reporting.
    analysis_pretransform_df = data[analysis_cols].copy()

    for col in to_standardize:
        data[col] = _zscore(data[col])

    # LCI mapping and section scores.
    lci_df = data[["valence_binary"] + lci_cols].copy()
    for col in lci_cols:
        lci_df[col] = pd.to_numeric(
            lci_df[col].apply(lambda v: LCI_MAP.get(v, v)), errors="coerce"
        )

    lci_score_cols: list[str] = []
    for section_name, cols in LCI_SECTIONS.items():
        score_col = f"LCI_{section_name}"
        lci_score_cols.append(score_col)
        lci_df[score_col] = lci_df[cols].mean(axis=1)

        min_valid = int(np.ceil(len(cols) * lci_min_valid_fraction))
        valid_count = lci_df[cols].notna().sum(axis=1)
        lci_df.loc[valid_count < min_valid, score_col] = np.nan

    # Master analysis frame used by valence and adjusted effects.
    analysis_df = data[analysis_cols].copy()

    return PreprocessedData(
        raw_df=data,
        analysis_df=analysis_df,
        analysis_pretransform_df=analysis_pretransform_df,
        lci_df=lci_df,
        lci_score_cols=lci_score_cols,
    )
