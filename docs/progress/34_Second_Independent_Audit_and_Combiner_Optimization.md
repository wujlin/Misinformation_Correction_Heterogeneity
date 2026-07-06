# 34. Second Independent Audit and Combiner Optimization

## Purpose

This round tests whether the current pair-level correction detector remains stable on a second independent audit sample. The earlier best clean result was obtained on the first 800-pair audit. A second audit is needed because repeated hard-case sampling and model selection can make the first audit less independent over time.

The key question is:

> Does the detector still rank public-correction pairs well when evaluated on a newly sampled, non-overlapping audit set?

## Second Audit Construction

The second audit sample contains 800 candidate claim-response pairs. It excludes the 5,432-label training set, the first independent audit set, and the recent hard-case development sample.

The sample keeps the same basic structure as the first audit:

- `parent_pair_random_calibration`: 200
- `earlier_claim_pair`: 160
- `parent_pair_near_threshold`: 120
- `parent_pair_high_score`: 120
- `parent_claim_cue_or_short`: 120
- `submission_title_pair`: 80

After Qwen-assisted annotation and combination, the second audit contains:

- negative: 498
- positive: 301
- unclear: 1

This makes audit2 more negative and harder than audit1, which had 410 positives and 390 negatives.

Main paths:

- Sample: `outputs/relation_pair_independent_audit2_sample_800_20260628T022000Z`
- Combined labels: `outputs/llm_qwen_pair_relation_independent_audit2_combined_800_20260628T022500Z`

## Audit2 Model Results

The previous clean thirteen-model ensemble remains stable on audit2 but does not reproduce the first-audit AP level.

On the 798-row inner-joined audit2 evaluation set:

| Score | AP | ROC-AUC | F1@0.5 |
|---|---:|---:|---:|
| current best ten-model mean | 0.778 | 0.867 | 0.744 |
| thirteen-model mean | 0.781 | 0.870 | 0.740 |
| fourteen-model mean with `type4800` | 0.786 | 0.871 | 0.743 |

The AP drop from audit1 is expected because audit2 has lower positive prevalence and harder negatives. The ROC-AUC remains high, which means the detector still ranks correction pairs reasonably well.

Main path:

- `outputs/pair_relation_ensemble_5432_finetune_all_on_independent_pair_audit2_800_20260628T033000Z`

## Combiner Optimization

A lightweight combiner was trained on audit1 predictions and tested on audit2. This uses audit1 as a calibration set and keeps audit2 as the external test.

The best combiner is a regularized logistic stack over 14 model scores. Its audit1 cross-validation selected `C = 0.01`.

Audit2 result:

| Score | AP | ROC-AUC | F1@0.5 |
|---|---:|---:|---:|
| audit1-trained logistic stack, 14 scores | 0.793 | 0.871 | 0.734 |
| audit1-trained logistic stack, 13 scores | 0.792 | 0.871 | 0.733 |
| rank mean, 14 scores | 0.788 | 0.873 | 0.747 |
| simple fourteen-model mean | 0.786 | 0.871 | 0.743 |

This is the strongest methodologically clean audit2 result in this round. It improves the second-audit AP from 0.781 to 0.793 without directly fitting on audit2 labels.

Main path:

- `outputs/pair_relation_ensemble_combiner_audit1_to_audit2_20260628T034500Z`

## Expanded 6,232-Label Training

The 5,432-label training set was combined with audit1, producing a 6,232-row training file:

- positive: 3,677
- negative: 2,551
- unclear: 4
- duplicate `pair_id` rows: 0

Three binary models were fine-tuned from the 5,432 checkpoints and evaluated on audit2:

| Model | Audit2 AP | ROC-AUC |
|---|---:|---:|
| claim6232 | 0.737 | 0.859 |
| title6232 | 0.754 | 0.859 |
| metadata6232 | 0.772 | 0.865 |

The metadata model benefits from the added audit1 labels, but the new binary models do not by themselves exceed the combiner result.

A type6232 model was also trained. Adding type6232 and the three 6232 binary models to the simple mean produces:

| Score | AP | ROC-AUC | F1@0.5 |
|---|---:|---:|---:|
| old14 + new3 + type6232 mean | 0.792 | 0.873 | 0.749 |

This is close to the logistic stack but still slightly below it.

Main paths:

- Combined training set: `outputs/llm_qwen_pair_relation_combined_6232_next_hard_plus_audit1_20260628T035000Z`
- Expanded ensemble: `outputs/pair_relation_ensemble_6232_plus_audit1_type6232_on_audit2_20260628T044500Z`

## Interpretation

The current result is not that the detector has fully reached a stable AP of 0.8 on any independent sample. The more accurate interpretation is:

1. The first-audit AP of 0.824 is optimistic for audit2.
2. The detector remains useful because audit2 ROC-AUC stays around 0.87.
3. Simple averaging is robust but leaves performance on the table.
4. A small audit1-trained combiner improves audit2 AP to 0.793.
5. Adding audit1 labels to the transformer training set helps some models, especially metadata, but does not automatically solve the hard-negative problem.

The next optimization should not only add more labels. It should improve measurement design around the pair relation itself: whether the response corrects the specific claim, not merely whether the response sounds corrective in isolation.
