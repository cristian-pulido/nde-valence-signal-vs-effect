from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt


def plot_intercepts(intercept_table, title: str, path: Path, dpi: int = 220) -> None:
    if intercept_table.empty:
        return

    df = intercept_table.copy().sort_values("intercept")
    colors = ["#2ca02c" if p < 0.05 else "gray" for p in df["intercept_p_value"]]

    plt.figure(figsize=(8, max(4, 0.45 * len(df))))
    plt.errorbar(
        df["intercept"],
        df["outcome"],
        xerr=[
            df["intercept"] - df["intercept_ci_low"],
            df["intercept_ci_high"] - df["intercept"],
        ],
        fmt="none",
        ecolor="gray",
        elinewidth=2,
        capsize=4,
    )
    plt.scatter(df["intercept"], df["outcome"], c=colors, s=80, zorder=3)
    plt.axvline(0, linestyle="--", linewidth=2, color="black")
    plt.xlabel("Baseline level (intercept)")
    plt.title(title)
    plt.grid(axis="x", linestyle=":", alpha=0.4)
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=dpi)
    plt.close()
