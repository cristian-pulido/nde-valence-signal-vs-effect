from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns


def plot_vif(vif_df, title: str, path: Path, dpi: int = 220) -> None:
    df = vif_df.copy().sort_values("vif", ascending=True)
    plt.figure(figsize=(8, max(4, 0.45 * len(df))))
    plt.barh(df["predictor"], df["vif"], color="#4C78A8")
    plt.axvline(2, linestyle="--", color="orange", label="Low threshold")
    plt.axvline(5, linestyle="--", color="red", label="Concern threshold")
    plt.xlabel("VIF")
    plt.title(title)
    plt.legend(loc="lower right")
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=dpi)
    plt.close()


def plot_correlation_heatmap(corr_df, title: str, path: Path, dpi: int = 220) -> None:
    mask = np.eye(len(corr_df), dtype=bool)
    plt.figure(figsize=(9, 7))
    sns.heatmap(
        corr_df,
        mask=mask,
        annot=True,
        fmt=".1f",
        cmap="coolwarm",
        center=0,
        square=True,
        linewidths=0.5,
        cbar_kws={"shrink": 0.8},
    )
    plt.title(title)
    plt.xticks(rotation=45, ha="right")
    plt.yticks(rotation=0)
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=dpi)
    plt.close()
