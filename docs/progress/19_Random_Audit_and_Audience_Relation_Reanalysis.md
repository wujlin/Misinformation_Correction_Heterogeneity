# 19. Random Audit and Audience-Relation Reanalysis

This note records the follow-up run designed to clarify the near-significant `high_early_audience_structural_heterogeneity` relationship.

## Motivation

The earlier 1,200-row heterogeneity-targeted annotation sample was not a representative random expansion. It was designed around the audience-heterogeneity mechanism and model-threshold uncertainty. Therefore, model-performance comparisons based on internal train/test splits were not clean.

This rerun separates two purposes:

- `random_audit`: an independent random sample for comparing detectors on the same evaluation set.
- `audience_relation_later`: a relation-focused later-comment sample for improving measurement around the later-correction outcome and the early-audience structural heterogeneity variable.

## Sample

Sample directory:

`outputs/audience_relation_random_annotation_sample_deberta3960_v2_20260626T181000Z`

Qwen annotation directory:

`outputs/llm_qwen_public_correction_audience_relation_random_v2_preserved_2000_20260626T203500Z`

The sample contains 2,000 newly annotated comments:

- Random audit: 800 rows
- Audience-relation later-comment sample: 1,200 rows

The relation sample is balanced on `high_early_audience_structural_heterogeneity`:

- Low early-audience structural heterogeneity: 600
- High early-audience structural heterogeneity: 600

Qwen label counts:

- Overall: 1,449 negative, 547 positive, 4 uncertain
- Random audit: 711 negative, 87 positive, 2 uncertain
- Audience-relation later sample: 738 negative, 460 positive, 2 uncertain

## Random Audit Model Comparison

Audit comparison directory:

`outputs/random_audit_model_comparison_with_5160_20260626T211000Z`

The random audit set contains 798 binary labels after excluding 2 uncertain labels. Positive rate is 10.9%.

| Model | Average precision | ROC-AUC | Positive F1 | Positive recall | Predicted positives |
|---|---:|---:|---:|---:|---:|
| DeBERTa 2,760 labels | 0.470 | 0.863 | 0.515 | 0.483 | 76 |
| DeBERTa 3,960 labels | 0.495 | 0.863 | 0.542 | 0.517 | 79 |
| DeBERTa 5,160 relation labels | 0.490 | 0.870 | 0.518 | 0.506 | 83 |

The clean audit comparison changes the earlier interpretation. The 3,960-label DeBERTa model does not perform worse than the 2,760-label model on the same independent random audit set. Its average precision and F1 are slightly higher. The earlier apparent decline came from comparing different internal test splits.

The 5,160-label relation-sensitive model has the highest ROC-AUC, but it does not improve average precision or F1 relative to the 3,960-label model. Therefore, the 5,160 model should not be treated as the best general detector.

## Relation-Sensitive Reanalysis

Training-label directory:

`outputs/llm_qwen_public_correction_combined_5160_relation_later_20260626T204500Z`

Detector directory:

`outputs/transformer_correction_deberta_v3_base_textonly_5160_relation_later_20260626T205000Z`

Dynamic table directory:

`outputs/thread_climate_dynamic_deberta_v3_base_textonly_5160_relation_later_20260626T211600Z`

Logit directory:

`outputs/thread_climate_logit_deberta_v3_base_textonly_5160_relation_later_20260626T211700Z`

The 5,160-label training set contains 5,151 binary labels:

- Negative labels: 3,482
- Positive labels: 1,669

Full-data prediction:

- Predicted public corrections: 16,976
- Threads with predicted public correction: 4,997
- High-participation threads without predicted correction: 215

## Key Heterogeneity Coefficients

| Term | 3,960-label OR | 3,960 p | 5,160-label OR | 5,160 p |
|---|---:|---:|---:|---:|
| `user_cross_group_observed` | 1.242 | 0.00022 | 1.254 | 0.00016 |
| `high_early_audience_structural_heterogeneity` | 1.055 | 0.339 | 1.130 | 0.039 |
| `user_cross_group_observed:high_early_audience_structural_heterogeneity` | 1.072 | 0.501 | 1.004 | 0.968 |
| `high_early_discursive_heterogeneity` | 1.125 | 0.046 | 1.165 | 0.013 |
| `early_correction_norm_presence` | 2.179 | < 0.001 | 2.305 | < 0.001 |
| `high_thread_anti_institutional_climate` | 1.416 | < 0.001 | 1.404 | < 0.001 |

The target variable becomes more stable in the relation-sensitive rerun:

> `high_early_audience_structural_heterogeneity`: OR = 1.130, p = 0.039.

The interaction with cross-group user status remains unsupported:

> `user_cross_group_observed:high_early_audience_structural_heterogeneity`: OR = 1.004, p = 0.968.

## Interpretation

The result supports a more precise interpretation:

1. Cross-group user structure is stable across detector versions.
2. Early discursive heterogeneity is stable across detector versions.
3. Early audience structural heterogeneity is positive in descriptive tables and becomes statistically detectable after adding relation-focused later-comment labels.
4. The evidence does not support a cross-group-by-audience-heterogeneity interaction.

The most defensible claim is:

> Public correction is more likely when users have cross-group participation and when the early thread environment contains either correction-relevant discourse or structurally heterogeneous visible audiences. However, the audience-heterogeneity result is detector-sensitive and should be framed as a relation-sensitive robustness result, not as the strongest main finding.

## Methodological Caveat

This rerun should not be described as p-value tuning. The additional 1,200 relation labels were sampled before observing the 5,160 model result and were balanced on the high/low early-audience structural heterogeneity variable among later comments. The purpose is measurement improvement for the outcome-relevant part of the data.

At the same time, the 5,160 detector is not the best general detector on random audit average precision. For manuscript writing, the 3,960-label detector can remain the cleaner general detector, while the 5,160-label detector can serve as a mechanism-sensitive robustness check.
