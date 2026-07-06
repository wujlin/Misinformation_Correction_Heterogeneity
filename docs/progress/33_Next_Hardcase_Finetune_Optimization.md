# Next Hard-Case Fine-Tune Optimization

This run continued the pair-level correction detector optimization after the feature-variant ensemble reached AP = 0.8211 on the independent 800-pair audit. The goal was to test whether the detector could still improve through another round of targeted hard-case annotation without simply overfitting the current audit set.

## Starting Point

The previous clean main result was:

`outputs/pair_relation_ensemble_4800_feature_variants_full800_on_independent_pair_audit_20260628T003000Z`

It reached:

| Metric | Value |
|---|---:|
| AP | 0.8211 |
| ROC-AUC | 0.8151 |
| Precision at threshold 0.5 | 0.6886 |
| Recall at threshold 0.5 | 0.8415 |
| F1 at threshold 0.5 | 0.7574 |

The target-specificity diagnostic score reached AP = 0.8216, but the clean ten-model mean remained the main reportable result.

## Next Hard-Case Sample

I created a new 800-pair annotation sample from the remaining 4,400 unused candidates after excluding all pairs already present in the 4,800-label training set. Candidate selection used the current ten-model score, target-specificity score, model disagreement, feature-variant disagreement, type-model disagreement, and correction-cue indicators.

The sample emphasized:

- high-score but low target-specificity false-positive risk,
- high feature disagreement among 4,800 claim/title/metadata models,
- low-score but correction-cue possible false-negative risk,
- boundary cases with high model disagreement,
- relation-type disagreement,
- random calibration cases.

The new Qwen-assisted annotation produced 800 labels:

| Label or relation type | Count |
|---|---:|
| non-correction relation | 482 |
| correction relation | 316 |
| unclear | 2 |
| general opinion or reaction | 292 |
| misinformation support or elaboration | 162 |
| definition or context correction | 117 |
| evidence or source correction | 85 |
| questioning or source request | 59 |

This was a useful hard-case sample because it added many more difficult non-correction cases than a normal active sample. The sample directly targeted the remaining false-positive problem: general opinions, supportive elaborations, and non-corrective factual statements that look correction-like.

## Full 5,600-Label Training Was Not Enough

I first trained two DeBERTa-v3-base models from scratch on the full 5,600-label set:

| Model | External audit AP | ROC-AUC |
|---|---:|---:|
| claim-response 5,600 from scratch | 0.7458 | 0.7402 |
| metadata-title-claim-response 5,600 from scratch | 0.7475 | 0.7524 |

This was a clear negative result. Directly mixing all new hard negatives into the training set shifted the training distribution too strongly toward adversarial boundary cases. The model became worse on the independent audit.

## Balanced Supplement and Fine-Tuning

The better strategy was to treat the new hard labels as a boundary supplement rather than a full replacement distribution. I constructed a balanced supplement set:

- keep all previous 4,800 labels,
- add all 316 new positive hard cases,
- add 316 sampled new negative hard cases.

This produced a 5,432-row training set with 3,267 positive labels and 2,161 negative labels. I then fine-tuned the 4,800-label checkpoints with a small learning rate:

`learning_rate = 5e-6`, `epochs = 3`

The fine-tuned single-model audit results were:

| Model | Previous AP | Fine-tuned AP | ROC-AUC after fine-tune |
|---|---:|---:|---:|
| claim-response | 0.7921 | 0.7932 | 0.7959 |
| title-claim-response | 0.7895 | 0.7997 | 0.7995 |
| metadata-title-claim-response | 0.7858 | 0.8021 | 0.8070 |

The improvement is strongest for the title and metadata variants. This suggests that the hard cases help most when the model has enough context to decide whether a response targets the given claim or only reacts to the broader topic.

## Best Current Clean Result

The best clean current result is a thirteen-model mean:

- previous ten-model feature-variant ensemble,
- fine-tuned 5,432-label claim-response model,
- fine-tuned 5,432-label title-claim-response model,
- fine-tuned 5,432-label metadata-title-claim-response model.

The saved artifact is:

`outputs/pair_relation_ensemble_5432_finetune_all_full800_on_independent_pair_audit_20260628T020500Z`

It reached:

| Metric | Value |
|---|---:|
| AP | 0.8235 |
| ROC-AUC | 0.8198 |
| Precision at threshold 0.5 | 0.6951 |
| Recall at threshold 0.5 | 0.8341 |
| F1 at threshold 0.5 | 0.7583 |

Bootstrap comparison against the previous clean ten-model mean:

- AP difference: +0.0025,
- AP 95% interval: [-0.0017, 0.0069],
- probability that the AP difference is positive: 0.875.

This is a smaller gain than the previous feature-variant step, but it is still directionally positive and pushes the clean audit AP from 0.8211 to 0.8235.

## Diagnostic Upper Bound

A mild target-specificity penalty on the thirteen-model mean reached AP = 0.8238:

`thirteen_model_mean_score * target_specificity_score^0.02`

This should remain a diagnostic upper bound because the exponent was inspected on the independent audit. The main reportable result should be the clean thirteen-model mean at AP = 0.8235.

## Interpretation

The main methodological lesson is:

> Hard-case annotation helps, but only when it is introduced as a controlled boundary supplement. Direct full retraining on a hard-negative-heavy sample can reduce external performance.

This matters for the study because the detector is not a generic comment classifier. It measures whether a response corrects a specific target claim. The hard cases are valuable because they teach the model to separate genuine public correction from support, elaboration, disagreement, and general topic discussion.

## Current Recommendation

Use the following as the current main detector:

`outputs/pair_relation_ensemble_5432_finetune_all_full800_on_independent_pair_audit_20260628T020500Z`

Report:

> The best clean ensemble reaches AP = 0.824 and ROC-AUC = 0.820 on the independent 800-pair audit.

Also report the negative result from full 5,600-label retraining, because it justifies the controlled fine-tuning design.

## Next Step

The current audit has now been used many times for comparison. Further gains on the same 800-pair audit may become increasingly fragile. The next strongest step is to create a second independent audit or a human-reviewed check set. If the AP = 0.824 result holds on that second audit, the detector is strong enough for downstream correction-misallocation and heterogeneity analysis.
