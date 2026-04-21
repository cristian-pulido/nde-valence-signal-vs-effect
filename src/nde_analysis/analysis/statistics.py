from __future__ import annotations

import numpy as np
import pandas as pd

from nde_analysis.analysis.multiple_testing import add_fdr_columns


def odds_ratio_table(model, label_map: dict[str, str] | None = None) -> pd.DataFrame:
    params = model.params
    conf = model.conf_int()
    conf.columns = ["CI_low_log", "CI_high_log"]

    out = pd.DataFrame(
        {
            "predictor": params.index,
            "coef": params.values,
            "or": np.exp(params.values),
            "ci_low": np.exp(conf["CI_low_log"]),
            "ci_high": np.exp(conf["CI_high_log"]),
            "p_value": model.pvalues.values,
        }
    )
    out = out[out["predictor"] != "const"].copy()
    out = add_fdr_columns(out, p_col="p_value")
    if label_map:
        out["predictor"] = out["predictor"].map(label_map).fillna(out["predictor"])
    return out
