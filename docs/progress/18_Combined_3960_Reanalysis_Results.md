# 18. Combined 3,960-Label Reanalysis Results

This note summarizes the rerun after adding the heterogeneity-targeted Qwen-assisted annotation sample.

## Annotation Merge

Run directory:

`outputs/llm_qwen_public_correction_combined_3960_heterogeneity_targeted_20260626T151000Z`

The combined annotation set contains 3,960 rows. Seven uncertain rows are excluded by the transformer training script, leaving 3,953 binary training rows.

- Negative labels: 2,744
- Positive labels: 1,209
- Duplicate comment keys: 0

## DeBERTa Rerun

Run directory:

`outputs/transformer_correction_deberta_v3_base_textonly_3960_heterogeneity_targeted_20260626T164000Z`

The model uses the same architecture and main settings as the previous DeBERTa run:

- Model: `microsoft/deberta-v3-base`
- Feature mode: `text_only`
- Selection metric: validation average precision
- Full prediction input: `data/interim/covidvaccine_comments.jsonl`

Holdout performance:

- Test positive F1: 0.679
- Test positive recall: 0.702
- Test ROC-AUC: 0.857
- Test average precision: 0.726

Compared with the earlier 2,760-label DeBERTa run, predictive performance is lower. The new labels were targeted toward heterogeneity-relevant strata rather than sampled as a neutral validation expansion, so the result should be treated as a measurement-improvement rerun rather than a clean model-selection gain.

Full-data prediction:

- Predicted public corrections: 17,800
- Threads with predicted public correction: 5,089
- High-participation threads without predicted correction: 197

## Heterogeneity Rerun

Dynamic table directory:

`outputs/thread_climate_dynamic_deberta_v3_base_textonly_3960_heterogeneity_v2_20260626T165500Z`

Logit directory:

`outputs/thread_climate_logit_deberta_v3_base_textonly_3960_heterogeneity_v2_20260626T165800Z`

The heterogeneity model improves fit slightly over the base thread-climate model:

- Base model pseudo R2: 0.0456
- Heterogeneity model pseudo R2: 0.0459
- Base AIC: 57,660.7
- Heterogeneity AIC: 57,640.2

Key coefficients from the heterogeneity logit model:

| Term | Odds ratio | p-value | Interpretation |
|---|---:|---:|---|
| `user_cross_group_observed` | 1.242 | 0.00022 | Cross-group users remain more likely to publicly correct. |
| `high_early_audience_structural_heterogeneity` | 1.055 | 0.339 | The audience-heterogeneity main effect is not robust after the label expansion. |
| `user_cross_group_observed:high_early_audience_structural_heterogeneity` | 1.072 | 0.501 | No robust interaction is detected. |
| `high_early_discursive_heterogeneity` | 1.125 | 0.046 | Early discursive heterogeneity is positively associated with later correction. |
| `early_correction_norm_presence` | 2.179 | < 0.001 | Early correction remains the strongest observable norm signal. |
| `high_thread_anti_institutional_climate` | 1.416 | < 0.001 | Anti-institutional climate is associated with more later correction. |

## Interpretation

The targeted-label rerun does not strengthen the earlier near-significant audience-structural heterogeneity effect. The earlier signal (`OR approximately 1.12, p approximately 0.08`) becomes weaker after adding targeted labels.

The more stable result is that structural cross-group participation is positively associated with correction. This supports the capacity side of the argument: users who participate across community groups appear more likely to produce public correction.

The new result is that early discursive heterogeneity becomes significant. This suggests that correction is not only shaped by who is present, but also by the early informational structure of the thread. Threads with more diverse early discourse cues may create more opportunities or triggers for later public correction.

The current evidence therefore supports a refined claim:

> Network heterogeneity should not be treated as a single construct. Cross-group user structure is associated with correction capacity, while early discursive heterogeneity is associated with later correction opportunities. Audience structural heterogeneity shows a positive descriptive pattern, but the current regression evidence is not robust enough to support it as a main explanatory mechanism.

## Caveat

The 3,960-label model is useful for rerunning heterogeneity-sensitive analyses, but the validation result is not stronger than the previous 2,760-label DeBERTa model. This means the current contribution should not be framed as "more labels improved the detector." The stronger claim is that targeted labeling clarified which heterogeneity mechanism is empirically supported.
