# 36. Audit3 Full Pair Ensemble and Mechanism Rerun

## Purpose

This round freezes the pair-level detector after the third independent audit and uses the latest pair-ensemble predictions to rerun the full downstream mechanism analysis.

The goal is not only to improve the detector. The more important goal is to check whether the substantive heterogeneity results remain interpretable after replacing the earlier comment-level correction detector with a relation-aware pair-level detector.

## Audit3 Detector Result

Audit3 is the cleanest current external check because it was constructed after the audit2 optimization round.

The best audit3 result is:

| Score | AP | ROC-AUC | F1@0.5 |
|---|---:|---:|---:|
| `base_best_plus_large_title_roberta_rank_mean` | 0.732 | 0.851 | 0.658 |
| `base_best_plus_large_title_roberta_mean` | 0.726 | 0.850 | 0.678 |
| `old14_plus_new3_type6232_largeboth_mean` | 0.721 | 0.847 | 0.671 |

The main downstream score uses `base_best_plus_large_title_roberta_mean`, which is the simple mean of all 22 raw pair-relation models.

This means the stable external estimate is not AP = 0.8. The safer measurement statement is that the current detector reaches AP around 0.72-0.73 and ROC-AUC around 0.85 on the newest independent audit. This is strong enough for downstream observational analysis, but the paper should report measurement uncertainty rather than treating the detector as ground truth.

## Full Prediction Rerun

Full pair candidates were built from the 5,160-label relation-later comment predictions.

Run paths:

- Pair pool: `outputs/relation_pair_full_candidate_pool_from5160_for_latest_ensemble_20260628T125000Z`
- Raw pair scores: `outputs/pair_relation_full_candidate_scores_latest22_20260628T125500Z`
- Full comment predictions: `outputs/full_comment_predictions_latest_pair_ensemble_20260628T142000Z`

Full prediction summary:

| Quantity | Value |
|---|---:|
| Pair candidates | 107,023 |
| Unique response comments in pair pool | 88,689 |
| Full comments | 165,061 |
| Pair-level predicted positives | 28,784 |
| Comment-level predicted public corrections | 23,780 |
| Legacy comment-model predicted public corrections | 16,976 |

The comment-level score is the maximum pair-relation score among all candidate claims for the same response comment. Comments without any pair candidate receive score 0.

## Mechanism Rerun

Downstream paths:

- Misallocation tables: `outputs/correction_misallocation_latest_pair_ensemble_20260628T143000Z`
- Thread climate tables: `outputs/thread_climate_latest_pair_ensemble_20260628T143000Z`
- Logit model: `outputs/thread_climate_logit_latest_pair_ensemble_20260628T143000Z`
- Score-based OLS: `outputs/thread_climate_score_ols_latest_pair_ensemble_20260628T143000Z`

The later-correction model uses 89,251 thread-author instances. The binary outcome mean is 0.151. The score-based outcome mean is 0.184.

## Core Results

The cross-group user effect remains stable.

In the heterogeneity logit model, `user_cross_group_observed` has OR = 1.138 and p = 0.0106. In the score-based OLS model, the coefficient is 0.0215 and p = 0.00010.

Early audience structural heterogeneity is weaker as a main effect. In the logit model, OR = 1.085 and p = 0.0748. In the score-based OLS model, the coefficient is 0.0092 and p = 0.0958.

The interaction becomes clearer in the threshold-free score model. The interaction between cross-group position and high early audience structural heterogeneity has coefficient = 0.0224 and p = 0.0376. In the binary logit model, the same interaction is positive but not significant at 0.05, OR = 1.153 and p = 0.103.

The scenario table shows the same pattern:

| Early audience structural heterogeneity | Non-cross predicted score | Cross predicted score | Difference |
|---:|---:|---:|---:|
| 0 | 0.180 | 0.202 | 0.021 |
| 1 | 0.189 | 0.233 | 0.044 |

In the descriptive table, the later correction rate also increases more strongly for cross-group users under high early audience structural heterogeneity:

| Early audience structural heterogeneity | Non-cross rate | Cross rate |
|---:|---:|---:|
| 0 | 0.144 | 0.178 |
| 1 | 0.167 | 0.227 |

## Additional Patterns

Early correction norm remains the strongest positive contextual signal. In the score-based OLS model, `early_correction_norm_presence` has coefficient = 0.0774 and p < 0.001.

Hostility has a negative relationship with later correction. In the logit model, high hostility has OR = 0.853 and p = 0.0159. In the score-based model, the direct hostility coefficient is negative but not significant, while the interaction between early correction norm and hostility is negative and significant.

Discursive heterogeneity is positive. In the score-based model, the coefficient is 0.0141 and p = 0.0121. This suggests that heterogeneous early discussion is associated with more later correction rather than with simple silence.

Anti-institutional climate is also positive. This probably reflects a demand-side pattern: threads with stronger anti-institutional content provide more claims that invite correction. This variable should not be interpreted as a pro-correction social climate without additional checks.

## Current Interpretation

The strongest result is no longer that heterogeneity suppresses public correction.

The stronger and more defensible interpretation is:

> Heterogeneity is not a single mechanism. Cross-group structural position is associated with more public correction, while early audience structural heterogeneity appears to condition how strongly that cross-group position converts into later correction. Correction is therefore shaped by the relation between user position and local discussion structure, not by either individual attitude or thread climate alone.

This result is useful because it avoids the weak claim that "heterogeneity is good" or "heterogeneity is bad." The contribution is to separate different forms of heterogeneity and show that they operate at different levels:

- user-level structural heterogeneity: cross-group participation and possible correction capacity;
- thread-level audience heterogeneity: the local visibility structure in which correction occurs;
- thread climate: correction norm, hostility, discursive heterogeneity, and anti-institutional demand.

## Contribution Claim

The current contribution should be framed as a measurement and mechanism contribution.

First, correction is measured as a relation-aware behavior. A public correction is not only a comment with corrective language. It is a response that corrects a specific prior claim. The pair-level detector makes this operational distinction more explicit.

Second, heterogeneity is decomposed into user position and local audience structure. Previous broad claims about heterogeneous networks are too coarse for this problem. The current results show that cross-group users are more correction-active, but their correction advantage is larger in structurally heterogeneous early thread environments.

Third, misinformation persistence can be studied as a mismatch between correction opportunities, correction capacity, and local correction climate. The current evidence is observational, but it points to a social organization of correction rather than a purely individual willingness model.

## Caveats

The current evidence is observational. The model does not directly observe private misinformation recognition or anticipated social accountability.

The correction detector is usable but not perfect. Audit3 AP around 0.72-0.73 means downstream models should be interpreted as measurement-informed estimates, not direct behavioral ground truth.

The audience heterogeneity measures are structural proxies from observed Reddit participation. They do not measure demographic, class, educational, or political identity heterogeneity directly.

The next manuscript-level step is to present the results as layered heterogeneity and correction allocation, rather than as a simple suppression model.
