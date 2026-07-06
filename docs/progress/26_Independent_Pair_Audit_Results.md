# 26. Independent Pair Audit Results

This note records the first external audit of the pair-level relation classifier.

## Purpose

The previous pair-level DeBERTa result was based on an internal response-group split. That result showed that pair-level measurement is promising, but it did not prove that the classifier generalizes to a new pair sample.

This audit tests the current best pair-level model on a new claim-response pair sample that does not overlap with the 1,200 training/validation/test annotation pairs.

## Audit Sample

Audit sample directory:

`outputs/relation_pair_independent_audit_sample_800_deberta5160_20260627T134000Z`

Training sample excluded:

`outputs/relation_pair_annotation_sample_1200_deberta5160_20260627T123000Z/annotation_pairs.csv`

Overlap check:

- training pair IDs: 1,200
- audit pair IDs: 800
- overlap: 0

Audit sample composition:

| Sample component | Rows |
|---|---:|
| `earlier_claim_pair` | 160 |
| `parent_claim_cue_or_short` | 120 |
| `parent_pair_high_score` | 120 |
| `parent_pair_near_threshold` | 120 |
| `parent_pair_random_calibration` | 200 |
| `submission_title_pair` | 80 |

Pair source:

| Pair source | Rows |
|---|---:|
| `parent_comment` | 560 |
| `earlier_thread_claim` | 160 |
| `submission_title` | 80 |

## Audit Annotation

The audit sample was annotated with Qwen3-8B on WSA using two GPUs.

Part outputs:

- `outputs/llm_qwen_pair_relation_independent_audit_part1_20260627T134500Z`
- `outputs/llm_qwen_pair_relation_independent_audit_part2_20260627T134500Z`

Combined output:

`outputs/llm_qwen_pair_relation_independent_audit_combined_800_20260627T134500Z`

Final audit labels:

| Label | Rows |
|---|---:|
| 0 | 390 |
| 1 | 410 |

Raw labels:

| Raw label | Rows |
|---|---:|
| 0 | 359 |
| 1 | 441 |

The consistency rule changed 31 raw positives into non-positive final labels. These cases are exported here:

`outputs/llm_qwen_pair_relation_independent_audit_combined_800_20260627T134500Z/tables/raw_final_label_conflicts.csv`

## Main External Evaluation

The best internal pair-level model from the previous round was:

`outputs/pair_relation_deberta_v3_base_claim_response_group_response_noweight_20260627T132500Z`

It uses:

- feature mode: `claim_response`
- class weight: none
- response-group split during training
- fixed threshold from validation: 0.384765625

External audit output:

`outputs/pair_relation_deberta_v3_base_claim_response_group_response_noweight_20260627T132500Z_on_independent_pair_audit_800_20260627T140500Z`

Main metrics at the fixed validation threshold:

| Metric | Value |
|---|---:|
| Average precision | 0.718 |
| ROC-AUC | 0.720 |
| Positive F1 | 0.706 |
| Positive precision | 0.619 |
| Positive recall | 0.822 |
| Predicted positives | 544 / 800 |

Confusion matrix:

|  | Predicted 0 | Predicted 1 |
|---|---:|---:|
| True 0 | 183 | 207 |
| True 1 | 73 | 337 |

The audit-oracle threshold gives only a small F1 improvement:

- oracle threshold: 0.345
- oracle positive F1: 0.718

This suggests the main issue is not only threshold calibration. The remaining issue is false positives on hard negative relations.

## Model Comparison on External Audit

All five pair-level DeBERTa variants were evaluated on the same independent audit sample.

| Feature mode | Class weight | Audit AP | Audit ROC-AUC | Positive F1 | Precision | Recall | Predicted positives |
|---|---|---:|---:|---:|---:|---:|---:|
| `title_claim_response` | balanced | 0.687 | 0.672 | 0.683 | 0.526 | 0.973 | 758 |
| `title_claim_response` | none | 0.707 | 0.706 | 0.696 | 0.586 | 0.856 | 599 |
| `metadata_title_claim_response` | balanced | 0.681 | 0.663 | 0.677 | 0.579 | 0.817 | 579 |
| `claim_response` | none | 0.718 | 0.720 | 0.706 | 0.619 | 0.822 | 544 |
| `metadata_title_claim_response` | none | 0.689 | 0.666 | 0.643 | 0.611 | 0.678 | 455 |

The external audit confirms the same model selection conclusion as the internal split:

> The clean claim-response input without metadata is the best current pair-level classifier.

Metadata does not help in the current setup. It likely introduces shortcut signals that do not generalize across pair samples.

## Error Pattern

Subgroup metrics show that the model performs better on explicit correction sources:

| Pair source | Rows | AP | Positive F1 |
|---|---:|---:|---:|
| `submission_title` | 80 | 0.897 | 0.905 |
| `earlier_thread_claim` | 160 | 0.765 | 0.711 |
| `parent_comment` | 560 | 0.623 | 0.659 |

The weakest area is parent-comment pairs, especially calibration and hard-negative cases.

By relation type, the main false-positive problem is clear:

| Relation type | Rows | True positives | Predicted positives |
|---|---:|---:|---:|
| `general_opinion_or_reaction` | 226 | 0 | 128 |
| `misinformation_support_or_elaboration` | 143 | 0 | 65 |
| `noncorrective_factual_statement` | 16 | 0 | 13 |

This means that the model still overpredicts correction on comments that have correction-like wording but do not correct the given claim.

The top false-positive and false-negative tables are exported here:

- `outputs/pair_relation_deberta_v3_base_claim_response_group_response_noweight_20260627T132500Z_on_independent_pair_audit_800_20260627T140500Z/tables/top_false_positives.csv`
- `outputs/pair_relation_deberta_v3_base_claim_response_group_response_noweight_20260627T132500Z_on_independent_pair_audit_800_20260627T140500Z/tables/top_false_negatives.csv`

## Interpretation

The independent audit supports the measurement redesign but also identifies the next bottleneck.

The improvement is real:

> Pair-level modeling generalizes better than the earlier comment-level detector because it asks whether a response corrects a specific claim, not whether a comment merely sounds corrective.

The remaining problem is also clear:

> The current pair model still confuses actual correction relations with hard negatives such as general reactions, support/elaboration of misinformation claims, and noncorrective factual statements.

Therefore, the next model improvement should focus on hard-negative learning, not on adding more metadata.

## Next Step

The next training sample should deliberately add hard negatives:

1. high-scoring false-positive-like pairs;
2. responses containing correction cues but supporting the given claim;
3. factual statements that do not target the given claim;
4. general opinion/reaction pairs with correction-like vocabulary.

The independent audit should remain held out. The next training expansion should be sampled from new non-overlapping pair IDs, annotated separately, and then evaluated again on this 800-pair audit.
