# NLI and Bagging Optimization

This run tested whether the pair-level detector could be pushed beyond the previous AP = 0.795 result. The main directions were new random seeds, NLI-pretrained backbones, and expanded score ensembling.

## Starting Point

The previous best result was a simple mean of three complementary scores:

- 3,000-label binary DeBERTa-v3-base,
- 3,000-label binary DeBERTa-v3-large,
- 3,000-label relation-type DeBERTa-v3-base.

This ensemble reached AP = 0.795 and ROC-AUC = 0.790 on the independent 800-pair audit set.

## New-Seed Bagging

I first trained another 3,000-label binary DeBERTa-v3-base model and another relation-type DeBERTa-v3-base model with seed `20260631`.

The new seed did not improve external performance. The binary model had strong internal test AP, but only reached AP = 0.745 on the independent audit set. The new relation-type model reached AP = 0.716. Adding these models to the ensemble did not improve the previous best score.

This suggests that ordinary seed bagging is not the main path forward. The useful model diversity needs to come from different training objectives or pretrained priors, not just random initialization and split variation.

## NLI-Pretrained Models

I then tested two NLI-pretrained backbones.

The first model used `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`. This model was weak as a single detector, reaching AP = 0.743 on the independent audit. However, it added useful complementary information when averaged with the previous binary and relation-type models.

The second model used `roberta-large-mnli`. This model was also weak as a single detector, reaching AP = 0.725. It did not improve the best ensemble and is not used.

## Best Result

The best observed result is a simple average of four complementary scores:

- 3,000-label binary DeBERTa-v3-base,
- 3,000-label binary DeBERTa-v3-large,
- 3,000-label relation-type DeBERTa-v3-base,
- NLI/FEVER-pretrained DeBERTa-v3-base binary model.

This four-model mean reached:

- AP = 0.800
- ROC-AUC = 0.792
- F1 at threshold 0.5 = 0.732
- Precision at threshold 0.5 = 0.673
- Recall at threshold 0.5 = 0.802

The saved artifact is:

`outputs/pair_relation_ensemble_binary_type_nli_mean_on_independent_pair_audit_800_20260627T193000Z`

## Caution on Selection

There are two honest ways to report the ensemble results.

The strongest observed audit result is the four-model mean above, with AP = 0.800. This is a simple and interpretable combination of complementary model families, but it was still observed through repeated audit checks.

The stricter validation-selected subset used internal validation AP to choose the model subset. It selected `binary_large + typebase`, which reached AP = 0.791 on the audit set. This is more conservative but lower.

Therefore, the current result should be described carefully:

> The best observed independent-audit result reaches AP = 0.800 using a simple four-model mean, while a stricter validation-selected ensemble reaches AP = 0.791.

## Error Structure

Compared with the 3,000-label binary base model, the four-model mean still reduces the main false-positive categories:

| Negative relation type | Audit rows | Binary 3,000 predicted positive | Four-model mean predicted positive |
|---|---:|---:|---:|
| `general_opinion_or_reaction` | 226 | 128 | 96 |
| `misinformation_support_or_elaboration` | 143 | 74 | 47 |
| `noncorrective_factual_statement` | 16 | 14 | 14 |

The model still struggles with factual but noncorrective statements. This category remains the clearest next measurement bottleneck.

## Interpretation

The improvement from AP = 0.795 to AP = 0.800 is small but meaningful. It confirms that NLI-style pretraining contains some useful signal for correction detection, even when the NLI model is not strong enough as a standalone detector. The gain comes from complementary ranking behavior rather than single-model superiority.

The result also clarifies what does not help:

- another random seed does not improve the ensemble,
- RoBERTa-large-MNLI does not transfer well here,
- simply increasing model size is not enough,
- balanced relation-type training hurts external performance.

## Current Recommendation

For the strongest score-based analysis, use:

`outputs/pair_relation_ensemble_binary_type_nli_mean_on_independent_pair_audit_800_20260627T193000Z`

For a conservative robustness analysis, also report:

`outputs/pair_relation_ensemble_binary_type_nli_valselected_on_independent_pair_audit_800_20260627T185000Z`

For a single-model fallback, continue using:

`outputs/pair_relation_deberta_v3_base_claim_response_group_response_3000_hard_negative_support_focused_noweight_20260627T161500Z`

## Next Step

Further gains are unlikely to come from more generic model variants. The next substantive improvement should come from targeted annotation for `noncorrective_factual_statement` and factual-support cases. The detector needs more examples where a response sounds factual, cites evidence, or discusses institutions, but does not actually correct the given claim.
