# Results

## Measurement Validation

The measurement analysis evaluates relation-aware detection for thread-level behavioral analysis. The relation-aware detector models correction as a pair-level relation. The pair-level design preserves the target-claim relation absent from standalone comment categories. In the independent audit used for the measurement analysis, the pair-ensemble detector reaches average precision of 0.726 and ROC-AUC of 0.850. The audit result supports aggregate behavioral analysis with explicit measurement caveats.

Full-corpus coverage indicates why relation-aware measurement matters for downstream analysis. The measurement pipeline moves from 165,061 comments to 107,023 candidate claim-response pairs and 23,780 predicted public correction comments. The earlier comment-level detector identified 16,976 predicted correction comments. The larger count is consistent with the measurement design because some corrections become identifiable only when the response is evaluated against a specific prior claim.

## Cross-Group Position and Later Public Correction

Cross-group users have a higher estimated probability of later public correction. In the main heterogeneity logit model, `user_cross_group_observed` has an odds ratio of 1.138 and p = 0.0104. The score-based model supports the same direction with a coefficient of 0.0216 and p < 0.001.

The cross-group association is a behavioral estimate, and private recognition remains outside direct observation. Cross-group participation is the observable correction-capacity measure. Users observed across community groups occupy more diverse informational contexts. The models account for user activity and thread activity when estimating the association. The trace data support the association between cross-group position and later public correction.

## Layered Heterogeneity

Early audience structural heterogeneity has a positive but less precise main association. In the binary logit model, high early audience structural heterogeneity has OR = 1.083 and p = 0.0888. In the score-based model, the coefficient is 0.0092 and p = 0.1102.

The interaction between cross-group position and early audience structural heterogeneity is positive in both outcome specifications. The binary-logit interaction has OR = 1.160 and p = 0.0892. The score-based interaction coefficient is 0.0234 with p = 0.0308. In the binary model, predicted correction probability rises from 14.8% to 15.8% for non-cross-group users and from 16.4% to 19.7% for cross-group users. In the score-based model, the corresponding predicted score rises from 0.180 to 0.189 for non-cross-group users. For cross-group users, the predicted score rises from 0.202 to 0.234.

The layered heterogeneity pattern separates user position from early audience structural heterogeneity. User-level structural position and thread-level early audience structural heterogeneity are distinct parts of the correction process. Cross-group users have a higher probability of later public correction overall. The predicted probability gap between cross-group and non-cross-group users is larger in structurally heterogeneous early thread environments. The binary-logit interaction is positive and less precise than the score-based interaction.

## Local Correction Norm and Hostile Thread Climate

Local thread climate shapes later public correction. Among the focal local-climate variables, early correction norm has the largest positive association. In the main heterogeneity logit model, `early_correction_norm_presence` has OR = 1.877 and p < 0.001. Hostile thread climate is negatively associated with correction, with OR = 0.854 and p = 0.0173.

The local-climate estimates support the correction activation argument. Public correction is more likely when correction has already become visible early in the thread. Hostile thread climate is associated with a lower probability of later public correction. The interaction between early correction norm and hostile thread climate is negative and imprecise in the binary calibration model. The simulation scenarios below evaluate the joint implications of early correction norm and hostile thread climate for aggregate correction activation.

## Simulation: From Individual Probability to Correction Activation

The agent-based model evaluates how fitted individual-level associations accumulate into system-level correction outcomes. The baseline simulation matches the observed correction rate of approximately 0.151 across 89,251 empirical thread-author instances. The key system-level outcome is the number of activated threads, defined as threads with at least one later public correction.

Early correction norm and hostile thread climate jointly shape correction activation in the condition map. When early correction norm is present and hostile thread climate is low, the simulated correction rate reaches 19.1%, with about 2,913 activated threads. The increase is about 185 activated threads relative to the observed baseline. When early correction norm is absent and hostile thread climate is high, the simulated correction rate falls to 9.7%, with about 2,385 activated threads. The decrease is about 344 activated threads relative to the observed baseline.

The broader scenario comparison separates correction-rate change from activated-thread change. The local activation scenarios show larger simulated shifts than scenarios that change early audience structural heterogeneity alone. The all-cross-group scenario produces a simulated correction-rate increase of about 2.07 percentage points and about 98 additional activated threads. The high early audience structural heterogeneity scenario produces a simulated correction-rate increase of about 0.85 percentage points and about 44 additional activated threads.

The local-climate scenarios show the largest simulated changes in correction supply. The no-early-correction-norm scenario produces a correction-rate decrease of about 4.40 percentage points and about 252 fewer activated threads. The universal hostile thread climate scenario produces a correction-rate decrease of about 2.09 percentage points and about 118 fewer activated threads. The contrast supports the interpretation of correction activation as a thread-level process.

## Result Synthesis

The results support a capacity-activation account of public misinformation correction. The cross-group association provides the correction-capacity result. Early correction norm and hostile thread climate provide the correction-activation result. Early audience structural heterogeneity connects the two layers by changing the size of the cross-group gap. The simulation translates the fitted associations into thread-level correction supply.
