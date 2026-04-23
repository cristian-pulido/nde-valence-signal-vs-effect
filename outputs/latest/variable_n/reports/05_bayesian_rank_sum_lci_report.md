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
- Dataset version: Variable-N (available-case per outcome)

## 3. Results

### Summary table

```
               variable  n_positive  n_non_positive  bf01           interpretation
   Appreciation of Life          96              33 2.689             inconclusive
     Concern for Others          96              33 0.147 moderate evidence for H1
                  Death          96              33 3.526 moderate evidence for H0
  Material Achievements          96              33 0.000   strong evidence for H1
        Meaning/Purpose          96              33 3.691 moderate evidence for H0
                  Other          96              33 1.073             inconclusive
            Religiosity          96              33 3.084 moderate evidence for H0
        Self-Acceptance          96              33 4.119 moderate evidence for H0
Social/Planetary Values          96              33 2.092             inconclusive
           Spirituality          95              33 1.700             inconclusive
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
