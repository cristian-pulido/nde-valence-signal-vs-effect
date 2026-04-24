from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import t

from nde_analysis.config import load_config
from nde_analysis.io import load_csv
from nde_analysis.preprocess.transform import preprocess_data


@dataclass(frozen=True)
class OutcomeSpec:
    source_name: str
    display_name: str
    data_column: str


@dataclass(frozen=True)
class PredictorSpec:
    column: str
    display_name: str


OUTCOME_SPECS: list[OutcomeSpec] = [
    OutcomeSpec("Meaning/Purpose", "Meaning", "LCI_Meaning/Purpose"),
    OutcomeSpec("Appreciation of Life", "Appreciation", "LCI_Appreciation of Life"),
    OutcomeSpec("Concern for Others", "Concern", "LCI_Concern for Others"),
    OutcomeSpec("Self-Acceptance", "Self-accept", "LCI_Self-Acceptance"),
    OutcomeSpec("Spirituality", "Spirituality", "LCI_Spirituality"),
    OutcomeSpec("Other", "Other", "LCI_Other"),
    OutcomeSpec(
        "Social/Planetary Values", "Social values", "LCI_Social/Planetary Values"
    ),
    OutcomeSpec("Death", "Death", "LCI_Death"),
    OutcomeSpec("Religiosity", "Religiosity", "LCI_Religiosity"),
    OutcomeSpec("Material Achievements", "Material", "LCI_Material Achievements"),
]

PREDICTOR_SPECS: list[PredictorSpec] = [
    PredictorSpec("valence_binary", "Valence"),
    PredictorSpec("age", "Age"),
    PredictorSpec("sex_Male", "Sex (male)"),
    PredictorSpec("education_ord", "Education"),
    PredictorSpec("CTQ_IM_SCORE", "CTQ"),
    PredictorSpec("ADHD_SCALE", "ASRS (ADHD)"),
    PredictorSpec("ERQ_total", "ERQ total"),
    PredictorSpec("greyson_total_no_affective", "Greyson\nnon-affective"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create the main short-paper figure for LCI outcomes: broad post-NDE change "
            "by valence and incremental explanatory value of valence after adjustment."
        )
    )
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--data-path", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--figures-dir", default=None)
    parser.add_argument("--reports-dir", default=None)
    return parser.parse_args()


def _load_required_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required table not found: {path}")
    return pd.read_csv(path)


def _mean_ci(
    series: pd.Series, confidence: float = 0.95
) -> tuple[float, float, float, int]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    n = int(values.shape[0])
    if n == 0:
        return np.nan, np.nan, np.nan, 0

    mean = float(values.mean())
    if n == 1:
        return mean, np.nan, np.nan, 1

    sem = float(values.std(ddof=1)) / np.sqrt(n)
    alpha = 1.0 - confidence
    t_crit = float(t.ppf(1.0 - alpha / 2.0, df=n - 1))
    margin = t_crit * sem
    return mean, mean - margin, mean + margin, n


def _prepare_panel_a_data(
    lci_by_valence: pd.DataFrame,
    prep,
) -> tuple[pd.DataFrame, bool]:
    needed = {
        "mean_positive",
        "mean_non_positive",
        "p_value",
        "p_value_fdr",
        "p_value_fdr_reject",
    }

    lci = lci_by_valence.rename(columns={"category": "source_name"}).copy()

    missing_lci = needed - set(lci.columns)
    if missing_lci:
        raise ValueError(f"LCI by-valence table missing columns: {sorted(missing_lci)}")

    rows: list[dict] = []
    ci_available = True
    for spec in OUTCOME_SPECS:
        hit = lci.loc[lci["source_name"] == spec.source_name]
        if hit.empty:
            raise ValueError(f"Outcome not found in summary table: {spec.source_name}")

        if spec.data_column not in prep.lci_df.columns:
            raise ValueError(
                f"Outcome column missing in preprocessed data: {spec.data_column}"
            )

        pos_series = prep.lci_df.loc[
            prep.lci_df["valence_binary"] == 1, spec.data_column
        ]
        non_series = prep.lci_df.loc[
            prep.lci_df["valence_binary"] == 0, spec.data_column
        ]
        _, pos_low, pos_high, n_pos = _mean_ci(pos_series, confidence=0.95)
        _, non_low, non_high, n_non = _mean_ci(non_series, confidence=0.95)

        if np.isnan(pos_low) or np.isnan(non_low):
            ci_available = False

        row = hit.iloc[0]
        rows.append(
            {
                "source_name": spec.source_name,
                "display_name": spec.display_name,
                "mean_positive": float(row["mean_positive"]),
                "mean_non_positive": float(row["mean_non_positive"]),
                "pos_ci_low": pos_low,
                "pos_ci_high": pos_high,
                "non_ci_low": non_low,
                "non_ci_high": non_high,
                "n_positive": n_pos,
                "n_non_positive": n_non,
                "p_value": float(row["p_value"]),
                "p_value_fdr": float(row["p_value_fdr"]),
                "p_value_fdr_reject": bool(row["p_value_fdr_reject"]),
            }
        )

    return pd.DataFrame(rows), ci_available


def _prepare_panel_b_data(lci_path: Path) -> pd.DataFrame:
    lci = _load_required_table(lci_path)

    needed = {
        "outcome",
        "r2_full",
        "r2_cov_only",
        "delta_r2",
        "effect_p_value_fdr_reject_full",
        "effect_p_value_fdr_full",
    }
    missing_lci = needed - set(lci.columns)
    if missing_lci:
        raise ValueError(f"LCI comparison table missing columns: {sorted(missing_lci)}")

    combo = lci[
        [
            "outcome",
            "r2_full",
            "r2_cov_only",
            "delta_r2",
            "effect_p_value_fdr_reject_full",
            "effect_p_value_fdr_full",
        ]
    ].copy()
    display_map = {spec.source_name: spec.display_name for spec in OUTCOME_SPECS}
    order_map = {spec.source_name: idx for idx, spec in enumerate(OUTCOME_SPECS)}
    combo["display_name"] = combo["outcome"].map(display_map).fillna(combo["outcome"])
    combo["panel_order"] = combo["outcome"].map(order_map).fillna(999)
    combo = combo.sort_values("panel_order", ascending=True).reset_index(drop=True)
    return combo


def _std_scale(x: pd.Series, y: pd.Series) -> float:
    x_sd = float(x.std(ddof=0))
    y_sd = float(y.std(ddof=0))
    if x_sd == 0.0 or y_sd == 0.0 or np.isnan(x_sd) or np.isnan(y_sd):
        return np.nan
    return x_sd / y_sd


def _prepare_panel_c_data(prep) -> tuple[pd.DataFrame, pd.DataFrame]:
    predictor_cols = [spec.column for spec in PREDICTOR_SPECS]
    predictor_map = {spec.column: spec.display_name for spec in PREDICTOR_SPECS}

    model_df = prep.analysis_df.copy()
    model_df["ERQ_total"] = model_df[["ERQ_reappraisal", "ERQ_suppression"]].mean(axis=1)
    model_df = pd.concat([model_df, prep.lci_df[prep.lci_score_cols]], axis=1)
    model_df = model_df.loc[:, ~model_df.columns.duplicated()].copy()

    for col in predictor_cols:
        if col in model_df.columns:
            model_df[col] = pd.to_numeric(model_df[col], errors="coerce")

    coef_rows: list[dict] = []
    for outcome in OUTCOME_SPECS:
        if outcome.data_column not in model_df.columns:
            continue

        use = model_df[[outcome.data_column, *predictor_cols]].dropna().copy()
        if use.shape[0] < 30:
            continue

        y = use[outcome.data_column]
        X = sm.add_constant(use[predictor_cols], has_constant="add")
        model = sm.OLS(y, X).fit()
        conf = model.conf_int(alpha=0.05)

        for pred in predictor_cols:
            if pred not in model.params.index:
                continue

            scale = _std_scale(use[pred], y)
            beta = float(model.params[pred])
            low = float(conf.loc[pred, 0])
            high = float(conf.loc[pred, 1])

            coef_rows.append(
                {
                    "outcome": outcome.display_name,
                    "predictor": pred,
                    "predictor_display": predictor_map[pred],
                    "beta_std": beta * scale,
                    "beta_std_ci_low": low * scale,
                    "beta_std_ci_high": high * scale,
                }
            )

    coef_df = pd.DataFrame(coef_rows)
    if coef_df.empty:
        raise ValueError("No predictor coefficients available for Panel C")

    summary_rows: list[dict] = []
    for pred in PREDICTOR_SPECS:
        subset = coef_df.loc[coef_df["predictor"] == pred.column].copy()
        if subset.empty:
            continue

        values = subset["beta_std"].dropna().to_numpy()
        n = int(values.shape[0])
        mean_beta = float(np.mean(values))
        mean_abs = float(np.mean(np.abs(values)))

        if n > 1:
            sem = float(np.std(values, ddof=1)) / np.sqrt(n)
            margin = float(t.ppf(0.975, df=n - 1) * sem)
            low = mean_beta - margin
            high = mean_beta + margin
        else:
            low = np.nan
            high = np.nan

        summary_rows.append(
            {
                "predictor": pred.column,
                "predictor_display": pred.display_name,
                "mean_beta_std": mean_beta,
                "mean_beta_std_ci_low": low,
                "mean_beta_std_ci_high": high,
                "mean_abs_beta_std": mean_abs,
            }
        )

    summary_df = pd.DataFrame(summary_rows).sort_values(
        "mean_abs_beta_std", ascending=False
    )
    return coef_df, summary_df


def _apply_publication_style() -> None:
    plt.style.use("default")
    mpl.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "axes.edgecolor": "#444444",
            "axes.labelcolor": "#222222",
            "xtick.color": "#222222",
            "ytick.color": "#222222",
            "text.color": "#222222",
            "axes.titlesize": 17,
            "axes.labelsize": 15,
            "xtick.labelsize": 13,
            "ytick.labelsize": 13,
            "legend.fontsize": 13,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def _build_figure(
    panel_a_df: pd.DataFrame,
    panel_b_df: pd.DataFrame,
    panel_c_coef_df: pd.DataFrame,
    panel_c_summary_df: pd.DataFrame,
) -> plt.Figure:
    _apply_publication_style()

    valence_colors = {"Positive": "#3B82C4", "Non-positive": "#E07A33"}

    fig, axes = plt.subplots(
        1,
        3,
        figsize=(18.6, 8.0),
        gridspec_kw={"width_ratios": [1.35, 0.95, 1.05]},
        constrained_layout=True,
    )

    ax = axes[0]
    y = np.arange(len(panel_a_df))

    for idx, row in panel_a_df.iterrows():
        pos_err = np.array(
            [
                [row["mean_positive"] - row["pos_ci_low"]],
                [row["pos_ci_high"] - row["mean_positive"]],
            ]
        )
        non_err = np.array(
            [
                [row["mean_non_positive"] - row["non_ci_low"]],
                [row["non_ci_high"] - row["mean_non_positive"]],
            ]
        )
        ax.errorbar(
            row["mean_positive"],
            idx - 0.18,
            xerr=pos_err,
            fmt="o",
            color=valence_colors["Positive"],
            ecolor=valence_colors["Positive"],
            capsize=3.5,
            ms=5.8,
            lw=1.3,
            zorder=3,
        )
        ax.errorbar(
            row["mean_non_positive"],
            idx + 0.18,
            xerr=non_err,
            fmt="s",
            color=valence_colors["Non-positive"],
            ecolor=valence_colors["Non-positive"],
            capsize=3.5,
            ms=5.8,
            lw=1.3,
            zorder=3,
        )

    not_fdr_mask = (panel_a_df["p_value"] < 0.05) & (~panel_a_df["p_value_fdr_reject"])

    x_min = float(
        min(
            panel_a_df["pos_ci_low"].min(),
            panel_a_df["non_ci_low"].min(),
            panel_a_df["mean_positive"].min(),
            panel_a_df["mean_non_positive"].min(),
            -0.05,
        )
        - 0.08
    )
    x_max_core = float(
        max(
            panel_a_df["pos_ci_high"].max(),
            panel_a_df["non_ci_high"].max(),
            panel_a_df["mean_positive"].max(),
            panel_a_df["mean_non_positive"].max(),
        )
    )
    x_marker = x_max_core + 0.08
    x_max = x_marker + 0.08

    if not_fdr_mask.any():
        ax.scatter(
            np.repeat(x_marker, int(not_fdr_mask.sum())),
            y[not_fdr_mask.to_numpy()],
            s=34,
            marker="o",
            facecolors="none",
            edgecolors="#666666",
            linewidths=1.0,
            zorder=4,
        )

    ax.axvline(0.0, linestyle="--", color="#AAAAAA", linewidth=1.1)
    ax.set_xlim(x_min, x_max)
    ax.set_yticks(y)
    ax.set_yticklabels(panel_a_df["display_name"])
    ax.invert_yaxis()
    ax.set_xlabel("Mean change (0 = no change)")
    ax.set_title("A. Mean change by valence", loc="left", pad=6)
    ax.grid(axis="x", color="#E8E8E8", linewidth=0.8)
    ax.grid(axis="y", visible=False)

    valence_handles = [
        mpl.lines.Line2D(
            [],
            [],
            marker="o",
            linestyle="",
            color=valence_colors["Positive"],
            label="Positive",
            markersize=6,
        ),
        mpl.lines.Line2D(
            [],
            [],
            marker="s",
            linestyle="",
            color=valence_colors["Non-positive"],
            label="Non-positive",
            markersize=6,
        ),
        mpl.lines.Line2D(
            [],
            [],
            marker="o",
            linestyle="",
            markerfacecolor="none",
            markeredgecolor="#666666",
            label="Nominal p<0.05,\nnot FDR-significant",
            markersize=6,
        ),
    ]
    ax.legend(
        handles=valence_handles,
        loc="upper left",
        bbox_to_anchor=(0.01, 0.92),
        ncol=2,
        frameon=False,
        borderaxespad=0.0,
        handletextpad=0.5,
        columnspacing=1.0,
    )

    ax = axes[1]
    y2 = np.arange(len(panel_b_df))
    base_color = "#9BC7B1"
    delta_color = "#1F9A72"
    ax.barh(
        y2,
        panel_b_df["r2_cov_only"],
        color=base_color,
        edgecolor="white",
        linewidth=0.8,
        height=0.68,
        label="Base R2 (covariates)",
    )
    ax.barh(
        y2,
        panel_b_df["delta_r2"],
        left=panel_b_df["r2_cov_only"],
        color=delta_color,
        edgecolor="white",
        linewidth=0.8,
        height=0.68,
        label="Delta R2 (valence)",
    )
    ax.set_yticks(y2)
    ax.set_yticklabels([])
    ax.tick_params(axis="y", length=0)
    ax.invert_yaxis()
    ax.set_xlabel("Total R2 (base + increment)")
    ax.set_title("B. Base R2 and increment from valence", loc="left", pad=6)
    ax.grid(axis="x", color="#E8E8E8", linewidth=0.8)
    ax.grid(axis="y", visible=False)
    max_r2 = float(panel_b_df["r2_full"].max())
    ax.set_xlim(0, max(0.06, max_r2 * 1.22))

    for idx, row in panel_b_df.iterrows():
        r2_full = float(row["r2_full"])
        inside_pad = max(0.005, max_r2 * 0.015)
        if r2_full >= 0.08:
            x_text = r2_full - inside_pad
            ha_text = "right"
        else:
            x_text = max(0.004, r2_full * 0.2)
            ha_text = "left"

        ax.text(
            x_text,
            idx,
            f"R2={r2_full:.3f}",
            va="center",
            ha=ha_text,
            fontsize=10.5,
            color="#2F2F2F",
        )

    panel_b_handles = [
        mpl.patches.Patch(facecolor=delta_color, edgecolor="none", label="Delta R2 (valence)"),
        mpl.patches.Patch(facecolor=base_color, edgecolor="none", label="Base R2 (covariates)"),
    ]
    ax.legend(
        handles=panel_b_handles,
        loc="lower right",
        bbox_to_anchor=(0.98, 0.16),
        ncol=1,
        frameon=False,
        borderaxespad=0.0,
    )

    any_significant = bool(
        panel_b_df["effect_p_value_fdr_reject_full"].astype(bool).any()
    )
    if not any_significant:
        axes[0].text(
            0.58,
            0.02,
            "No Delta R2\nsurvives FDR\ncorrection\n(all q > 0.05)",
            transform=axes[0].transAxes,
            ha="left",
            va="bottom",
            fontsize=12.5,
            color="#5C5C5C",
            style="italic",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.85, "pad": 2.0},
        )
        axes[0].annotate(
            "",
            xy=(1.02, 0.15),
            xycoords=axes[0].transAxes,
            xytext=(0.70, 0.15),
            textcoords=axes[0].transAxes,
            arrowprops={
                "arrowstyle": "-|>",
                "lw": 2.4,
                "color": "#6A6A6A",
                "shrinkA": 0,
                "shrinkB": 0,
                "mutation_scale": 18,
            },
            annotation_clip=False,
        )

    ax = axes[2]
    order = panel_c_summary_df["predictor_display"].tolist()
    y3 = np.arange(len(order))
    y_map = {name: idx for idx, name in enumerate(order)}

    for pred_name in order:
        subset = panel_c_coef_df.loc[
            panel_c_coef_df["predictor_display"] == pred_name
        ].copy()
        if subset.empty:
            continue

        y_base = y_map[pred_name]
        jitter = (
            np.linspace(-0.18, 0.18, len(subset))
            if len(subset) > 1
            else np.array([0.0])
        )
        ax.scatter(
            subset["beta_std"],
            y_base + jitter,
            s=24,
            color="#B6B6B6",
            edgecolors="none",
            alpha=0.9,
            zorder=2,
        )

    for _, row in panel_c_summary_df.iterrows():
        y_base = y_map[row["predictor_display"]]
        is_valence = row["predictor"] == "valence_binary"
        marker = "D" if is_valence else "o"
        face = "white" if is_valence else "#222222"

        if np.isfinite(row["mean_beta_std_ci_low"]) and np.isfinite(
            row["mean_beta_std_ci_high"]
        ):
            err = np.array(
                [
                    [row["mean_beta_std"] - row["mean_beta_std_ci_low"]],
                    [row["mean_beta_std_ci_high"] - row["mean_beta_std"]],
                ]
            )
            ax.errorbar(
                row["mean_beta_std"],
                y_base,
                xerr=err,
                fmt=marker,
                color="#111111",
                ecolor="#111111",
                markerfacecolor=face,
                markeredgecolor="#111111",
                markeredgewidth=1.0,
                capsize=3.0,
                lw=1.2,
                ms=7.0,
                zorder=4,
            )
        else:
            ax.scatter(
                [row["mean_beta_std"]],
                [y_base],
                marker=marker,
                s=56,
                facecolors=face,
                edgecolors="#111111",
                linewidths=1.0,
                zorder=4,
            )

    x_vals = np.concatenate(
        [
            panel_c_coef_df["beta_std"].to_numpy(dtype=float),
            panel_c_summary_df["mean_beta_std_ci_low"].dropna().to_numpy(dtype=float),
            panel_c_summary_df["mean_beta_std_ci_high"].dropna().to_numpy(dtype=float),
        ]
    )
    x_pad = 0.07
    ax.set_xlim(float(np.nanmin(x_vals)) - x_pad, float(np.nanmax(x_vals)) + x_pad)
    ax.axvline(0.0, linestyle="--", color="#999999", linewidth=1.0, zorder=1)
    ax.set_yticks(y3)
    ax.set_yticklabels(order)
    ax.invert_yaxis()
    ax.set_xlabel("Standardized beta")
    ax.set_title("C. Predictor importance in full models", loc="left", pad=6)
    ax.grid(axis="x", color="#E8E8E8", linewidth=0.8)
    ax.grid(axis="y", visible=False)

    ax.legend(
        handles=[
            mpl.lines.Line2D(
                [],
                [],
                marker="o",
                linestyle="",
                color="#B6B6B6",
                label="Outcome-specific",
                markersize=5,
            ),
            mpl.lines.Line2D(
                [],
                [],
                marker="o",
                linestyle="",
                color="#111111",
                label="Mean beta (95% CI)",
                markersize=6,
            ),
            mpl.lines.Line2D(
                [],
                [],
                marker="D",
                linestyle="",
                markerfacecolor="white",
                markeredgecolor="#111111",
                color="#111111",
                label="Valence",
                markersize=6,
            ),
        ],
        loc="lower center",
        bbox_to_anchor=(0.5, 0.005),
        ncol=1,
        frameon=False,
        borderaxespad=0.4,
    )

    return fig


def _print_console_summary(
    lci_by_valence_path: Path,
    lci_delta_path: Path,
    ci_available: bool,
) -> None:
    print("Data sources used:")
    print(f"- {lci_by_valence_path}")
    print(f"- {lci_delta_path}")
    print(
        "- underlying preprocessed outcome values (from configured input CSV) for CI computation"
    )
    print(f"Number of outcomes plotted: {len(OUTCOME_SPECS)}")
    if ci_available:
        print("Uncertainty intervals: 95% CIs computed from underlying outcome data")
    else:
        print(
            "Uncertainty intervals: unavailable for one or more outcomes due to insufficient data"
        )


def main() -> None:
    args = parse_args()
    cfg = load_config(
        config_path=Path(args.config),
        data_path_override=args.data_path,
        output_dir_override=args.output_dir,
        figures_dir_override=args.figures_dir,
        reports_dir_override=args.reports_dir,
    )

    lci_by_valence_path = cfg.tables_dir / "lci_by_valence.csv"
    lci_delta_path = cfg.tables_dir / "lci_full_vs_covariates_comparison.csv"

    lci_by_valence = _load_required_table(lci_by_valence_path)

    raw = load_csv(cfg.data_path)
    prep = preprocess_data(
        raw, lci_min_valid_fraction=cfg.analysis.lci_min_valid_fraction
    )

    panel_a_df, ci_available = _prepare_panel_a_data(lci_by_valence, prep)
    panel_b_df = _prepare_panel_b_data(lci_delta_path)
    panel_c_coef_df, panel_c_summary_df = _prepare_panel_c_data(prep)

    fig = _build_figure(panel_a_df, panel_b_df, panel_c_coef_df, panel_c_summary_df)

    cfg.figures_dir.mkdir(parents=True, exist_ok=True)
    out_png = cfg.figures_dir / "main_shortpaper_figure.png"
    out_pdf = cfg.figures_dir / "main_shortpaper_figure.pdf"

    fig.savefig(out_png, dpi=450, bbox_inches="tight")
    fig.savefig(out_pdf, bbox_inches="tight")
    plt.close(fig)

    print(f"Saved PNG: {out_png}")
    print(f"Saved PDF: {out_pdf}")
    _print_console_summary(
        lci_by_valence_path=lci_by_valence_path,
        lci_delta_path=lci_delta_path,
        ci_available=ci_available,
    )


if __name__ == "__main__":
    main()
