from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class PlotConfig:
    format: str = "png"
    dpi: int = 220
    style: str = "whitegrid"


@dataclass
class AnalysisConfig:
    min_n_models: int = 30
    lci_min_valid_fraction: float = 0.5
    alpha: float = 0.05


@dataclass
class ReproConfig:
    seed: int = 42


@dataclass
class AppConfig:
    data_path: Path
    output_dir: Path
    figures_dir: Path
    tables_dir: Path
    reports_dir: Path
    plot: PlotConfig
    analysis: AnalysisConfig
    reproducibility: ReproConfig


def _deep_get(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = d
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def load_config(
    config_path: Path,
    data_path_override: str | None = None,
    output_dir_override: str | None = None,
    figures_dir_override: str | None = None,
    reports_dir_override: str | None = None,
) -> AppConfig:
    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    default_output_dir = Path(
        _deep_get(raw, "output", "output_dir", default="outputs/latest")
    )
    output_dir = (
        Path(output_dir_override) if output_dir_override else default_output_dir
    )

    figures_dir = (
        Path(figures_dir_override)
        if figures_dir_override
        else Path(
            _deep_get(raw, "output", "figures_dir", default=str(output_dir / "figures"))
        )
    )
    tables_dir = Path(
        _deep_get(raw, "output", "tables_dir", default=str(output_dir / "tables"))
    )
    reports_dir = (
        Path(reports_dir_override)
        if reports_dir_override
        else Path(
            _deep_get(raw, "output", "reports_dir", default=str(output_dir / "reports"))
        )
    )

    if output_dir_override and not figures_dir_override:
        figures_dir = output_dir / "figures"
    if output_dir_override:
        tables_dir = output_dir / "tables"
    if output_dir_override and not reports_dir_override:
        reports_dir = output_dir / "reports"

    data_path = (
        Path(data_path_override)
        if data_path_override
        else Path(
            _deep_get(
                raw, "input", "data_path", default="../../DATA/data_for_model.csv"
            )
        )
    )

    plot = PlotConfig(
        format=_deep_get(raw, "plot", "format", default="png"),
        dpi=int(_deep_get(raw, "plot", "dpi", default=220)),
        style=_deep_get(raw, "plot", "style", default="whitegrid"),
    )

    analysis = AnalysisConfig(
        min_n_models=int(_deep_get(raw, "analysis", "min_n_models", default=30)),
        lci_min_valid_fraction=float(
            _deep_get(raw, "analysis", "lci_min_valid_fraction", default=0.5)
        ),
        alpha=float(_deep_get(raw, "analysis", "alpha", default=0.05)),
    )

    reproducibility = ReproConfig(
        seed=int(_deep_get(raw, "reproducibility", "seed", default=42))
    )

    return AppConfig(
        data_path=data_path,
        output_dir=output_dir,
        figures_dir=figures_dir,
        tables_dir=tables_dir,
        reports_dir=reports_dir,
        plot=plot,
        analysis=analysis,
        reproducibility=reproducibility,
    )
