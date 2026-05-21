from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from nde_analysis.preprocess.mappings import (
    CORE_MODEL_COLS,
    EDUCATION_MAP,
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


def preprocess_collinearity_data(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    needed = [
        "valence",
        "CTQ_IM_SCORE",
        "CTQ_PA_SCORE",
        "CTQ_SA_SCORE",
        "CTQ_EN_SCORE",
        "CTQ_PN_SCORE",
        "greyson_total_no_affective",
        "age_first_NDE",
        "sex",
        "education",
        "dx_prior_NDE",
        "dx_prior_NDE_specify",
        "death_context_nature",
    ]
    require_columns(data, needed, context="preprocess_collinearity")

    data = data[data["valence"].isin(["Positive", "Mixed", "Negative"])].copy()
    data["valence_binary"] = data["valence"].map(VALENCE_MAP)

    data["education_ord"] = data["education"].map(EDUCATION_MAP)
    data["sex_Male"] = (data["sex"].astype(str).str.lower() == "male").astype(int)

    for col in [
        "CTQ_IM_SCORE",
        "CTQ_PA_SCORE",
        "CTQ_SA_SCORE",
        "CTQ_EN_SCORE",
        "CTQ_PN_SCORE",
        "greyson_total_no_affective",
        "age_first_NDE",
        "education_ord",
        "valence_binary",
    ]:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    data["dx_prior_NDE"] = data["dx_prior_NDE"].astype(str)
    data["dx_prior_NDE_specify"] = data["dx_prior_NDE_specify"].astype(str)
    data["death_context_nature"] = data["death_context_nature"].astype(str)
    return data


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
    needed = CORE_MODEL_COLS + lci_cols
    require_columns(data, needed, context="preprocess")

    # Keep valid valence classes and derive binary target.
    data = data[data["valence"].isin(["Positive", "Mixed", "Negative"])].copy()
    data["valence_binary"] = data["valence"].map(VALENCE_MAP)

    # Demographic encoding.
    data["education_ord"] = data["education"].map(EDUCATION_MAP)
    data["sex_Male"] = (data["sex"].astype(str).str.lower() == "male").astype(int)
    data["dx_prior_NDE_Yes"] = (
        data["dx_prior_NDE"].astype(str).str.lower() == "yes"
    ).astype(int)
    death_ctx = pd.get_dummies(
        data["death_context_nature"],
        prefix="death_context_nature",
        drop_first=True,
        dtype=float,
    )
    data = pd.concat([data, death_ctx], axis=1)
    death_context_cols = sorted(
        c for c in data.columns if c.startswith("death_context_nature_")
    )

    analysis_cols = [
        "valence",
        "valence_binary",
        "age_first_NDE",
        "sex_Male",
        "education_ord",
        "CTQ_IM_SCORE",
        "dx_prior_NDE_Yes",
        "greyson_total_no_affective",
    ] + death_context_cols

    # Numeric normalization for valence models.
    to_standardize = [
        "age_first_NDE",
        "greyson_total_no_affective",
        "CTQ_PA_SCORE",
        "CTQ_SA_SCORE",
        "CTQ_EN_SCORE",
        "CTQ_PN_SCORE",
    ]
    for col in to_standardize:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")

    # Snapshot before z-score transformation for descriptive reporting.
    analysis_pretransform_df = data[analysis_cols].copy()

    for col in to_standardize:
        if col in data.columns:
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
