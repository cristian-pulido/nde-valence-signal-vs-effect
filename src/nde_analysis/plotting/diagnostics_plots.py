from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns


def plot_covariate_kde_grid(
    overlap_df,
    variables: list[str],
    path: Path,
    dpi: int = 220,
) -> None:
    n_vars = len(variables)
    n_cols = 2
    n_rows = (n_vars + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(11, 4 * n_rows))
    axes = axes.flatten()
    for ax, var in zip(axes, variables):
        tmp = overlap_df[["valence", var]].dropna()
        sns.kdeplot(
            data=tmp,
            x=var,
            hue="valence",
            fill=True,
            common_norm=False,
            alpha=0.35,
            ax=ax,
        )
        ax.set_title(f"Overlap by valence: {var}")
        ax.set_xlabel(var)
        ax.set_ylabel("Density")

    for j in range(len(variables), len(axes)):
        axes[j].axis("off")

    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=dpi)
    plt.close()


def plot_covariate_box_grid(
    overlap_df,
    variables: list[str],
    path: Path,
    dpi: int = 220,
) -> None:
    n_vars = len(variables)
    n_cols = 2
    n_rows = (n_vars + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(11, 4 * n_rows))
    axes = axes.flatten()

    for ax, var in zip(axes, variables):
        tmp = overlap_df[["valence", var]].dropna()
        sns.boxplot(data=tmp, x="valence", y=var, ax=ax)
        sns.stripplot(
            data=tmp,
            x="valence",
            y=var,
            ax=ax,
            color="black",
            alpha=0.25,
            jitter=0.15,
            size=3,
        )
        ax.set_title(f"Distribution by valence: {var}")
        ax.set_xlabel("")
        ax.set_ylabel(var)

    for j in range(len(variables), len(axes)):
        axes[j].axis("off")

    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=dpi)
    plt.close()


def plot_sex_distribution(sex_summary, path: Path, dpi: int = 220) -> None:
    plt.figure(figsize=(6, 4))
    sns.barplot(data=sex_summary, x="valence", y="proportion", hue="sex_label")
    plt.ylabel("Proportion")
    plt.xlabel("")
    plt.title("Sex distribution by valence")
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=dpi)
    plt.close()
