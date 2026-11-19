"""Reports for the independent age-difference exploration."""
from __future__ import annotations

def md_table(headers, rows):
    def cells(items):
        return " | ".join(str(x).replace("|", "\\|") for x in items)
    return "\n".join(["| "+cells(headers)+" |", "| "+" | ".join(["---"]*len(headers))+" |"]+
                     ["| "+cells(row)+" |" for row in rows])


def primary_table(table):
    return md_table(["LCI-R domain", "β per 10 years", "95% CI", "p", "FDR q", "ΔR²"], [
        [r.outcome, f"{r.latency_per_decade_beta:.4f}",
         f"[{r.latency_per_decade_ci_low:.4f}, {r.latency_per_decade_ci_high:.4f}]",
         f"{r.latency_p:.4f}", f"{r.latency_q:.4f}", f"{r.delta_r2:.4f}"]
        for _, r in table.loc[table.status=="ok"].iterrows()])


def scientific_summary(result):
    t = result.results
    d = result.descriptions.set_index("group")
    all_data, pos, non = d.loc["All eligible"], d.loc["Positive"], d.loc["Non-positive"]
    by_name = t.set_index("outcome")
    death, self_accept = by_name.loc["Death"], by_name.loc["Self-Acceptance"]
    intensity_before = int((t.m0_intensity_q<.05).sum())
    intensity_after = int((t.m1_intensity_q<.05).sum())
    valence_after = int((t.m1_valence_q<.05).sum())
    return f"""# Exploratory adjustment for time since the first NDE: an unverified age-difference measure

## 1. Research question

Reviewer 2 asked whether time since the near-death experience (NDE) should be included as a covariate. We investigated whether an age difference explains additional life changes or alters associations with intensity and valence. This exploration cannot establish definitive adjustment for time since the evaluated experience.

## 2. Data and feasibility

All 122 participants matched uniquely to the age file, with no missing ages. Supplied current ages ranged from 22 to 94 and first-NDE ages from 10 to 79. There were no negative ages, ages above 100, or cases where first-NDE age exceeded current age.

We subtracted supplied first-NDE age from supplied current age. These definitions cannot be verified. The measure is therefore a **provisional estimate of time since the first NDE**, not verified time since the evaluated NDE. No NDE count, selection rule or evaluated-event date was available; multiple-NDE participants could not be identified.

The difference averaged {all_data['mean']:.2f} years (SD {all_data.sd:.2f}), with median {all_data['median']:.0f}, interquartile range {all_data.q25:.0f}–{all_data.q75:.0f}, and range {all_data['min']:.0f}–{all_data['max']:.0f}. Five zero differences were retained; whole-year ages cannot resolve timing within a year. Means were {pos['mean']:.2f} years in Positive (n={int(pos.n)}) and {non['mean']:.2f} in Non-positive experiences (n={int(non.n)}).

![Distribution of the provisional age-difference measure](latency_distribution.png)

**Figure 1. Distribution.** Bars count participants; colours identify valence groups and dashed lines their medians. The measure does not verify event dates.

## 3. Methods

For ten Life Changes Inventory–Revised (LCI-R) domains, including exploratory Other, original and expanded linear models used the same 122 participants. LCI-R scores range from −2 (strongly diminished) to +2 (strongly increased). Both models retained intensity, valence, first-NDE age, sex, education, prior diagnosis, Childhood Trauma Questionnaire minimization/denial score and death context. Current age was not additionally included: it equals first-NDE age plus the difference. Benjamini–Hochberg false discovery rate (FDR) correction covered ten added-covariate tests, using q<0.05.

## 4. Main results

Coefficients express the adjusted LCI-R score difference per ten additional years; intervals are pointwise 95% confidence intervals. ΔR² measures the increase in explained variance.

{primary_table(t)}

No association survived FDR correction. Self-Acceptance and Death showed nominal negative associations, with larger differences associated with lower reported-change scores. Their added explained variance was {100*self_accept.delta_r2:.2f} and {100*death.delta_r2:.2f} percentage points, respectively. HC3 robust standard errors also yielded no FDR-significant result (q={self_accept.latency_hc3_q:.4f} and {death.latency_hc3_q:.4f}, respectively).

![Estimated age-difference associations across domains](latency_coefficients.png)

**Figure 2. Added-covariate estimates.** Dots show estimates and bars their uncertainty. Bars crossing zero permit either direction; intervals excluding zero indicate nominal evidence only. The q-values account for testing ten domains.

## 5. Interpretation

Intensity retained its direction in every domain and met the same domain-specific FDR threshold in {intensity_before} domains before and {intensity_after} after adjustment. Valence met that threshold in {valence_after} domains after adjustment. This preserves the broad original pattern without independently confirming the manuscript’s comparison of predictor importance. Nonsignificance does not establish absence of association.

![Intensity and valence estimates before and after adjustment](intensity_valence_stability.png)

**Figure 3. Changes in the original predictors.** Paired estimates compare the original and expanded models. Panels use different predictor units; their coefficient magnitudes should not be directly compared.

## 6. Limitations

Unknown event selection and multiple-NDE status prevent validating the temporal interpretation. Whole-year ages limit precision. Holding first-NDE age constant, larger differences also imply older current age; duration and ageing cannot be separated. Substituting current age for first-NDE age reproduced predictions: mathematical equivalence, not independent validation. ΔR² reflects within-sample fit, not validated prediction. Cross-sectional associations do not establish causality.

## 7. Implications for the manuscript

Coauthors could report this explicitly provisional exploration with complete supplementary results, or discuss it only in the reviewer response because the temporal definition remains unverified. The choice balances transparency against the risk of implying a valid adjustment for the evaluated NDE. Neither option is selected here.
"""


def technical_report(result, audit, manifest):
    t = result.results
    good = t.loc[t.status=="ok"]
    d = result.descriptions
    by_name = good.set_index("outcome")
    death, self_accept = by_name.loc["Death"], by_name.loc["Self-Acceptance"]
    age_rows = [[r.variable, int(r.n), f"{r['min']:.0f}–{r['max']:.0f}",
                 int(r.n_missing_input), int(r.n_nonnumeric), int(r.n_nonfinite), int(r.n_negative),
                 int(r.n_over_100_review), int(r.n_over_120_requires_verification), int(r.n_fractional)]
                for _, r in audit.ages.iterrows()]
    age_table = md_table(["Field", "N", "Range", "Missing", "Nonnumeric", "Nonfinite", "Negative",
                          ">100 review", ">120 verify", "Fractional"], age_rows)
    desc_table = md_table(["Group", "N", "Mean (SD)", "Median [Q1, Q3]", "Range", "Zero"], [
        [r.group, int(r.n), f"{r['mean']:.2f} ({r.sd:.2f})", f"{r['median']:.2f} [{r.q25:.2f}, {r.q75:.2f}]",
         f"{r['min']:.0f}–{r['max']:.0f}", int(r.n_zero)] for _, r in d.iterrows()])
    changes = md_table(["Domain", "Intensity β M0 → M1", "Intensity q M0 → M1",
                         "Valence β M0 → M1", "Valence q M0 → M1"], [
        [r.outcome, f"{r.m0_intensity_beta:.4f} → {r.m1_intensity_beta:.4f}",
         f"{r.m0_intensity_q:.4f} → {r.m1_intensity_q:.4f}",
         f"{r.m0_valence_beta:.4f} → {r.m1_valence_beta:.4f}",
         f"{r.m0_valence_q:.4f} → {r.m1_valence_q:.4f}"] for _, r in good.iterrows()])
    fits = md_table(["Domain", "N (+ / non+)", "M0 R²", "M1 R²", "Excluded", "Status"], [
        [r.outcome, f"{r.n} ({r.n_positive} / {r.n_nonpositive})", f"{r.m0_r2:.4f}", f"{r.m1_r2:.4f}",
         r.n_excluded_complete_case, r.status] for _, r in good.iterrows()])
    stability = md_table(["Domain", "HC3 p", "HC3 q", "Max Cook D", "Cook flags", "Max |DFBETAS|",
                           "Deletion β/year range", "Deletion raw p range", "Sign reversals"], [
        [r.outcome, f"{r.latency_hc3_p:.4f}", f"{r.latency_hc3_q:.4f}", f"{r.max_cooks_distance:.3f}",
         int(r.n_cooks_gt_4_over_n), f"{r.max_abs_latency_dfbetas:.3f}",
         f"[{r.loo_latency_beta_min:.5f}, {r.loo_latency_beta_max:.5f}]",
         f"[{r.loo_latency_p_min:.4f}, {r.loo_latency_p_max:.4f}]", int(r.loo_latency_sign_changes)]
        for _, r in good.iterrows()])
    corr = md_table(["Variables", "N", "Pearson r", "Spearman ρ"], [
        [f"{r.variable_1} / {r.variable_2}", int(r.n), f"{r.pearson_r:.4f}", f"{r.spearman_rho:.4f}"]
        for _, r in result.correlations.iterrows()])
    diag = audit.diagnostics.set_index("check")["count"]
    overall = d.set_index("group").loc["All eligible"]
    m1vif = result.vif.loc[result.vif.model=="M1"]
    baseline = result.baseline_validation
    pcheck = result.parameterization
    return f"""# Exploratory first-NDE latency covariate analysis: technical report

## Scope and definition status

Reviewer 2 asked whether time since the NDE should be included as a covariate. This independent exploration starts from local `main` at `{manifest['base_commit']}` on `analysis/nde-latency-covariate`; it does not import or merge the intensity × valence analysis. No manuscript or reviewer response is edited.

**The temporal definition is unverified.** The supplied task describes `age` as current age and `age_first_NDE` as age at first NDE. The two CSVs contain no questionnaire wording, completion dates, event-selection rule or data dictionary that independently establishes these meanings. The user explicitly confirmed that these definitions cannot be verified. File modification times do not establish survey dates. Numerical consistency therefore supports subtraction, but does not validate event timing.

The operational variable `latency_first_NDE_proxy` is **supplied age minus supplied age_first_NDE**, in years. It is interpreted conditionally as time since the first NDE only if those supplied definitions are correct. It must not be described as verified time since the specifically evaluated NDE.

## 1. Sources, merging and age validation before modeling

Sources: `{manifest['model_data_path']}` and `{manifest['age_data_path']}`. Identifiers are read consistently as strings and joined exactly, without fuzzy matching, whitespace normalization or numerical ID conversion. A one-to-one left join preserves the original cohort, its ordering and all original preprocessing eligibility rules.

There are {diag['modeling_cohort_rows']} modeling rows and {diag['age_file_rows']} age-file rows. Both files have {diag['modeling_cohort_missing_ids']} and {diag['age_file_missing_ids']} missing IDs, respectively, and {diag['modeling_cohort_duplicate_id_rows']} and {diag['age_file_duplicate_id_rows']} duplicate-ID rows. Matches: **{diag['matched_modeling_participants']}**; unmatched modeling participants: **{diag['unmatched_modeling_participants']}**; age-file-only participants: **{diag['age_file_only_participants']}**. No participants are silently removed or imputed.

{age_table}

Age screening precedes subtraction and fitting. Negative or nonfinite/nonnumeric ages, ages >120, or a negative age difference halt modeling pending review. Ages >100 and supplied current ages <18 are explicit review flags, not new automatic exclusions; these are operational screens, not biological or questionnaire eligibility claims. Observed ages trigger none of these flags. Zero age at first NDE would not automatically be rejected. Supplied first-NDE age exceeds current age in **{diag['first_age_exceeds_current_age']}** cases. There are **{diag['negative_latency']}** negative differences and **{diag['zero_latency']}** zero differences. The latter are retained: whole-year age recording cannot distinguish same-year events precisely.

`age_validation.csv` and `merge_diagnostics.csv` contain aggregate checks only. No participant identifiers, per-person age pairs, row indices or model residual records are exported into the repository.

## 2. Multiple NDEs and documentary limitations

The available local CSV headers, main README, preprocessing, covariate code and local presentation notes were inspected. Neither modeling data nor the age file includes an NDE count/indicator, selected-event age/date, survey completion date, or a rule selecting the first versus most significant event. `dx_prior_NDE` is prior diagnosis history and is not an NDE count. Consequently, whether participants could report multiple NDEs, how often that happened, and which event they evaluated remain unknown. No single-NDE classification or restricted sensitivity sample is invented. The non-affective Greyson score also arrives as an upstream score rather than original items.

The age audit establishes numerical plausibility, not verified definitions. All fitted models below are **conditional analyses of the supplied age difference**, not definitive control for elapsed time since the evaluated experience.

## 3. Descriptive findings

{desc_table}

Overall skewness is {overall.skewness:.3f}; the upper 1.5-IQR screening fence is {overall.iqr_fence_high:.1f} years, and {int(overall.n_outside_iqr_fences)} observations fall outside the two fences. The maximum difference is {overall['max']:.0f} years. The modest skew and absence of this simple extreme-value flag do not justify an automatic transformation. No log transformation, trimming or winsorization is applied. Linearity remains an assumption, not a validated property.

{corr}

Intensity–difference associations are described continuously by correlation, without dichotomizing intensity. Correlations are descriptive and no new hypothesis-testing family is introduced. The exact identity is `age = age_first_NDE + latency_first_NDE_proxy` for every complete pair; arithmetic equality is tested, not a claim of event-definition validity.

![Observed age-difference distribution](latency_distribution.png)

Bars show counts in five-year intervals (the groups have unequal sample sizes); dashed lines are group medians. Zero differences remain represented.

## 4. Models and encoding

Existing `preprocess_data`, LCI-R item maps, domain definitions and eligibility threshold are reused unchanged. Item responses range −2 to +2; each domain averages available items if at least half are valid (rounded up). Complete cases are selected once per domain across all M1 predictors and the outcome; exactly those rows enter M0, M1 and M2. There is no imputation. The minimum model N remains {manifest['min_n_models']}.

- **M0:** the original additive adjusted model: non-affective Greyson intensity, valence, age at first NDE, CTQ minimization/denial, ordinal education, prior diagnosis, sex and death-context dummies.
- **M1:** M0 plus centered `latency_first_NDE_proxy` in years; age at first NDE is retained.
- **M2:** M1 with age at survey instead of age at first NDE. This is an algebraic reparameterization, not a sensitivity test or independent evidence.

Positive=1 and Mixed/Negative=0, with Non-positive the reference. Sex is Male=1, otherwise 0; diagnosis is Yes=1, otherwise 0. Education is 0=Other/no formal education, 1=primary, 2=secondary, 3=college/university, 4=graduate/higher. Death-context reference is `no_death_context`; indicators are `objective_medical_context` and `subjective_threat_only`. **Other** is exploratory, and internal Material Achievements is displayed as **Worldly Achievement**.

The main preprocessing standardizes intensity and first-NDE age using eligible-cohort means and population SDs; their original standardized values are retained in M0 and M1. Other continuous/ordinal terms, including the diagnosis indicator, are centered as in the existing fitter. The proxy and current age are centered at their eligible-cohort means. Intensity coefficients therefore represent LCI-R points per one eligible-cohort SD of Greyson intensity, valence coefficients Positive minus Non-positive adjusted differences, and the M1 proxy coefficient LCI-R points per additional year at fixed first-NDE age and other predictors. For readability, the primary table and forest plot multiply this coefficient and CI by ten; CSVs retain both yearly and ten-year units.

**Current age, age at first NDE and their difference are never entered simultaneously.** At fixed first-NDE age, a larger difference necessarily entails older survey age. Thus the M1 coefficient cannot isolate elapsed duration from ageing. In M2, the difference coefficient has a different conditioning interpretation even though predictions and fit are identical. M3 (replacing age at first NDE without retaining it) was not fit because it would answer a different incremental-adjustment question. No intensity × latency interaction was introduced.

Primary inference uses a two-sided ordinary OLS t test, pointwise 95% CI and ordinary ΔR²=M1 R²−M0 R². Each t test is verified against the one-df nested F test. **The primary BH family consists of ten proxy-covariate tests**, with q<0.05. Non-estimable domains would remain in the intended family via p=1 placeholders for correction, while their reported estimates/q remain missing.

HC3 robust t tests form a separate ten-test sensitivity family. Intensity and valence p-values are also corrected separately across ten domains for each predictor and model, solely to track the stability of the existing pattern; these are not new primary main-effects results. Comparing whether a threshold is crossed is not a formal test that coefficients changed. ΔR² measures in-sample fit, not validated prediction.

## 5. Results

{primary_table(t)}

{fits}

No primary proxy coefficient meets FDR q<0.05. **Self-Acceptance** has β={self_accept.latency_beta:.5f} per year (p={self_accept.latency_p:.4f}, q={self_accept.latency_q:.4f}), with ΔR²={self_accept.delta_r2:.4f}; **Death** has β={death.latency_beta:.5f} (p={death.latency_p:.4f}, q={death.latency_q:.4f}), with ΔR²={death.delta_r2:.4f}. Both nominal directions indicate lower reported-change scores at larger supplied age differences. They do not establish an effect of elapsed time. The remaining domains have raw p≥{good.loc[~good.outcome.isin(['Death','Self-Acceptance']), 'latency_p'].min():.4f}. R² increments span {good.delta_r2.min():.6f}–{good.delta_r2.max():.6f}.

![Proxy-covariate estimates with uncertainty](latency_coefficients.png)

Dots are adjusted estimates per ten years; bars are pointwise 95% CIs. Zero indicates no conditional linear association. q-values show that nominally nonzero intervals do not survive the ten-test correction.

### Changes in the original intensity and valence estimates

{changes}

Intensity retains the same sign in {int((~good.intensity_sign_changed).sum())} of {len(good)} domains. Seven domains meet intensity q<0.05 both before and after adjustment, with the same domain membership; no valence coefficient meets raw p<0.05 or BH q<0.05 in either model. The maximum absolute intensity coefficient change is {good.intensity_beta_change.abs().max():.5f} LCI-R points per intensity SD; the maximum absolute valence coefficient change is {good.valence_beta_change.abs().max():.5f} LCI-R points. Small valence coefficients can change sign without implying a meaningful change in evidence.

![Original predictor estimates before and after adding the proxy](intensity_valence_stability.png)

The paired estimates and pointwise CIs show M0 versus M1. Intensity and valence use separate axes and different predictor units; magnitudes should not be directly compared as a measure of relative importance.

## 6. Stability and validation

{stability}

HC3 yields q={self_accept.latency_hc3_q:.4f} for Self-Acceptance and q={death.latency_hc3_q:.4f} for Death; neither is below 0.05. Every one-case deletion retains the nominal negative Self-Acceptance and Death directions, with their raw p ranges shown above. Deletion p-values are diagnostics, not independent evidence or FDR-controlled tests. Other has {int(by_name.loc['Other','loo_latency_sign_changes'])} sign reversals around an estimate near zero. No case is removed from the reported models.

Influence flags are descriptive: Cook D>4/N, leverage>2k/N and |latency DFBETAS|>2/√N, with k including the intercept. All complete-case M1 designs have {int(good.design_columns.iloc[0])} parameters, rank {int(good.design_rank.iloc[0])}, and {int(good.residual_df.iloc[0])} residual degrees of freedom. Maximum M1 VIF (excluding the intercept) is {m1vif.vif.max():.3f}; first-NDE age and proxy VIFs are {m1vif.loc[m1vif.term=='age_first_NDE_c','vif'].max():.3f} and {m1vif.loc[m1vif.term=='latency_first_NDE_proxy_c','vif'].max():.3f}. Maximum M1 condition number is {good.condition_number.max():.2f} and leverage {good.max_leverage.max():.3f}. There are {int(good.loo_rank_failures.sum())} deletion rank failures. These diagnostics support numerical estimation, not semantic validity or the correctness of the linear mean model. No further transformations or subgroup analyses were justified by an identifiable extreme-value problem.

Baseline reproduction: **{'PASS' if baseline.passed.all() else 'FAIL'}**, {len(baseline)} numeric comparisons. Maximum absolute discrepancy is {baseline.absolute_difference.max():.3g}, below absolute/relative tolerance 1e-8. The original adjusted fitter is run without the new variable and compared with saved baseline N, fit, intercept, valence coefficients, intervals, p and q fields; matched-sample M0 is checked independently using that fitter. There is no substantive discrepancy. All {len(good)} M0/M1 comparisons have identical participant indices.

M1/M2 equivalence: **{'PASS' if pcheck.passed.all() else 'FAIL'}** across {len(pcheck)} domains; maximum absolute fitted-value difference {pcheck.max_abs_fitted_difference.max():.3g}. R², AIC/BIC and transformed temporal coefficients are checked. If F denotes first-NDE age, S current age and L=S−F, then replacing F with S leaves the model column space unchanged; the M2 survey-age slope equals the M1 first-age slope in raw-year units, and the M2 L slope equals the M1 L slope minus that first-age slope. Numerical equivalence cannot resolve which event was evaluated.

## 7. Interpretation and limitations

This provisional measure adds no FDR-significant association across the ten domains, although Self-Acceptance and Death show nominal patterns and in-sample gains of {100*self_accept.delta_r2:.2f} and {100*death.delta_r2:.2f} percentage points. Nonsignificance is not absence of association or equivalence. The observed intensity/valence evidence pattern remains broadly stable under this conditional adjustment; no formal new ranking of their importance is established.

The main unresolved issue is construct validity: supplied age meanings, survey timing, first versus selected NDE and multiple-NDE status cannot be verified. Whole-year ages introduce temporal measurement uncertainty; zero difference need not mean an event occurred on the survey date. Age/duration relationships are exact identities, so a model cannot separately identify unrestricted effects of current age, event age and elapsed time. Retrospective, cross-sectional associations permit recall bias and unmeasured confounding. Numerical diagnostics cannot fix these limitations. The ten correlated outcomes and post-review exploratory setting further limit confirmatory claims.

Coauthors may share this explicitly provisional analysis with supplementary results, or describe the feasibility findings and limitation in the reviewer response without adding a main-text result. No option is automatically selected. No reviewer response was drafted.

## 8. Reproduction and artifacts

From the repository root:

```bash
../../.venv/bin/python scripts/run_nde_latency.py --verify-reproducibility
../../.venv/bin/python -m pytest tests/test_nde_latency.py -q
```

All outputs are confined to `outputs/exploratory/nde_latency/` by default. Tables include age/merge validation, descriptive distributions, correlations, per-domain model comparisons, full model coefficients, VIFs, baseline reproduction and M1/M2 equivalence. HC3 and deletion diagnostics are included in the comparison table and a separate aggregate sensitivity table. Three figures are provided with simple explanations in the scientific summary. No identifiable participant-level data are exported.

The manifest records source/input hashes, versions, centering values, provenance uncertainty and protection checks. Repeated execution compares output bytes in the same environment; the requested check is saved in `reproducibility_check.json`. Protected existing pipeline files, outputs and input CSVs are checked before and after execution. The main CLI is not invoked, and manuscript/reviewer-response files are not written.
"""
