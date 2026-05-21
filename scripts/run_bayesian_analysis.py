from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nde_analysis.analysis.bayesian_reporting import run_bayesian_reporting
from nde_analysis.config import AppConfig, load_config
from nde_analysis.io import ensure_directories, load_csv
from nde_analysis.preprocess.transform import preprocess_data


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Bayesian rank-sum analyses for valence groups"
    )
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--data-path", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--reports-dir", default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-iter", type=int, default=300)
    parser.add_argument("--burn", type=int, default=100)
    return parser.parse_args()


def _prepare_config(args: argparse.Namespace) -> AppConfig:
    return load_config(
        config_path=Path(args.config),
        data_path_override=args.data_path,
        output_dir_override=args.output_dir,
        reports_dir_override=args.reports_dir,
    )


def main() -> None:
    args = _parse_args()
    cfg = _prepare_config(args)

    raw = load_csv(cfg.data_path)
    prep = preprocess_data(
        raw, lci_min_valid_fraction=cfg.analysis.lci_min_valid_fraction
    )
    variable_root = cfg.output_dir / "main"

    ensure_directories(
        variable_root, variable_root / "tables", variable_root / "reports"
    )

    out_variable = run_bayesian_reporting(
        prep,
        tables_dir=variable_root / "tables",
        reports_dir=variable_root / "reports",
        seed=args.seed,
        n_iter=args.n_iter,
        burn=args.burn,
        variant_desc="Main analysis",
    )

    print(f"Saved: {out_variable['table']}")
    print(f"Saved: {out_variable['report']}")


if __name__ == "__main__":
    main()
