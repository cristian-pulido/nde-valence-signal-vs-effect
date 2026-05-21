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
- Dataset version: Main analysis

## 3. Results

### Summary table

```
               variable  n_positive  n_non_positive  bf01           interpretation
   Appreciation of Life          90              32 3.275 moderate evidence for H0
     Concern for Others          90              32 0.949             inconclusive
                  Death          90              32 4.429 moderate evidence for H0
  Material Achievements          90              32 0.031   strong evidence for H1
        Meaning/Purpose          90              32 3.267 moderate evidence for H0
                  Other          90              32 1.793             inconclusive
            Religiosity          90              32 3.122 moderate evidence for H0
        Self-Acceptance          90              32 4.190 moderate evidence for H0
Social/Planetary Values          90              32 1.678             inconclusive
           Spirituality          90              32 3.700 moderate evidence for H0
```

### Aggregated summary

```
                    metric  value
 % variables with BF01 > 3   60.0
% variables with BF01 > 10    0.0
            % inconclusive   30.0
```

## 4. Interpretation

Across 10 outcomes, 6 showed BF01 > 3 and 0 showed BF01 > 10. Here, H0 means no difference between Positive and Non-positive groups, and H1 means a difference exists. These patterns indicate evidence consistent with no meaningful differences for a subset of outcomes, while remaining outcomes are inconclusive where BF01 is near 1. Frequentist Mann-Whitney tests were FDR-significant for 0/10 outcomes. Non-significant p-values alone are not evidence for no effect; BF01 quantifies this directly.
