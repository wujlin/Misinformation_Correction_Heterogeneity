# 35. No-Leak Combiner and Large6232 Optimization

## Purpose

This round continues the audit2 optimization after the second independent audit showed that the previous clean thirteen-model ensemble reached AP = 0.781 and the audit1-trained logistic stack reached AP = 0.793.

The goal is to test whether performance can be improved without weakening the measurement design.

## Leakage Check

An initial meta-combiner run produced unrealistically high audit2 AP above 0.99. That result is invalid.

The invalid run included Qwen-derived categorical labels as features:

- `llm_pair_relation_type`
- `llm_pair_target_specificity`

These fields are annotation outputs, not operational prediction inputs. Including them leaks the label structure into the combiner. The run below must not be cited:

- `outputs/pair_relation_meta_combiner_audit1_to_audit2_target_typeprob_20260628T051000Z`

The corrected no-leak run excludes all label-derived fields and uses only operational features:

- model scores
- target-specificity model score
- type-model probabilities
- `sample_component`
- `pair_source`
- `subreddit`

Corrected path:

- `outputs/pair_relation_meta_combiner_audit1_to_audit2_target_typeprob_noleak_20260628T052000Z`

## Target-Specificity Feature

A target-specificity score was generated for audit2 using the existing balanced target-specificity model.

Audit2 target-specificity label distribution:

- `given_claim`: 508
- not `given_claim`: 292

The target-specificity model performs reasonably for its own auxiliary task:

- AP = 0.845
- ROC-AUC = 0.788

This score helps describe whether the response is about the specific claim, but it does not by itself solve public-correction detection.

Paths:

- `outputs/target_specificity_audit2_800_20260628T050000Z`
- `outputs/target_specificity_deberta_v3_base_3700_balanced_on_audit2_800_20260628T050000Z`

## No-Leak Meta-Combiner Result

After removing leakage, the strongest audit2 result among the no-leak combiner variants is:

| Score | AP | ROC-AUC | F1@0.5 |
|---|---:|---:|---:|
| L1 logistic, 14 scores, `C=0.1` | 0.796 | 0.871 | 0.732 |

However, this is the best audit2-observed no-leak variant, not the top audit1-CV-selected variant. The audit1-CV-selected variants remain around AP = 0.791-0.793 on audit2. Therefore, the no-leak target/type-probability combiner improves diagnosis but does not provide a clean, decisive jump beyond the previous audit1-trained stack.

The main interpretation is that target specificity and type probabilities are useful auxiliary signals, but the dominant bottleneck remains the core pair-relation ranking problem.

## Large6232 Models

Two DeBERTa-v3-large models were trained using the 6,232-label set, which combines the 5,432 training labels with audit1. Audit2 remains external.

The large models were initialized from the earlier large3000 checkpoint because the previous large4800 run was incomplete and had degenerated to near-random validation behavior.

Training paths:

- `outputs/pair_relation_deberta_v3_large_claim_response_group_response_6232_plus_audit1_finetune3000_lr2e6_20260628T053500Z`
- `outputs/pair_relation_deberta_v3_large_metadata_title_claim_response_group_response_6232_plus_audit1_finetune3000_lr2e6_20260628T053500Z`

Audit2 single-model results:

| Model | AP | ROC-AUC | F1@0.5 |
|---|---:|---:|---:|
| large claim6232 | 0.788 | 0.861 | 0.716 |
| large metadata6232 | 0.769 | 0.849 | 0.701 |

The large claim model is not the best single model, but it adds useful complementary ranking signal.

## Current Best Audit2 Result

Adding both large6232 models to the previous old14 + new3 + type6232 simple ensemble gives the best observed audit2 score so far:

| Score | AP | ROC-AUC | F1@0.5 |
|---|---:|---:|---:|
| old14 + new3 + type6232 + large claim + large metadata mean | 0.802 | 0.876 | 0.749 |
| old14 + new3 + type6232 + large claim mean | 0.799 | 0.875 | 0.749 |
| previous old14 + new3 + type6232 mean | 0.792 | 0.873 | 0.749 |
| previous audit1-trained logistic stack | 0.793 | 0.871 | 0.734 |

Main path:

- `outputs/pair_relation_ensemble_large6232_on_audit2_20260628T060000Z`

## Bootstrap Comparison

The large6232 ensemble improves over the previous simple type6232 ensemble with positive bootstrap support:

- AP difference: +0.0095
- 95% CI: [+0.0006, +0.0208]
- `p(diff <= 0) = 0.015`

Against the previous audit1-trained logistic stack:

- AP difference: +0.0087
- 95% CI: [-0.0039, +0.0207]
- `p(diff <= 0) = 0.0736`

This means the new result is a real improvement over the previous simple ensemble, but the comparison with the logistic stack is still not fully conclusive.

## Interpretation

The practical progress is that audit2 now has a model configuration above AP = 0.8. The methodological caution is that this is still a best-observed audit2 result after several optimization attempts.

The current strongest statement is:

> A larger model trained on the expanded 6,232-label set adds complementary ranking information. When combined with the previous base, type, and feature-variant models, audit2 AP reaches 0.802 and ROC-AUC reaches 0.876.

The next step should be a third independent audit or a frozen holdout. If the large6232 ensemble remains near or above AP = 0.8 on audit3, the detector result becomes much safer to report.
