# Combined Label Rerun Results

## Purpose

This step expands the correction-label training set and reruns the full empirical pipeline. The purpose is to test whether the correction-misallocation and thread-climate results remain stable after moving from the first 360 Qwen labels to a combined set of 2,760 Qwen-assisted labels.

The combined label file is:

```text
outputs/llm_qwen_public_correction_combined_2760_20260625T062000Z
```

The label distribution is:

```text
rows = 2,760
usable binary labels = 2,755
negative labels = 1,988
positive labels = 767
uncertain labels = 5
```

## Classifier Choice

The benchmark tested 16 lightweight text models across `text_only` and `text_candidate` feature modes. The best overall model by best positive F1 was:

```text
text_candidate + word_char_logreg_balanced
best positive F1 = 0.613
ROC-AUC = 0.807
average precision = 0.637
```

The main pipeline uses a cleaner text-only model:

```text
text_only + word_char_logreg_balanced
default positive precision = 0.559
default positive recall = 0.634
default positive F1 = 0.594
ROC-AUC = 0.804
average precision = 0.632
best positive F1 = 0.603 at threshold 0.476
```

The text-only model is preferred for the main dependent variable because it avoids feeding the candidate-retrieval flag back into the classifier. The performance gap between the best `text_candidate` model and the selected `text_only` model is small.

## Main Threshold Result

The main full-data prediction uses threshold `0.5`:

```text
outputs/correction_classifier_combined2760_wordchar_textonly_20260625T064000Z
```

Applied to the full COVID vaccine comment dataset:

```text
comments = 165,061
threads = 10,220
users = 58,278
predicted public corrections = 12,108
threads with predicted public correction = 3,705
```

Correction misallocation remains visible:

```text
high-participation no-correction threads = 583
```

The later-correction climate table reports:

```text
later predicted public corrections = 6,604
threads with later predicted correction = 1,539
later thread-author instances = 89,251
```

## Main Logit Result

The main observational logit estimates later correction at the thread-author level. Standard errors are clustered by thread:

```text
outputs/thread_climate_logit_combined2760_wordchar_textonly_20260625T071000Z
```

The model converged:

```text
observations = 89,251
outcome mean = 0.068
pseudo R2 = 0.137
```

The main coefficients are:

```text
early correction norm:
  odds ratio = 6.62
  p < 0.001

hostility climate:
  odds ratio = 0.81
  p = 0.033

hostility climate x early correction norm:
  odds ratio = 0.64
  p = 0.025

anti-institutional climate:
  odds ratio = 1.52
  p < 0.001

cross-group user:
  odds ratio = 1.21
  p = 0.132

cross-group x hostility x early norm:
  odds ratio = 1.63
  p = 0.138
```

The strongest stable result is the thread-climate result. Early visible correction is strongly associated with later correction, while hostile discussion climate is associated with lower later correction. Anti-institutional climate is positively associated with later correction, which likely marks more contested misinformation environments rather than a safer expression environment.

The cross-group result should not be written as a central suppression finding. Cross-group users often show higher descriptive correction rates, but the controlled logit does not support a stable cross-group inhibition effect.

## Threshold Sensitivity

A second full-data prediction uses the cross-validation best-F1 threshold `0.476`:

```text
outputs/correction_classifier_combined2760_wordchar_textonly_thr0476_20260625T073000Z
```

This threshold increases recall and predicts more public corrections:

```text
predicted public corrections = 14,246
threads with predicted public correction = 4,069
high-participation no-correction threads = 510
later predicted public corrections = 7,792
threads with later predicted correction = 1,679
```

The threshold-sensitive logit remains consistent:

```text
early correction norm:
  odds ratio = 6.41
  p < 0.001

hostility climate:
  odds ratio = 0.82
  p = 0.038

hostility climate x early correction norm:
  odds ratio = 0.68
  p = 0.039

anti-institutional climate:
  odds ratio = 1.56
  p < 0.001

cross-group user:
  odds ratio = 1.15
  p = 0.285

cross-group x hostility x early norm:
  odds ratio = 1.18
  p = 0.610
```

The sensitivity run supports the same interpretation. The exact number of predicted corrections changes with the threshold, but the main climate pattern remains stable.

## Updated Interpretation

The expanded-label rerun strengthens the empirical basis of the project but narrows the safest theoretical claim.

First, the project can still claim correction misallocation. Hundreds of highly active threads have no predicted public correction under both thresholds. This supports the idea that public correction is not automatically supplied where discussion volume is high.

Second, the strongest mechanism is local thread climate. Early correction appears to create a local correction norm or cascade condition. Hostility reduces later correction, including in threads where early correction is present. This result fits a correction-safety interpretation better than a simple individual-capacity interpretation.

Third, anti-institutional climate should be interpreted carefully. Its positive association with later correction does not mean anti-institutional spaces are safer. It more likely indicates that these threads contain more contested claims and more correction opportunities.

Fourth, the cross-group mechanism is not yet supported as a main finding. The current data do not show that cross-community users are systematically inhibited after controls. The cross-group idea can remain a secondary mechanism or future refinement, but it should not carry the paper.

The current contribution should therefore be framed as:

```text
Misinformation persistence can arise from a mismatch between correction need and correction-supportive local conditions. Public correction is more likely when early correction has already made correction locally visible, and less likely when the thread climate is hostile. Correction failure is therefore not only a problem of whether knowledgeable users exist, but also a problem of whether the local discussion environment allows correction to continue.
```

## Remaining Measurement Boundary

The classifier is now more stable than the first pilot, but it is still trained on Qwen-assisted labels. The current results should be treated as exploratory empirical evidence, not final manuscript-level evidence.

The next validation step should be:

```text
1. create a stratified human-validation sample;
2. compare Qwen labels, classifier labels, and human labels;
3. estimate precision and recall for public correction detection;
4. rerun the main climate models after human-validated calibration.
```

The first blind human-validation sample has been prepared:

```text
outputs/human_validation_sample_combined2760_wordchar_textonly_20260625T083000Z
```

It contains:

```text
sample rows = 400
model-predicted negatives = 205
model-predicted positives = 195
rows with existing Qwen labels = 106
public_health_or_news = 130
skeptical_or_anti_institutional = 162
vaccine_experience_or_health = 108
```

The file for blind human coding is:

```text
human_validation_sample_blind.csv
```

The file with model scores, Qwen labels, and thread-climate metadata is:

```text
human_validation_sample_with_metadata.csv
```
