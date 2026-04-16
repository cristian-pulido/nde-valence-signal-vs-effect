from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd

from nde_analysis.analysis.adjusted_effects import compare_full_vs_covariates
from nde_analysis.analysis.collinearity import compute_vif_table
from nde_analysis.analysis.diagnostics import build_covariate_diagnostics
from nde_analysis.analysis.post_effects_lci import run_lci_analyses
from nde_analysis.analysis.post_effects_mcq import run_mcq_analyses
from nde_analysis.analysis.valence_models import run_valence_models
from nde_analysis.config import AppConfig, load_config
from nde_analysis.io import ensure_directories, load_csv, write_table
from nde_analysis.plotting.adjusted_plots import plot_intercepts
from nde_analysis.plotting.collinearity_plots import (
    plot_correlation_heatmap,
    plot_vif,
)
from nde_analysis.plotting.diagnostics_plots import (
    plot_covariate_box_grid,
    plot_covariate_kde_grid,
    plot_sex_distribution,
)
from nde_analysis.plotting.lci_plots import (
    plot_adjusted_delta,
    plot_lci_mean_pointplot,
    plot_lci_median_heatmap,
)
from nde_analysis.plotting.mcq_plots import (
    plot_mcq_mean_pointplot,
    plot_mcq_median_heatmap,
)
from nde_analysis.plotting.style import apply_plot_style
from nde_analysis.plotting.valence_plots import (
    plot_odds_ratio_forest,
    plot_predicted_probabilities,
    plot_roc,
)
from nde_analysis.preprocess.mappings import MCQ_COLS
from nde_analysis.preprocess.transform import preprocess_data
from nde_analysis.reporting.render import render_report
from nde_analysis.utils.logging import setup_logging


LOGGER = logging.getLogger("nde_analysis")


def _table_text(df: pd.DataFrame, digits: int = 3) -> str:
    if df.empty:
        return "No rows available."
    view = df.copy()
    view = view.dropna(axis=1, how="all")
    for col in view.select_dtypes(include=["float", "float64"]).columns:
        view[col] = view[col].round(digits)
    for col in view.select_dtypes(include=["bool"]).columns:
        view[col] = view[col].map({True: "Yes", False: "No"})
    view = view.fillna("-")
    return "```\n" + view.to_string(index=False) + "\n```"


def _select_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    selected = [c for c in cols if c in df.columns]
    return df[selected].copy()


def _relative_link(report_path: Path, artifact_path: Path) -> str:
    return Path(os.path.relpath(artifact_path, start=report_path.parent)).as_posix()


def _interpret_valence(sample_table: pd.DataFrame, fit_table: pd.DataFrame) -> str:
    r2_m1 = sample_table.loc[sample_table["model"] == "Model 1", "pseudo_r2"].iloc[0]
    r2_m3 = sample_table.loc[sample_table["model"] == "Model 3", "pseudo_r2"].iloc[0]
    p_21 = fit_table.loc[
        fit_table["comparison"] == "Model 2 vs Model 1", "p_value"
    ].iloc[0]
    p_32 = fit_table.loc[
        fit_table["comparison"] == "Model 3 vs Model 2", "p_value"
    ].iloc[0]
    return (
        f"Model fit improved from pseudo-R²={r2_m1:.3f} (demographics only) to "
        f"pseudo-R²={r2_m3:.3f} (full model). LR tests indicated p={p_21:.3f} for "
        f"Model 2 vs 1 and p={p_32:.3f} for Model 3 vs 2."
    )


def _interpret_post_effects(comparison_df: pd.DataFrame, label: str) -> str:
    if comparison_df.empty:
        return f"No adjusted {label} models met the minimum sample threshold."
    n_add = int(comparison_df["valence_adds_signal"].sum())
    return (
        f"{n_add} outcomes showed evidence that valence adds explanatory value beyond covariates. "
        "Interpretation is based on the valence term p-value in the full model and model-fit deltas "
        "between full and covariates-only specifications."
    )


def _interpret_covariate_balance(balance_df: pd.DataFrame) -> str:
    if balance_df.empty:
        return "No balance diagnostics were available."
    near_imbalance = int((balance_df["p_value"] < 0.10).sum())
    significant = int((balance_df["p_value"] < 0.05).sum())
    return (
        f"{significant} covariates were imbalanced at p<0.05 and {near_imbalance} at p<0.10. "
        "Distribution overlap plots and balance tests jointly support whether adjusted analysis is plausible."
    )


def run_valence_pipeline(cfg: AppConfig, prep) -> dict[str, Path]:
    results = run_valence_models(prep.analysis_df)

    original_valence_dist = (
        prep.raw_df["valence"]
        .value_counts(dropna=False)
        .rename_axis("valence")
        .reset_index(name="n")
    )
    original_valence_dist["pct"] = (
        100 * original_valence_dist["n"] / original_valence_dist["n"].sum()
    )

    binary_valence_dist = (
        prep.analysis_df["valence_binary"]
        .map({1: "Positive", 0: "Non-positive (Mixed + Negative)"})
        .value_counts(dropna=False)
        .rename_axis("valence_binary")
        .reset_index(name="n")
    )
    binary_valence_dist["pct"] = (
        100 * binary_valence_dist["n"] / binary_valence_dist["n"].sum()
    )

    vif_predictors = [
        "CTQ_PA_SCORE",
        "CTQ_SA_SCORE",
        "CTQ_EN_SCORE",
        "CTQ_PN_SCORE",
        "ADHD_SCALE",
        "ERQ_reappraisal",
        "ERQ_suppression",
        "greyson_total_no_affective",
        "age",
        "education_ord",
        "sex_Male",
        "valence_binary",
    ]
    vif_table = compute_vif_table(prep.raw_df, vif_predictors)
    corr_df = (
        prep.raw_df[vif_predictors]
        .apply(pd.to_numeric, errors="coerce")
        .corr(method="spearman")
    )

    # Tables
    t_m1 = cfg.tables_dir / "valence_model1_odds_ratios.csv"
    t_m2 = cfg.tables_dir / "valence_model2_odds_ratios.csv"
    t_m3 = cfg.tables_dir / "valence_model3_odds_ratios.csv"
    t_fit = cfg.tables_dir / "valence_model_fit_comparisons.csv"
    t_sample = cfg.tables_dir / "valence_model_sample_sizes.csv"
    t_vif = cfg.tables_dir / "valence_multicollinearity_vif.csv"
    t_corr = cfg.tables_dir / "valence_predictor_correlation_spearman.csv"
    write_table(results.table_m1, t_m1)
    write_table(results.table_m2, t_m2)
    write_table(results.table_m3, t_m3)
    write_table(results.fit_table, t_fit)
    write_table(results.sample_table, t_sample)
    write_table(vif_table, t_vif)
    write_table(corr_df.reset_index().rename(columns={"index": "predictor"}), t_corr)

    # Figures
    fig_m1 = cfg.figures_dir / "valence_model1_or_forest.png"
    fig_m2 = cfg.figures_dir / "valence_model2_or_forest.png"
    fig_m3 = cfg.figures_dir / "valence_model3_or_forest.png"
    fig_roc = cfg.figures_dir / "valence_model3_roc.png"
    fig_pred = cfg.figures_dir / "valence_model3_predicted_probabilities.png"
    fig_vif = cfg.figures_dir / "valence_multicollinearity_vif.png"
    fig_corr = cfg.figures_dir / "valence_predictor_correlation_heatmap.png"

    plot_odds_ratio_forest(
        results.table_m1, "Model 1: Demographics", fig_m1, cfg.plot.dpi
    )
    plot_odds_ratio_forest(
        results.table_m2, "Model 2: + Psychological", fig_m2, cfg.plot.dpi
    )
    plot_odds_ratio_forest(
        results.table_m3, "Model 3: + Experiential", fig_m3, cfg.plot.dpi
    )
    roc_auc = plot_roc(
        y_true=results.model3_predictions["valence_binary"],
        y_score=results.model3_predictions["pred_prob"],
        path=fig_roc,
        dpi=cfg.plot.dpi,
    )
    plot_predicted_probabilities(results.model3_predictions, fig_pred, cfg.plot.dpi)
    plot_vif(vif_table, "Variance Inflation Factor (VIF)", fig_vif, cfg.plot.dpi)
    plot_correlation_heatmap(
        corr_df,
        "Spearman Correlation Between Predictors",
        fig_corr,
        cfg.plot.dpi,
    )

    report = cfg.reports_dir / "01_valence_multivariate_report.md"
    render_report(
        template_dir=Path(__file__).parent / "reporting" / "templates",
        template_name="valence_report.md.j2",
        context={
            "sample_table": _table_text(results.sample_table),
            "original_valence_dist": _table_text(original_valence_dist),
            "binary_valence_dist": _table_text(binary_valence_dist),
            "fit_table": _table_text(results.fit_table),
            "vif_table": _table_text(vif_table),
            "model1_table": _table_text(results.table_m1),
            "model2_table": _table_text(results.table_m2),
            "model3_table": _table_text(results.table_m3),
            "fig_model1": _relative_link(report, fig_m1),
            "fig_model2": _relative_link(report, fig_m2),
            "fig_model3": _relative_link(report, fig_m3),
            "fig_roc": _relative_link(report, fig_roc),
            "fig_pred": _relative_link(report, fig_pred),
            "fig_vif": _relative_link(report, fig_vif),
            "fig_corr": _relative_link(report, fig_corr),
            "interpretation": _interpret_valence(
                results.sample_table, results.fit_table
            )
            + f" Model 3 ROC AUC={roc_auc:.3f}.",
        },
        output_path=report,
    )

    return {
        "report": report,
        "fig_m1": fig_m1,
        "fig_m2": fig_m2,
        "fig_m3": fig_m3,
        "fig_roc": fig_roc,
        "fig_pred": fig_pred,
        "fig_vif": fig_vif,
        "fig_corr": fig_corr,
    }


def run_post_effects_pipeline(cfg: AppConfig, prep) -> dict[str, Path]:
    mcq = run_mcq_analyses(prep.mcq_df)
    lci = run_lci_analyses(prep.lci_df, prep.lci_score_cols)

    write_table(mcq.global_table, cfg.tables_dir / "mcq_global_change.csv")
    write_table(mcq.by_valence_table, cfg.tables_dir / "mcq_by_valence.csv")
    write_table(
        mcq.response_distribution, cfg.tables_dir / "mcq_response_distribution.csv"
    )
    write_table(lci.global_table, cfg.tables_dir / "lci_global_change.csv")
    write_table(lci.by_valence_table, cfg.tables_dir / "lci_by_valence.csv")
    write_table(lci.missingness_table, cfg.tables_dir / "lci_missingness.csv")

    fig_mcq_heat = cfg.figures_dir / "mcq_median_heatmap_by_valence.png"
    fig_mcq_point = cfg.figures_dir / "mcq_mean_change_by_valence.png"
    fig_lci_heat = cfg.figures_dir / "lci_median_heatmap_by_valence.png"
    fig_lci_point = cfg.figures_dir / "lci_mean_change_by_valence.png"
    fig_cov_kde = cfg.figures_dir / "covariates_overlap_kde_by_valence.png"
    fig_cov_box = cfg.figures_dir / "covariates_boxstrip_by_valence.png"
    fig_cov_sex = cfg.figures_dir / "covariates_sex_distribution_by_valence.png"

    plot_mcq_median_heatmap(mcq.long_df, fig_mcq_heat, cfg.plot.dpi)
    plot_mcq_mean_pointplot(mcq.long_df, fig_mcq_point, cfg.plot.dpi)
    plot_lci_median_heatmap(lci.long_df, fig_lci_heat, cfg.plot.dpi)
    plot_lci_mean_pointplot(lci.long_df, fig_lci_point, cfg.plot.dpi)

    cov_diag = build_covariate_diagnostics(prep.analysis_df)
    overlap_vars = [
        "age",
        "CTQ_IM_SCORE",
        "ADHD_SCALE",
        "ERQ_reappraisal",
        "ERQ_suppression",
        "education_ord",
    ]
    plot_covariate_kde_grid(
        cov_diag.overlap_df, overlap_vars, fig_cov_kde, cfg.plot.dpi
    )
    plot_covariate_box_grid(
        cov_diag.overlap_df, overlap_vars, fig_cov_box, cfg.plot.dpi
    )
    plot_sex_distribution(cov_diag.sex_summary, fig_cov_sex, cfg.plot.dpi)

    write_table(
        cov_diag.summary_table, cfg.tables_dir / "covariate_summary_by_valence.csv"
    )
    write_table(cov_diag.balance_table, cfg.tables_dir / "covariate_balance_tests.csv")
    write_table(cov_diag.sex_summary, cfg.tables_dir / "covariate_sex_distribution.csv")

    # Adjusted models (full vs covariates-only)
    cov_cont = [
        "age",
        "CTQ_IM_SCORE",
        "ADHD_SCALE",
        "ERQ_reappraisal",
        "ERQ_suppression",
        "education_ord",
        "greyson_total_no_affective",
    ]
    cov_cat = ["sex_Male"]

    mcq_model_df = pd.concat([prep.analysis_df, prep.mcq_df[MCQ_COLS]], axis=1)
    lci_model_df = pd.concat(
        [prep.analysis_df, prep.lci_df[prep.lci_score_cols]], axis=1
    )
    mcq_model_df = mcq_model_df.loc[:, ~mcq_model_df.columns.duplicated()].copy()
    lci_model_df = lci_model_df.loc[:, ~lci_model_df.columns.duplicated()].copy()
    for df in (mcq_model_df, lci_model_df):
        for c in cov_cont + cov_cat + ["valence_binary"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

    # Explicit labels for reproducible report names.
    mcq_comp = compare_full_vs_covariates(
        model_df=mcq_model_df,
        outcomes=MCQ_COLS,
        outcome_labels={
            "NDE-MCQ_01_Since_NDE": "Responsibility to help others",
            "NDE-MCQ_02_Since_NDE": "Act by moral rules",
            "NDE-MCQ_03_Since_NDE": "Consider others' perspectives",
            "NDE-MCQ_04_Since_NDE": "Willingness to forgive others",
            "NDE-MCQ_05_Since_NDE": "Consider long-term consequences",
        },
        continuous_covariates=cov_cont,
        categorical_covariates=cov_cat,
        min_n=cfg.analysis.min_n_models,
    )
    lci_comp = compare_full_vs_covariates(
        model_df=lci_model_df,
        outcomes=prep.lci_score_cols,
        outcome_labels={c: c.replace("LCI_", "") for c in prep.lci_score_cols},
        continuous_covariates=cov_cont,
        categorical_covariates=cov_cat,
        min_n=cfg.analysis.min_n_models,
    )

    write_table(mcq_comp.full_table, cfg.tables_dir / "mcq_adjusted_full_models.csv")
    write_table(
        mcq_comp.covariates_only_table,
        cfg.tables_dir / "mcq_covariates_only_models.csv",
    )
    write_table(
        mcq_comp.comparison_table,
        cfg.tables_dir / "mcq_full_vs_covariates_comparison.csv",
    )

    write_table(lci_comp.full_table, cfg.tables_dir / "lci_adjusted_full_models.csv")
    write_table(
        lci_comp.covariates_only_table,
        cfg.tables_dir / "lci_covariates_only_models.csv",
    )
    write_table(
        lci_comp.comparison_table,
        cfg.tables_dir / "lci_full_vs_covariates_comparison.csv",
    )

    full_cols = [
        "outcome",
        "n",
        "intercept",
        "intercept_ci_low",
        "intercept_ci_high",
        "intercept_p_value",
        "effect",
        "effect_ci_low",
        "effect_ci_high",
        "effect_p_value",
        "r2",
        "aic",
        "bic",
    ]
    cov_cols = [
        "outcome",
        "n",
        "intercept",
        "intercept_ci_low",
        "intercept_ci_high",
        "intercept_p_value",
        "r2",
        "aic",
        "bic",
    ]
    comp_cols = [
        "outcome",
        "n_full",
        "effect_full",
        "effect_ci_low_full",
        "effect_ci_high_full",
        "effect_p_value_full",
        "r2_full",
        "r2_cov_only",
        "delta_r2",
        "delta_aic",
        "delta_bic",
        "valence_adds_signal",
    ]

    mcq_full_view = _select_columns(mcq_comp.full_table, full_cols)
    mcq_cov_view = _select_columns(mcq_comp.covariates_only_table, cov_cols)
    mcq_comp_view = _select_columns(mcq_comp.comparison_table, comp_cols)
    lci_full_view = _select_columns(lci_comp.full_table, full_cols)
    lci_cov_view = _select_columns(lci_comp.covariates_only_table, cov_cols)
    lci_comp_view = _select_columns(lci_comp.comparison_table, comp_cols)

    rename_map = {
        "n": "N",
        "n_full": "N",
        "intercept": "baseline",
        "intercept_ci_low": "baseline_ci_low",
        "intercept_ci_high": "baseline_ci_high",
        "intercept_p_value": "baseline_p",
        "effect": "valence_beta",
        "effect_ci_low": "valence_ci_low",
        "effect_ci_high": "valence_ci_high",
        "effect_p_value": "valence_p",
        "effect_full": "valence_beta",
        "effect_ci_low_full": "valence_ci_low",
        "effect_ci_high_full": "valence_ci_high",
        "effect_p_value_full": "valence_p",
        "r2_full": "R2_full",
        "r2_cov_only": "R2_cov_only",
        "delta_r2": "delta_R2",
        "delta_aic": "delta_AIC",
        "delta_bic": "delta_BIC",
        "valence_adds_signal": "valence_adds_signal",
    }
    mcq_full_view = mcq_full_view.rename(columns=rename_map)
    mcq_cov_view = mcq_cov_view.rename(columns=rename_map)
    mcq_comp_view = mcq_comp_view.rename(columns=rename_map)
    lci_full_view = lci_full_view.rename(columns=rename_map)
    lci_cov_view = lci_cov_view.rename(columns=rename_map)
    lci_comp_view = lci_comp_view.rename(columns=rename_map)

    fig_mcq_delta = cfg.figures_dir / "mcq_adjusted_full_vs_covariates_delta.png"
    fig_lci_delta = cfg.figures_dir / "lci_adjusted_full_vs_covariates_delta.png"
    fig_mcq_intercept_full = cfg.figures_dir / "mcq_adjusted_intercepts_full.png"
    fig_lci_intercept_full = cfg.figures_dir / "lci_adjusted_intercepts_full.png"
    fig_mcq_intercept_cov = (
        cfg.figures_dir / "mcq_adjusted_intercepts_covariates_only.png"
    )
    fig_lci_intercept_cov = (
        cfg.figures_dir / "lci_adjusted_intercepts_covariates_only.png"
    )
    plot_adjusted_delta(
        mcq_comp.comparison_table,
        "NDE-MCQ: full model vs covariates-only (Delta R²)",
        fig_mcq_delta,
        cfg.plot.dpi,
    )
    plot_adjusted_delta(
        lci_comp.comparison_table,
        "LCI-R: full model vs covariates-only (Delta R²)",
        fig_lci_delta,
        cfg.plot.dpi,
    )
    plot_intercepts(
        mcq_comp.full_table,
        "NDE-MCQ baseline levels (full adjusted model)",
        fig_mcq_intercept_full,
        cfg.plot.dpi,
    )
    plot_intercepts(
        lci_comp.full_table,
        "LCI-R baseline levels (full adjusted model)",
        fig_lci_intercept_full,
        cfg.plot.dpi,
    )
    plot_intercepts(
        mcq_comp.covariates_only_table,
        "NDE-MCQ baseline levels (covariates-only model)",
        fig_mcq_intercept_cov,
        cfg.plot.dpi,
    )
    plot_intercepts(
        lci_comp.covariates_only_table,
        "LCI-R baseline levels (covariates-only model)",
        fig_lci_intercept_cov,
        cfg.plot.dpi,
    )

    template_dir = Path(__file__).parent / "reporting" / "templates"

    report_mcq = cfg.reports_dir / "02_post_effects_mcq_report.md"
    render_report(
        template_dir=template_dir,
        template_name="post_effects_report.md.j2",
        context={
            "domain_name": "NDE-MCQ",
            "global_table": _table_text(mcq.global_table),
            "by_valence_table": _table_text(mcq.by_valence_table),
            "full_table": _table_text(mcq_full_view),
            "cov_only_table": _table_text(mcq_cov_view),
            "comparison_table": _table_text(mcq_comp_view),
            "figures": [
                _relative_link(report_mcq, fig_mcq_heat),
                _relative_link(report_mcq, fig_mcq_point),
                _relative_link(report_mcq, fig_mcq_delta),
                _relative_link(report_mcq, fig_mcq_intercept_full),
                _relative_link(report_mcq, fig_mcq_intercept_cov),
            ],
            "interpretation": _interpret_post_effects(mcq_comp.comparison_table, "MCQ"),
        },
        output_path=report_mcq,
    )

    report_lci = cfg.reports_dir / "03_post_effects_lci_report.md"
    render_report(
        template_dir=template_dir,
        template_name="post_effects_report.md.j2",
        context={
            "domain_name": "LCI-R",
            "global_table": _table_text(lci.global_table),
            "by_valence_table": _table_text(lci.by_valence_table),
            "full_table": _table_text(lci_full_view),
            "cov_only_table": _table_text(lci_cov_view),
            "comparison_table": _table_text(lci_comp_view),
            "figures": [
                _relative_link(report_lci, fig_lci_heat),
                _relative_link(report_lci, fig_lci_point),
                _relative_link(report_lci, fig_lci_delta),
                _relative_link(report_lci, fig_lci_intercept_full),
                _relative_link(report_lci, fig_lci_intercept_cov),
            ],
            "interpretation": _interpret_post_effects(lci_comp.comparison_table, "LCI"),
        },
        output_path=report_lci,
    )

    # Combined adjusted comparison report.
    report_adj = cfg.reports_dir / "04_adjusted_models_comparison_report.md"
    report_adj.write_text(
        "# Adjusted Models Comparison\n\n"
        "## LCI-R: Full vs Covariates-Only\n\n"
        + _table_text(lci_comp_view)
        + "\n\n![LCI-R full-model intercepts]("
        + _relative_link(report_adj, fig_lci_intercept_full)
        + ")\n\n![LCI-R covariates-only intercepts]("
        + _relative_link(report_adj, fig_lci_intercept_cov)
        + ")\n"
        + "\n\n## NDE-MCQ: Full vs Covariates-Only\n\n"
        + _table_text(mcq_comp_view)
        + "\n\n![NDE-MCQ full-model intercepts]("
        + _relative_link(report_adj, fig_mcq_intercept_full)
        + ")\n\n![NDE-MCQ covariates-only intercepts]("
        + _relative_link(report_adj, fig_mcq_intercept_cov)
        + ")\n"
        + "\n",
        encoding="utf-8",
    )

    report_cov = cfg.reports_dir / "05_covariate_diagnostics_report.md"
    render_report(
        template_dir=template_dir,
        template_name="covariate_diagnostics_report.md.j2",
        context={
            "summary_table": _table_text(cov_diag.summary_table),
            "balance_table": _table_text(cov_diag.balance_table),
            "fig_kde": _relative_link(report_cov, fig_cov_kde),
            "fig_box": _relative_link(report_cov, fig_cov_box),
            "fig_sex": _relative_link(report_cov, fig_cov_sex),
            "interpretation": _interpret_covariate_balance(cov_diag.balance_table),
        },
        output_path=report_cov,
    )

    return {
        "report_mcq": report_mcq,
        "report_lci": report_lci,
        "report_adj": report_adj,
        "report_cov": report_cov,
        "fig_mcq_heat": fig_mcq_heat,
        "fig_mcq_point": fig_mcq_point,
        "fig_mcq_delta": fig_mcq_delta,
        "fig_mcq_intercept_full": fig_mcq_intercept_full,
        "fig_mcq_intercept_cov": fig_mcq_intercept_cov,
        "fig_lci_heat": fig_lci_heat,
        "fig_lci_point": fig_lci_point,
        "fig_lci_delta": fig_lci_delta,
        "fig_lci_intercept_full": fig_lci_intercept_full,
        "fig_lci_intercept_cov": fig_lci_intercept_cov,
        "fig_cov_kde": fig_cov_kde,
        "fig_cov_box": fig_cov_box,
        "fig_cov_sex": fig_cov_sex,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NDE analysis CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p):
        p.add_argument("--config", default="configs/default.yaml")
        p.add_argument("--data-path", default=None)
        p.add_argument("--output-dir", default=None)
        p.add_argument("--figures-dir", default=None)
        p.add_argument("--reports-dir", default=None)
        p.add_argument("--seed", type=int, default=None)

    add_common(sub.add_parser("run-all", help="Run full pipeline"))
    add_common(sub.add_parser("run-valence", help="Run valence models only"))
    add_common(sub.add_parser("run-post-effects", help="Run MCQ/LCI analyses only"))
    return parser.parse_args()


def _prepare_config(args: argparse.Namespace) -> AppConfig:
    cfg = load_config(
        config_path=Path(args.config),
        data_path_override=args.data_path,
        output_dir_override=args.output_dir,
        figures_dir_override=args.figures_dir,
        reports_dir_override=args.reports_dir,
    )
    if args.seed is not None:
        cfg.reproducibility.seed = args.seed
    return cfg


def main() -> None:
    setup_logging()
    args = _parse_args()
    cfg = _prepare_config(args)

    ensure_directories(cfg.output_dir, cfg.figures_dir, cfg.tables_dir, cfg.reports_dir)
    apply_plot_style(cfg.plot.style)

    np.random.seed(cfg.reproducibility.seed)

    raw = load_csv(cfg.data_path)
    prep = preprocess_data(
        raw, lci_min_valid_fraction=cfg.analysis.lci_min_valid_fraction
    )

    generated_reports: list[Path] = []
    generated_figures: list[Path] = []

    if args.command in {"run-all", "run-valence"}:
        out_valence = run_valence_pipeline(cfg, prep)
        generated_reports.append(out_valence["report"])
        generated_figures.extend(
            [
                out_valence["fig_m1"],
                out_valence["fig_m2"],
                out_valence["fig_m3"],
                out_valence["fig_roc"],
                out_valence["fig_pred"],
                out_valence["fig_vif"],
                out_valence["fig_corr"],
            ]
        )

    if args.command in {"run-all", "run-post-effects"}:
        out_post = run_post_effects_pipeline(cfg, prep)
        generated_reports.extend(
            [
                out_post["report_mcq"],
                out_post["report_lci"],
                out_post["report_adj"],
                out_post["report_cov"],
            ]
        )
        generated_figures.extend(
            [
                out_post["fig_mcq_heat"],
                out_post["fig_mcq_point"],
                out_post["fig_mcq_delta"],
                out_post["fig_mcq_intercept_full"],
                out_post["fig_mcq_intercept_cov"],
                out_post["fig_lci_heat"],
                out_post["fig_lci_point"],
                out_post["fig_lci_delta"],
                out_post["fig_lci_intercept_full"],
                out_post["fig_lci_intercept_cov"],
                out_post["fig_cov_kde"],
                out_post["fig_cov_box"],
                out_post["fig_cov_sex"],
            ]
        )

    summary_report = cfg.reports_dir / "00_run_summary.md"
    render_report(
        template_dir=Path(__file__).parent / "reporting" / "templates",
        template_name="run_summary.md.j2",
        context={
            "data_path": str(cfg.data_path),
            "output_dir": str(cfg.output_dir),
            "figures_dir": str(cfg.figures_dir),
            "tables_dir": str(cfg.tables_dir),
            "reports_dir": str(cfg.reports_dir),
            "reports": [str(p) for p in generated_reports],
            "figures": [str(p) for p in generated_figures],
        },
        output_path=summary_report,
    )

    LOGGER.info("Run complete. Summary report: %s", summary_report)


if __name__ == "__main__":
    main()
