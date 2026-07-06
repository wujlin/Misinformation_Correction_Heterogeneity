# 22. Relation Active Annotation and Detector Rerun

This note records the WSA run after the active relation-aware sample was generated.

## Run Summary

The active relation-aware sample was annotated with Qwen3-8B on WSA using two parallel GPU jobs.

Input sample:

`outputs/active_relation_annotation_sample_1000_deberta5160_vs_distilroberta_parent_20260627T091500Z`

Part outputs:

- `outputs/llm_qwen_relation_schema_active_sample_part1_20260627T024500Z`
- `outputs/llm_qwen_relation_schema_active_sample_part2_20260627T024500Z`

Combined output:

`outputs/llm_qwen_relation_schema_active_sample_combined_1000_20260627T030500Z`

The two annotation jobs completed normally:

- Part 1: 500 rows, elapsed 1,068 seconds
- Part 2: 500 rows, elapsed 1,002 seconds

## Relation-Aware Label Distribution

The combined active sample contains 1,000 labeled comments:

| Binary label | Rows |
|---|---:|
| 0 | 522 |
| 1 | 478 |

Relation types:

| Relation type | Rows |
|---|---:|
| `general_opinion_or_reaction` | 498 |
| `noncorrective_factual_statement` | 127 |
| `misinformation_support_or_claim` | 98 |
| `sarcastic_or_quote_edit_correction` | 98 |
| `direct_parent_correction` | 93 |
| `evidence_or_source_correction` | 50 |
| `thread_claim_correction` | 36 |

Target specificity:

| Target specificity | Rows |
|---|---:|
| `none` | 627 |
| `parent` | 333 |
| `earlier_thread_claim` | 37 |
| `general_thread_topic` | 3 |

The relation distribution confirms that the sample is not a representative random sample. It is a hard-case pool with many short reactions, factual-but-noncorrective statements, and relation-specific corrections.

## Active Components

The sample was intentionally concentrated in model-error regions.

| Sample component | Negative | Positive |
|---|---:|---:|
| `model_disagreement` | 72 | 148 |
| `near_primary_threshold` | 35 | 55 |
| `parent_misinfo_low_score` | 35 | 5 |
| `possible_false_negative_contextual` | 193 | 27 |
| `possible_false_positive_high_score_without_cue` | 16 | 164 |
| `quote_edit_or_sarcasm` | 63 | 67 |
| `short_context_dependent` | 108 | 12 |

The table shows why this sample is useful for diagnosis. The old detector's difficult regions contain both real corrections and convincing noncorrections. The sample should therefore be used to model boundary distinctions, not simply to change the overall positive rate.

## Binary Training Set

The active sample was merged with the previous 5,160-label training set:

`outputs/llm_qwen_public_correction_combined_6160_relation_active_20260627T031000Z`

Combined labels:

| Label | Rows |
|---|---:|
| 0 | 4,004 |
| 1 | 2,147 |
| U | 9 |

The combined file contains 6,151 binary training labels after excluding uncertain labels during training.

## Detector Reruns

Three DeBERTa reruns were trained and evaluated against the independent parent-aware random audit set. The audit set is unchanged:

`outputs/llm_qwen_public_correction_random_audit_parent_context_preserved_800_20260626T215500Z`

Audit labels:

- 676 negative
- 123 positive
- 799 binary rows after excluding one uncertain row

External audit comparison:

| Model | Feature mode | Class weight | Audit AP | ROC-AUC | Positive F1 | Predicted positives |
|---|---|---|---:|---:|---:|---:|
| 5,160 previous best | `text_only` | balanced | 0.539 | 0.857 | 0.485 | 83 |
| 6,160 active | `text_parent_candidate` | balanced | 0.519 | 0.831 | 0.487 | 189 |
| 6,160 active | `text_only` | balanced | 0.528 | 0.791 | 0.539 | 118 |
| 6,160 active | `text_only` | none | 0.493 | 0.718 | 0.506 | 138 |

The direct binary merge does not improve average precision. The balanced 6,160 text-only model improves threshold-level positive F1, but its ranking quality is lower than the previous 5,160 model. The no-weight model performs worse.

## Interpretation

The result is not that active annotation failed. The result is more specific:

> Relation-aware active labels are useful for identifying model boundary errors, but directly pooling them into a standard binary training set changes the training distribution and does not improve audit average precision.

This distinction matters. The 1,000 active labels are enriched for hard cases and cannot be treated like another random block of training labels. They should be used as a structured diagnostic and auxiliary source.

## Method Consequence

The next prediction step should not be another simple binary rerun. The evidence points to three better options:

1. **Stratified training or sample weighting.** Active cases should be weighted differently from random or relation-balanced labels.
2. **Two-stage prediction.** Use a high-recall candidate detector first, then a relation-type classifier to distinguish direct correction, evidence correction, sarcastic correction, factual noncorrection, and misinformation support.
3. **Auxiliary relation supervision.** Use relation labels to train or evaluate a secondary error-type classifier instead of collapsing all relation categories into one binary label at the input stage.

Until one of these approaches improves independent-audit AP, the previous 5,160-label text-only DeBERTa remains the best ranking detector for downstream aggregate analysis.

## Current Claim Boundary

The active relation annotation strengthens the measurement story but does not yet improve the main detector. Therefore, downstream heterogeneity models should not be rerun from the 6,160 active detector. The current defensible position is:

> Public correction detection requires relation-aware measurement, but relation-aware data must be incorporated through a model design that respects sampling and relation-type structure. Simply adding hard cases as ordinary binary labels improves some threshold behavior while reducing ranking performance.
