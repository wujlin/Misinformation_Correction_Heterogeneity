# Correction Classifier Benchmark

## Purpose

This step compares several lightweight classifiers for detecting predicted public correction from the current Qwen-assisted labels. The goal is to select a stronger temporary scaling classifier before human validation.

The benchmark evaluates models against Qwen-assisted labels, not human ground truth. The result should guide the next pilot, but it should not be treated as final measurement validity.

## Preferred Run

```text
outputs/correction_classifier_benchmark_qwen_labels_20260625T041000Z
```

The benchmark was run on WSA in the `dpl` environment.

## Input Labels

```text
annotations = 360
positive public correction labels = 91
negative labels = 269
positive rate = 0.253
```

## Models Tested

The benchmark tested 16 combinations:

```text
feature modes:
  text_only
  text_candidate

models:
  word TF-IDF + balanced Logistic Regression
  word TF-IDF + unweighted Logistic Regression
  char n-gram TF-IDF + balanced Logistic Regression
  word + char TF-IDF + balanced Logistic Regression
  word TF-IDF + Linear SVM
  char n-gram TF-IDF + Linear SVM
  word TF-IDF + Complement Naive Bayes
  word TF-IDF + chi-square feature selection + balanced Logistic Regression
```

All models used 5-fold stratified cross-validation.

## Best Model

The best model by positive-class best F1 is:

```text
text_only + char n-gram TF-IDF + balanced Logistic Regression
```

Default threshold result:

```text
positive precision = 0.690
positive recall = 0.637
positive F1 = 0.663
ROC-AUC = 0.818
average precision = 0.693
```

Best-F1 threshold result:

```text
threshold = 0.497
positive precision = 0.685
positive recall = 0.670
positive F1 = 0.678
```

High-precision threshold options:

```text
precision >= 0.75:
  threshold = 0.526
  precision = 0.750
  recall = 0.527
  F1 = 0.619

precision >= 0.80:
  threshold = 0.543
  precision = 0.808
  recall = 0.462
  F1 = 0.587
```

## Comparison With Previous Preferred Model

The previous temporary classifier was:

```text
text_only + word TF-IDF + balanced Logistic Regression
```

Its benchmark result is:

```text
positive precision = 0.679
positive recall = 0.582
positive F1 = 0.627
ROC-AUC = 0.807
average precision = 0.670
```

The char n-gram model improves the current Qwen-label benchmark:

```text
positive F1: 0.627 -> 0.663
ROC-AUC: 0.807 -> 0.818
average precision: 0.670 -> 0.693
```

## Interpretation

The improvement is meaningful but moderate. Character n-grams likely help because correction language often contains short recurring expressions, negations, links, quoted claims, spelling variation, and informal Reddit phrasing. The result suggests that the next temporary scaling classifier should use the char n-gram Logistic Regression model rather than the original word-only Logistic Regression model.

The `text_candidate` version has slightly higher ROC-AUC and average precision in some settings, but `text_only` remains preferable for the main pipeline because it avoids depending on the candidate keyword flag. The candidate flag should remain a retrieval aid, not a central feature for the dependent variable.

## Measurement Boundary

The best current model is better than the first baseline, but it is still not a final paper-level classifier:

```text
best positive F1 = 0.678 against Qwen-assisted labels
best ROC-AUC = 0.818 against Qwen-assisted labels
```

This is enough to improve exploratory scaling, but the model still needs human validation. The next measurement step should be a stratified human-labeled sample and a validation report against human labels.

## Next Step

The next empirical step should retrain the best model on all 360 assisted labels and apply it to the full comment dataset:

```text
text_only + char n-gram TF-IDF + balanced Logistic Regression
```

Then the correction-misallocation and thread-climate analyses should be rerun to test whether the main substantive patterns remain stable under the improved temporary classifier.
