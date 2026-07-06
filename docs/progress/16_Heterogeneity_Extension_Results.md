# Heterogeneity Extension Results

## Purpose

This step implements the feasible part of the advisor's heterogeneity suggestion. The key adjustment is to stop treating heterogeneity as one variable. The current Reddit trace data can support several observable proxies, but it cannot directly measure perceived audience distance, education, class, occupation, income, or private sanction expectations.

The implemented extension therefore separates three measurable layers:

```text
user structural heterogeneity
thread-level visible audience heterogeneity
thread-level discursive heterogeneity
```

The current results support a capacity-based interpretation of heterogeneity. Cross-group users are more likely to provide public correction, while early visible correction and local climate still shape whether correction continues.

## Implemented Measures

User structural heterogeneity is measured from observed user participation across subreddits and community groups:

```text
user_subreddits_observed
user_community_groups_observed
user_cross_subreddit_observed
user_cross_group_observed
user_subreddit_entropy
user_community_group_entropy
```

This layer captures whether a user is structurally exposed to multiple discussion spaces. It maps onto correction capacity or correction supply.

Thread-level visible audience heterogeneity is measured from the early visible audience in each thread:

```text
early_audience_cross_group_author_share
early_audience_mean_community_group_entropy
early_audience_dominant_community_group_entropy
high_early_audience_structural_heterogeneity
```

This layer is a trace-data proxy for audience heterogeneity. It does not observe perceived social distance directly. It measures whether the early thread audience contains users who themselves participate across community groups.

Thread-level discursive heterogeneity is measured from early visible comment cues:

```text
early_discursive_cue_entropy
high_early_discursive_heterogeneity
```

The cue categories are:

```text
correction
anti_institutional
hostility
other
```

This layer approximates whether the local discussion contains mixed forms of corrective, anti-institutional, hostile, and neutral discourse.

## Non-Implemented Measures

The following parts of the advisor's suggestion are theoretically useful but not directly observable in the current Reddit trace data:

```text
audience social-location heterogeneity
perceived audience distance
audience epistemic capacity
audience sanctioning power
individual-level anticipated accountability
```

These require survey data, profile data, experimental manipulation, or a stronger identity-inference design. They should remain in the theory and future-design section rather than being forced into the current observational model.

## Runs

The heterogeneity dynamic tables are:

```text
outputs/thread_climate_dynamic_deberta_v3_base_heterogeneity_20260626T121500Z
```

The heterogeneity logit models are:

```text
outputs/thread_climate_logit_deberta_v3_base_heterogeneity_20260626T122000Z
```

The base model remains the same as the DeBERTa result:

```text
later_corrected_in_thread
~ user_cross_group_observed * high_thread_hostility_climate * early_correction_norm_presence
+ high_thread_anti_institutional_climate
+ log_thread_comments
+ log_user_comments
+ C(community_group_proxy)
```

The extended heterogeneity model is:

```text
later_corrected_in_thread
~ user_cross_group_observed * high_early_audience_structural_heterogeneity
+ early_correction_norm_presence * high_thread_hostility_climate
+ high_early_discursive_heterogeneity
+ high_thread_anti_institutional_climate
+ log_thread_comments
+ log_user_comments
+ C(community_group_proxy)
```

The extended model converged and improves model fit slightly:

```text
base AIC = 53628.7
heterogeneity AIC = 53603.4
base pseudo R2 = 0.0499
heterogeneity pseudo R2 = 0.0504
```

The improvement is modest, but it shows that the added heterogeneity measures are not only decorative.

## Main Heterogeneity Results

The extended model shows that cross-group users are more likely to correct later:

```text
user_cross_group_observed:
  odds ratio = 1.28
  p < 0.001
```

This result supports the correction-supply interpretation. Structural heterogeneity is associated with a higher probability of becoming a correction supplier.

Early audience structural heterogeneity is weakly positive but not conventionally significant:

```text
high_early_audience_structural_heterogeneity:
  odds ratio = 1.12
  p = 0.080
```

The interaction between user cross-group status and early audience heterogeneity is not significant:

```text
user_cross_group_observed x high_early_audience_structural_heterogeneity:
  odds ratio = 0.93
  p = 0.468
```

This does not support a strong audience-heterogeneity suppression mechanism in the current Reddit data.

Early discursive heterogeneity is also positive but not significant:

```text
high_early_discursive_heterogeneity:
  odds ratio = 1.11
  p = 0.151
```

The stable local-environment results remain:

```text
early_correction_norm_presence:
  odds ratio = 2.38
  p < 0.001

early_correction_norm_presence x high_thread_hostility_climate:
  odds ratio = 0.79
  p = 0.037

high_thread_anti_institutional_climate:
  odds ratio = 1.36
  p < 0.001
```

The extension therefore preserves the earlier interpretation: early correction norm is the strongest mechanism, hostility weakens this local correction norm, and anti-institutional climate likely marks contested correction opportunities.

## Descriptive Patterns

The dynamic tables show that cross-group users have higher later correction rates in both low and high early-audience-heterogeneity threads:

```text
low early audience heterogeneity:
  non-cross correction rate = 0.088
  cross correction rate = 0.125

high early audience heterogeneity:
  non-cross correction rate = 0.115
  cross correction rate = 0.153
```

The same pattern appears for discursive heterogeneity:

```text
low thread discursive heterogeneity:
  non-cross correction rate = 0.061
  cross correction rate = 0.085

high thread discursive heterogeneity:
  non-cross correction rate = 0.171
  cross correction rate = 0.223
```

These descriptive patterns reinforce the capacity interpretation. Cross-group users are not disappearing from heterogeneous or contentious spaces. They are more likely to correct, but the continuation of correction still depends on local correction norms.

## Advisor Feedback Integration

The advisor's core suggestion was to unpack heterogeneity into multiple levels:

```text
structural heterogeneity
audience heterogeneity
macro online environment
```

The current implementation handles the first two levels with trace-data proxies. Structural heterogeneity is measured at the user level. Audience heterogeneity is approximated from the early visible thread audience. Macro online environment is only partially captured through subreddit and community-group context because this dataset comes from one platform.

The current evidence does not support the strongest version of the earlier theory:

```text
heterogeneity -> audience cost -> public correction inhibition
```

The current evidence supports a different version:

```text
structural heterogeneity -> correction capacity / correction supply
local correction environment -> correction continuation
```

This is a better fit to the observed Reddit results.

## Updated Contribution

The contribution should be reframed around the conversion from correction capacity to sustained correction.

The current empirical results show that structurally heterogeneous users are more likely to provide public correction. This means that heterogeneity can increase correction supply. However, correction supply alone does not explain whether correction becomes sustained in a thread. Sustained correction is more strongly associated with early visible correction, and hostile climate weakens the continuation of that early correction norm.

The revised claim is:

```text
Network heterogeneity contributes to correction supply, but local correction environments determine correction continuation. Cross-group users are more likely to correct misinformation, yet misinformation can persist when correction does not become locally visible or when hostile climates weaken the continuation of early correction norms.
```

This keeps heterogeneity in the research question while avoiding the unsupported claim that cross-group users are systematically silenced.
