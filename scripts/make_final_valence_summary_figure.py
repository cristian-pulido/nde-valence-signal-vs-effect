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
    # source_name is the outcome label used in precomputed tables under outputs/latest/tables.
    source_name: str
    # display_name is the compact label shown in the figure.
    display_name: str
    domain: str
    # data_column is the numeric column in preprocessed mcq_df/lci_df used for CI computation.
    data_column: str


# Mapping from repository outcome labels to short paper display labels.
# Order follows the requested panel ordering: MCQ first (5), then LCI-R (10).
OUTCOME_SPECS: list[OutcomeSpec] = [
    OutcomeSpec(
        "Responsibility to help others", "Help others", "MCQ", "NDE-MCQ_01_Since_NDE"
    ),
    OutcomeSpec("Act by moral rules", "Moral rules", "MCQ", "NDE-MCQ_02_Since_NDE"),
    OutcomeSpec(
        "Consider others' perspectives", "Perspective", "MCQ", "NDE-MCQ_03_Since_NDE"
    ),
    OutcomeSpec(
        "Willingness to forgive others", "Forgiveness", "MCQ", "NDE-MCQ_04_Since_NDE"
    ),
    OutcomeSpec(
        "Consider long-term consequences", "Long-term", "MCQ", "NDE-MCQ_05_Since_NDE"
    ),
    OutcomeSpec("Meaning/Purpose", "Meaning", "LCI-R", "LCI_Meaning/Purpose"),
    OutcomeSpec(
        "Appreciation of Life", "Appreciation", "LCI-R", "LCI_Appreciation of Life"
    ),
    OutcomeSpec("Concern for Others", "Concern", "LCI-R", "LCI_Concern for Others"),
    OutcomeSpec("Self-Acceptance", "Self-accept", "LCI-R", "LCI_Self-Acceptance"),
    OutcomeSpec("Spirituality", "Spirituality", "LCI-R", "LCI_Spirituality"),
    OutcomeSpec("Other", "Other", "LCI-R", "LCI_Other"),
    OutcomeSpec(
        "Social/Planetary Values",
        "Social values",
        "LCI-R",
        "LCI_Social/Planetary Values",
    ),
    OutcomeSpec("Death", "Death", "LCI-R", "LCI_Death"),
    OutcomeSpec("Religiosity", "Religiosity", "LCI-R", "LCI_Religiosity"),
    OutcomeSpec(
        "Material Achievements", "Material", "LCI-R", "LCI_Material Achievements"
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create the main short-paper figure: broad post-NDE change by valence and "
            "incremental explanatory value of valence after adjustment."
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
    mcq_by_valence: pd.DataFrame,
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

    mcq = mcq_by_valence.rename(columns={"item": "source_name"}).copy()
    lci = lci_by_valence.rename(columns={"category": "source_name"}).copy()

    missing_mcq = needed - set(mcq.columns)
    missing_lci = needed - set(lci.columns)
    if missing_mcq:
        raise ValueError(f"MCQ by-valence table missing columns: {sorted(missing_mcq)}")
    if missing_lci:
        raise ValueError(f"LCI by-valence table missing columns: {sorted(missing_lci)}")

    summary = pd.concat([mcq, lci], ignore_index=True)

    rows: list[dict] = []
    ci_available = True
    for spec in OUTCOME_SPECS:
        hit = summary.loc[summary["source_name"] == spec.source_name]
        if hit.empty:
            raise ValueError(f"Outcome not found in summary tables: {spec.source_name}")

        source_df = prep.mcq_df if spec.domain == "MCQ" else prep.lci_df
        if spec.data_column not in source_df.columns:
            raise ValueError(
                f"Outcome column missing in preprocessed data: {spec.data_column}"
            )

        pos_series = source_df.loc[source_df["valence_binary"] == 1, spec.data_column]
        non_series = source_df.loc[source_df["valence_binary"] == 0, spec.data_column]
        _, pos_low, pos_high, n_pos = _mean_ci(pos_series, confidence=0.95)
        _, non_low, non_high, n_non = _mean_ci(non_series, confidence=0.95)

        if np.isnan(pos_low) or np.isnan(non_low):
            ci_available = False

        row = hit.iloc[0]
        rows.append(
            {
                "source_name": spec.source_name,
                "display_name": spec.display_name,
                "domain": spec.domain,
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


def _prepare_panel_b_data(mcq_path: Path, lci_path: Path) -> pd.DataFrame:
    mcq = _load_required_table(mcq_path)
    lci = _load_required_table(lci_path)

    needed = {
        "outcome",
        "delta_r2",
        "effect_p_value_fdr_reject_full",
        "effect_p_value_fdr_full",
    }
    missing_mcq = needed - set(mcq.columns)
    missing_lci = needed - set(lci.columns)
    if missing_mcq:
        raise ValueError(f"MCQ comparison table missing columns: {sorted(missing_mcq)}")
    if missing_lci:
        raise ValueError(f"LCI comparison table missing columns: {sorted(missing_lci)}")

    mcq_out = mcq[
        [
            "outcome",
            "delta_r2",
            "effect_p_value_fdr_reject_full",
            "effect_p_value_fdr_full",
        ]
    ].copy()
    lci_out = lci[
        [
            "outcome",
            "delta_r2",
            "effect_p_value_fdr_reject_full",
            "effect_p_value_fdr_full",
        ]
    ].copy()
    mcq_out["domain"] = "MCQ"
    lci_out["domain"] = "LCI-R"

    display_map = {spec.source_name: spec.display_name for spec in OUTCOME_SPECS}
    order_map = {spec.source_name: idx for idx, spec in enumerate(OUTCOME_SPECS)}
    combo = pd.concat([mcq_out, lci_out], ignore_index=True)
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
    domain_colors = {"MCQ": "#3B82C4", "LCI-R": "#1F9A72"}

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(13.6, 7.7),
        gridspec_kw={"width_ratios": [1.0, 1.0]},
        constrained_layout=True,
    )

    # Panel A: means with 95% CIs, derived from preprocessed outcome values by valence group.
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

    # Subtle marker for nominal (uncorrected) between-group differences that fail FDR.
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
    ax.axhline(4.5, linestyle="-", color="#DDDDDD", linewidth=0.8)
    ax.set_xlim(x_min, x_max)
    ax.set_yticks(y)
    ax.set_yticklabels(panel_a_df["display_name"])
    ax.invert_yaxis()
    ax.set_xlabel("Mean change (0 = no change)")
    ax.set_title("A. Broad post-NDE change by valence group", pad=8)
    ax.grid(axis="x", color="#E8E8E8", linewidth=0.8)
    ax.grid(axis="y", visible=False)

    ax.text(
        0.01,
        0.94,
        "MCQ",
        transform=ax.transAxes,
        fontsize=11,
        color="#6A6A6A",
        ha="left",
        va="center",
    )
    ax.text(
        0.01,
        0.46,
        "LCI-R",
        transform=ax.transAxes,
        fontsize=11,
        color="#6A6A6A",
        ha="left",
        va="center",
    )
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
    ]
    ax.legend(
        handles=valence_handles,
        loc="upper left",
        bbox_to_anchor=(0.02, 0.34),
        frameon=False,
    )

    if not_fdr_mask.any():
        ax.text(
            0.98,
            0.03,
            "○ nominal p<0.05, not FDR-significant",
            transform=ax.transAxes,
            ha="right",
            va="center",
            fontsize=11,
            color="#5C5C5C",
        )

    # Panel B: delta R^2 bars from adjusted full-vs-covariates tables.
    ax = axes[1]
    y2 = np.arange(len(panel_b_df))
    ax.barh(
        y2,
        panel_b_df["delta_r2"],
        color=panel_b_df["domain"].map(domain_colors),
        edgecolor="white",
        linewidth=0.8,
        height=0.68,
    )
    ax.set_yticks(y2)
    ax.set_yticklabels([])
    ax.invert_yaxis()
    ax.set_xlabel("Incremental contribution of valence (ΔR²)")
    ax.set_title("B. Valence adds little after adjustment", pad=8)
    ax.grid(axis="x", color="#E8E8E8", linewidth=0.8)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, max(0.03, float(panel_b_df["delta_r2"].max()) * 1.18))

    any_significant = bool(
        panel_b_df["effect_p_value_fdr_reject_full"].astype(bool).any()
    )
    if not any_significant:
        ax.text(
            0.98,
            0.52,
            "No ΔR² survives FDR correction\n(all q > 0.05)",
            transform=ax.transAxes,
            ha="right",
            va="center",
            fontsize=14,
            color="#5C5C5C",
            style="italic",
        )

    legend_handles = [
        mpl.patches.Patch(color=domain_colors["MCQ"], label="MCQ"),
        mpl.patches.Patch(color=domain_colors["LCI-R"], label="LCI-R"),
    ]
    ax.legend(
        handles=legend_handles, title="Outcome domain", loc="lower right", frameon=False
    )

    return fig


def _print_console_summary(
    mcq_by_valence_path: Path,
    lci_by_valence_path: Path,
    mcq_delta_path: Path,
    lci_delta_path: Path,
    ci_available: bool,
) -> None:
    print("Data sources used:")
    print(f"- {mcq_by_valence_path}")
    print(f"- {lci_by_valence_path}")
    print(f"- {mcq_delta_path}")
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

    mcq_by_valence_path = cfg.tables_dir / "mcq_by_valence.csv"
    lci_by_valence_path = cfg.tables_dir / "lci_by_valence.csv"
    mcq_delta_path = cfg.tables_dir / "mcq_full_vs_covariates_comparison.csv"
    lci_delta_path = cfg.tables_dir / "lci_full_vs_covariates_comparison.csv"

    mcq_by_valence = _load_required_table(mcq_by_valence_path)
    lci_by_valence = _load_required_table(lci_by_valence_path)

    raw = load_csv(cfg.data_path)
    prep = preprocess_data(
        raw, lci_min_valid_fraction=cfg.analysis.lci_min_valid_fraction
    )

    panel_a_df, ci_available = _prepare_panel_a_data(
        mcq_by_valence, lci_by_valence, prep
    )
    panel_b_df = _prepare_panel_b_data(mcq_delta_path, lci_delta_path)

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
        mcq_by_valence_path=mcq_by_valence_path,
        lci_by_valence_path=lci_by_valence_path,
        mcq_delta_path=mcq_delta_path,
        lci_delta_path=lci_delta_path,
        ci_available=ci_available,
    )


if __name__ == "__main__":
    main()
