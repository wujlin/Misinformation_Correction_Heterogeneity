# 23. AP Target and Hard-Case Filter Results

This note records the prediction-improvement experiments after the 6,160-label relation-aware rerun. The goal was to test whether the correction detector can be pushed toward an average precision near 0.8 on the independent parent-aware random audit set.

## Evaluation Anchor

The evaluation anchor remains the independent parent-aware random audit set:

`outputs/llm_qwen_public_correction_random_audit_parent_context_preserved_800_20260626T215500Z`

The binary audit set contains:

- 676 negative comments
- 123 public correction comments
- 799 binary rows after excluding one uncertain row

This audit set is treated as the main external validity check. Internal validation or hard-case test performance should not be compared directly with this random audit score.

## Baseline to Beat

The strongest deployable detector before this round remains:

`outputs/transformer_correction_deberta_v3_base_textonly_5160_relation_later_20260626T205000Z`

Independent audit performance:

| Model | Audit AP | ROC-AUC | Positive F1 | Predicted positives |
|---|---:|---:|---:|---:|
| DeBERTa 5,160 text-only | 0.539 | 0.857 | 0.485 | 83 |

This model is still the main ranking detector unless a later model improves independent-audit average precision.

## Score Reranker

A score-level reranker was trained using existing model scores and lightweight text/context features.

Run directory:

`outputs/score_reranker_6160_multi_base_independent_audit_20260627T111500Z`

The reranker compared:

- the 5,160-label DeBERTa detector
- the 3,960-label DeBERTa detector
- earlier DeBERTa and DistilRoBERTa variants
- lightweight logistic and tree-based score combinations
- context and cue features
- active-sample weighting variants

Result:

| Model family | Best audit AP | ROC-AUC | Positive F1 |
|---|---:|---:|---:|
| Best single baseline | 0.539 | 0.857 | 0.488 |
| Best reranker | 0.511 | 0.798 | 0.472 |

The score reranker did not improve ranking quality. The best result remained the previous 5,160-label DeBERTa score.

## Hard-Case Filter

A separate hard-case filter was trained only on the 1,000 active relation-aware labels.

Run directory:

`outputs/transformer_hardcase_filter_deberta_v3_base_text_parent_candidate_active1000_eval_20260627T115500Z`

Internal hard-case split performance:

| Split | AP | ROC-AUC | Positive F1 | Positive precision | Positive recall |
|---|---:|---:|---:|---:|---:|
| Validation | 0.815 | 0.816 | 0.756 | 0.674 | 0.861 |
| Test | 0.795 | 0.828 | 0.759 | 0.698 | 0.833 |

This looks close to the 0.8 AP target, but the interpretation is narrow. The model is evaluated on an enriched active-learning pool, not on the full random comment distribution.

External random audit evaluation:

Run directory:

`outputs/parent_context_random_audit_eval_hardcase_filter_active1000_text_parent_candidate_20260627T120000Z`

| Model | Audit AP | ROC-AUC | Positive F1 | Positive precision | Positive recall | Predicted positives |
|---|---:|---:|---:|---:|---:|---:|
| Hard-case filter | 0.459 | 0.783 | 0.341 | 0.210 | 0.894 | 523 |

The hard-case filter has high recall but overpredicts correction on the random audit set. It is useful as a boundary detector, but not as a global public-correction detector.

## Base Plus Hard-Case Combination

The hard-case score was then combined with the 5,160-label baseline score.

Validation-selected combination:

`outputs/combo_base5160_hardcase_fullpred_val_selected_20260627T122000Z`

| Selector | Combination | Audit AP | ROC-AUC | Positive F1 | Predicted positives |
|---|---|---:|---:|---:|---:|
| 5,160 validation | Linear, alpha 1.00 | 0.539 | 0.857 | 0.480 | 81 |
| 6,160 validation | Linear, alpha 0.99 | 0.548 | 0.864 | 0.485 | 83 |

The validation-selected combination gives a small audit AP improvement from 0.539 to 0.548. This is a real but modest gain. It does not change the overall measurement conclusion.

Oracle diagnostic:

`outputs/audit_oracle_combo_base5160_hardcase_active1000_20260627T120500Z`

| Diagnostic setting | Combination | Audit AP | ROC-AUC | Positive F1 |
|---|---|---:|---:|---:|
| Audit oracle, do not report as model | Linear | 0.560 | 0.857 | 0.587 |
| Audit oracle, do not report as model | Geometric | 0.586 | 0.861 | 0.592 |
| Audit oracle, do not report as model | Product penalty | 0.574 | 0.867 | 0.589 |

The oracle result uses audit labels to choose combination weights. It is only a diagnostic upper-bound check for current score complementarity. It cannot be reported as a deployable model result.

## AP 0.8 Assessment

The current evidence does not support the claim that audit AP near 0.8 is reachable by simple model selection, score ensembling, or direct pooling of active labels.

The key evidence is:

1. Directly adding the 1,000 relation-aware active labels reduced independent-audit AP relative to the 5,160-label detector.
2. Score-level reranking did not outperform the strongest single DeBERTa score.
3. The hard-case filter reached AP near 0.8 only inside the active hard-case distribution.
4. On the independent random audit, the hard-case filter overpredicted positives and reached AP 0.459.
5. Even an audit-oracle score combination only reached AP 0.586.

Therefore, the current bottleneck is not ordinary hyperparameter tuning. The bottleneck is measurement design: public correction is relational, target-specific, and context-dependent.

## Method Consequence

The next prediction improvement should be a measurement redesign rather than another flat binary classifier.

The most defensible next options are:

1. **Two-stage detection.** First retrieve high-recall correction candidates; then classify whether the target comment corrects the parent, an earlier thread claim, a general false claim, or no concrete claim.
2. **Relation-pair training.** Train on target-comment plus correction target pairs, not only target-comment text. The parent comment, nearest prior misinformation-like claim, and submission title should be represented as structured fields.
3. **Relation-type auxiliary supervision.** Keep the relation labels as auxiliary targets instead of collapsing them too early into one binary label.
4. **Human-validated audit expansion.** Expand the independent random audit with stratified human checks, especially for high-score false positives, short false negatives, quote-edit corrections, and parent-dependent corrections.

## Current Reporting Position

The best current deployable score for downstream aggregate analysis is still the 5,160-label DeBERTa detector, with the validation-selected base-plus-hardcase combination as a minor robustness check.

The strongest methodological conclusion is:

> The project should not treat AP 0.8 as a tuning target under the current flat binary setup. The active labels show that the remaining errors are relation-level measurement errors. Improving the detector requires modeling correction as a relation between a target comment and a corrected claim.

This conclusion is useful for the research design. It explains why the empirical contribution should not depend on a single fragile classifier, and why the next substantive improvement should target correction measurement rather than only model complexity.
