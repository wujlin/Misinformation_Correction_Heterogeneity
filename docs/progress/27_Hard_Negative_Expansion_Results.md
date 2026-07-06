# Hard-Negative Expansion for Pair-Level Correction Detection

This run tested whether relation-pair detection can be improved by adding hard examples selected from high-scoring candidate pairs. The independent 800-pair audit set was kept held out and was not used for training.

## Motivation

The previous pair-level detector improved the measurement design by asking whether a response corrects a specific claim. However, the independent audit showed a remaining false-positive problem. Many general reactions, supportive replies, or factual but noncorrective comments still received high correction scores. This means the main bottleneck is no longer only model architecture. The bottleneck is whether the training data contains enough relation-level boundary cases.

## Hard-Negative Sampling

A fresh 8,000-pair candidate pool was generated from the COVID vaccine Reddit data. The pool excluded both the original 1,200 pair-level training sample and the independent 800-pair audit sample.

The first hard-example round used the original 1,200-pair model to score the 8,000 candidates. From this scored pool, 1,000 additional pairs were selected from high-risk regions, including high-score support-like responses, reaction-like responses, correction-cue responses, parent-comment pairs, and random calibration cases. Qwen labeled this sample as 591 positive correction relations and 409 non-correction relations.

The second round used the 2,200-pair model to rescore the same candidate pool. After excluding the first 1,000 added pairs, 800 more support-focused candidates were selected. Qwen labeled this second sample as 579 positive correction relations and 221 non-correction relations.

The final expanded training set therefore contains 3,000 pair annotations, with 2,999 binary labels after excluding one unclear case: 1,935 positive correction relations and 1,064 non-correction relations.

## Model Runs

The main setting remained DeBERTa-v3-base with `claim_response` input, response-group splitting, and no class weighting. I also tested `title_claim_response`, `metadata_title_claim_response`, and a class-balanced 3,000-pair model.

External evaluation used the same independent 800-pair audit set.

| Model | Training labels | Input / setting | External AP | ROC-AUC | F1 | Precision | Recall |
|---|---:|---|---:|---:|---:|---:|---:|
| Base pair model | 1,200 | `claim_response`, no weight | 0.718 | 0.720 | 0.706 | 0.619 | 0.822 |
| First hard-example model | 2,200 | `claim_response`, no weight | 0.761 | 0.758 | 0.733 | 0.633 | 0.871 |
| Second hard-example model | 3,000 | `claim_response`, no weight | 0.765 | 0.766 | 0.728 | 0.622 | 0.878 |
| Title variant | 2,200 | `title_claim_response`, no weight | 0.700 | 0.703 | 0.682 | 0.633 | 0.739 |
| Metadata variant | 2,200 | `metadata_title_claim_response`, no weight | 0.704 | 0.709 | 0.711 | 0.580 | 0.920 |
| Balanced variant | 3,000 | `claim_response`, class weight balanced | 0.732 | 0.746 | 0.712 | 0.624 | 0.829 |

A simple average ensemble of the 2,200-pair and 3,000-pair `claim_response` models reached AP = 0.771 and ROC-AUC = 0.771 on the audit set. This was the best observed ranking result, but it is still below the target AP = 0.8. The saved ensemble artifact is:

`outputs/pair_relation_ensemble_2200_3000_claim_on_independent_pair_audit_800_20260627T164000Z`

## Interpretation

The first hard-example round produced a real improvement. External AP increased from 0.718 to 0.761, and ROC-AUC increased from 0.720 to 0.758. This shows that relation-level hard examples improve the detector in a substantive way.

The second support-focused round produced only a small AP increase, from 0.761 to 0.765. The added data improved ranking slightly, but it did not solve the main false-positive categories. On the independent audit, the 3,000-pair model still predicted many non-correction cases as correction:

| Negative relation type | Audit rows | Predicted positive by 2,200 model | Predicted positive by 3,000 model |
|---|---:|---:|---:|
| `general_opinion_or_reaction` | 226 | 116 | 128 |
| `misinformation_support_or_elaboration` | 143 | 73 | 74 |
| `noncorrective_factual_statement` | 16 | 14 | 14 |

This means the current gains mainly come from better ranking of true correction relations, not from fully suppressing hard false positives. The most difficult distinction remains: a response may mention evidence, source, misinformation, or official institutions while still supporting or elaborating the original claim rather than correcting it.

## Current Best Measurement Choice

For downstream analysis, the current safest single model is:

`outputs/pair_relation_deberta_v3_base_claim_response_group_response_3000_hard_negative_support_focused_noweight_20260627T161500Z`

The current best ranking-only option is the average of the 2,200-pair and 3,000-pair `claim_response` models, saved at:

`outputs/pair_relation_ensemble_2200_3000_claim_on_independent_pair_audit_800_20260627T164000Z`

If the next downstream analysis needs a single reproducible model, use the 3,000-pair no-weight model. If the analysis uses scores and can document an ensemble clearly, the 2-model ensemble is slightly stronger.

## Next Technical Step

Further improvement is unlikely to come from simply adding more high-score samples of the same kind. The next useful step should directly target the relation distinction between correction and support. A better sample should overrepresent cases where:

- the response contains correction cues but agrees with the claim,
- the response asks for sources but does not challenge the claim,
- the response says another actor is spreading misinformation while supporting the given claim,
- the response adds factual details that elaborate the claim rather than refute it.

This suggests a more schema-aware sampling strategy rather than a generic hard-negative strategy.
