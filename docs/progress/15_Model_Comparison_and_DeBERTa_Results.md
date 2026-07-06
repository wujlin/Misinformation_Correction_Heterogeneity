# Model Comparison and DeBERTa Results

## Purpose

This step compares stronger transformer correction detectors after the expanded human-audited LLM-assisted label set became usable for model development. The purpose is not only to improve prediction quality, but also to check whether the downstream correction-misallocation and thread-climate findings remain stable when the dependent variable is measured by a stronger detector.

The main result is that `microsoft/deberta-v3-base` is the current best public-correction detector. It improves positive F1, ROC-AUC, and average precision relative to the previous lightweight classifier and the first DistilRoBERTa baseline. The downstream interpretation also becomes more precise: early visible correction remains the strongest and most stable predictor of later correction, while the direct hostility effect is weaker than the earlier DistilRoBERTa run suggested.

## Model Comparison

All transformer models use the same binary label pool:

```text
labels = outputs/llm_qwen_public_correction_combined_2760_20260625T062000Z/llm_annotations.csv
usable binary labels = 2,755
negative labels = 1,988
positive labels = 767
```

The comparison uses the held-out test split for the transformer models. The lightweight baseline reports the earlier cross-validation result.

| Model | Feature mode | Positive F1 | Recall | ROC-AUC | Average precision |
|---|---:|---:|---:|---:|---:|
| word-char logistic regression | text only | 0.594 | 0.634 | 0.804 | 0.632 |
| DistilRoBERTa | text only | 0.733 | 0.800 | 0.894 | 0.732 |
| DistilRoBERTa | title + comment + parent | 0.649 | 0.635 | 0.868 | 0.694 |
| RoBERTa-base | text only | 0.700 | 0.852 | 0.889 | 0.735 |
| DeBERTa-v3-base | text only | 0.740 | 0.757 | 0.917 | 0.792 |

DeBERTa-v3-base should be treated as the current main detector. It has the best positive F1, ROC-AUC, and average precision. RoBERTa-base has slightly higher recall than DeBERTa, but DeBERTa has stronger overall ranking and classification performance. For this project, average precision is the better model-selection metric because public correction is a positive class and the decision threshold may be adjusted later for calibration.

Average precision summarizes the precision-recall curve across thresholds. It is therefore more informative than one threshold-specific value when the final paper still needs an independent human-validation step and possible threshold calibration.

The parent-context variant does not improve the detector. Only 972 of 2,755 labeled rows have parent context, and adding parent context lowers positive F1 and average precision. The current main dependent variable should therefore use the text-only DeBERTa detector.

## Full Prediction

The selected DeBERTa detector was applied to the full COVID vaccine comment dataset:

```text
comments = 165,061
threads = 10,220
threshold = 0.812
predicted public corrections = 16,549
threads with predicted public correction = 5,003
```

Compared with DistilRoBERTa, DeBERTa predicts fewer public corrections:

```text
DistilRoBERTa predicted public corrections = 18,953
DeBERTa predicted public corrections = 16,549

DistilRoBERTa threads with predicted correction = 5,428
DeBERTa threads with predicted correction = 5,003
```

This difference is useful rather than problematic. The higher average precision of DeBERTa suggests that the smaller count is likely a cleaner estimate of public correction supply. The earlier lightweight classifier under-detected corrections, while the DeBERTa result suggests that public correction is more common than the lightweight model implied but less diffuse than the first DistilRoBERTa full prediction suggested.

## Misallocation Result

The DeBERTa-based correction-misallocation run is:

```text
outputs/correction_misallocation_deberta_v3_base_textonly_20260626T113000Z
```

The main counts are:

```text
predicted public corrections = 16,549
threads with predicted correction = 5,003
high-participation no-correction threads = 226
```

The high-participation no-correction count remains close to the DistilRoBERTa result:

```text
DistilRoBERTa high-participation no-correction threads = 218
DeBERTa high-participation no-correction threads = 226
```

This supports a narrowed correction-misallocation claim. The project should not claim that public correction is rare in general. The stronger claim is that even with a better detector, some highly active threads still receive no predicted public correction. Correction absence is therefore not only a volume problem; it remains linked to local discussion conditions.

## Thread Climate Results

The DeBERTa-based dynamic thread-climate run is:

```text
outputs/thread_climate_dynamic_deberta_v3_base_textonly_20260626T113500Z
```

The main descriptive counts are:

```text
later predicted public corrections = 9,177
threads with later predicted correction = 2,131
later thread-author instances = 89,251
threads with sanction-to-correction cue = 283
```

Early visible correction remains the strongest descriptive contrast:

```text
without early correction:
  non-cross correction rate = 0.057
  cross correction rate = 0.076

with early correction:
  non-cross correction rate = 0.137
  cross correction rate = 0.187
```

Hostility shows a weaker descriptive environment for later correction:

```text
low hostility:
  non-cross correction rate = 0.103
  cross correction rate = 0.137

high hostility:
  non-cross correction rate = 0.075
  cross correction rate = 0.122
```

Cross-group users still have higher descriptive correction rates in both low- and high-hostility threads. This pattern does not support a simple claim that cross-group users are generally suppressed.

## Logit Result

The DeBERTa-based later-correction logit is:

```text
outputs/thread_climate_logit_deberta_v3_base_textonly_20260626T114000Z
```

The model converged:

```text
observations = 89,251
outcome mean = 0.096
pseudo R2 = 0.050
standard errors = clustered by thread
```

The main coefficients are:

```text
early correction norm:
  odds ratio = 2.46
  p < 0.001

hostility climate:
  odds ratio = 0.96
  p = 0.625

hostility climate x early correction norm:
  odds ratio = 0.78
  p = 0.036

anti-institutional climate:
  odds ratio = 1.39
  p < 0.001

cross-group user:
  odds ratio = 1.15
  p = 0.207

cross-group x hostility:
  odds ratio = 1.16
  p = 0.426

cross-group x early correction norm:
  odds ratio = 1.03
  p = 0.800

cross-group x hostility x early correction norm:
  odds ratio = 1.16
  p = 0.536
```

The controlled model supports three conclusions.

First, early correction norm is the most stable result. Once correction is visible in the early part of a thread, later correction becomes much more likely. This is the strongest current empirical basis for a local correction-environment argument.

Second, hostility should be interpreted as a moderator of correction-supportive conditions rather than as a simple direct suppressor. In the DeBERTa model, the main hostility coefficient is not statistically significant, but the interaction between hostility and early correction norm is negative and significant. This means hostility appears to weaken the effect of early correction visibility.

Third, the cross-group suppression thesis is not supported by the current evidence. Cross-group users are descriptively more likely to correct, and the controlled interaction terms do not show a stable inhibition pattern. Cross-group exposure can remain part of the theoretical setup, but it should not carry the main empirical claim in this version.

## Current Interpretation

The current strongest contribution is a local correction-environment account of misinformation persistence. Public correction is not determined only by whether knowledgeable or cross-community users are present. Public correction becomes more likely when correction is already visible in the local thread environment, and the effect of this early correction norm is weaker in hostile threads.

This result refines the earlier correction-misallocation argument. The problem is not that public correction is absent everywhere. The problem is that correction supply depends on local thread conditions, and some high-participation threads still lack predicted correction even under a stronger detector. Misinformation persistence can therefore be framed as a mismatch between correction need and correction-supportive local conditions.

The current claim should avoid three overstatements:

```text
Do not claim that public correction is rare in general.
Do not claim that cross-group users are systematically silenced.
Do not claim that hostility always directly suppresses correction.
```

The safer and more interesting claim is:

```text
Public correction depends on local correction-supportive conditions. Early visible correction is strongly associated with later correction, while hostile discussion climate weakens this local correction norm. Even with a stronger DeBERTa detector, some high-participation threads still receive no predicted correction, which suggests that misinformation persistence is partly a local correction-environment problem rather than only an individual knowledge problem.
```

## Remaining Boundary

The current test split comes from the same human-audited LLM-assisted label pool used for model development. The result is strong enough for internal model selection and exploratory downstream analysis, but the final paper still needs an independent human-validation sample before making manuscript-level measurement claims.

The next empirical step should be:

```text
1. use DeBERTa as the main detector;
2. create an independent stratified human-validation set;
3. estimate average precision and the main error patterns on that validation set;
4. rerun the main tables after any calibration;
5. then convert the DeBERTa thread-climate result into manuscript tables or figures.
```
