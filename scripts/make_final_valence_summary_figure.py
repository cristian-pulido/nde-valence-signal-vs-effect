from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import t

from nde_analysis.config import load_config
from nde_analysis.io import load_csv
from nde_analysis.preprocess.transform import preprocess_data


@dataclass(frozen=True)
class OutcomeSpec:
    source_name: str
    display_name: str
    data_column: str


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


def _build_figure(panel_a_df: pd.DataFrame, panel_b_df: pd.DataFrame) -> plt.Figure:
    _apply_publication_style()

    valence_colors = {"Positive": "#3B82C4", "Non-positive": "#E07A33"}

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(12.8, 7.7),
        gridspec_kw={"width_ratios": [1.25, 0.85]},
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
            label="Nominal p<0.05, not FDR-significant",
            markersize=6,
        ),
    ]
    ax.legend(
        handles=valence_handles,
        loc="upper left",
        bbox_to_anchor=(0.0, 0.965),
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
    ax.grid(axis="x", color="#E8E8E8", linewidth=0.8)
    ax.grid(axis="y", visible=False)
    max_r2 = float(panel_b_df["r2_full"].max())
    ax.set_xlim(0, max(0.06, max_r2 * 1.22))

    for idx, row in panel_b_df.iterrows():
        ax.text(
            float(row["r2_full"]) + max(0.0015, max_r2 * 0.01),
            idx,
            f"R2={row['r2_full']:.3f}",
            va="center",
            ha="left",
            fontsize=10.5,
            color="#3F3F3F",
        )

    ax.legend(
        loc="upper left",
        bbox_to_anchor=(0.0, 1.02),
        ncol=2,
        frameon=False,
        borderaxespad=0.0,
    )

    any_significant = bool(
        panel_b_df["effect_p_value_fdr_reject_full"].astype(bool).any()
    )
    if not any_significant:
        axes[0].annotate(
            "No Delta R2 survives FDR correction\n(all q > 0.05)",
            xy=(0.02, 0.54),
            xycoords=ax.transAxes,
            xytext=(0.60, 0.06),
            textcoords=axes[0].transAxes,
            ha="left",
            va="bottom",
            fontsize=13.5,
            color="#5C5C5C",
            style="italic",
            arrowprops={
                "arrowstyle": "->",
                "lw": 1.4,
                "color": "#6A6A6A",
                "shrinkA": 4,
                "shrinkB": 4,
            },
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.85, "pad": 3},
            annotation_clip=False,
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

    fig = _build_figure(panel_a_df, panel_b_df)

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
