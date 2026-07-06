# Thread Climate Logit Progress

## Purpose

This step moves from descriptive contrast tables to a formal observational model. The dependent variable is:

```text
later predicted public correction after the first 10 comments
```

The purpose is to test whether the descriptive pattern in the thread-climate tables remains visible after controlling for community group, thread size, user activity, anti-institutional climate, and clustered standard errors by thread.

## Preferred Run

```text
outputs/thread_climate_logit_dynamic_textonly_bodyonly_20260625T034000Z
```

The model was run on WSA in the `dpl` environment because the local Python environment does not include `statsmodels`.

## Model

The fitted model is:

```text
later_corrected_in_thread
~ cross_group_user * high_hostility_thread * early_correction_norm
+ high_anti_institutional_thread
+ log(thread_comments)
+ log(user_comments)
+ community_group fixed effects
```

Standard errors are clustered by `submission_id`.

## Main Diagnostics

```text
observations = 89,251
outcome mean = 0.0649
converged = true
pseudo R2 = 0.145
covariance = clustered by thread
```

## Main Coefficients

The strongest result is early correction norm:

```text
early_correction_norm_presence:
  odds ratio = 7.90
  p < 0.001
```

Threads with a predicted correction in the first 10 comments are much more likely to have later predicted correction. This is consistent with a correction-norm or correction-cascade interpretation, but it remains observational because early correction may also reflect thread visibility, controversy, or participant composition.

Anti-institutional climate is also positive:

```text
high_thread_anti_institutional_climate:
  odds ratio = 1.77
  p < 0.001
```

This reinforces the interpretation from the descriptive table: anti-institutional cues should not be treated as simple suppression. They appear closer to a contested information environment where correction opportunities are more common.

Hostility is negative but weaker:

```text
high_thread_hostility_climate:
  odds ratio = 0.81
  p = 0.068
```

The direction is consistent with expressive cost, but the model does not support a strong claim on this coefficient alone.

The cross-group main effect and interaction terms are not statistically stable:

```text
cross_group_user:
  odds ratio = 1.21
  p = 0.138

cross_group_user x high_hostility_thread x early_correction_norm:
  odds ratio = 0.79
  p = 0.479
```

This means the formal model does not support a strong claim that cross-group users are systematically inhibited under hostile climates. The descriptive pattern remains useful as a mechanism signal, but not as a confirmed finding.

## Scenario Probabilities

The scenario predictions are still substantively informative:

```text
no early correction, low hostility:
  non-cross = 0.027
  cross = 0.032
  difference = +0.005

no early correction, high hostility:
  non-cross = 0.022
  cross = 0.027
  difference = +0.005

early correction, low hostility:
  non-cross = 0.177
  cross = 0.195
  difference = +0.018

early correction, high hostility:
  non-cross = 0.105
  cross = 0.098
  difference = -0.007
```

The clearest pattern is that early correction substantially raises later correction probability. Hostility reduces later correction probability, especially when early correction is present. The cross-group advantage becomes negative only in the early-correction/high-hostility scenario, but the formal interaction is not statistically stable.

## Interpretation

The formal model narrows the claim. The current evidence supports:

```text
Public correction is more likely to continue when correction appears early in a thread. Hostile climates are associated with lower later correction, while anti-institutional climates are associated with higher later correction.
```

The current evidence does not yet support:

```text
Cross-community users are clearly suppressed by hostile climates.
```

The research contribution should therefore focus on correction misallocation, early correction norms, and the distinction between contested information environments and expressive-cost environments. The cross-community inhibition mechanism remains plausible, but it needs stronger measurement or a richer dataset before becoming the central empirical claim.

## Next Step

The next empirical step should improve measurement before adding more models:

```text
1. human-validate a subset of the predicted correction labels;
2. separate hostility directed at correctors from general hostile language;
3. construct a cleaner local stance or misinformation-supportive climate variable;
4. test whether early correction predicts later correction after excluding the original early corrector.
```

This keeps the project from overclaiming and points toward a stronger second pilot.
