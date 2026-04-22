from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nde_analysis.analysis.bayesian_rank_sum import run_bayesian_rank_sum
from nde_analysis.config import AppConfig, load_config
from nde_analysis.io import ensure_directories, load_csv, write_table
from nde_analysis.preprocess.mappings import MCQ_COLS, MCQ_ITEM_LABELS
from nde_analysis.preprocess.transform import preprocess_data


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Bayesian rank-sum analyses for valence groups"
    )
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--data-path", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--reports-dir", default=None)
    parser.add_argument("--fixed-output-dir", default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-iter", type=int, default=300)
    parser.add_argument("--burn", type=int, default=100)
    return parser.parse_args()


def _prepare_config(args: argparse.Namespace) -> AppConfig:
    return load_config(
        config_path=Path(args.config),
        data_path_override=args.data_path,
        output_dir_override=args.output_dir,
        reports_dir_override=args.reports_dir,
    )


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
    paths = [tables_dir / "mcq_by_valence.csv", tables_dir / "lci_by_valence.csv"]
    available = [p for p in paths if p.exists()]
    if not available:
        return (
            "Frequentist comparison unavailable: Mann-Whitney result tables "
            "were not found in the tables directory."
        )

    frames = [pd.read_csv(p) for p in available]
    freq = pd.concat(frames, ignore_index=True)
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
    if v in MCQ_ITEM_LABELS:
        return MCQ_ITEM_LABELS[v]
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

    summary_cols = [
        "variable",
        "n_positive",
        "n_non_positive",
        "bf01",
        "interpretation",
    ]
    summary_table = report_df[summary_cols].copy()

    agg = _summarize_bf(report_df)
    agg_table = pd.DataFrame(
        [
            {
                "metric": "% variables with BF01 > 3",
                "value": agg["pct_bf01_gt_3"],
            },
            {
                "metric": "% variables with BF01 > 10",
                "value": agg["pct_bf01_gt_10"],
            },
            {
                "metric": "% inconclusive",
                "value": agg["pct_inconclusive"],
            },
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
        f"- Variables analyzed: {len(variable_names)} outcomes across NDE-MCQ items and LCI-R aggregated domains.",
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


def _combined_analysis_df(prep) -> tuple[pd.DataFrame, list[str]]:
    group_col = "valence_binary"
    variables = [*MCQ_COLS, *prep.lci_score_cols]

    combined = pd.concat(
        [
            prep.mcq_df[[group_col] + MCQ_COLS],
            prep.lci_df[[group_col] + prep.lci_score_cols],
        ],
        axis=1,
    )
    combined = combined.loc[:, ~combined.columns.duplicated()].copy()
    return combined, variables


def main() -> None:
    args = _parse_args()
    cfg = _prepare_config(args)

    variable_output_dir = cfg.output_dir
    variable_tables_dir = cfg.tables_dir
    variable_reports_dir = cfg.reports_dir

    fixed_output_dir = (
        Path(args.fixed_output_dir)
        if args.fixed_output_dir
        else (cfg.output_dir.parent / "no_empty_no_missing_test")
    )
    fixed_tables_dir = fixed_output_dir / "tables"
    fixed_reports_dir = fixed_output_dir / "reports"

    ensure_directories(
        variable_output_dir,
        variable_tables_dir,
        variable_reports_dir,
        fixed_output_dir,
        fixed_tables_dir,
        fixed_reports_dir,
    )

    raw = load_csv(cfg.data_path)
    prep = preprocess_data(
        raw, lci_min_valid_fraction=cfg.analysis.lci_min_valid_fraction
    )

    combined_df, variables = _combined_analysis_df(prep)
    group_col = "valence_binary"

    variable_n_results = run_bayesian_rank_sum(
        df=combined_df,
        variables=variables,
        group_col=group_col,
        prior_scale=0.707,
        n_iter=args.n_iter,
        burn=args.burn,
        seed=args.seed,
    )

    fixed_df = combined_df[[group_col] + variables].dropna(axis=0).copy()
    fixed_n_results = run_bayesian_rank_sum(
        df=fixed_df,
        variables=variables,
        group_col=group_col,
        prior_scale=0.707,
        n_iter=args.n_iter,
        burn=args.burn,
        seed=args.seed,
    )

    table_variable_n = variable_tables_dir / "bayesian_rank_sum_variable_N.csv"
    table_fixed_n = fixed_tables_dir / "bayesian_rank_sum_fixed_N.csv"
    write_table(variable_n_results, table_variable_n)
    write_table(fixed_n_results, table_fixed_n)

    frequentist_note = _load_frequentist_summary(variable_tables_dir)

    report_variable_n = variable_reports_dir / "bayesian_rank_sum_variable_N.md"
    report_fixed_n = fixed_reports_dir / "bayesian_rank_sum_fixed_N.md"

    report_variable_n.write_text(
        _build_report_text(
            title="Bayesian Rank-Sum Report (Variable-N)",
            result_df=variable_n_results,
            variable_names=variables,
            frequentist_note=frequentist_note,
            variant_desc="Variable-N (available-case per outcome; rows with missing values are dropped only for each tested variable).",
        ),
        encoding="utf-8",
    )
    report_fixed_n.write_text(
        _build_report_text(
            title="Bayesian Rank-Sum Report (Fixed-N)",
            result_df=fixed_n_results,
            variable_names=variables,
            frequentist_note=frequentist_note,
            variant_desc="Fixed-N (complete-case set shared across all selected outcomes).",
        ),
        encoding="utf-8",
    )

    # Clean stale files from opposite directories to keep mode separation explicit.
    stale_files = [
        variable_tables_dir / "bayesian_rank_sum_fixed_N.csv",
        variable_reports_dir / "bayesian_rank_sum_fixed_N.md",
        fixed_tables_dir / "bayesian_rank_sum_variable_N.csv",
        fixed_reports_dir / "bayesian_rank_sum_variable_N.md",
    ]
    for stale in stale_files:
        if stale.exists():
            stale.unlink()

    print(f"Saved: {table_variable_n}")
    print(f"Saved: {table_fixed_n}")
    print(f"Saved: {report_variable_n}")
    print(f"Saved: {report_fixed_n}")


if __name__ == "__main__":
    main()
