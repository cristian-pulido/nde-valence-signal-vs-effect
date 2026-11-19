#!/usr/bin/env python3
"""Reproduce the isolated exploration; output is restricted to outputs/exploratory."""
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
sys.path.insert(0, str(ROOT / "src"))

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "nde-intensity-valence-interaction"
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from nde_analysis.analysis.intensity_valence_interaction import (
    CENTERED, INTENSITY, INTERACTION, analyze, describe_sample,
)
from nde_analysis.config import load_config
from nde_analysis.io import load_csv
from nde_analysis.preprocess.mappings import LCI_SECTIONS
from nde_analysis.preprocess.transform import preprocess_data


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_output_dir(path: Path) -> Path:
    resolved = path.resolve()
    allowed = (ROOT / "outputs/exploratory").resolve()
    if not resolved.is_relative_to(allowed) or resolved == allowed:
        raise ValueError("Choose a dedicated directory under outputs/exploratory/")
    return resolved


def protected_hashes(output: Path) -> dict:
    """Fingerprint existing tracked files and every existing main output."""
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    files = {ROOT / x for x in tracked if x}
    files.update((ROOT / "outputs/latest/main").rglob("*"))
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(files)
            if p.is_file() and not p.resolve().is_relative_to(output)}


def markdown_table(headers: list[str], rows: list[list]) -> str:
    def cells(values):
        return " | ".join(str(x).replace("|", "\\|") for x in values)
    return "\n".join(["| " + cells(headers) + " |",
                      "| " + " | ".join(["---"] * len(headers)) + " |"] +
                     ["| " + cells(row) + " |" for row in rows])


def plot_coefficients(result, output: Path, dpi: int):
    table = result.results
    ok = table.status == "ok"
    fig, ax = plt.subplots(figsize=(8.6, 5.4))
    y = np.arange(len(table))
    if ok.any():
        t = table.loc[ok]
        ax.errorbar(t.interaction_beta, y[ok],
                    xerr=np.vstack([t.interaction_beta-t.interaction_ci_low,
                                    t.interaction_ci_high-t.interaction_beta]),
                    fmt="o", color="#235b80", ecolor="#235b80", capsize=3)
        for pos, (_, row) in zip(y[ok], t.iterrows()):
            ax.text(1.02, pos, f"q={row.interaction_q:.3f}",
                    transform=ax.get_yaxis_transform(), va="center", fontsize=9)
    ax.axvline(0, color="#666666", linewidth=1, linestyle="--")
    ax.set_yticks(y, table.outcome)
    ax.invert_yaxis()
    ax.set_xlabel("Intensity slope difference: Positive minus Non-positive\nLCI-R points per non-affective Greyson point")
    ax.set_title("Exploratory adjusted intensity × valence interactions")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", alpha=.2)
    fig.text(.5, .015, "Bars: pointwise 95% OLS confidence intervals. q: BH FDR across ten domains.",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .055, .88, 1))
    for suffix in ("png", "svg"):
        path = output / f"interaction_coefficients.{suffix}"
        fig.savefig(path, dpi=dpi,
                    metadata={"Date": None} if suffix == "svg" else None)
        if suffix == "svg":
            path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
    plt.close(fig)


def plot_overlap(prep, output: Path, dpi: int):
    data = prep.analysis_pretransform_df
    fig, ax = plt.subplots(figsize=(7, 3.4))
    all_values = data[INTENSITY].dropna()
    bins = np.arange(np.floor(all_values.min())-.5, np.ceil(all_values.max())+1.5)
    for value, label, color in ((0, "Non-positive", "#b45a36"), (1, "Positive", "#235b80")):
        values = data.loc[data.valence_binary == value, INTENSITY].dropna()
        ax.hist(values, bins=bins, histtype="step", linewidth=1.8,
                label=f"{label} (n={len(values)})", color=color)
    ax.set(xlabel="Non-affective Greyson intensity (original points)",
           ylabel="Participants", title="Observed intensity distribution by valence")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(output / "intensity_overlap.png", dpi=dpi)
    plt.close(fig)


def predicted_plot(result, domain: str, output: Path, dpi: int) -> str:
    """Average the design over the SAME covariate distribution for both groups.

    Mean-response uncertainty uses a linear contrast of the OLS covariance.
    Curves are restricted to the observed common intensity range, not tails.
    """
    model, used = result.fits[domain], result.samples[domain]
    groups = [used.loc[used.valence_binary == v, INTENSITY] for v in (0, 1)]
    lower, upper = max(g.min() for g in groups), min(g.max() for g in groups)
    grid = np.linspace(lower, upper, 100)
    rows = []
    fig, ax = plt.subplots(figsize=(7.3, 4.6))
    for value, label, color in ((0, "Non-positive", "#b45a36"), (1, "Positive", "#235b80")):
        observed = used.loc[used.valence_binary == value]
        ax.scatter(observed[INTENSITY], observed[result.results.set_index("outcome").loc[domain, "outcome_column"]],
                   color=color, s=17, alpha=.28, label=f"{label}: observed")
        design = pd.DataFrame(np.tile(model.model.exog.mean(axis=0), (len(grid), 1)),
                              columns=model.model.exog_names)
        design["const"] = 1
        design["valence_binary"] = value
        design[CENTERED] = grid-result.intensity_center
        design[INTERACTION] = design[CENTERED]*value
        prediction = model.get_prediction(design).summary_frame(alpha=.05)
        ax.plot(grid, prediction["mean"], color=color, linewidth=2,
                label=f"{label}: adjusted prediction")
        ax.fill_between(grid, prediction.mean_ci_lower, prediction.mean_ci_upper,
                        color=color, alpha=.15)
        for i, x in enumerate(grid):
            rows.append({"outcome": domain, "valence": label, "intensity": x,
                         "predicted_mean": prediction["mean"].iloc[i],
                         "mean_ci_low": prediction.mean_ci_lower.iloc[i],
                         "mean_ci_high": prediction.mean_ci_upper.iloc[i]})
    ax.set(xlabel="Non-affective Greyson intensity (original points)",
           ylabel=f"LCI-R {domain} score", title=f"{domain}: illustrative adjusted interaction")
    ax.set_ylim(-2.15, 2.15)
    ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(.5, .015, "Curves: sample-standardized means within common support; bands: pointwise 95% mean CIs.\n"
             "Points: observed outcomes, without covariate adjustment. Selected by raw interaction p < 0.05.",
             ha="center", fontsize=8)
    fig.tight_layout(rect=(0, .07, 1, 1))
    slug = domain.lower().replace("/", "_").replace(" ", "_")
    name = f"predicted_{slug}.png"
    fig.savefig(output / name, dpi=dpi)
    plt.close(fig)
    pd.DataFrame(rows).to_csv(output / f"predicted_{slug}.csv", index=False)
    return name


def report(result, prep, raw, output: Path, images: dict, manifest: dict) -> str:
    t, u = result.results, result.unadjusted
    good = t.loc[t.status == "ok"]
    eligible = prep.analysis_pretransform_df
    positive = int((eligible.valence_binary == 1).sum())
    nonpositive = int((eligible.valence_binary == 0).sum())
    mixed = int((eligible.valence == "Mixed").sum())
    negative = int((eligible.valence == "Negative").sum())
    desc = pd.DataFrame(describe_sample(eligible, "Eligible cohort"))
    distribution = markdown_table(
        ["Group", "N", "Mean (SD)", "Median [Q1, Q3]", "Range", "Within common range"],
        [[r.valence, r.n, f"{r['mean']:.2f} ({r.sd:.2f})",
          f"{r['median']:.2f} [{r.q25:.2f}, {r.q75:.2f}]", f"{r['min']:.0f}–{r['max']:.0f}",
          f"{r.n_in_overlap_range}/{r.n}"] for _, r in desc.iterrows()])
    compact = markdown_table(
        ["Domain", "β interaction [95% CI]", "p", "q (BH)", "R² baseline", "R² interaction", "ΔR²"],
        [[r.outcome, f"{r.interaction_beta:.4f} [{r.interaction_ci_low:.4f}, {r.interaction_ci_high:.4f}]",
          f"{r.interaction_p:.4f}", f"{r.interaction_q:.4f}", f"{r.baseline_r2:.4f}",
          f"{r.interaction_r2:.4f}", f"{r.delta_r2:.4f}"] for _, r in good.iterrows()])
    lci_missing_items = prep.lci_df[[c for cols in LCI_SECTIONS.values() for c in cols]].isna()
    validation = result.baseline_validation
    max_diff = validation.absolute_difference.max()
    passed = bool(validation.passed.all())
    missing_table = markdown_table(
        ["Domain", "N (+ / non+)", "Missing outcome", "Missing predictors", "Complete-case exclusions", "Status"],
        [[r.outcome, f"{r.n} ({r.n_positive} / {r.n_nonpositive})", r.n_missing_outcome,
          r.n_missing_predictors, r.n_excluded_complete_case, r.status] for _, r in t.iterrows()])
    robustness = markdown_table(
        ["Domain", "HC3 p", "HC3 q", "Cook flags", "Max |DFBETAS|", "Deletion β range", "Deletion p range", "Sign flips"],
        [[r.outcome, f"{r.interaction_hc3_p:.4f}", f"{r.interaction_hc3_q:.4f}",
          int(r.n_cooks_gt_4_over_n), f"{r.max_abs_interaction_dfbetas:.3f}",
          f"[{r.loo_beta_min:.4f}, {r.loo_beta_max:.4f}]", f"[{r.loo_p_min:.4f}, {r.loo_p_max:.4f}]",
          int(r.loo_sign_changes)] for _, r in good.iterrows()])
    sensitivity = markdown_table(
        ["Domain", "Unadjusted β [95% CI]", "p", "q (separate family)", "ΔR²"],
        [[r.outcome, f"{r.interaction_beta:.4f} [{r.interaction_ci_low:.4f}, {r.interaction_ci_high:.4f}]",
          f"{r.interaction_p:.4f}", f"{r.interaction_q:.4f}", f"{r.delta_r2:.4f}"]
         for _, r in u.loc[u.status == "ok"].iterrows()])
    noteworthy = good.loc[good.interaction_p < .05]
    findings = []
    for _, r in noteworthy.iterrows():
        ur = u.set_index("outcome").loc[r.outcome]
        findings.append(
            f"For **{r.outcome}**, the slope difference is {r.interaction_beta:.4f} "
            f"LCI-R points per Greyson point (95% CI {r.interaction_ci_low:.4f} to {r.interaction_ci_high:.4f}; "
            f"p={r.interaction_p:.4f}, q={r.interaction_q:.4f}). The non-positive slope is "
            f"{r.slope_nonpositive:.4f} [{r.slope_nonpositive_ci_low:.4f}, {r.slope_nonpositive_ci_high:.4f}], "
            f"and the positive slope is {r.slope_positive:.4f} "
            f"[{r.slope_positive_ci_low:.4f}, {r.slope_positive_ci_high:.4f}]. "
            f"These are descriptive slopes within the interaction model, not new primary main-effect tests. "
            f"R² rises from {r.baseline_r2:.4f} to {r.interaction_r2:.4f}: "
            f"ΔR²={r.delta_r2:.4f}, or {100*r.delta_r2:.2f} percentage points. "
            f"HC3 gives p={r.interaction_hc3_p:.4f}, q={r.interaction_hc3_q:.4f}. "
            f"Deleting each observation in turn yields β from {r.loo_beta_min:.4f} to {r.loo_beta_max:.4f} "
            f"and raw p from {r.loo_p_min:.4f} to {r.loo_p_max:.4f}; "
            f"there are {int(r.loo_sign_changes)} sign reversals. "
            f"The unadjusted estimate on the same sample is {ur.interaction_beta:.4f} "
            f"(p={ur.interaction_p:.4f}, q={ur.interaction_q:.4f}).")
    remaining = good.loc[good.interaction_p >= .05]
    if len(remaining):
        findings.append(f"In the other {len(remaining)} domains, raw p ranges from "
                        f"{remaining.interaction_p.min():.4f} to {remaining.interaction_p.max():.4f}, "
                        f"and ΔR² ranges from {remaining.delta_r2.min():.4f} to {remaining.delta_r2.max():.4f}.")
    plots = "\n\n".join(f"![Illustrative {d} prediction]({name})" for d, name in images.items())
    narrowest = (good.interaction_ci_high-good.interaction_ci_low).min() if len(good) else np.nan
    widest = (good.interaction_ci_high-good.interaction_ci_low).max() if len(good) else np.nan
    ctx = [c for c in eligible if c.startswith("death_context_nature_")]
    positive_tails = desc.loc[desc.valence == "Positive", "n_outside_overlap_range"].iloc[0]
    cohort_by_original = eligible.groupby("valence")[INTENSITY].agg(["count", "mean", "std", "min", "max"])
    subgroups = markdown_table(["Original valence", "N", "Mean (SD)", "Range"], [
        [label, int(r['count']), f"{r['mean']:.2f} ({r['std']:.2f})", f"{r['min']:.0f}–{r['max']:.0f}"]
        for label, r in cohort_by_original.iterrows()])
    support_text = (f"The common observed intensity range is {desc.overlap_min.iloc[0]:.0f}–"
                    f"{desc.overlap_max.iloc[0]:.0f}, with {desc.n_shared_discrete_values.iloc[0]} exact "
                    f"intensity values represented in both groups. {positive_tails} positive participants "
                    "lie outside the non-positive range. Range overlap does not guarantee comparable "
                    "covariate combinations or equally dense observations throughout that range.")
    fdr_count = int((good.interaction_q < .05).sum())
    min_q = good.interaction_q.min() if len(good) else np.nan
    interpretation = (f"{fdr_count} of ten adjusted interactions meet BH q<0.05 (smallest q={min_q:.4f}). "
                      "The estimates therefore provide no multiplicity-adjusted evidence that the intensity "
                      "association differs by binary valence in this dataset. This does not demonstrate "
                      "equal slopes or equivalence: the interaction intervals remain compatible with "
                      "potentially meaningful differences. The nominal Death finding warrants a cautious "
                      "description, rather than a claim of established moderation. These tests address "
                      "moderation; they do not re-establish the manuscript's comparison of the relative "
                      "importance of intensity and valence. No causal interpretation is supported."
                      if fdr_count == 0 and len(good) == 10 and passed else
                      "Review the domain-specific estimates and validation status before interpreting moderation; "
                      "non-estimable or non-reproduced baselines preclude an unqualified conclusion.")
    return f"""# Exploratory intensity × valence interaction analysis

## 1. Research question

Does the association between continuous non-affective Greyson intensity and each of ten LCI-R domain scores differ between Positive and Non-positive experiences? The reviewer is asking about moderation, which an additive model cannot test. This exploration informs a later team decision; it does not revise the manuscript or its primary analysis.

## 2. Data and feasibility

The local input has {len(raw)} rows; existing preprocessing retains {len(eligible)} after `TO_DROP` and valid-valence filtering ({len(raw)-len(eligible)} excluded). There are {positive} Positive and {nonpositive} Non-positive participants. Non-positive consists of {mixed} Mixed and {negative} Negative experiences ({100*mixed/nonpositive:.1f}% Mixed). Intensity below is in original score points.

{distribution}

{support_text}

{subgroups}

![Observed intensity overlap](intensity_overlap.png)

{missing_table}

There are {int(lci_missing_items.sum().sum())} missing item responses among {int(lci_missing_items.size)} LCI-R item cells, involving {int(lci_missing_items.any(axis=1).sum())} participants. Domain eligibility uses the existing threshold (at least half the items, rounded up); available eligible items are averaged. Missing domain scores and covariates are then handled by complete cases per domain, without imputation. Item missingness need not imply a missing domain. All {len(good)} fitted interaction designs are full rank; total single-deletion rank failures: {int(good.loo_rank_failures.sum()) if len(good) else 0}.

## 3. Methods

Existing `preprocess_data`, `LCI_SECTIONS`, `LCI_MAP`, education coding, and death-context dummy construction are reused unchanged. LCI-R item responses map from −2 (Strongly diminished) to +2 (Strongly increased); each domain is an unweighted mean. The ten domains include exploratory **Other**. The internal `Material Achievements` domain is displayed as **Worldly Achievement**, matching current reports. There is no intensity split or additional outcome recoding.

The intensity variable is **`{INTENSITY}`**. Existing preprocessing z-scores it; this analysis takes the same score from `analysis_pretransform_df` to express the coefficient per original Greyson point. Its eligible-cohort mean, **{result.intensity_center:.6f}**, is subtracted before fitting. This centering uses the entire preprocessed eligible cohort and stays fixed across domains and sensitivity models. The provided CSV does not include the original Greyson items, so the upstream construction of this supplied non-affective score cannot be independently re-audited here.

Let I be centered intensity, V=1 for Positive and V=0 for Mixed/Negative (Non-positive, the reference). For each domain Y, fit OLS:

- Baseline: `Y ~ I + V + age_first_NDE + CTQ_IM_SCORE + education_ord + dx_prior_NDE_Yes + sex_Male + death-context dummies`.
- Interaction: the same predictors plus `I:V`.

These preserve exactly the current adjusted specification: age at first NDE (already standardized by existing preprocessing), CTQ minimization/denial score (`CTQ_IM_SCORE`), ordinal education, prior diagnosis indicator, sex indicator and the existing death-context dummies. Education is coded 0=Other/no formal education, 1=primary, 2=secondary, 3=college/university, 4=graduate or higher. Diagnosis is Yes=1, otherwise 0; sex is Male=1, otherwise 0. The dummies are `{', '.join(ctx)}`; the observed reference is `no_death_context`. The intensity main effect is included once. Other continuous/ordinal covariates, including the diagnosis indicator, are mean-centered just as in the current adjusted fitter; sex and death-context dummies retain their existing coding. The existing minimum model N is {manifest['min_n_models']}.

The interaction coefficient β is the Positive slope **minus** the Non-positive slope per one original Greyson point. A negative β indicates a less positive (or more negative) slope in Positive experiences. The intensity main coefficient is the slope for Non-positive experiences; adding β gives the Positive slope. The valence coefficient is the adjusted group difference at mean intensity. The intercept describes Non-positive participants at centered covariate values, sex_Male=0 and the reference death context. These conditional terms are not a replacement for the original additive main-effect analysis.

The primary test is a two-sided OLS t test of β=0, with residual degrees of freedom and a pointwise 95% CI. It is checked against the one-degree-of-freedom nested F test. **BH FDR corrects the ten interaction p-values together**; q<0.05 is the reporting threshold. ΔR² is interaction-model minus baseline ordinary R² on identical observations; it is in-sample improvement, not validated predictive gain. CIs are not adjusted for multiplicity.

Focused sensitivity checks include HC3 heteroskedasticity-robust intervals and t tests on the same fitted coefficients, plus an unadjusted interaction fit on the *same adjusted-model sample*. Each sensitivity's ten p-values form a separate BH family; they do not enlarge or replace the prespecified primary family. Influence screening uses Cook's D>4/N, leverage>2k/N (k includes the intercept), and |interaction DFBETAS|>2/√N as descriptive flags, followed by one-case-at-a-time refits. No observations are removed from the reported estimates, and deletion p-values are diagnostic, not independent hypothesis tests.

Baseline validation: **{'PASS' if passed else 'FAIL'}**, {len(validation)} numerical comparisons, maximum absolute difference **{max_diff:.3g}**. `baseline_validation.csv` compares all numeric fields reproduced by the existing adjusted fitter against `outputs/latest/main/tables/lci_adjusted_full_models.csv`, then checks baseline N, R², intercept, valence coefficient/p, AIC and BIC after the raw-intensity reparameterization. Differences within 1e-8 absolute/relative tolerance are numerical rounding or library arithmetic, not a specification discrepancy. Baseline and interaction row indices are asserted identical for every model, and the unadjusted sensitivity receives those same rows.

## 4. Results

{compact}

{' '.join(findings)}

![Adjusted interaction coefficients and pointwise confidence intervals](interaction_coefficients.png)

Illustrative prediction plots are generated only for domains with raw interaction p<0.05. This selection is descriptive, not evidence of FDR significance. Curves average the model over the same observed covariate distribution for both groups, are restricted to the common observed intensity range, and use pointwise confidence intervals for the estimated mean (not individual prediction intervals). Faint points are unadjusted observations. The CSV stores the plotted predictions.

{plots or 'No domain met the descriptive plotting criterion.'}

### Focused robustness checks

{robustness}

Cook flags concern overall model influence; interaction DFBETAS and deletion ranges specifically assess the moderation estimate. `influence_diagnostics.csv` records each diagnostic by input data row (one-based, excluding the header), without copying response identifiers. Flagged cases remain in all reported fits.

Across the adjusted designs, there are {int(good.design_columns.iloc[0]) if len(good) else 0} fitted parameters including the intercept, with {int(good.residual_df.iloc[0]) if len(good) else 0} residual degrees of freedom. The condition number is {good.condition_number.max() if len(good) else float('nan'):.2f}; maximum leverage is {good.max_leverage.max() if len(good) else float('nan'):.3f}. Cook-flag counts range from {int(good.n_cooks_gt_4_over_n.min()) if len(good) else 0} to {int(good.n_cooks_gt_4_over_n.max()) if len(good) else 0}. Worldly Achievement and Religiosity show {int(good.set_index('outcome').loc['Worldly Achievement', 'loo_sign_changes']) if 'Worldly Achievement' in set(good.outcome) else 0} and {int(good.set_index('outcome').loc['Religiosity', 'loo_sign_changes']) if 'Religiosity' in set(good.outcome) else 0} deletion sign reversals, respectively; their intervals already span zero. These flags identify sensitivity, not grounds for automatic exclusion.

{sensitivity}

## 5. Interpretation

{interpretation}

## 6. Limitations

Group sizes are {positive}:{nonpositive} (ratio {positive/nonpositive:.2f}:1), and intensity variability is lower in Non-positive experiences (SD {desc.loc[desc.valence == 'Non-positive', 'sd'].iloc[0]:.2f} versus {desc.loc[desc.valence == 'Positive', 'sd'].iloc[0]:.2f}). The slope difference is consequently less precisely informed by that group. Non-positive is {100*mixed/nonpositive:.1f}% Mixed, with only {negative} Negative cases; the analysis cannot establish moderation specific to clearly negative experiences. There is no Non-positive support beyond its {desc.loc[desc.valence == 'Non-positive', 'min'].iloc[0]:.0f}–{desc.loc[desc.valence == 'Non-positive', 'max'].iloc[0]:.0f} range, and the {positive_tails} Positive observations outside common support still contribute to the full-sample linear fit.

Adjusted interaction CI widths span {narrowest:.4f}–{widest:.4f} LCI-R points per intensity point. No equivalence margin was specified or tested. Domain averages are bounded [−2, 2]; OLS assumes a linear conditional mean and independent observations. HC3 addresses sensitivity of standard errors to heteroskedasticity, not nonlinear mean structure, selection bias or unmeasured confounding. Marginal range overlap does not establish joint covariate overlap. The ten domains are measured in the same people and are correlated; BH is applied as requested, without claiming arbitrary-dependence guarantees. **Other** remains exploratory, and all interaction analyses were prompted after the original analysis. Item scoring and exclusions inherit the existing preprocessing, including its indicator handling; original covariates have no missing values in this input. No external or out-of-sample validation is performed.

## 7. Decision considerations

Arguments for reporting: the analysis directly addresses the reviewer's moderation question, reproduces the additive baseline to {max_diff:.3g} maximum absolute difference, and adds only one prespecified term per domain on matched samples. Reporting all ten estimates, intervals, q-values and ΔR² would expose both the nominal Death pattern and the precision limits, without changing the original primary analysis.

Arguments for restraint: only {nonpositive} participants inform the Non-positive slope, {mixed} of whom are Mixed; {'no adjusted interaction survives' if fdr_count == 0 else str(fdr_count)+' adjusted interactions survive'} correction across ten domains. The nominal finding is selected from a post-review exploratory family, and the interaction intervals do not establish equivalence. The influence and unadjusted tables quantify sensitivity and should accompany any selected example. ΔR² is an in-sample statistic and cannot establish predictive or clinical usefulness.

These are decision considerations for the research team, not an automatic recommendation to add the analysis. No manuscript edits or reviewer response were produced.

Reproduction from the repository root:

```bash
../../.venv/bin/python scripts/run_intensity_valence_interaction.py
../../.venv/bin/python -m pytest tests/test_intensity_valence_interaction.py -q
```

All generated files are confined to `outputs/exploratory/intensity_valence_interaction/` by default. `run_manifest.json` records input/config/source hashes, base commit, package versions and protection checks. Repeated-run equality is checked separately in `reproducibility_check.json`. Existing tracked files and all `outputs/latest/main/` contents are fingerprinted before and after execution; changed protected files trigger an error. The main CLI is never invoked.

Implementation references: [statsmodels OLS/HC3](https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.OLSResults.html), [influence diagnostics](https://www.statsmodels.org/stable/generated/statsmodels.stats.outliers_influence.OLSInfluence.html), and [multiple testing](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html). These describe the implementation; all numerical conclusions above come from the local data.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/default.yaml")
    parser.add_argument("--data-path", type=Path)
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "outputs/exploratory/intensity_valence_interaction")
    args = parser.parse_args()
    output = safe_output_dir(args.output_dir)
    protected = protected_hashes(output)
    cfg = load_config(args.config)
    data_path = args.data_path or cfg.data_path
    if not data_path.is_absolute():
        data_path = ROOT / data_path
    data_path = data_path.resolve()
    baseline_path = ROOT / "outputs/latest/main/tables/lci_adjusted_full_models.csv"
    raw = load_csv(data_path)
    prep = preprocess_data(raw, lci_min_valid_fraction=cfg.analysis.lci_min_valid_fraction)
    result = analyze(prep, pd.read_csv(baseline_path), min_n=cfg.analysis.min_n_models)
    output.mkdir(parents=True, exist_ok=True)
    for name, table in {
        "interaction_results.csv": result.results,
        "unadjusted_sensitivity.csv": result.unadjusted,
        "intensity_distribution_by_domain.csv": result.feasibility,
        "influence_diagnostics.csv": result.influence,
        "model_coefficients.csv": result.coefficients,
        "baseline_validation.csv": result.baseline_validation,
    }.items():
        table.to_csv(output / name, index=False)
    pd.DataFrame(describe_sample(prep.analysis_pretransform_df, "Eligible cohort")).to_csv(
        output / "intensity_distribution_eligible.csv", index=False)
    plot_coefficients(result, output, cfg.plot.dpi)
    plot_overlap(prep, output, cfg.plot.dpi)
    images = {r.outcome: predicted_plot(result, r.outcome, output, cfg.plot.dpi)
              for _, r in result.results.iterrows()
              if r.status == "ok" and r.interaction_p < cfg.analysis.alpha}
    sources = sorted((ROOT / "src/nde_analysis").rglob("*.py")) + [Path(__file__).resolve()]
    manifest = {
        "analysis": "Exploratory intensity x valence interaction",
        "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT).decode().strip(),
        "base_commit": subprocess.check_output(["git", "merge-base", "HEAD", "main"], cwd=ROOT).decode().strip(),
        "input": str(data_path), "input_sha256": digest(data_path),
        "config_sha256": digest(args.config), "saved_baseline_sha256": digest(baseline_path),
        "source_sha256": {str(p.relative_to(ROOT)): digest(p) for p in sources},
        "python": platform.python_version(),
        "packages": {p: importlib.metadata.version(p) for p in
                     ("numpy", "pandas", "scipy", "statsmodels", "matplotlib", "pytest")},
        "intensity_center": result.intensity_center, "family_size": 10,
        "min_n_models": cfg.analysis.min_n_models,
        "lci_min_valid_fraction": cfg.analysis.lci_min_valid_fraction,
        "baseline_validation_passed": bool(result.baseline_validation.passed.all()),
        "protected_files": protected,
    }
    (output / "interaction_analysis_report.md").write_text(
        report(result, prep, raw, output, images, manifest), encoding="utf-8")
    after = protected_hashes(output)
    changed = sorted(p for p in set(protected) | set(after) if protected.get(p) != after.get(p))
    manifest["protected_files_unchanged"] = not changed
    manifest["changed_protected_files"] = changed
    (output / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if changed:
        raise RuntimeError(f"Protected files changed: {changed}")
    print(result.results[["outcome", "n", "interaction_beta", "interaction_p",
                          "interaction_q", "delta_r2"]].to_string(index=False))
    print(f"Report: {output / 'interaction_analysis_report.md'}")
    if not manifest["baseline_validation_passed"]:
        raise RuntimeError("Baseline validation failed; inspect report and validation CSV before interpretation")


if __name__ == "__main__":
    main()
