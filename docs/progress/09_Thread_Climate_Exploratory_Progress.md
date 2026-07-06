# Thread Climate Exploratory Progress

## Purpose

This step adds observable thread-level climate variables to the correction-misallocation analysis. The purpose is to test a more precise version of the expressive mechanism:

```text
cross-community users may correct more in general, but this correction advantage may weaken in threads with higher visible expression cost.
```

The analysis does not observe private recognition, perceived accountability, or intention. It only tests whether observable discussion climate changes the relationship between cross-community participation and predicted public correction.

## Preferred Run

The preferred run is the dynamic body-only climate version:

```text
outputs/thread_climate_dynamic_textonly_bodyonly_20260625T032000Z
```

The earlier runs below are diagnostic only:

```text
outputs/thread_climate_textonly_20260625T030000Z
outputs/thread_climate_textonly_bodyonly_20260625T031000Z
```

The first diagnostic run counted submission title cues in every comment. The second diagnostic run corrected this by using comment bodies for comment-level climate variables. The preferred dynamic run keeps the body-only climate measure and adds a later-correction outcome after the first 10 comments.

## Inputs

Predicted public correction labels:

```text
outputs/correction_classifier_qwen_labels_tfidf_logreg_textonly_20260625T005000Z/predictions/full_comment_predictions.csv
```

Standardized Reddit COVID vaccine comments:

```text
data/interim/covidvaccine_comments.jsonl
```

## Constructed Variables

The run constructs four exploratory climate variables:

```text
hostility cue:
  body-level language such as insults, shill accusations, or aggressive dismissal.

anti-institutional cue:
  body-level language around Fauci, CDC, big pharma, mandates, censorship, plandemic, VAERS, and related terms.

early correction norm:
  whether any predicted public correction appears in the first 10 comments of a thread.

sanction to correction:
  whether a predicted correction receives a direct hostile reply.
```

These variables should not be treated as final validated measures. They are used to decide whether the mechanism is empirically worth developing.

## Main Counts

```text
comments = 165,061
threads = 10,220
users = 58,278
thread-author instances = 145,215
later thread-author instances = 89,251
predicted public corrections = 11,120
later predicted public corrections = 6,316
threads with predicted public correction = 3,520
threads with later predicted public correction = 1,444
high-participation no-correction threads = 599
threads with hostile replies to predicted corrections = 162
```

Lexicon diagnostics:

```text
hostility comment match rate = 0.071
anti-institutional comment match rate = 0.069
```

## Key Pattern 1: Hostility Weakens the Cross-Group Correction Advantage

For the overall correction outcome, lower-hostility threads show:

```text
non-cross-group correction rate = 0.079
cross-group correction rate = 0.111
difference = +0.032
```

Higher-hostility threads show:

```text
non-cross-group correction rate = 0.043
cross-group correction rate = 0.053
difference = +0.010
```

This pattern is closer to the expressive-cost mechanism than the previous simple cross-group comparison. Cross-group users still correct more overall, but their relative correction advantage becomes much smaller in higher-hostility contexts.

The same pattern remains when the outcome is restricted to later correction after the first 10 comments:

```text
lower-hostility threads:
  non-cross = 0.076
  cross = 0.106
  difference = +0.030

higher-hostility threads:
  non-cross = 0.038
  cross = 0.050
  difference = +0.012
```

At the community-group level, the pattern is sharper:

```text
public_health_or_news, high hostility:
  non-cross = 0.028
  cross = 0.025
  difference = -0.003

vaccine_experience_or_health, high hostility:
  non-cross = 0.156
  cross = 0.150
  difference = -0.006
```

For the later-correction outcome, the high-hostility pattern remains negative in `public_health_or_news` and `vaccine_experience_or_health`:

```text
public_health_or_news, high hostility, later outcome:
  non-cross = 0.026
  cross = 0.024
  difference = -0.002

vaccine_experience_or_health, high hostility, later outcome:
  non-cross = 0.173
  cross = 0.158
  difference = -0.015
```

The current evidence supports a moderated claim rather than a simple claim:

```text
cross-community users are not generally more silent, but hostile thread climates appear to reduce their correction advantage.
```

## Key Pattern 2: Anti-Institutional Cues Do Not Behave Like Suppression

Anti-institutional climate does not show the same pattern as hostility. In higher anti-institutional threads:

```text
non-cross-group correction rate = 0.113
cross-group correction rate = 0.166
difference = +0.053
```

This suggests that anti-institutional language may be measuring controversy intensity or correction opportunity rather than expression cost. It should not be merged with hostility under a single "sanction climate" concept.

This distinction is important for the theoretical model:

```text
hostility climate = closer to expressive cost;
anti-institutional climate = closer to contested information environment.
```

## Key Pattern 3: Early Correction Norm Is Strong but Needs a Dynamic Test

Threads with early predicted correction have much higher later correction rates:

```text
without early correction:
  non-cross = 0.025
  cross = 0.034

with early correction:
  non-cross = 0.166
  cross = 0.212
```

This result is cleaner than the overall correction table because the outcome excludes the first 10 comments. It suggests that early correction may be associated with a later correction norm or correction cascade. The current table is still descriptive because early correction is not randomly assigned and may reflect thread-level controversy, visibility, or user composition.

## Interpretation

This run changes the empirical direction in a useful way. The earlier finding showed that cross-community users are more likely to correct in general, which did not support a simple "heterogeneity suppresses correction" claim. The thread-climate analysis suggests a more precise mechanism: structural heterogeneity may be associated with more correction, but hostile local climates may reduce that advantage.

The current empirical claim should therefore be:

```text
Public correction is unevenly distributed across threads. Cross-community users provide more predicted correction overall, but this correction advantage is weaker in hostile discussion climates.
```

The current empirical claim should not be:

```text
Cross-community users privately recognize misinformation but remain silent.
```

The second claim requires stronger evidence, such as validated correction labels, better exposure measures, and a temporal model separating early and later corrections.

## Next Step

The next analysis should move from descriptive contrasts to a formal model:

```text
later public correction after the first 10 comments
```

The formal test should estimate:

```text
early correction norm x hostility climate x cross-community user status -> later public correction
```

This would separate correction opportunity, local climate, and later correction behavior more cleanly than the current descriptive table. The model should still be described as observational unless a stronger identification strategy is added.

This formal observational model is summarized in [10_Thread_Climate_Logit_Progress.md](10_Thread_Climate_Logit_Progress.md).
