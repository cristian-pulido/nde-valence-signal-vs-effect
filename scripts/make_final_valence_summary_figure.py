from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.metrics import auc, roc_curve

from nde_analysis.analysis.valence_models import run_valence_models
from nde_analysis.config import load_config
from nde_analysis.io import load_csv
from nde_analysis.preprocess.transform import preprocess_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a publication-ready two-panel summary figure for valence predictability "
            "and incremental explanatory value across post-NDE outcomes."
        )
    )
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--data-path", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--figures-dir", default=None)
    parser.add_argument("--reports-dir", default=None)
    return parser.parse_args()


def _load_delta_table(path: Path, domain: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required table not found: {path}")
    df = pd.read_csv(path)
    needed = {"outcome", "delta_r2"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"Table {path} missing required columns: {sorted(missing)}")
    out = df[["outcome", "delta_r2"]].copy()
    out["domain"] = domain
    return out


def _prepare_panel_b_data(mcq_path: Path, lci_path: Path) -> pd.DataFrame:
    mcq = _load_delta_table(mcq_path, "MCQ")
    lci = _load_delta_table(lci_path, "LCI-R")
    combo = pd.concat([mcq, lci], ignore_index=True)
    combo = combo.sort_values("delta_r2", ascending=False).reset_index(drop=True)
    return combo


def _apply_publication_style() -> None:
    mpl.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#4a4a4a",
            "axes.labelcolor": "#222222",
            "xtick.color": "#222222",
            "ytick.color": "#222222",
            "text.color": "#222222",
            "font.size": 12,
            "axes.titlesize": 16,
            "axes.labelsize": 14,
            "xtick.labelsize": 12,
            "ytick.labelsize": 12,
            "legend.fontsize": 13,
            "legend.title_fontsize": 13,
            "axes.grid": False,
            "savefig.facecolor": "white",
        }
    )


def _build_figure(
    roc_fpr, roc_tpr, roc_auc: float, panel_b_df: pd.DataFrame
) -> plt.Figure:
    _apply_publication_style()

    domain_colors = {"MCQ": "#4C78A8", "LCI-R": "#72B7B2"}
    highlight_outcome = "Consider long-term consequences"

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(13.5, 5.5),
        gridspec_kw={"width_ratios": [1.0, 1.45]},
        constrained_layout=True,
    )

    # Panel A: ROC
    ax = axes[0]
    ax.plot(roc_fpr, roc_tpr, color="#2F5E8E", lw=2.4, label="Model ROC")
    ax.plot([0, 1], [0, 1], linestyle="--", color="#9a9a9a", lw=1.5, label="Chance")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("A. Valence is only weakly predictable", pad=10)
    ax.text(
        0.16,
        0.84,
        f"AUC = {roc_auc:.3f}",
        transform=ax.transAxes,
        fontsize=11,
        fontweight="semibold",
        bbox={
            "boxstyle": "round,pad=0.25",
            "facecolor": "white",
            "edgecolor": "#d0d0d0",
        },
    )
    ax.text(
        0.16,
        0.79,
        "weak discrimination",
        transform=ax.transAxes,
        fontsize=10,
        color="#4a4a4a",
    )
    ax.legend(loc="lower right", frameon=False)

    # Panel B: horizontal bars of incremental value
    ax = axes[1]
    y = range(len(panel_b_df))
    bars = ax.barh(
        y,
        panel_b_df["delta_r2"],
        color=panel_b_df["domain"].map(domain_colors),
        edgecolor="white",
        linewidth=0.8,
        height=0.75,
    )

    for idx, (bar, outcome) in enumerate(zip(bars, panel_b_df["outcome"])):
        if outcome == highlight_outcome:
            bar.set_edgecolor("#1f1f1f")
            bar.set_linewidth(1.6)
            bar.set_zorder(3)
            ax.text(
                max(0.0003, bar.get_width() - 0.0042),
                idx + 0.46,
                "highest signal",
                va="top",
                ha="left",
                fontsize=9,
                color="#2b2b2b",
            )

    ax.set_yticks(list(y))
    ax.set_yticklabels(panel_b_df["outcome"])
    ax.invert_yaxis()
    ax.axvline(0, linestyle="--", color="gray", alpha=0.7)
    ax.set_xlabel("Incremental contribution of valence (ΔR²)")
    ax.set_title("B. Valence adds little explanatory value", pad=10)
    ax.grid(axis="x", color="#e8e8e8", linewidth=0.8)
    ax.grid(axis="y", visible=False)

    legend_handles = [
        mpl.patches.Patch(color=domain_colors["MCQ"], label="MCQ"),
        mpl.patches.Patch(color=domain_colors["LCI-R"], label="LCI-R"),
    ]
    ax.legend(
        handles=legend_handles, title="Outcome domain", loc="lower right", frameon=False
    )

    return fig


def main() -> None:
    args = parse_args()
    cfg = load_config(
        config_path=Path(args.config),
        data_path_override=args.data_path,
        output_dir_override=args.output_dir,
        figures_dir_override=args.figures_dir,
        reports_dir_override=args.reports_dir,
    )

    # Panel A data: compute ROC/AUC from final valence model (Model 3).
    raw = load_csv(cfg.data_path)
    prep = preprocess_data(
        raw, lci_min_valid_fraction=cfg.analysis.lci_min_valid_fraction
    )
    valence_results = run_valence_models(prep.analysis_df)
    roc_source = valence_results.model3_predictions
    fpr, tpr, _ = roc_curve(roc_source["valence_binary"], roc_source["pred_prob"])
    roc_auc = auc(fpr, tpr)

    # Panel B data: robustly use generated full-vs-covariates tables.
    mcq_path = cfg.tables_dir / "mcq_full_vs_covariates_comparison.csv"
    lci_path = cfg.tables_dir / "lci_full_vs_covariates_comparison.csv"
    panel_b_df = _prepare_panel_b_data(mcq_path, lci_path)

    fig = _build_figure(fpr, tpr, roc_auc, panel_b_df)

    cfg.figures_dir.mkdir(parents=True, exist_ok=True)
    out_png = cfg.figures_dir / "final_valence_summary_figure.png"
    out_pdf = cfg.figures_dir / "final_valence_summary_figure.pdf"

    fig.savefig(out_png, dpi=350, bbox_inches="tight")
    fig.savefig(out_pdf, bbox_inches="tight")
    plt.close(fig)

    print(f"Saved PNG: {out_png}")
    print(f"Saved PDF: {out_pdf}")


if __name__ == "__main__":
    main()
