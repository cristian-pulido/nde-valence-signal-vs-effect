# Covariate Diagnostics Report

## Purpose

Evaluate covariate overlap and group balance between positive and non-positive valence groups before adjusted outcome modeling.

## Methodology

- Continuous and ordinal covariates: Mann-Whitney U tests.
- Categorical covariate (`sex_Male`): chi-square test.
- Analysis sample: complete-case intersection across `valence_binary`, `sex_Male`, `age`, `CTQ_IM_SCORE`, `ADHD_SCALE`, `ERQ_reappraisal`, `ERQ_suppression`, and `education_ord`.
- Multiple-testing control: Benjamini-Hochberg FDR correction across balance tests.
- Visual diagnostics:
  - KDE overlap by valence
  - box/strip distributions by valence
  - sex distribution bar chart

## Overall Descriptive Statistics (Pre-Transformation)

```
       variable   n   mean    std
            age 143 60.797 13.078
   CTQ_IM_SCORE 143 24.748  7.755
     ADHD_SCALE 143 26.671 13.056
ERQ_reappraisal 143  4.696  1.112
ERQ_suppression 143  3.390  1.321
  education_ord 143  2.839  0.819
```

### Categorical Variable Summary

```
variable          top_category  top_pct   n
sex_Male Female/other baseline    60.14 143
```

## Descriptive Summary by Valence

```
       variable      valence  count   mean   std  median    min    max
            age Non-positive     35  0.118 1.080   0.016 -2.198  2.536
            age     Positive    108 -0.038 0.973   0.207 -2.962  1.848
   CTQ_IM_SCORE Non-positive     35 23.657 7.700  21.000 14.000 42.000
   CTQ_IM_SCORE     Positive    108 25.102 7.776  23.000 14.000 48.000
     ADHD_SCALE Non-positive     35  0.167 0.859   0.254 -1.866  1.693
     ADHD_SCALE     Positive    108 -0.052 1.025  -0.276 -1.866  2.753
ERQ_reappraisal Non-positive     35 -0.266 1.089  -0.035 -2.724  1.757
ERQ_reappraisal     Positive    108  0.074 0.956   0.263 -2.873  2.055
ERQ_suppression Non-positive     35  0.053 1.041   0.091 -1.812  1.995
ERQ_suppression     Positive    108 -0.007 0.999   0.091 -1.812  1.995
  education_ord Non-positive     35  2.657 0.968   3.000  0.000  4.000
  education_ord     Positive    108  2.898 0.760   3.000  0.000  4.000
```

## Balance Tests

```
       variable               type  p_value  mean_positive  mean_non_positive  p_value_fdr p_value_fdr_reject
ERQ_reappraisal continuous/ordinal    0.111          0.074             -0.266        0.424                 No
     ADHD_SCALE continuous/ordinal    0.121         -0.052              0.167        0.424                 No
   CTQ_IM_SCORE continuous/ordinal    0.288         25.102             23.657        0.504                 No
  education_ord continuous/ordinal    0.259          2.898              2.657        0.504                 No
            age continuous/ordinal    0.697         -0.038              0.118        0.907                 No
ERQ_suppression continuous/ordinal    0.778         -0.007              0.053        0.907                 No
       sex_Male        categorical    1.000          0.398              0.400        1.000                 No
```

## Figures

![Covariate KDE overlap](../figures/covariates_overlap_kde_by_valence.png)

![Covariate box/strip distributions](../figures/covariates_boxstrip_by_valence.png)

![Sex distribution by valence](../figures/covariates_sex_distribution_by_valence.png)

## Interpretation

0 covariates were imbalanced at FDR-adjusted p<0.05 and 0 at FDR-adjusted p<0.10. Distribution overlap plots and balance tests jointly support whether adjusted analysis is plausible.