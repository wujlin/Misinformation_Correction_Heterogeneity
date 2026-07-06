# 25. Pair-Relation Classifier Results

This note records the first DeBERTa cross-encoder experiments after the relation-pair measurement redesign.

## Input Labels

The training input is the combined pair-level Qwen annotation file:

`outputs/llm_qwen_pair_relation_combined_1200_20260627T130000Z/llm_pair_annotations.csv`

The project owner reviewed the raw/final label conflict cases and found the consistency-rule corrections broadly aligned with manual judgment. Therefore, the first pair-level classifier uses the final pair label:

`llm_pair_label`

Binary rows:

| Label | Rows |
|---|---:|
| 0 | 434 |
| 1 | 765 |

One uncertain row was excluded, leaving 1,199 binary pair labels.

## Model Task

The model task is:

`given claim + response -> correction relation / no correction relation`

This differs from the earlier comment-level detector:

`comment -> public correction / not public correction`

The pair-level model is a cross-encoder because the claim and response are encoded together. This allows the model to learn whether the response corrects the given claim rather than merely contains correction-like language.

## Split Design

The split uses `group_response` mode. The same `response_id` is not allowed to appear in both train and validation/test sets.

This matters because a response can have more than one candidate claim pair. A random split would risk placing the same response in both training and evaluation, which would overstate performance.

Split summary:

| Split | Rows | Negative | Positive | Unique response IDs |
|---|---:|---:|---:|---:|
| Train | 837 | 303 | 534 | 810 |
| Validation | 179 | 64 | 115 | 174 |
| Test | 183 | 67 | 116 | 174 |

## Runs

Five DeBERTa-v3-base variants were trained on WSA. Checkpoints remain on WSA; local sync keeps only logs, metrics, tables, and validation/test predictions.

| Feature mode | Class weight | Best epoch | Val AP | Test AP | Test ROC-AUC | Test positive F1 | Test precision | Test recall |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `title_claim_response` | balanced | 2 | 0.804 | 0.743 | 0.604 | 0.769 | 0.635 | 0.974 |
| `title_claim_response` | none | 5 | 0.794 | 0.772 | 0.628 | 0.776 | 0.661 | 0.940 |
| `metadata_title_claim_response` | balanced | 2 | 0.796 | 0.720 | 0.576 | 0.710 | 0.637 | 0.802 |
| `claim_response` | none | 4 | 0.830 | 0.775 | 0.662 | 0.767 | 0.680 | 0.879 |
| `metadata_title_claim_response` | none | 2 | 0.797 | 0.701 | 0.566 | 0.667 | 0.645 | 0.690 |

Best run:

`outputs/pair_relation_deberta_v3_base_claim_response_group_response_noweight_20260627T132500Z`

Best test metrics:

- Test AP: 0.775
- Test ROC-AUC: 0.662
- Positive F1: 0.767
- Positive precision: 0.680
- Positive recall: 0.879

## Interpretation

The best pair-level model uses only the claim and response text. Adding submission title does not improve the held-out test score, and adding subreddit/pair-source metadata reduces performance. This suggests that the core signal is the semantic relation between the claim and response, not external metadata.

The result also supports the measurement redesign. The previous comment-level detector struggled because it asked whether a comment looked like correction. The pair-level detector asks whether the response corrects a specific claim, which is closer to the theoretical object and produces better internal separation.

However, the result should be reported carefully:

> The pair-level classifier reaches test AP around 0.775 under a response-group split, but this is still an internal pair-level evaluation on an actively sampled relation dataset. It is not equivalent to the earlier independent random comment audit.

## Method Consequence

The next methodological step is not to return to comment-level binary classification. The better path is:

1. build an independent pair-level audit set;
2. include hard negatives where responses contain correction-like words but support or elaborate the given claim;
3. evaluate the best pair-level model on that audit;
4. only then aggregate pair-level relation scores back to response, user, thread, and subreddit levels.

The current best deployable pair model is:

`outputs/pair_relation_deberta_v3_base_claim_response_group_response_noweight_20260627T132500Z/checkpoints/best_model`

The local lightweight result copy is:

`outputs/pair_relation_deberta_v3_base_claim_response_group_response_noweight_20260627T132500Z`

## Current Research Implication

The substantive measurement claim is now stronger:

> Public correction should be measured as a relation between a response and a corrected claim. Comment-level correction detection confuses correction-like language with actual correction relations, while pair-level measurement can separate rebuttal, evidence correction, support, elaboration, and general opinion.

This supports the broader theoretical model because the outcome is now closer to "conversion from exposure to correction relation" rather than generic corrective wording.
