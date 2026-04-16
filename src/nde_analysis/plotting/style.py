from __future__ import annotations

import seaborn as sns


def apply_plot_style(style: str = "whitegrid") -> None:
    sns.set_theme(style=style)
