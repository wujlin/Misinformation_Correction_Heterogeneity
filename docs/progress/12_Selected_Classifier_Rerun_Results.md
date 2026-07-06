# Selected Classifier Rerun Results

## Purpose

This step reruns the full empirical pipeline with the benchmark-selected classifier:

```text
text_only + char n-gram TF-IDF + balanced Logistic Regression
```

The purpose is to test whether the correction-misallocation and thread-climate findings remain stable when the temporary scaling classifier is improved.

## Runs

Selected classifier full prediction:

```text
outputs/correction_classifier_selected_charlogreg_textonly_20260625T043000Z
```

Correction misallocation:

```text
outputs/correction_misallocation_selected_charlogreg_textonly_20260625T044000Z
```

Thread climate dynamic tables:

```text
outputs/thread_climate_dynamic_selected_charlogreg_textonly_20260625T045000Z
```

Later-correction logit:

```text
outputs/thread_climate_logit_selected_charlogreg_textonly_20260625T050000Z
```

All runs were executed on WSA in the `dpl` environment.

## Classifier Result

The selected classifier improves the Qwen-label benchmark relative to the earlier word-only baseline:

```text
positive precision = 0.690
positive recall = 0.637
positive F1 = 0.663
ROC-AUC = 0.818
average precision = 0.693
```

Applied to the full comment dataset:

```text
comments = 165,061
predicted public corrections = 13,507
threads with predicted public correction = 3,998
```

Compared with the previous word-only classifier:

```text
predicted public corrections:
  11,120 -> 13,507

threads with predicted public correction:
  3,520 -> 3,998
```

The selected classifier is more sensitive, but still remains an exploratory classifier because the target labels are Qwen-assisted labels rather than human ground truth.

## Correction Misallocation

The selected classifier reduces but does not remove high-participation correction-poor threads:

```text
high-participation no-correction threads:
  599 -> 533
```

This supports the robustness of the correction-misallocation observation. The exact count changes with model sensitivity, but a substantial number of active threads still contain no predicted public correction.

## Thread Climate Dynamic Results

The selected classifier increases the amount of later correction:

```text
later predicted public corrections:
  6,316 -> 7,383

threads with later predicted correction:
  1,444 -> 1,612
```

The descriptive contrast remains consistent:

```text
low hostility:
  non-cross = 0.089
  cross = 0.126
  difference = +0.037

high hostility:
  non-cross = 0.043
  cross = 0.063
  difference = +0.020
```

Cross-group users still correct more than non-cross users, but the advantage is smaller in high-hostility threads. This supports a moderated interpretation rather than a simple suppression claim.

Early correction norm remains strong:

```text
without early correction:
  non-cross = 0.029
  cross = 0.035

with early correction:
  non-cross = 0.165
  cross = 0.229
```

This reinforces the interpretation that public correction is a norm-dependent or cascade-like process.

## Logit Result

The later-correction logit converged with:

```text
observations = 89,251
outcome mean = 0.0756
pseudo R2 = 0.137
standard errors clustered by thread
```

The main coefficients are:

```text
early correction norm:
  odds ratio = 6.58
  p < 0.001

hostility climate:
  odds ratio = 0.71
  p < 0.001

anti-institutional climate:
  odds ratio = 1.99
  p < 0.001

cross-group user:
  odds ratio = 1.05
  p = 0.703

cross-group x hostility x early norm:
  odds ratio = 1.04
  p = 0.908
```

The model strengthens the main environmental interpretation:

```text
early correction norm is strongly associated with later correction;
hostile climate is associated with lower later correction;
anti-institutional climate is associated with higher later correction.
```

The model does not support cross-group suppression:

```text
cross-group status does not have a stable main effect after controls;
the three-way interaction is not statistically meaningful.
```

## Updated Interpretation

The selected-classifier rerun strengthens the project in two ways.

First, the main substantive finding is robust to a better temporary classifier. Public correction appears to be shaped by local discussion dynamics rather than only by individual user type. Early correction makes later correction much more likely, hostile climate makes later correction less likely, and anti-institutional climate marks a contested information environment where correction opportunities are more common.

Second, the rerun clarifies what should not be the central claim. Cross-community users are not clearly suppressed. They often correct more in descriptive tables, and the formal model does not show a stable cross-group inhibition effect.

The strongest current contribution should therefore be:

```text
Misinformation persistence can arise from a mismatch between correction demand and correction safety. Anti-institutional climates create more contested claims and more correction opportunities, but hostile climates reduce the continuation of public correction. Early visible correction can shift the local norm and make later correction more likely.
```

## Next Step

The next step should be measurement validation rather than adding more exploratory models:

```text
1. create a stratified human-validation sample;
2. validate the selected classifier against human labels;
3. separate general hostility from hostility directed at correctors;
4. rerun the same pipeline after human-validated label calibration.
```

The selected classifier is currently the best temporary scaling model, but manuscript-level claims require human validation.
