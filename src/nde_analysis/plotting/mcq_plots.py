from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns


def plot_mcq_median_heatmap(long_df, path: Path, dpi: int = 220) -> None:
    heat = (
        long_df.groupby(["item", "valence"])["score"]
        .median()
        .reset_index()
        .pivot(index="item", columns="valence", values="score")
    )
    plt.figure(figsize=(7, 5.5))
    sns.heatmap(heat, annot=True, cmap="coolwarm", center=0, vmin=-2, vmax=2)
    plt.title("NDE-MCQ median change by valence")
    plt.xlabel("")
    plt.ylabel("")
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=dpi)
    plt.close()


def plot_mcq_mean_pointplot(long_df, path: Path, dpi: int = 220) -> None:
    plt.figure(figsize=(9.5, 5.2))
    sns.barplot(
        data=long_df,
        x="item",
        y="score",
        hue="valence",
        errorbar=("ci", 95),
        estimator="mean",
        capsize=0.08,
        err_kws={"linewidth": 1.8},
    )
    plt.axhline(0, linestyle="--", linewidth=1.5, color="black")
    plt.title("NDE-MCQ mean change by valence")
    plt.xlabel("")
    plt.ylabel("Mean change relative to 'Not changed'")
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=dpi)
    plt.close()
