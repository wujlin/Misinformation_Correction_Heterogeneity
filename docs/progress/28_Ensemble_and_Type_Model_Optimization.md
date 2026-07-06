# Ensemble and Relation-Type Model Optimization

This run continued optimization after the hard-negative expansion. The goal was to test whether model architecture, relation-type supervision, and score ensembling can improve pair-level correction detection on the independent 800-pair audit set.

## Starting Point

The best previous single model was the 3,000-label `claim_response` DeBERTa-v3-base binary classifier:

`outputs/pair_relation_deberta_v3_base_claim_response_group_response_3000_hard_negative_support_focused_noweight_20260627T161500Z`

Its independent audit performance was AP = 0.765 and ROC-AUC = 0.766. A simple ensemble of the 2,200-label and 3,000-label binary models reached AP = 0.771.

## Tests

I tested four additional directions.

First, I trained a larger binary cross-encoder using `microsoft/deberta-v3-large`. This did not improve external performance. The large binary model reached AP = 0.755 and ROC-AUC = 0.750 on the audit set. The result suggests that the bottleneck is not simply model capacity.

Second, I trained a relation-type classifier instead of a binary correction classifier. The model predicts relation types such as `direct_rebuttal`, `evidence_or_source_correction`, `misinformation_support_or_elaboration`, and `general_opinion_or_reaction`. The correction score is then computed as the sum of probabilities for corrective relation types. This base relation-type model reached AP = 0.767 and ROC-AUC = 0.766 on the audit set. The single-model gain was small, but the score was complementary to binary classifiers.

Third, I tested a large relation-type model. This failed to learn stable relation-type boundaries and reached only AP = 0.537 on the audit set. I also tested a balanced relation-type base model, which reached AP = 0.668. These runs are not used.

Fourth, I ensembled the useful models. The best observed result came from a simple average of three scores:

- 3,000-label binary DeBERTa-v3-base score,
- 3,000-label binary DeBERTa-v3-large score,
- 3,000-label relation-type DeBERTa-v3-base correction score.

This simple three-model average reached AP = 0.795 and ROC-AUC = 0.790 on the independent audit set.

The saved artifact is:

`outputs/pair_relation_ensemble_binary_type_on_independent_pair_audit_800_20260627T173000Z`

## Result Summary

| Model / score | External AP | ROC-AUC | Interpretation |
|---|---:|---:|---|
| 3,000-label binary base | 0.765 | 0.766 | Best previous single model |
| 2,200 + 3,000 binary ensemble | 0.771 | 0.771 | Small gain from same-task ensembling |
| 3,000-label binary large | 0.755 | 0.750 | Larger model alone did not improve |
| 3,000-label relation-type base | 0.767 | 0.766 | Small single-model gain; useful complement |
| Binary base + binary large + type base mean | 0.795 | 0.790 | Current best ranking result |
| Validation-tuned weighted ensemble | 0.791 | 0.783 | Did not beat simple mean on audit |
| Relation-type large | 0.537 | 0.523 | Failed run |
| Relation-type base balanced | 0.668 | 0.684 | Failed run |

## Error Structure

The current best ensemble substantially reduces the hardest false-positive types compared with the 3,000-label binary base model.

| Negative relation type | Audit rows | Binary 3,000 predicted positive | Best ensemble predicted positive |
|---|---:|---:|---:|
| `general_opinion_or_reaction` | 226 | 128 | 91 |
| `misinformation_support_or_elaboration` | 143 | 74 | 46 |
| `noncorrective_factual_statement` | 16 | 14 | 14 |

This is the most important technical result from this round. The relation-type model does not simply add another score. It helps distinguish correction from supportive elaboration and general reaction, which was the core measurement problem.

The remaining hard case is `noncorrective_factual_statement`. The ensemble still predicts 14 of 16 such cases as correction. This category is small in the audit set, but it signals that factual language without a correction relation remains difficult.

## Interpretation

The improvement from AP = 0.765 to AP = 0.795 is meaningful because it comes from changing the learning target, not from adding more similar labels. Binary models learn whether a response is a correction. The relation-type model forces the classifier to represent different non-correction forms. This provides a more direct handle on the false-positive problem.

The current result is close to the AP = 0.8 target. However, it should be described as "approximately 0.80" only with care. The strict number is AP = 0.795 on the independent 800-pair audit set.

## Current Recommendation

For downstream score-based analysis, use the ensemble score:

`outputs/pair_relation_ensemble_binary_type_on_independent_pair_audit_800_20260627T173000Z`

For a single-model fallback, use:

`outputs/pair_relation_deberta_v3_base_claim_response_group_response_3000_hard_negative_support_focused_noweight_20260627T161500Z`

The ensemble is better for ranking likely correction relations. The single model is simpler and easier to describe if the analysis needs a single detector.

## Next Step

The next useful optimization is not another generic hard-negative sample. The next sample should target `noncorrective_factual_statement` and borderline support cases with factual language. A focused annotation batch should include cases where the response:

- provides factual information without rejecting the claim,
- cites evidence while supporting the claim,
- discusses CDC, FDA, study, data, source, or misinformation without correcting the given claim,
- asks for sources but does not clearly challenge the claim.

That batch should be designed for relation-type learning rather than binary learning.
