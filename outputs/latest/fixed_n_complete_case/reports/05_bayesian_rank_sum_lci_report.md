# Bayesian Rank-Sum Report (LCI)

## 1. Research Question

Do post-NDE outcomes differ between Positive and Non-positive NDE groups, or is there evidence supporting no meaningful difference?

## 2. Methodology

- Groups: Positive valence vs Non-positive valence (Mixed + Negative).
- Variables analyzed: 10 outcomes across LCI-R aggregated domains.
- Test: Bayesian rank-sum test using latent-normal augmentation (van Doorn et al., 2020).
- Prior: Cauchy prior on effect size delta with scale r = 0.707.
- Hypotheses: H0 = no group difference (delta = 0); H1 = group difference (delta != 0).
- Bayes factor interpretation: BF01 > 3 (moderate evidence for H0), BF01 > 10 (strong evidence for H0), BF01 near 1 (inconclusive).
- Dataset version: Fixed-N complete-case (rows with missing values removed upfront)

## 3. Results

### Summary table

```
               variable  n_positive  n_non_positive  bf01           interpretation
   Appreciation of Life          90              29 3.487 moderate evidence for H0
     Concern for Others          90              29 0.228 moderate evidence for H1
                  Death          90              29 3.261 moderate evidence for H0
  Material Achievements          90              29 0.026   strong evidence for H1
        Meaning/Purpose          90              29 2.704             inconclusive
                  Other          90              29 0.343             inconclusive
            Religiosity          90              29 3.652 moderate evidence for H0
        Self-Acceptance          90              29 3.612 moderate evidence for H0
Social/Planetary Values          90              29 0.936             inconclusive
           Spirituality          90              29 2.830             inconclusive
```

### Aggregated summary

```
                    metric  value
 % variables with BF01 > 3   40.0
% variables with BF01 > 10    0.0
            % inconclusive   40.0
```

## 4. Interpretation

Across 10 outcomes, 4 showed BF01 > 3 and 0 showed BF01 > 10. Here, H0 means no difference between Positive and Non-positive groups, and H1 means a difference exists. These patterns indicate evidence consistent with no meaningful differences for a subset of outcomes, while remaining outcomes are inconclusive where BF01 is near 1. Frequentist Mann-Whitney tests were FDR-significant for 0/10 outcomes. Non-significant p-values alone are not evidence for no effect; BF01 quantifies this directly.
