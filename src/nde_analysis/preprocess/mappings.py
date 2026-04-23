from __future__ import annotations

MISSING_LABEL = "Missing"

ERQ_COLS = [f"ERQ_{i:02d}" for i in range(1, 11)]
ERQ_REAPPRAISAL_ITEMS = ["ERQ_01", "ERQ_03", "ERQ_05", "ERQ_07", "ERQ_08", "ERQ_10"]
ERQ_SUPPRESSION_ITEMS = ["ERQ_02", "ERQ_04", "ERQ_06", "ERQ_09"]

ERQ_LIKERT_MAP = {
    "Not at all agree": 1,
    "Disagree": 2,
    "Rather disagree": 3,
    "Neutral": 4,
    "Okay.": 4,
    "Rather agree": 5,
    "Pretty much agree": 6,
    "Totally agree": 7,
}

EDUCATION_MAP = {
    "No formal education": 0,
    "Primary education": 1,
    "Secondary education": 2,
    "College or university degree": 3,
    "Graduate degree or higher": 4,
}

VALENCE_MAP = {"Positive": 1, "Mixed": 0, "Negative": 0}

LCI_MAP = {
    "Strongly diminished": -2,
    "Decreased": -1,
    "Not changed": 0,
    "Increased": 1,
    "Strongly increased": 2,
    "Missing": None,
}

LCI_SECTIONS = {
    "Appreciation of Life": [
        "LCI-R_03_since_NDE",
        "LCI-R_08_since_NDE",
        "LCI-R_17_since_NDE",
        "LCI-R_26_since_NDE",
    ],
    "Self-Acceptance": [
        "LCI-R_05_since_NDE",
        "LCI-R_28_since_NDE",
        "LCI-R_40_since_NDE",
    ],
    "Concern for Others": [
        "LCI-R_01_since_NDE",
        "LCI-R_02_since_NDE",
        "LCI-R_04_since_NDE",
        "LCI-R_10_since_NDE",
        "LCI-R_11_since_NDE",
        "LCI-R_15_since_NDE",
        "LCI-R_16_since_NDE",
        "LCI-R_25_since_NDE",
        "LCI-R_37_since_NDE",
        "LCI-R_47_since_NDE",
    ],
    "Material Achievements": [
        "LCI-R_09_since_NDE",
        "LCI-R_12_since_NDE",
        "LCI-R_18_since_NDE",
        "LCI-R_27_since_NDE",
        "LCI-R_34_since_NDE",
        "LCI-R_44_since_NDE",
        "LCI-R_46_since_NDE",
    ],
    "Social/Planetary Values": [
        "LCI-R_21_since_NDE",
        "LCI-R_33_since_NDE",
        "LCI-R_38_since_NDE",
        "LCI-R_45_since_NDE",
        "LCI-R_49_since_NDE",
    ],
    "Meaning/Purpose": [
        "LCI-R_22_since_NDE",
        "LCI-R_23_since_NDE",
        "LCI-R_30_since_NDE",
        "LCI-R_48_since_NDE",
    ],
    "Spirituality": [
        "LCI-R_13_since_NDE",
        "LCI-R_14_since_NDE",
        "LCI-R_20_since_NDE",
        "LCI-R_24_since_NDE",
        "LCI-R_41_since_NDE",
    ],
    "Religiosity": [
        "LCI-R_07_since_NDE",
        "LCI-R_19_since_NDE",
        "LCI-R_35_since_NDE",
        "LCI-R_39_since_NDE",
    ],
    "Death": ["LCI-R_32_since_NDE", "LCI-R_43_since_NDE", "LCI-R_50_since_NDE"],
    "Other": [
        "LCI-R_06_since_NDE",
        "LCI-R_29_since_NDE",
        "LCI-R_31_since_NDE",
        "LCI-R_36_since_NDE",
        "LCI-R_42_since_NDE",
    ],
}

CORE_MODEL_COLS = [
    "valence",
    "CTQ_IM_SCORE",
    "CTQ_PA_SCORE",
    "CTQ_SA_SCORE",
    "CTQ_EN_SCORE",
    "CTQ_PN_SCORE",
    "ADHD_SCALE",
    "greyson_total_no_affective",
    "age",
    "sex",
    "education",
]
