# Target-Specificity Filter and Hard Annotation

This run continued the pair-level correction detector optimization after the factual-support run reached AP = 0.8068 with a five-model mean. The goal was to address a remaining false-positive pattern: many high-scoring non-corrections were not actually directed at the given claim.

## Starting Point

The previous best observed result was:

`outputs/pair_relation_ensemble_oldbase_newbase_large_oldtype_nli_mean_on_independent_pair_audit_800_20260627T213000Z`

It reached:

| Metric | Value |
|---|---:|
| AP | 0.8068 |
| ROC-AUC | 0.7971 |
| Precision at threshold 0.5 | 0.6805 |
| Recall at threshold 0.5 | 0.8415 |
| F1 at threshold 0.5 | 0.7525 |

The residual false positives at threshold 0.5 were concentrated in three negative relation types:

| False-positive type | Count |
|---|---:|
| general opinion or reaction | 93 |
| misinformation support or elaboration | 51 |
| noncorrective factual statement | 15 |

Many false positives also had target specificity `none` or `general_topic`, which suggests that target specificity is a necessary condition for public correction.

## Target-Specificity Auxiliary Model

I derived a binary target-specificity label:

`target_given_claim = 1` if `llm_pair_target_specificity == given_claim`, otherwise `0`.

The 3,700-label training set had 3,044 target-given-claim rows and 656 non-target rows. The independent audit had 633 target-given-claim rows and 167 non-target rows.

Two DeBERTa-v3-base target-specificity models were trained:

| Model | Audit AP for target specificity | ROC-AUC |
|---|---:|---:|
| no-weight | 0.9096 | 0.7471 |
| balanced | 0.9130 | 0.7526 |

The balanced target-specificity model was therefore used for score combination and hard-case retrieval.

## Target Filter Diagnostic

I combined the previous correction ensemble with the target-specificity score. The best diagnostic combination was a mild power penalty:

`correction_score * target_score^0.1`

This reached AP = 0.8085, compared with AP = 0.8068 for the unfiltered five-model ensemble. The gain was small and unstable:

- AP difference versus five-model ensemble: +0.0017,
- bootstrap 95% interval: [-0.0062, 0.0102],
- probability that the difference is positive: 0.637.

This means target specificity is useful for diagnosing false positives, but the score filter alone is not a strong enough final improvement.

## Target-Specificity Hard Annotation

The more useful step was to use the target-specificity model for new data selection. I scored the remaining 5,500 unused pair candidates and selected 500 new pairs, with emphasis on high correction score but low target-specificity score.

The 500-label supplement contained:

| Label or relation type | Count |
|---|---:|
| correction relation | 264 |
| non-correction relation | 234 |
| unclear | 2 |
| general opinion or reaction | 166 |
| questioning or source request | 74 |
| misinformation support or elaboration | 34 |
| noncorrective factual statement | 30 |

The full combined set then contained 4,200 pair labels:

| Label or relation type | Count |
|---|---:|
| correction relation | 2,615 |
| non-correction relation | 1,581 |
| unclear | 4 |
| general opinion or reaction | 941 |
| misinformation support or elaboration | 523 |
| noncorrective factual statement | 94 |
| questioning or source request | 538 |

## 4,200-Label Model Results

The 4,200-label binary DeBERTa-v3-base model reached AP = 0.7904 on the independent audit. This is higher than the 3,700-label base model at AP = 0.7883, so the target-specificity hard annotation added useful ranking information.

The 4,200-label relation-type model reached AP = 0.7606. This is only slightly better than the old 3,000-label relation-type model as a single score, but it provided useful diversity inside an ensemble.

## Best Current Result

The clean main result is a simple seven-model mean:

- old 3,000-label binary DeBERTa-v3-base,
- 3,700-label binary DeBERTa-v3-base,
- 4,200-label binary DeBERTa-v3-base,
- old 3,000-label binary DeBERTa-v3-large,
- old 3,000-label relation-type DeBERTa-v3-base,
- 4,200-label relation-type DeBERTa-v3-base,
- old 3,000-label NLI/FEVER-pretrained DeBERTa-v3-base.

This seven-model mean reached:

| Metric | Value |
|---|---:|
| AP | 0.8129 |
| ROC-AUC | 0.8019 |
| Precision at threshold 0.5 | 0.6795 |
| Recall at threshold 0.5 | 0.8171 |
| F1 at threshold 0.5 | 0.7420 |

The saved artifact is:

`outputs/pair_relation_ensemble_4200_seven_model_and_target_filter_on_independent_pair_audit_800_20260627T225000Z`

The same output directory also stores a diagnostic upper-bound score using a mild target-specificity penalty:

`seven_model_mean_score * target_specificity_score^0.05`

This reached AP = 0.8141 and ROC-AUC = 0.8046. Because the exponent was inspected on the audit set, this score should be described as a diagnostic upper bound rather than the main deployable result.

## Improvement Over Prior Results

| Result | AP | ROC-AUC |
|---|---:|---:|
| old four-model mean | 0.8001 | 0.7917 |
| previous five-model mean | 0.8068 | 0.7971 |
| new seven-model mean | 0.8129 | 0.8019 |
| target-filter diagnostic upper bound | 0.8141 | 0.8046 |

Bootstrap comparison between the new seven-model mean and the previous five-model mean:

- AP difference: +0.0061,
- AP 95% interval: [-0.0041, 0.0172],
- probability that the AP difference is positive: 0.868.

This indicates another small but directionally positive gain. The improvement is larger than the target-filter-only step, but still needs validation on a future held-out audit before being treated as a stable final detector.

## Error Structure

At threshold 0.5, the seven-model mean had:

| Error type | Count |
|---|---:|
| false positives | 158 |
| false negatives | 75 |
| general-opinion false positives | 89 |
| support/elaboration false positives | 51 |
| noncorrective factual false positives | 15 |

The target-filter diagnostic reduced false positives further to 150, including 84 general-opinion false positives, but it also increased false negatives to 78. This confirms the trade-off: target-specificity filtering improves precision-oriented behavior but can suppress some true corrections.

## Current Recommendation

For the main detector result, use:

`outputs/pair_relation_ensemble_4200_seven_model_and_target_filter_on_independent_pair_audit_800_20260627T225000Z`

Report the seven-model mean as the main result:

> The best clean ensemble reaches AP = 0.813 and ROC-AUC = 0.802 on the independent 800-pair audit.

Report the target-filtered score only as a diagnostic upper bound:

> A mild target-specificity filter can push AP to 0.814, but this setting should be validated on another held-out audit before being treated as a final model.

## Next Step

Further improvement should now focus on validation rather than only optimization. The current audit has been used repeatedly for model comparison, so the next strong step is to build a second independent audit set or a small human-reviewed check set. Without that, additional ensemble tuning risks optimizing the current 800-pair audit rather than improving general measurement quality.
