from __future__ import annotations

from pathlib import Path

import pandas as pd

from nde_analysis.analysis.bayesian_rank_sum import run_bayesian_rank_sum
from nde_analysis.io import write_table


def _table_text(df: pd.DataFrame, digits: int = 3) -> str:
    if df.empty:
        return "No rows available."
    view = df.copy()
    for col in view.select_dtypes(include=["float", "float64"]).columns:
        view[col] = view[col].round(digits)
    view = view.fillna("-")
    return "```\n" + view.to_string(index=False) + "\n```"


def _summarize_bf(df: pd.DataFrame) -> dict[str, float]:
    valid = df["bf01"].dropna()
    if valid.empty:
        return {
            "n_variables": 0,
            "pct_bf01_gt_3": float("nan"),
            "pct_bf01_gt_10": float("nan"),
            "pct_inconclusive": float("nan"),
        }

    n = valid.size
    return {
        "n_variables": int(n),
        "pct_bf01_gt_3": 100.0 * float((valid > 3).sum()) / n,
        "pct_bf01_gt_10": 100.0 * float((valid > 10).sum()) / n,
        "pct_inconclusive": 100.0
        * float(((valid >= (1 / 3)) & (valid <= 3)).sum())
        / n,
    }


def _load_frequentist_summary(tables_dir: Path) -> str:
    path = tables_dir / "lci_by_valence.csv"
    if not path.exists():
        return (
            "Frequentist comparison unavailable: Mann-Whitney result table "
            "was not found in the tables directory."
        )

    freq = pd.read_csv(path)
    if "p_value_fdr" in freq.columns:
        sig = int((freq["p_value_fdr"] < 0.05).sum())
        total = int(freq.shape[0])
        return (
            f"Frequentist Mann-Whitney tests were FDR-significant for {sig}/{total} outcomes. "
            "Non-significant p-values alone are not evidence for no effect; BF01 quantifies this directly."
        )

    sig = int((freq["p_value"] < 0.05).sum()) if "p_value" in freq.columns else 0
    total = int(freq.shape[0])
    return (
        f"Frequentist Mann-Whitney tests were nominally significant for {sig}/{total} outcomes. "
        "Bayes factors were used to evaluate evidence for H0 versus H1."
    )


def _display_variable_name(v: str) -> str:
    if v.startswith("LCI_"):
        return v.replace("LCI_", "")
    return v


def _build_report_text(
    title: str,
    result_df: pd.DataFrame,
    variable_names: list[str],
    frequentist_note: str,
    variant_desc: str,
) -> str:
    report_df = result_df.copy()
    report_df["variable"] = report_df["variable"].map(_display_variable_name)

    summary_table = report_df[
        ["variable", "n_positive", "n_non_positive", "bf01", "interpretation"]
    ].copy()

    agg = _summarize_bf(report_df)
    agg_table = pd.DataFrame(
        [
            {"metric": "% variables with BF01 > 3", "value": agg["pct_bf01_gt_3"]},
            {"metric": "% variables with BF01 > 10", "value": agg["pct_bf01_gt_10"]},
            {"metric": "% inconclusive", "value": agg["pct_inconclusive"]},
        ]
    )

    evidence_h0 = int((report_df["bf01"] > 3).sum())
    evidence_strong_h0 = int((report_df["bf01"] > 10).sum())
    total = int(report_df["bf01"].notna().sum())

    interpretation = (
        f"Across {total} outcomes, {evidence_h0} showed BF01 > 3 and {evidence_strong_h0} showed BF01 > 10. "
        "Here, H0 means no difference between Positive and Non-positive groups, and H1 means a difference exists. "
        "These patterns indicate evidence consistent with no meaningful differences for a subset of outcomes, "
        "while remaining outcomes are inconclusive where BF01 is near 1. "
        + frequentist_note
    )

    lines = [
        f"# {title}",
        "",
        "## 1. Research Question",
        "",
        "Do post-NDE outcomes differ between Positive and Non-positive NDE groups, or is there evidence supporting no meaningful difference?",
        "",
        "## 2. Methodology",
        "",
        "- Groups: Positive valence vs Non-positive valence (Mixed + Negative).",
        f"- Variables analyzed: {len(variable_names)} outcomes across LCI-R aggregated domains.",
        "- Test: Bayesian rank-sum test using latent-normal augmentation (van Doorn et al., 2020).",
        "- Prior: Cauchy prior on effect size delta with scale r = 0.707.",
        "- Hypotheses: H0 = no group difference (delta = 0); H1 = group difference (delta != 0).",
        "- Bayes factor interpretation: BF01 > 3 (moderate evidence for H0), BF01 > 10 (strong evidence for H0), BF01 near 1 (inconclusive).",
        f"- Dataset version: {variant_desc}",
        "",
        "## 3. Results",
        "",
        "### Summary table",
        "",
        _table_text(summary_table),
        "",
        "### Aggregated summary",
        "",
        _table_text(agg_table),
        "",
        "## 4. Interpretation",
        "",
        interpretation,
    ]
    return "\n".join(lines) + "\n"


def run_bayesian_reporting(
    prep,
    tables_dir: Path,
    reports_dir: Path,
    seed: int = 42,
    n_iter: int = 300,
    burn: int = 100,
    variant_desc: str = "Variable-N",
) -> dict[str, Path]:
    group_col = "valence_binary"
    variables = [*prep.lci_score_cols]

    combined_df = prep.lci_df[[group_col] + prep.lci_score_cols].copy()
    combined_df = combined_df.loc[:, ~combined_df.columns.duplicated()].copy()

    results = run_bayesian_rank_sum(
        df=combined_df,
        variables=variables,
        group_col=group_col,
        prior_scale=0.707,
        n_iter=n_iter,
        burn=burn,
        seed=seed,
    )

    table_path = tables_dir / "bayesian_rank_sum_lci.csv"
    write_table(results, table_path)

    frequentist_note = _load_frequentist_summary(tables_dir)
    report_path = reports_dir / "05_bayesian_rank_sum_lci_report.md"
    report_path.write_text(
        _build_report_text(
            title="Bayesian Rank-Sum Report (LCI)",
            result_df=results,
            variable_names=variables,
            frequentist_note=frequentist_note,
            variant_desc=variant_desc,
        ),
        encoding="utf-8",
    )

    return {
        "table": table_path,
        "report": report_path,
    }
