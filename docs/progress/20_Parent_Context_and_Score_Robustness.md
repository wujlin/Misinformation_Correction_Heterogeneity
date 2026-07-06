# 20. Parent Context and Score-Based Robustness

This note records the measurement upgrade after the 5,160-label relation-sensitive rerun.

## Motivation

The previous result made `high_early_audience_structural_heterogeneity` statistically detectable in the binary later-correction logit model. However, two measurement questions remained:

1. Whether public correction detection improves when the model can see the parent comment being replied to.
2. Whether the heterogeneity results remain stable when the later-correction outcome is measured with continuous correction scores rather than a hard classification threshold.

This run addresses both questions.

## Parent-Aware Random Audit

The earlier 800-row random audit sample was augmented with parent-comment context. Parent bodies were available for 287 of the 800 audit rows. The Qwen annotation prompt was then revised to include the parent comment when available.

Parent-aware audit annotation directory:

`outputs/llm_qwen_public_correction_random_audit_parent_context_preserved_800_20260626T215500Z`

Label counts:

- Negative: 676
- Positive: 123
- Uncertain: 1

After excluding the uncertain label, the audit set contains 799 binary labels. The positive rate is 15.4%.

## Detector Comparison on Parent-Aware Audit

The evaluation uses the same parent-aware audit labels across all models.

| Model | Feature mode | Average precision | ROC-AUC | Positive F1 | Positive recall | Predicted positives |
|---|---|---:|---:|---:|---:|---:|
| DeBERTa 3,960 labels | `text_only` | 0.514 | 0.834 | 0.485 | 0.398 | 79 |
| DeBERTa 5,160 labels | `text_only` | 0.539 | 0.857 | 0.485 | 0.407 | 83 |
| DeBERTa 5,160 labels | `text_parent` | 0.529 | 0.816 | 0.507 | 0.602 | 169 |
| DeBERTa 5,160 labels | `text_parent_candidate` | 0.529 | 0.813 | 0.525 | 0.520 | 121 |

The best average precision comes from the 5,160-label text-only DeBERTa model:

`outputs/parent_context_random_audit_eval_deberta5160_text_only_20260626T220000Z`

The parent-context models increase positive recall or positive F1, but they do not improve average precision. Therefore, parent context does not currently solve the detector-quality problem. The most defensible detector for aggregate analysis remains the 5,160-label text-only model if average precision is the primary criterion.

## Score-Based Outcome

The binary logit model depends on a selected classification threshold. To reduce threshold dependence, a score-based outcome was constructed at the thread-author level:

`later_public_correction_score_any = 1 - product(1 - score_i)`

Here, `score_i` is the predicted public-correction score for each later comment by the same author in the same thread. The outcome approximates the predicted probability that the author makes at least one later public correction in that thread.

Score-based model directory:

`outputs/thread_climate_score_ols_deberta_v3_base_textonly_5160_relation_later_20260626T222000Z`

Model scale:

- Comments: 165,061
- Threads: 10,220
- Thread-author instances: 145,215
- Later thread-author instances: 89,251
- Binary later-correction mean: 0.099
- Score-based later-correction mean: 0.128

## Score-Based Coefficients

The score-based model uses clustered standard errors by submission.

| Term | Coef. | p-value | Interpretation |
|---|---:|---:|---|
| `user_cross_group_observed` | 0.0266 | < 0.001 | Stable positive association |
| `high_early_audience_structural_heterogeneity` | 0.0087 | 0.171 | Not stable under score-based outcome |
| `user_cross_group_observed:high_early_audience_structural_heterogeneity` | 0.0055 | 0.672 | No interaction support |
| `early_correction_norm_presence` | 0.0799 | < 0.001 | Strong positive association |
| `early_correction_norm_presence:high_thread_hostility_climate` | -0.0287 | 0.007 | Hostility weakens the correction-norm association |
| `high_early_discursive_heterogeneity` | 0.0221 | 0.002 | Stable positive association |
| `high_thread_anti_institutional_climate` | 0.0443 | < 0.001 | Positive association in this dataset |

The scenario table gives the same substantive pattern:

| Early audience structural heterogeneity | Cross-group user | Predicted score-based correction probability |
|---:|---:|---:|
| 0 | 0 | 0.125 |
| 0 | 1 | 0.151 |
| 1 | 0 | 0.133 |
| 1 | 1 | 0.166 |

Cross-group users have higher predicted correction scores in both audience settings. The additional difference associated with high audience structural heterogeneity is smaller and not statistically stable in the score-based model.

## Continuous Heterogeneity Probe

A second probe replaced the binary high-audience-heterogeneity flag with the continuous early audience cross-group author share.

Probe directory:

`outputs/thread_climate_continuous_heterogeneity_probe_5160_relation_20260626T223000Z`

Key terms:

| Model | Term | Coef. | p-value |
|---|---|---:|---:|
| Score-based OLS | `user_cross_group_observed` | 0.0265 | < 0.001 |
| Score-based OLS | `early_audience_cross_group_author_share` | 0.0273 | 0.410 |
| Score-based OLS | `user_cross_group_observed:early_audience_cross_group_author_share` | 0.0253 | 0.680 |
| Score-based OLS | `early_discursive_cue_entropy` | 0.0423 | < 0.001 |
| Binary logit | `user_cross_group_observed` | 0.2160 | < 0.001 |
| Binary logit | `early_audience_cross_group_author_share` | 0.4284 | 0.184 |
| Binary logit | `user_cross_group_observed:early_audience_cross_group_author_share` | 0.1409 | 0.790 |
| Binary logit | `early_discursive_cue_entropy` | 0.4343 | < 0.001 |

The continuous probe reinforces the same conclusion. User-level cross-group participation and discursive heterogeneity are stable. Visible-audience structural heterogeneity is not stable enough to serve as the main finding.

## Current Substantive Conclusion

The stronger current conclusion is not that all forms of heterogeneity suppress public correction. The stronger conclusion is that heterogeneity has to be separated into different levels:

1. User structural heterogeneity is stable and positive. Users who participate across community groups are more likely to produce later public corrections.
2. Discursive heterogeneity is stable and positive. Threads with more varied early correction-relevant cues are more likely to generate later correction.
3. Visible-audience structural heterogeneity is weaker. It becomes detectable in the 5,160-label binary logit but does not remain stable under score-based or continuous-audience specifications.
4. Hostile climates do not simply eliminate correction. The clearest hostility result is conditional: hostility weakens the positive association between early correction norms and later correction in the score-based model.

The contribution should therefore avoid treating audience heterogeneity as the central empirical result at the current stage. A more defensible contribution is:

> Public correction is shaped by heterogeneous network positions and local discussion environments, but different forms of heterogeneity do not work in the same way. Cross-community user participation and discursive heterogeneity consistently predict more public correction, while visible-audience structural heterogeneity is more measurement-sensitive.

## Detector Quality Assessment

The current parent-aware audit result is not strong enough for confident individual-level correction classification. However, it is meaningfully above the random-audit base rate:

- Parent-aware audit positive rate: 0.154
- Best average precision: 0.539
- ROC-AUC: 0.857

This supports aggregate and probabilistic analysis more than hard individual-level claims. For the next round, the priority should be improving measurement rather than adding more downstream models.

Recommended next measurement steps:

1. Review false positives and false negatives from the parent-aware audit.
2. Add relation-focused labels for high-disagreement cases rather than only threshold-near cases.
3. Consider an ensemble or calibration step only after the error categories are understood.
4. Keep score-based outcomes as robustness checks in all downstream models.

## Error Review Table

An error-review table was generated for the best average-precision detector on the parent-aware audit set.

Error-review directory:

`outputs/parent_context_random_audit_error_review_deberta5160_text_only_20260626T224000Z`

Confusion counts:

- True negatives: 643
- True positives: 50
- False positives: 33
- False negatives: 73

The table files are:

- `tables/false_positives_top80.csv`
- `tables/false_negatives_top80.csv`
- `tables/largest_errors_top160.csv`
- `tables/all_audit_predictions_with_text.csv`

The first manual look suggests two likely error sources. Some false positives are factual or argumentative comments that resemble corrections but do not clearly correct a specific prior false claim. Some false negatives are short, sarcastic, quote-edit, or context-dependent corrections. This means the next labeling pass should not simply add more random rows. It should target boundary cases where correction depends on parent-comment relation, sarcasm, quote edits, and whether a factual statement counts as public correction.
