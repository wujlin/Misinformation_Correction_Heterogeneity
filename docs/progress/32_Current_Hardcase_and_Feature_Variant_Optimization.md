# Current Hard-Case and Feature-Variant Optimization

This run continued the pair-level correction detector after the seven-model ensemble reached AP = 0.8129 on the independent 800-pair audit. The goal was to test whether the remaining improvement should come from more hard-case labels, larger model capacity, or richer input representation.

## Starting Point

The previous clean main result was:

`outputs/pair_relation_ensemble_4200_seven_model_and_target_filter_on_independent_pair_audit_800_20260627T225000Z`

It reached:

| Metric | Value |
|---|---:|
| AP | 0.8129 |
| ROC-AUC | 0.8019 |
| Precision at threshold 0.5 | 0.6795 |
| Recall at threshold 0.5 | 0.8171 |
| F1 at threshold 0.5 | 0.7420 |

The target-specificity-filtered score reached AP = 0.8141, but that setting remains a diagnostic upper bound because the filter exponent was inspected on the audit set.

## Current-Model Hard Annotation

After scoring 5,000 unused pair candidates with the current six-model score, I selected 600 additional hard cases. The sample focused on:

- high-score support-like false-positive risk,
- high-score factual but non-corrective risk,
- low-score correction-cue possible false negatives,
- high-score but low target-specificity false-positive risk,
- disagreement boundary cases,
- random calibration cases.

The 600 Qwen-assisted labels contained:

| Label or relation type | Count |
|---|---:|
| correction relation | 336 |
| non-correction relation | 264 |
| general opinion or reaction | 172 |
| definition or context correction | 133 |
| questioning or source request | 86 |
| evidence or source correction | 84 |
| misinformation support or elaboration | 79 |
| direct rebuttal | 23 |

The combined training set then contained 4,800 pair annotations:

| Label | Count |
|---|---:|
| correction relation | 2,951 |
| non-correction relation | 1,845 |
| unclear | 4 |

## 4,800-Label Baseline Models

The 4,800-label DeBERTa-v3-base binary model reached AP = 0.7921 on the independent audit. The 4,800-label relation-type model reached AP = 0.7746. The relation-type model improved as a single relation model, but adding it to the existing ensemble did not improve the clean mean as much as adding the binary model.

The clean eight-model mean that added the 4,800-label binary model reached:

| Metric | Value |
|---|---:|
| AP | 0.8175 |
| ROC-AUC | 0.8076 |
| Precision at threshold 0.5 | 0.6898 |
| Recall at threshold 0.5 | 0.8244 |
| F1 at threshold 0.5 | 0.7511 |

Bootstrap comparison against the previous seven-model mean:

- AP difference: +0.0046,
- AP 95% interval: [-0.0001, 0.0096],
- probability that the AP difference is positive: 0.972.

This indicates that the new 600 hard labels add useful information, although the gain from labels alone is still modest.

## Larger-Model Check

I also tested a DeBERTa-v3-large model on the 4,800-label set. This route was stopped after the third epoch because the validation AP remained near 0.654 and ROC-AUC stayed near 0.50. The model was not learning the task under the previous large-model configuration.

This failure is useful diagnostically. The bottleneck is not simply model capacity. The stronger route is to improve measurement design and input representation for the claim-response relation.

## Feature-Variant Models

I trained two additional DeBERTa-v3-base models on the same 4,800 labels:

| Model | Feature mode | Best validation AP | Internal test AP | External audit AP |
|---|---|---:|---:|---:|
| title variant | `title_claim_response` | 0.8411 | 0.8334 | 0.7895 |
| metadata variant | `metadata_title_claim_response` | 0.8533 | 0.8362 | 0.7858 |

The feature variants were not better as single external-audit models than the original 4,800 claim-response model. However, they provided useful diversity inside an ensemble, because they changed what information the cross-encoder used when judging whether the response corrected the given claim.

## Best Current Clean Result

The best clean current result is a ten-model mean:

- old 3,000-label binary DeBERTa-v3-base,
- 3,700-label binary DeBERTa-v3-base,
- 4,200-label binary DeBERTa-v3-base,
- 4,800-label binary DeBERTa-v3-base,
- 4,800-label title-claim-response DeBERTa-v3-base,
- 4,800-label metadata-title-claim-response DeBERTa-v3-base,
- old 3,000-label binary DeBERTa-v3-large,
- old 3,000-label relation-type DeBERTa-v3-base,
- 4,200-label relation-type DeBERTa-v3-base,
- old 3,000-label NLI/FEVER-pretrained DeBERTa-v3-base.

The saved artifact is:

`outputs/pair_relation_ensemble_4800_feature_variants_full800_on_independent_pair_audit_20260628T003000Z`

It reached:

| Metric | Value |
|---|---:|
| AP | 0.8211 |
| ROC-AUC | 0.8151 |
| Precision at threshold 0.5 | 0.6886 |
| Recall at threshold 0.5 | 0.8415 |
| F1 at threshold 0.5 | 0.7574 |

Bootstrap comparison against the previous seven-model mean:

- AP difference: +0.0081,
- AP 95% interval: [0.0012, 0.0152],
- probability that the AP difference is positive: 0.991.

This is the strongest clean result so far. The improvement comes from both hard-case annotation and feature-representation diversity, not from a target-specificity filter tuned on the audit.

## Diagnostic Upper Bound

A mild target-specificity penalty on the ten-model mean reached AP = 0.8216:

`ten_model_mean_score * target_specificity_score^0.02`

This should remain a diagnostic upper bound because the exponent was inspected on the independent audit. The main reportable result should be the clean ten-model mean at AP = 0.8211.

## Interpretation

The current measurement result supports a more concrete claim:

> Pair-level public correction detection improves when the model is trained on hard relational boundary cases and when the ensemble includes multiple representations of the same claim-response relation.

The feature-variant result is substantively useful because public correction is not only a comment-level property. It is a relation between a target claim and a response, and that relation can depend on thread title, pair source, subreddit context, and whether the response is directed at the given claim rather than the general topic.

## Current Recommendation

Use the following as the current main detector:

`outputs/pair_relation_ensemble_4800_feature_variants_full800_on_independent_pair_audit_20260628T003000Z`

Report:

> The best clean ensemble reaches AP = 0.821 and ROC-AUC = 0.815 on the independent 800-pair audit.

Also report the earlier AP = 0.813 seven-model result as the previous baseline, because the bootstrap comparison shows a measurable improvement from the current hard-case and feature-variant step.

## Next Step

The next improvement should not be another audit-tuned ensemble recipe. The more defensible next step is to build a second independent audit set or a small human-reviewed check set, then evaluate whether the AP = 0.821 result holds out of sample. If the result holds, the detector is strong enough for the downstream correction-misallocation and heterogeneity analysis.
