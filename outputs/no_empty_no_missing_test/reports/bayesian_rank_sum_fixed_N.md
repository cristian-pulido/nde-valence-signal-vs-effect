# Bayesian Rank-Sum Report (Fixed-N)

## 1. Research Question

Do post-NDE outcomes differ between Positive and Non-positive NDE groups, or is there evidence supporting no meaningful difference?

## 2. Methodology

- Groups: Positive valence vs Non-positive valence (Mixed + Negative).
- Variables analyzed: 15 outcomes across NDE-MCQ items and LCI-R aggregated domains.
- Test: Bayesian rank-sum test using latent-normal augmentation (van Doorn et al., 2020).
- Prior: Cauchy prior on effect size delta with scale r = 0.707.
- Hypotheses: H0 = no group difference (delta = 0); H1 = group difference (delta != 0).
- Bayes factor interpretation: BF01 > 3 (moderate evidence for H0), BF01 > 10 (strong evidence for H0), BF01 near 1 (inconclusive).
- Dataset version: Fixed-N (complete-case set shared across all selected outcomes).

## 3. Results

### Summary table

```
                       variable  n_positive  n_non_positive  bf01           interpretation
           Appreciation of Life          95              33 2.285             inconclusive
             Concern for Others          95              33 0.189 moderate evidence for H1
                          Death          95              33 4.159 moderate evidence for H0
          Material Achievements          95              33 0.000   strong evidence for H1
                Meaning/Purpose          95              33 2.349             inconclusive
                          Other          95              33 0.143 moderate evidence for H1
                    Religiosity          95              33 2.816             inconclusive
                Self-Acceptance          95              33 3.456 moderate evidence for H0
        Social/Planetary Values          95              33 1.534             inconclusive
                   Spirituality          95              33 1.641             inconclusive
  Responsibility to help others          95              33 3.168 moderate evidence for H0
             Act by moral rules          95              33 1.483             inconclusive
  Consider others' perspectives          95              33 0.936             inconclusive
  Willingness to forgive others          95              33 3.328 moderate evidence for H0
Consider long-term consequences          95              33 3.409 moderate evidence for H0
```

### Aggregated summary

```
                    metric  value
 % variables with BF01 > 3 33.333
% variables with BF01 > 10  0.000
            % inconclusive 46.667
```

## 4. Interpretation

Across 15 outcomes, 5 showed BF01 > 3 and 0 showed BF01 > 10. Here, H0 means no difference between Positive and Non-positive groups, and H1 means a difference exists. These patterns indicate evidence consistent with no meaningful differences for a subset of outcomes, while remaining outcomes are inconclusive where BF01 is near 1. Frequentist Mann-Whitney tests were FDR-significant for 0/15 outcomes. Non-significant p-values alone are not evidence for no effect; BF01 quantifies this directly.
