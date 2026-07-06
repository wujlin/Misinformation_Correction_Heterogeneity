# Correction Classifier Progress

## Purpose

This step scales the 360 Qwen-assisted annotations to the full Reddit COVID vaccine comment dataset. The goal is not to produce a final paper-level dependent variable. The goal is to test whether public correction can be detected beyond simple keyword retrieval and whether the resulting label can support thread-level and community-level analysis.

## Input

Training labels:

```text
outputs/llm_qwen_public_correction_annotation_gpu0_20260625T003500Z/llm_annotations.csv
```

Full comment dataset:

```text
data/interim/covidvaccine_comments.jsonl
```

Training label distribution:

```text
public correction = 91
not public correction = 269
total = 360
```

## Model

The current classifier is intentionally simple:

- TF-IDF word features;
- logistic regression;
- class-balanced loss;
- 5-fold stratified cross-validation;
- threshold = `0.5`.

The classifier target is the Qwen-assisted label, not human ground truth.

## Ablation Runs

Three feature settings were tested:

```text
metadata_full: title + comment + keyword candidate flag + subreddit + community group
text_candidate: title + comment + keyword candidate flag
text_only: title + comment
```

The ablation is important because `metadata_full` can learn community differences rather than correction language. The stricter `text_only` model avoids this leakage.

## Main Metrics

```text
metadata_full:
  CV positive F1 = 0.627
  CV ROC-AUC = 0.811
  predicted full-data corrections = 7,834
  threads with predicted correction = 2,892

text_candidate:
  CV positive F1 = 0.624
  CV ROC-AUC = 0.807
  predicted full-data corrections = 10,779
  threads with predicted correction = 3,473

text_only:
  CV positive F1 = 0.624
  CV ROC-AUC = 0.806
  predicted full-data corrections = 11,120
  threads with predicted correction = 3,520
```

The text-only model performs almost as well as the metadata-full model. This suggests that the correction signal is present in language itself rather than only in subreddit membership or the keyword flag.

## Preferred Exploratory Version

The preferred exploratory classifier is:

```text
outputs/correction_classifier_qwen_labels_tfidf_logreg_textonly_20260625T005000Z
```

This version is methodologically cleaner because it does not use subreddit, community group, or keyword candidate status as predictive metadata. It is therefore more suitable for constructing a provisional public-correction variable before community-level analysis.

## Full-Data Pattern From Text-Only Classifier

The text-only classifier predicts:

```text
public correction comments = 11,120 / 165,061
threads with at least one predicted correction = 3,520 / 10,220
```

Predicted correction rate by community group:

```text
vaccine_experience_or_health: 0.123
skeptical_or_anti_institutional: 0.070
public_health_or_news: 0.060
```

This pattern is still exploratory. It should be interpreted as a model-derived signal from Qwen-assisted labels, not as a validated behavioral finding.

## Methodological Implication

The keyword flag should remain a retrieval aid rather than the final dependent variable. Qwen-assisted annotation and text-based classification give a richer label, but the pipeline still needs a human-validated subset before manuscript-level claims.

## Next Step

The next step is to use the text-only predicted correction label to construct the first correction-misallocation table:

- community-level correction supply;
- thread-level exposed-but-not-correcting denominator;
- comparison between candidate keyword correction and classifier-predicted correction;
- identification of threads with high participation but no predicted correction.

After this, the project can move from label construction to the main network mechanism: whether cross-community users are more or less likely to correct in different community contexts.
