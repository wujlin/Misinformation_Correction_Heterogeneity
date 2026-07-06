# 21. Prediction Improvement and Active Relation Sample

This note records the next measurement-improvement step after the parent-context audit and score-based robustness check.

## Problem

The current correction detector is strong enough for aggregate analysis but not strong enough for confident individual-level classification. The parent-aware audit shows the core issue:

- Best parent-aware audit average precision: 0.539
- ROC-AUC: 0.857
- False positives: 33
- False negatives: 73

The error pattern shows that public correction is not a simple single-comment text classification problem. Some high-score false positives are factual or argumentative statements that resemble corrections but do not clearly correct a prior claim. Some false negatives are short, sarcastic, quote-edit, or parent-dependent corrections.

## Research Basis

Recent prediction-oriented work supports three changes to the pipeline.

First, social correction should be modeled relationally. He et al. (2024) construct triples of misinformation tweet, counter-misinformation reply, and user response, and predict corrective, neutral, or backfire responses. This suggests that correction detection should not rely only on the target comment body. Source: <https://par.nsf.gov/servlets/purl/10523633>

Second, context should be selected rather than simply expanded. Zeng et al. (2025) show that large language models struggle with long structured social context in rumor detection. This supports a refined-context design: parent comment, nearest relevant prior claim, submission title, and selected thread signals. Source: <https://aclanthology.org/2025.naacl-long.128/>

Third, active learning is a better next step than random expansion. CoALFake (Aimeur et al., 2026) combines human-LLM co-annotation with domain-aware active learning for fake-news detection. For this project, active learning means sampling boundary cases that explain current detector errors. Source: <https://arxiv.org/abs/2604.04174>

## New Scripts

Two scripts were added.

`src/prepare_active_relation_annotation_sample.py`

This script prepares active-learning samples for relation-aware annotation. It samples boundary cases from full model predictions and preserves refined context fields:

- submission title
- parent comment
- nearest prior misinformation-like claim in the thread
- target comment
- thread climate variables
- primary and secondary model scores
- active-sampling reason

`src/llm_annotate_correction_relation_schema.py`

This script uses a richer annotation schema. It keeps the binary `is_public_correction` label but adds relation type and target specificity.

Relation types:

- `direct_parent_correction`
- `thread_claim_correction`
- `evidence_or_source_correction`
- `sarcastic_or_quote_edit_correction`
- `noncorrective_factual_statement`
- `misinformation_support_or_claim`
- `general_opinion_or_reaction`
- `unclear`

Target specificity:

- `parent`
- `earlier_thread_claim`
- `general_thread_topic`
- `none`
- `unclear`

The purpose of this schema is measurement improvement. It should not become an over-complicated theory section.

## Active Sample Run

Sample directory:

`outputs/active_relation_annotation_sample_1000_deberta5160_vs_distilroberta_parent_20260627T091500Z`

Primary detector:

`outputs/transformer_correction_deberta_v3_base_textonly_5160_relation_later_20260626T205000Z/predictions/full_comment_predictions.csv`

Secondary detector:

`outputs/transformer_correction_distilroberta_textparent_20260626T105000Z/predictions/full_comment_predictions.csv`

The secondary detector is not treated as a better model. It is used as a weak context-aware disagreement signal until the DeBERTa parent-candidate full prediction can be run on WSA.

Existing LLM-labeled comments were excluded. After exclusion, 159,901 comments were available for sampling.

Selected rows:

- 1,000 active-learning annotation candidates

Sample components:

| Component | Rows |
|---|---:|
| `model_disagreement` | 220 |
| `possible_false_positive_high_score_without_cue` | 180 |
| `possible_false_negative_contextual` | 220 |
| `quote_edit_or_sarcasm` | 130 |
| `short_context_dependent` | 120 |
| `near_primary_threshold` | 90 |
| `parent_misinfo_low_score` | 40 |

The `parent_misinfo_low_score` component selected fewer than its quota because the script enforces no repeated comment IDs and limits over-concentration by submission.

Subreddit distribution:

| Subreddit | Rows |
|---|---:|
| `conspiracy` | 504 |
| `coronavirus` | 197 |
| `news` | 142 |
| `conservative` | 69 |
| other subreddits | 88 |

Sample features:

- Mean primary score: 0.450
- Primary predicted positive share: 0.412
- Rows with parent body: 0.612
- Rows with correction cue: 0.142
- Rows with sarcasm cue: 0.135
- Rows with quote marker: 0.037
- Mean body length: 123 characters

This confirms that the sample targets relation-sensitive and boundary cases rather than ordinary random comments.

## Next Execution Step

When WSA access is available, run relation-aware Qwen annotation on:

`outputs/active_relation_annotation_sample_1000_deberta5160_vs_distilroberta_parent_20260627T091500Z/annotation_sample.csv`

The sample has also been split for two parallel annotation jobs:

- `annotation_sample_part1.csv`: 500 rows
- `annotation_sample_part2.csv`: 500 rows

Expected output directory:

`outputs/llm_qwen_relation_schema_active_sample_1000_20260627TxxxxxxZ`

After annotation, the pipeline should:

1. Map relation labels back to binary correction labels.
2. Train a binary detector and a relation-type auxiliary detector.
3. Compare the new detector on the parent-aware random audit set.
4. Re-run the score-based downstream models only if audit average precision improves.

## Revised Contribution Logic

The contribution should not be written as "audience structural heterogeneity is unstable." That is only a measurement result.

The stronger contribution is:

> Public correction is a conversion process. Cross-community participation creates correction capacity, while local conversational context helps convert that capacity into public correction. The stable empirical pattern is that cross-group users and discursively heterogeneous early threads produce more later correction. Visible-audience structural heterogeneity is a weaker condition, suggesting that audience diversity alone is not enough to explain public correction.

This framing keeps the theoretical value of heterogeneity while avoiding an overclaim about one unstable proxy.
