from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns


def plot_lci_median_heatmap(long_df, path: Path, dpi: int = 220) -> None:
    heat = (
        long_df.groupby(["category", "valence"])["score"]
        .median()
        .reset_index()
        .pivot(index="category", columns="valence", values="score")
    )
    plt.figure(figsize=(7.2, 6.5))
    sns.heatmap(heat, annot=True, cmap="coolwarm", center=0, vmin=-2, vmax=2)
    plt.title("LCI-R median change by valence")
    plt.xlabel("")
    plt.ylabel("")
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=dpi)
    plt.close()


def plot_lci_mean_pointplot(long_df, path: Path, dpi: int = 220) -> None:
    plt.figure(figsize=(11.5, 6.0))
    sns.barplot(
        data=long_df,
        x="category",
        y="score",
        hue="valence",
        errorbar=("ci", 95),
        estimator="mean",
        capsize=0.08,
        err_kws={"linewidth": 1.8},
    )
    plt.axhline(0, linestyle="--", linewidth=1.5, color="black")
    plt.title("LCI-R mean change by category and valence")
    plt.xlabel("")
    plt.ylabel("Mean change relative to 'Not changed'")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=dpi)
    plt.close()


def plot_adjusted_delta(comparison_df, title: str, path: Path, dpi: int = 220) -> None:
    if comparison_df.empty:
        return
    df = comparison_df.sort_values("delta_r2")
    plt.figure(figsize=(8, max(4, 0.45 * len(df))))
    colors = ["#1f77b4" if v else "gray" for v in df["valence_adds_signal"]]
    plt.barh(df["outcome"], df["delta_r2"], color=colors)
    plt.axvline(0, linestyle="--", linewidth=1.6, color="black")
    plt.xlabel("Delta R² (full minus covariates-only)")
    plt.title(title)
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=dpi)
    plt.close()
