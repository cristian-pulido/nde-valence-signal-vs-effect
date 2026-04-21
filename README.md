# NDE Multivariate Analysis Pipeline

This repository provides a complete command-line workflow to analyze near-death experience (NDE) data for publication-ready statistical reporting.

The pipeline answers two main analytical questions:

1. Which demographic, psychological, and experiential variables independently predict NDE valence?
2. How do post-NDE outcomes (moral cognition and life changes) behave globally, by valence group, and after covariate adjustment?

## Direct access to latest article results

For reviewers, the most recent analysis outputs reported in the article are available directly at [`outputs/latest/reports/`](outputs/latest/reports/)

## Analytical scope

The workflow includes:

- **Valence modeling** (binary logistic regression; hierarchical models)
  - Model 1: demographics
  - Model 2: demographics + psychological predictors
  - Model 3: demographics + psychological + experiential predictor
- **Collinearity and dependency diagnostics**
  - Variance Inflation Factor (VIF), including `valence_binary`
  - Spearman correlation heatmap across predictors
- **Post-NDE effects: unadjusted analyses**
  - NDE-MCQ (5 outcomes): Wilcoxon and valence-group Mann-Whitney tests
  - LCI-R section scores: Wilcoxon and valence-group Mann-Whitney tests
  - Multiple testing control with Benjamini-Hochberg FDR correction within each hypothesis family
- **Post-NDE effects: adjusted analyses**
  - Full model: `outcome ~ valence_binary + covariates`
  - Covariates-only model: `outcome ~ covariates`
  - Comparison metrics: Delta R², Delta AIC, Delta BIC, FDR-adjusted valence tests, and interpretation per outcome
- **Covariate diagnostics for model plausibility**
  - Distribution overlap plots
  - Group balance tests by valence with FDR correction across tests
  - Sex composition by valence
- **Intercept-focused visualizations**
  - Baseline outcome levels (full vs covariates-only) for MCQ and LCI adjusted models

## Data input

- Default input file: `../../DATA/data_for_model.csv`
- Input is expected to be preprocessed survey data with all required columns.
- The pipeline validates required variables and raises explicit errors for missing columns.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## How to run

### Full analysis

```bash
nde-analysis run-all --config configs/default.yaml --output-dir ../../DATA/Results
```

### Valence module only

```bash
nde-analysis run-valence --config configs/default.yaml --output-dir ../../DATA/Results
```

### Post-effects module only (MCQ + LCI + adjusted models + diagnostics)

```bash
nde-analysis run-post-effects --config configs/default.yaml --output-dir ../../DATA/Results
```

## Output structure

Each run writes to:

- `<output-dir>/figures`
- `<output-dir>/tables`
- `<output-dir>/reports`

All figures are exported as PNG.

## Reports generated

- `reports/00_run_summary.md`
- `reports/01_valence_multivariate_report.md`
- `reports/02_post_effects_mcq_report.md`
- `reports/03_post_effects_lci_report.md`
- `reports/04_adjusted_models_comparison_report.md`
- `reports/05_covariate_diagnostics_report.md`

Reports include methodology, key tables, embedded figures, and interpretation blocks.

## Key modeling details

- **Valence recoding:** `Positive = 1`, `Mixed/Negative = 0`
- **MCQ/LCI coding:** ordinal labels mapped to numeric change scores
- **ERQ scoring:** reappraisal and suppression subscales derived from item means
- **Missingness handling:** complete-case per model/outcome
- **Multiple testing correction:** Benjamini-Hochberg FDR (`fdr_bh`, alpha=0.05) applied to families of related p-values
- **Adjusted model covariates:**
  - Continuous/ordinal: `age`, `CTQ_IM_SCORE`, `ADHD_SCALE`, `ERQ_reappraisal`, `ERQ_suppression`, `education_ord`, `greyson_total_no_affective`
  - Categorical: `sex_Male`

## Statistical output columns

- Raw p-values are kept as `p_value` (or model-specific names like `effect_p_value`).
- FDR-adjusted p-values are added as `<p_column>_fdr`.
- FDR significance flags are added as `<p_column>_fdr_reject` (`True`/`False`).

## Configuration

Runtime options are defined in `configs/default.yaml`, including:

- input data path
- output directories
- figure format and DPI
- minimum sample size per model
- LCI valid-answer threshold
- significance alpha
- random seed

CLI options can override config paths, especially `--output-dir`.
