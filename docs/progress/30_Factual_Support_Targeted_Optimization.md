# Factual-Support Targeted Optimization

This run continued the pair-level correction detector optimization after the NLI ensemble reached AP = 0.800. The goal was to address the remaining measurement bottleneck: responses that look factual, cite numbers or institutions, or elaborate on vaccine/COVID claims, but do not actually correct the given claim.

## Starting Point

The previous best observed result was the four-model mean:

- 3,000-label binary DeBERTa-v3-base,
- 3,000-label binary DeBERTa-v3-large,
- 3,000-label relation-type DeBERTa-v3-base,
- NLI/FEVER-pretrained DeBERTa-v3-base.

This ensemble reached AP = 0.800 and ROC-AUC = 0.792 on the independent 800-pair audit set.

## Targeted Annotation

I first scored the remaining 6,200 unused pair candidates with four existing models:

- binary 3,000-label DeBERTa-v3-base,
- binary 3,000-label DeBERTa-v3-large,
- NLI/FEVER-pretrained DeBERTa-v3-base,
- relation-type DeBERTa-v3-base.

Then I selected 700 additional pair samples focused on factual and support-like boundary cases. The sample included high-score factual cases, support-like factual cases, numeric factual cases, correction-cue factual cases, type-model support cases, low-score factual calibration cases, and random calibration cases.

The combined 700-label supplement contained:

| Label or relation type | Count |
|---|---:|
| correction relation | 416 |
| non-correction relation | 283 |
| unclear | 1 |
| misinformation support or elaboration | 114 |
| general opinion or reaction | 146 |
| noncorrective factual statement | 17 |

The new full training set contains 3,700 pair labels, with 2,351 positive correction relations, 1,347 negative relations, and 2 unclear rows excluded by binary training.

## Single-Model Results

The 3,700-label binary DeBERTa-v3-base model improved as a standalone external-audit detector:

| Model | Audit AP | ROC-AUC | F1 at threshold 0.5 |
|---|---:|---:|---:|
| old 3,000-label binary base | 0.765 | 0.766 | 0.727 |
| new 3,700-label binary base | 0.788 | 0.775 | 0.729 |

This means the targeted factual-support labels helped the base binary model learn a better ranking on the independent audit set.

The same improvement did not transfer to all model families. The 3,700-label relation-type model fell to AP = 0.745. The 3,700-label DeBERTa-large model fell to AP = 0.730. The 3,700-label NLI/FEVER model fell to AP = 0.712. The class-balanced 3,700-label base model reached AP = 0.764. These variants are not used in the final ensemble.

## Best Ensemble

The best observed result is a five-model mean that keeps the strongest old models and adds the new 3,700-label binary base model:

- old 3,000-label binary DeBERTa-v3-base,
- new 3,700-label binary DeBERTa-v3-base,
- old 3,000-label binary DeBERTa-v3-large,
- old 3,000-label relation-type DeBERTa-v3-base,
- old 3,000-label NLI/FEVER-pretrained DeBERTa-v3-base.

This ensemble reached:

| Metric | Value |
|---|---:|
| AP | 0.8068 |
| ROC-AUC | 0.7971 |
| Precision at threshold 0.5 | 0.6805 |
| Recall at threshold 0.5 | 0.8415 |
| F1 at threshold 0.5 | 0.7525 |
| Predicted positives at threshold 0.5 | 507 |

The saved artifact is:

`outputs/pair_relation_ensemble_oldbase_newbase_large_oldtype_nli_mean_on_independent_pair_audit_800_20260627T213000Z`

## Improvement Over Previous Best

Compared with the previous four-model mean:

| Ensemble | Audit AP | ROC-AUC |
|---|---:|---:|
| previous four-model mean | 0.8001 | 0.7917 |
| new five-model mean | 0.8068 | 0.7971 |
| difference | +0.0067 | +0.0054 |

A 5,000-iteration bootstrap comparison gives:

- AP difference 95% interval: [-0.0009, 0.0148],
- probability that the AP difference is positive: 0.956,
- AUC difference 95% interval: [-0.0014, 0.0121],
- probability that the AUC difference is positive: 0.939.

This supports a cautious interpretation: the new factual-support annotation produces a small, directionally stable improvement, but the gain is not large enough to claim a decisive breakthrough from the same 800-pair audit alone.

## Interpretation

The main lesson is that targeted measurement work helps more than generic model expansion. Adding factual-support boundary labels improved the base binary model and improved the ensemble when combined with earlier complementary models. However, retraining all model families on the expanded set did not automatically help. The relation-type, large, NLI, and balanced variants all declined on the independent audit.

The current best detector should therefore be treated as a heterogeneous ensemble: older models preserve useful decision boundaries, while the new 3,700-label base model contributes additional ranking information learned from factual-support hard cases.

## Current Recommendation

For the strongest observed detector, use:

`outputs/pair_relation_ensemble_oldbase_newbase_large_oldtype_nli_mean_on_independent_pair_audit_800_20260627T213000Z`

For comparison with the previous best, use:

`outputs/pair_relation_ensemble_binary_type_nli_mean_on_independent_pair_audit_800_20260627T193000Z`

For a single-model fallback, use:

`outputs/pair_relation_deberta_v3_base_3700_factual_support_on_independent_pair_audit_800_20260627T204000Z`

## Next Step

The next improvement should not be another generic backbone test. The useful direction is a second independent audit or a small human-reviewed validation set focused on factual-support and noncorrective factual cases. Without another held-out set, further audit-driven ensemble selection will increasingly risk overfitting the current 800-pair audit.
