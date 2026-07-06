# 24. Relation-Pair Measurement Progress

This note records the first implementation of the measurement redesign proposed after the AP-target experiment. The main change is to move from comment-level public-correction detection to claim-response relation detection.

## Measurement Change

The previous binary detector used a single target comment as the unit:

`comment -> public correction / not public correction`

The new relation-level design uses a pair as the unit:

`given claim + response -> correction relation / no correction relation`

This change is necessary because many correction comments are context-dependent. A short response such as "not true", "source?", or "that study was retracted" cannot be reliably classified without knowing what claim is being corrected.

## New Scripts

Three scripts were added.

`src/prepare_relation_pair_annotation_sample.py`

This script creates claim-response candidate pairs from the Reddit COVID vaccine comments. It constructs three types of pairs:

- parent-comment pair
- earlier-thread-claim pair
- submission-title pair

It keeps the previous DeBERTa public-correction score as a sampling signal but changes the annotation unit to `claim_id + response_id`.

`src/llm_annotate_correction_pair_schema.py`

This script runs Qwen annotation on relation pairs. The prompt asks whether the response corrects the given claim, not whether the response sounds like a correction in general.

The schema includes:

- `llm_pair_label_raw`
- `llm_pair_label`
- `llm_pair_relation_type`
- `llm_pair_target_specificity`
- `llm_pair_confidence`
- `llm_corrected_claim_summary`
- `llm_pair_rationale`

The script keeps the raw binary label and also applies a consistency rule. If the model classifies a pair as misinformation support, general opinion, or non-specific target, the final binary label is forced away from a positive correction-relation label.

`src/combine_pair_annotations.py`

This script combines parallel pair-level annotation outputs and exports count tables.

## Pair Sample

Sample directory:

`outputs/relation_pair_annotation_sample_1200_deberta5160_20260627T123000Z`

Inputs:

- comments: `data/interim/covidvaccine_comments.jsonl`
- score signal: `outputs/transformer_correction_deberta_v3_base_textonly_5160_relation_later_20260626T205000Z/predictions/full_comment_predictions.csv`

Candidate pairs:

- 107,023 candidate claim-response pairs
- 1,200 selected annotation pairs

Sample composition:

| Sample component | Rows |
|---|---:|
| `earlier_claim_pair` | 250 |
| `parent_claim_cue_or_short` | 200 |
| `parent_pair_high_score` | 250 |
| `parent_pair_near_threshold` | 180 |
| `parent_pair_random_calibration` | 200 |
| `submission_title_pair` | 120 |

Pair source:

| Pair source | Rows |
|---|---:|
| `parent_comment` | 830 |
| `earlier_thread_claim` | 250 |
| `submission_title` | 120 |

This sample is not a representative random sample. It is a relation-aware measurement sample designed to capture high-score pairs, boundary pairs, short contextual responses, earlier-thread correction, and calibration negatives.

## WSA Annotation Run

The 1,200 pairs were split into two parts and annotated on WSA with Qwen3-8B using both GPUs.

Part outputs:

- `outputs/llm_qwen_pair_relation_part1_20260627T130000Z`
- `outputs/llm_qwen_pair_relation_part2_20260627T130000Z`

Combined output:

`outputs/llm_qwen_pair_relation_combined_1200_20260627T130000Z`

The two jobs completed normally:

- Part 1: 600 rows
- Part 2: 600 rows
- Combined: 1,200 rows

## Label Distribution

Final pair-level label distribution:

| Label | Rows |
|---|---:|
| 0 | 434 |
| 1 | 765 |
| U | 1 |

Raw pair-level label distribution:

| Raw label | Rows |
|---|---:|
| 0 | 389 |
| 1 | 810 |
| U | 1 |

The consistency rule changed 45 raw positive labels into non-positive final labels. This is substantively important. These are cases where the response may contain correction-like language, but the relation to the given claim is not a correction relation.

The changed rows are exported for audit:

`outputs/llm_qwen_pair_relation_combined_1200_20260627T130000Z/tables/raw_final_label_conflicts.csv`

## Relation Types

| Relation type | Rows |
|---|---:|
| `definition_or_context_correction` | 298 |
| `direct_rebuttal` | 85 |
| `evidence_or_source_correction` | 229 |
| `general_opinion_or_reaction` | 232 |
| `misinformation_support_or_elaboration` | 172 |
| `noncorrective_factual_statement` | 28 |
| `questioning_or_source_request` | 133 |
| `sarcastic_or_quote_edit_correction` | 22 |
| `unclear` | 1 |

Target specificity:

| Target specificity | Rows |
|---|---:|
| `given_claim` | 1,001 |
| `general_topic` | 55 |
| `none` | 143 |
| `unclear` | 1 |

## Why This Matters

The run confirms the measurement problem behind the previous AP ceiling. A single comment can look like a correction because it contains words such as misinformation, false, evidence, CDC, FDA, study, or source. However, at the pair level, some of these comments support or elaborate the given claim rather than correct it.

This is exactly the distinction that a comment-level classifier cannot reliably learn:

> correction-looking language is not the same as a correction relation to a specific claim.

This provides a stronger measurement basis for the next detector. The next model should classify claim-response pairs rather than comments alone.

## Important Caution

The consistency rule is useful but not sufficient. Some changed cases show disagreement between the raw binary label, relation type, and rationale. For example, Qwen may produce a corrective rationale but choose a noncorrective relation type, or the reverse.

Therefore, the 45 changed rows should be treated as a priority human-audit subset before they are used as gold training labels.

The current safe interpretation is:

> Pair-level annotation improves the measurement object, but label consistency must be audited before the pair labels become the final training target.

## Next Step

The next modeling step should be:

1. human-audit the 45 raw/final conflict cases;
2. train a preliminary pair-level DeBERTa cross-encoder on `claim_text + response_body + submission_title`;
3. evaluate whether pair-level training reduces false positives among support, elaboration, and noncorrective factual statements;
4. aggregate relation-level scores back to response, user, thread, and subreddit levels.

Only after this relation-level detector improves a pair-level audit should the downstream heterogeneity models be rerun.
