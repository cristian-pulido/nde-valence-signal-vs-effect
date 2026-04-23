# NDE Multivariate Analysis Pipeline

This repository provides a complete command-line workflow to analyze near-death experience (NDE) data for publication-ready statistical reporting.

The pipeline answers two main analytical questions:

1. Which demographic, psychological, and experiential variables independently predict NDE valence?
2. How do post-NDE life-change outcomes behave globally, by valence group, and after covariate adjustment?

## Direct access to latest article results

For reviewers, the most recent analysis outputs reported in the article are available under:

- [`outputs/latest/variable_n/reports/`](outputs/latest/variable_n/reports/)
- [`outputs/latest/fixed_n_complete_case/reports/`](outputs/latest/fixed_n_complete_case/reports/)

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
  - LCI-R section scores: Wilcoxon and valence-group Mann-Whitney tests
  - Multiple testing control with Benjamini-Hochberg FDR correction within each hypothesis family
  - Bayesian rank-sum inference in two modes:
    - Variable-N (available-case per outcome)
    - Fixed-N complete-case (rows with any missing selected outcomes removed before testing)
- **Post-NDE effects: adjusted analyses**
  - Full model: `outcome ~ valence_binary + covariates`
  - Covariates-only model: `outcome ~ covariates`
  - Comparison metrics: Delta R², Delta AIC, Delta BIC, FDR-adjusted valence tests, and interpretation per outcome
- **Covariate diagnostics for model plausibility**
  - Distribution overlap plots
  - Group balance tests by valence with FDR correction across tests
  - Sex composition by valence
- **Intercept-focused visualizations**
  - Baseline outcome levels (full vs covariates-only) for LCI adjusted models

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

This includes valence modeling, LCI post-effects/adjusted diagnostics, and both Bayesian rank-sum variants.

### Valence module only

```bash
nde-analysis run-valence --config configs/default.yaml --output-dir ../../DATA/Results
```

### Post-effects module only (LCI + adjusted models + diagnostics)

```bash
nde-analysis run-post-effects --config configs/default.yaml --output-dir ../../DATA/Results
```

This also runs both Bayesian rank-sum variants.

## Output structure

Each habitual run writes two fully separated analysis trees:

- `<output-dir>/variable_n/{figures,tables,reports}`
- `<output-dir>/fixed_n_complete_case/{figures,tables,reports}`

All figures are exported as PNG.

## Reports generated

- `reports/00_run_summary.md`
- `reports/01_valence_multivariate_report.md`
- `reports/02_post_effects_lci_report.md`
- `reports/03_adjusted_models_comparison_report.md`
- `reports/04_covariate_diagnostics_report.md`
- `reports/05_bayesian_rank_sum_lci_report.md`

Bayesian rank-sum tables are written to:

- `tables/bayesian_rank_sum_lci.csv`

Reports include methodology, key tables, embedded figures, and interpretation blocks.

## Key modeling details

- **Valence recoding:** `Positive = 1`, `Mixed/Negative = 0`
- **LCI coding:** ordinal labels mapped to numeric change scores
- **ERQ scoring:** reappraisal and suppression subscales derived from item means
- **Missingness handling:** complete-case per model/outcome
- **Covariate diagnostics sample:** complete-case intersection over balance covariates (`valence_binary`, `sex_Male`, `age`, `CTQ_IM_SCORE`, `ADHD_SCALE`, `ERQ_reappraisal`, `ERQ_suppression`, `education_ord`)
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
