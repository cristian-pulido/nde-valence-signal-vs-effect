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
from nde_analysis.preprocess.transform import PreprocessedData, preprocess_data


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


def _fixed_complete_case(prep: PreprocessedData) -> PreprocessedData:
    analysis_complete = prep.analysis_df.notna().all(axis=1)
    lci_complete = (
        prep.lci_df[["valence_binary", *prep.lci_score_cols]].notna().all(axis=1)
    )
    mask = analysis_complete & lci_complete

    return PreprocessedData(
        raw_df=prep.raw_df.loc[mask].copy(),
        analysis_df=prep.analysis_df.loc[mask].copy(),
        analysis_pretransform_df=prep.analysis_pretransform_df.loc[mask].copy(),
        lci_df=prep.lci_df.loc[mask].copy(),
        lci_score_cols=prep.lci_score_cols,
    )


def main() -> None:
    args = _parse_args()
    cfg = _prepare_config(args)

    raw = load_csv(cfg.data_path)
    prep = preprocess_data(
        raw, lci_min_valid_fraction=cfg.analysis.lci_min_valid_fraction
    )
    prep_fixed = _fixed_complete_case(prep)

    variable_root = cfg.output_dir / "variable_n"
    fixed_root = cfg.output_dir / "fixed_n_complete_case"

    ensure_directories(
        variable_root, variable_root / "tables", variable_root / "reports"
    )
    ensure_directories(fixed_root, fixed_root / "tables", fixed_root / "reports")

    out_variable = run_bayesian_reporting(
        prep,
        tables_dir=variable_root / "tables",
        reports_dir=variable_root / "reports",
        seed=args.seed,
        n_iter=args.n_iter,
        burn=args.burn,
        variant_desc="Variable-N (available-case per outcome)",
    )
    out_fixed = run_bayesian_reporting(
        prep_fixed,
        tables_dir=fixed_root / "tables",
        reports_dir=fixed_root / "reports",
        seed=args.seed,
        n_iter=args.n_iter,
        burn=args.burn,
        variant_desc="Fixed-N complete-case (rows with missing values removed upfront)",
    )

    print(f"Saved: {out_variable['table']}")
    print(f"Saved: {out_variable['report']}")
    print(f"Saved: {out_fixed['table']}")
    print(f"Saved: {out_fixed['report']}")


if __name__ == "__main__":
    main()
