#!/usr/bin/env python3
"""Run the independent, explicitly provisional first-NDE age-difference analysis."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "nde-latency-exploration"
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from nde_analysis.analysis.nde_latency import LATENCY, analyze_latency, audit_ages
from nde_analysis.config import load_config
from nde_analysis.preprocess.transform import preprocess_data
from nde_analysis.reporting.nde_latency_reports import scientific_summary, technical_report

PROVENANCE = {
    "age_at_survey_definition": "unverified",
    "first_lifetime_nde_age_definition": "unverified",
    "evaluated_event_selection": "unknown",
    "multiple_nde_indicator_or_count": "not available in local data",
    "evaluated_nde_age_or_date": "not available in local data",
    "user_clarification": "User states the age definitions and event selection cannot be verified.",
    "operational_definition": "supplied age minus supplied age_first_NDE",
    "interpretation": "Provisional first-NDE latency proxy only, conditional on supplied field meanings; not verified evaluated-event latency.",
    "local_documentation_checked": ["README.md", "src/nde_analysis/preprocess/transform.py",
                                    "src/nde_analysis/preprocess/mappings.py", "src/nde_analysis/cli.py",
                                    "../../COLLINEARITY_PRESENTATION_INPUT.md",
                                    "../../COLLINEARITY_PRESENTATION_INPUT copy.md"],
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe_output(path):
    resolved = Path(path).resolve()
    base = (ROOT/"outputs/exploratory").resolve()
    if resolved == base or not resolved.is_relative_to(base):
        raise ValueError("Use a dedicated output directory under outputs/exploratory/")
    return resolved


def protection_snapshot(output, inputs):
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    paths = {ROOT/p for p in tracked if p}
    paths.update(p for p in (ROOT/"outputs").rglob("*") if p.is_file())
    paths.update(inputs)
    return {str(p.resolve()): sha256(p) for p in sorted(paths)
            if p.is_file() and not p.resolve().is_relative_to(output)}


def save_figure(fig, output, name):
    for extension in ("png", "svg"):
        path = output/f"{name}.{extension}"
        fig.savefig(path, dpi=300, metadata={"Date": None} if extension == "svg" else None)
        if extension == "svg":
            path.write_text("\n".join(x.rstrip() for x in path.read_text().splitlines())+"\n")
    plt.close(fig)


def figures(result, output):
    frame = result.eligible
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    maximum = frame[LATENCY].max()
    bins = np.arange(0, (np.ceil(maximum/5)+1)*5+1, 5)
    for value, label, colour in ((0, "Non-positive", "#b45a36"), (1, "Positive", "#235b80")):
        series = frame.loc[frame.valence_binary==value, LATENCY].dropna()
        ax.hist(series, bins=bins, histtype="stepfilled", alpha=.18, color=colour)
        ax.hist(series, bins=bins, histtype="step", linewidth=1.8, color=colour,
                label=f"{label} (n={len(series)})")
        ax.axvline(series.median(), color=colour, linestyle="--", linewidth=1.2)
    ax.set(xlabel="Supplied age difference (years)", ylabel="Participants",
           title="Provisional time since first NDE: unverified event link")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    save_figure(fig, output, "latency_distribution")

    table = result.results.loc[result.results.status=="ok"]
    y = np.arange(len(table))
    fig, ax = plt.subplots(figsize=(8.8, 5.5))
    ax.errorbar(table.latency_per_decade_beta, y,
                xerr=np.vstack([table.latency_per_decade_beta-table.latency_per_decade_ci_low,
                                table.latency_per_decade_ci_high-table.latency_per_decade_beta]),
                fmt="o", color="#235b80", capsize=3)
    for i, (_, r) in enumerate(table.iterrows()):
        ax.text(1.02, i, f"q={r.latency_q:.3f}", transform=ax.get_yaxis_transform(), va="center", fontsize=9)
    ax.axvline(0, color="#777777", linestyle="--", linewidth=1)
    ax.set_yticks(y, table.outcome)
    ax.invert_yaxis()
    ax.set(xlabel="Adjusted LCI-R difference per 10 additional years\nSupplied age difference, not verified evaluated-event latency",
           title="Exploratory added-covariate associations")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", alpha=.2)
    fig.text(.5, .015, "Bars: pointwise 95% confidence intervals. q: BH FDR across ten domains.",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .05, .89, 1))
    save_figure(fig, output, "latency_coefficients")

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.6))
    for ax, predictor, caption in zip(axes, ("intensity", "valence"),
                                       ("Intensity: LCI-R points per Greyson SD", "Valence: Positive minus Non-positive")):
        for m, offset, colour, symbol, caption_model in (
            ("m0", -.12, "#707070", "o", "Original model (M0)"),
            ("m1", .12, "#235b80", "s", "With age difference (M1)")):
            beta = table[f"{m}_{predictor}_beta"]
            low, high = table[f"{m}_{predictor}_ci_low"], table[f"{m}_{predictor}_ci_high"]
            ax.errorbar(beta, y+offset, xerr=np.vstack([beta-low, high-beta]),
                        fmt=symbol, color=colour, markersize=4, capsize=2, label=caption_model)
        ax.axvline(0, color="#777777", linestyle="--", linewidth=1)
        ax.set_yticks(y, table.outcome if predictor == "intensity" else [])
        ax.invert_yaxis()
        ax.set_xlabel(caption)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x", alpha=.2)
    handles, labels = axes[1].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, fontsize=9, loc="upper center",
               bbox_to_anchor=(.62, .935), ncol=2)
    fig.suptitle("Original predictor estimates before and after provisional adjustment")
    fig.text(.5, .015, "Bars: pointwise 95% confidence intervals. Panels use different predictor units and separate axes.",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .05, 1, .88))
    save_figure(fig, output, "intensity_valence_stability")


def run_once(args):
    output = safe_output(args.output_dir)
    config_path = args.config.resolve()
    cfg = load_config(config_path)
    def absolute(path):
        return (ROOT/path).resolve() if not path.is_absolute() else path.resolve()
    model_path = absolute(args.data_path or cfg.data_path)
    age_path = absolute(args.age_path)
    before = protection_snapshot(output, [model_path, age_path])
    raw = pd.read_csv(model_path, dtype={"response_id": "string"})
    ages = pd.read_csv(age_path, dtype={"response_id": "string"})
    audit = audit_ages(raw, ages)
    output.mkdir(parents=True, exist_ok=True)
    audit.ages.to_csv(output/"age_validation.csv", index=False)
    audit.diagnostics.to_csv(output/"merge_diagnostics.csv", index=False)
    (output/"provenance_status.json").write_text(json.dumps(PROVENANCE, indent=2)+"\n")
    if audit.issues:
        text = "# Latency analysis withheld\n\nAge validation requires review before modeling:\n\n"+"\n".join(f"- {s}" for s in audit.issues)+"\n\nNo participants were silently excluded or imputed. See aggregate age and merge diagnostics.\n"
        for name in ("latency_analysis_report.md", "latency_analysis_summary.md"):
            (output/name).write_text(text)
        raise ValueError("Age validation failed; modeling withheld. Inspect aggregate validation outputs.")
    prep = preprocess_data(raw, lci_min_valid_fraction=cfg.analysis.lci_min_valid_fraction)
    saved_path = ROOT/"outputs/latest/main/tables/lci_adjusted_full_models.csv"
    result = analyze_latency(prep, audit, pd.read_csv(saved_path), cfg.analysis.min_n_models)
    if not (result.results.status=="ok").all():
        result.results.to_csv(output/"latency_model_comparison.csv", index=False)
        problems = result.results.loc[result.results.status!="ok", ["outcome", "status"]]
        text = "# Latency estimation incomplete\n\n"+problems.to_string(index=False)+"\n\nDo not interpret a complete ten-domain analysis. See the comparison CSV.\n"
        (output/"latency_analysis_report.md").write_text(text)
        (output/"latency_analysis_summary.md").write_text(text)
        raise ValueError("At least one model is not estimable; no full interpretation generated")
    tables = {
        "latency_model_comparison.csv": result.results,
        "latency_descriptive_statistics.csv": result.descriptions,
        "temporal_correlations.csv": result.correlations,
        "model_coefficients.csv": result.coefficients,
        "baseline_validation.csv": result.baseline_validation,
        "m1_m2_equivalence.csv": result.parameterization,
        "model_vif.csv": result.vif,
    }
    sensitivity_columns = [c for c in result.results if c.startswith(("latency_hc3", "loo_", "max_", "n_cooks", "n_leverage", "n_latency_dfbetas"))]
    tables["aggregate_sensitivity.csv"] = result.results[["outcome", "n"]+sensitivity_columns]
    for name, table in tables.items():
        table.to_csv(output/name, index=False)
    sources = sorted((ROOT/"src/nde_analysis").rglob("*.py"))+[
        Path(__file__).resolve(), ROOT/"tests/test_nde_latency.py"]
    manifest = {
        "analysis": "Provisional first-NDE age-difference covariate exploration",
        "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT).decode().strip(),
        "base_commit": subprocess.check_output(["git", "merge-base", "HEAD", "main"], cwd=ROOT).decode().strip(),
        "model_data_path": str(model_path), "age_data_path": str(age_path),
        "model_input_sha256": sha256(model_path), "age_input_sha256": sha256(age_path),
        "config_sha256": sha256(config_path), "saved_baseline_sha256": sha256(saved_path),
        "source_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in sources if p.is_file()},
        "python": platform.python_version(),
        "packages": {p: importlib.metadata.version(p) for p in
                     ("numpy", "pandas", "scipy", "statsmodels", "matplotlib")},
        "provenance": PROVENANCE, "min_n_models": cfg.analysis.min_n_models,
        "lci_min_valid_fraction": cfg.analysis.lci_min_valid_fraction,
        "primary_fdr_family_size": 10, "centering": {
            "latency_years": result.eligible[LATENCY].mean(),
            "survey_age_years": result.eligible.age_at_survey.mean()},
        "baseline_validation_passed": bool(result.baseline_validation.passed.all()),
        "m1_m2_equivalence_passed": bool(result.parameterization.passed.all()),
        "protected_files_before": before,
    }
    figures(result, output)
    (output/"latency_analysis_report.md").write_text(technical_report(result, audit, manifest), encoding="utf-8")
    (output/"latency_analysis_summary.md").write_text(scientific_summary(result), encoding="utf-8")
    after = protection_snapshot(output, [model_path, age_path])
    changed = [p for p in set(before)|set(after) if before.get(p)!=after.get(p)]
    manifest["protected_files_unchanged"] = not changed
    manifest["changed_protected_files"] = sorted(changed)
    (output/"run_manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    if changed:
        raise RuntimeError("Protected existing files changed during execution")
    if not manifest["baseline_validation_passed"] or not manifest["m1_m2_equivalence_passed"]:
        raise RuntimeError("Model validation failed; inspect the technical report before interpreting")
    return output, result


def artifact_hashes(output):
    return {p.name: sha256(p) for p in sorted(output.iterdir()) if p.is_file()
            and p.name not in {"reproducibility_check.json", "test_validation.json"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT/"configs/default.yaml")
    parser.add_argument("--data-path", type=Path)
    parser.add_argument("--age-path", type=Path, default=Path("../../DATA/data_age.csv"))
    parser.add_argument("--output-dir", type=Path, default=ROOT/"outputs/exploratory/nde_latency")
    parser.add_argument("--verify-reproducibility", action="store_true")
    args = parser.parse_args()
    output, result = run_once(args)
    if args.verify_reproducibility:
        before = artifact_hashes(output)
        output, result = run_once(args)
        after = artifact_hashes(output)
        different = sorted(p for p in set(before)|set(after) if before.get(p)!=after.get(p))
        check = {"same_environment": True, "byte_identical": not different,
                 "n_files_compared": len(before), "different_files": different, "sha256": after}
        (output/"reproducibility_check.json").write_text(json.dumps(check, indent=2)+"\n")
        if different:
            raise RuntimeError(f"Repeated-run artifact differences: {different}")
        print(f"Reproducibility: {len(before)} artifacts byte-identical")
    print(result.results[["outcome", "n", "latency_beta", "latency_p", "latency_q", "delta_r2"]].to_string(index=False))
    print(f"Summary: {output/'latency_analysis_summary.md'}")
    print("Definition remains unverified: this is an age-difference proxy, not verified evaluated-event latency.")


if __name__ == "__main__":
    main()
