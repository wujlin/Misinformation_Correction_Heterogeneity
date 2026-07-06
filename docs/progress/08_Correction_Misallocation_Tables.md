# Correction Misallocation Tables

## Purpose

This step uses the text-only correction classifier to construct the first correction-misallocation tables. The purpose is to move from label construction to the empirical structure of the problem: where predicted public corrections appear, where many users participate without predicted correction, and whether cross-community users behave differently across community contexts.

The current output is exploratory because the correction label is derived from Qwen-assisted annotation and a lightweight text classifier.

## Input

Preferred classifier run:

```text
outputs/correction_classifier_qwen_labels_tfidf_logreg_textonly_20260625T005000Z
```

Misallocation output:

```text
outputs/correction_misallocation_textonly_20260625T005500Z
```

## Main Counts

```text
comments = 165,061
users = 58,278
threads = 10,220
thread-author instances = 145,215
predicted public corrections = 11,120
threads with predicted correction = 3,520
high-participation threads without predicted correction = 599
```

High-participation threads are currently defined as threads with at least 20 observed authors and zero predicted public correction.

## Community-Level Pattern

Thread-level correction presence:

```text
public_health_or_news:
  threads with predicted correction = 0.380
  high-participation no-correction thread rate = 0.074

skeptical_or_anti_institutional:
  threads with predicted correction = 0.333
  high-participation no-correction thread rate = 0.055

vaccine_experience_or_health:
  threads with predicted correction = 0.255
  high-participation no-correction thread rate = 0.009
```

At the subreddit level, `news` and `conservative` have the highest rates of high-participation no-correction threads in this exploratory run. This may indicate large discussion spaces where many users participate but no comment crosses the model threshold for public correction.

## Cross-Community User Pattern

Thread-author correction rates by community group and cross-group status:

```text
public_health_or_news:
  non-cross-group users = 0.060
  cross-group users = 0.073

skeptical_or_anti_institutional:
  non-cross-group users = 0.074
  cross-group users = 0.100

vaccine_experience_or_health:
  non-cross-group users = 0.120
  cross-group users = 0.155
```

This pattern does not support a simple claim that cross-community users are more publicly silent. In this within-dataset proxy, cross-group users are more likely to produce predicted public correction in every community group.

## Interpretation

This result is useful because it forces the mechanism to become more precise. Structural heterogeneity alone is not enough to demonstrate expressive inhibition. Cross-community users may be more active, more informed, or more correction-oriented in general. The expressive mechanism needs a sharper context variable, such as thread hostility, local norm climate, direct replies attacking correctors, or the local share of misinformation-supportive comments.

The current evidence supports a weaker but measurable claim:

```text
public correction is unevenly distributed across threads and communities, and some high-participation threads contain no predicted correction.
```

The current evidence does not yet support the stronger mechanism:

```text
cross-community users recognize misinformation but remain publicly silent in hostile communities.
```

That stronger mechanism requires a better measure of local correction cost or sanction climate.

## Next Step

The next step is to construct thread-level climate variables:

- hostile reply language;
- anti-correction or anti-institutional cues;
- local correction norm, measured by early thread replies;
- whether first correction receives supportive or hostile replies;
- local majority proxy from stance or misinformation-supportive language.

After adding thread climate, the core test should become an interaction:

```text
cross-community exposure × hostile/sanctioning thread climate -> public correction
```

This is closer to the theoretical claim than a simple comparison between cross-group and non-cross-group users.
