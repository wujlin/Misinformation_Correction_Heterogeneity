# Methods

## Data

The data come from the public Reddit COVID-19 vaccine discussion dataset christinegu27/reddit_covidvaccine_data. The raw files contain Reddit comments and submission metadata from COVID-19 vaccine-related submissions. After preprocessing, the analytic corpus contains 165,061 comments from 10,220 submission threads across 12 subreddits and 58,278 observed authors. Reddit discussion structure links submissions, comments, replies, users, and local conversational context. The design separates early thread conditions from later user behavior and constructs thread-author instances in which users remain present in a discussion.

The main behavioral unit is the later thread-author instance. A thread-author instance represents one author in one submission thread. The behavioral analysis focuses on instances in which the author has at least one later comment after the early-comment window. The design creates a denominator for public correction behavior. The denominator includes visible correctors and participating authors who remain present in the thread without producing later public correction.

## Measuring Public Correction

Public correction is defined as a relation between a response comment and a prior claim. The relational definition differs from a comment-level label. A comment sometimes contains factual information, disagreement, or critical language without correcting the specific claim to which the comment responds. A short response functions as a correction when the response directly challenges a prior claim. The measurement task is to identify a correction relation between a response and a specific target claim.

To operationalize the relational definition, the analysis constructs candidate claim-response pairs from Reddit reply structure and thread context. Each pair contains a potential target claim and a response comment. A relation-aware detector then scores the correction relation between the response and the target claim. For comment-level aggregation, a response comment receives the public correction score from the highest-scoring correction relation among the response comment's candidate pairs. Comments without any candidate correction relation receive a score of zero.

An independent audit evaluates the correction detector. The final correction detector uses a pair-ensemble score to reduce dependence on a single model. The empirical models use predicted correction labels as measurement-informed estimates of public correction behavior. Public correction is a relational construct, and automated labels contain measurement error.

## Analytical Unit and Outcome

The analytical unit connects early thread conditions to later public correction behavior. For each submission thread, comments are ordered chronologically. The early-comment window contains the first ten comments and defines the initial discussion environment. Later comments provide the behavioral outcome period. The outcome is the author's production of at least one later public correction in that thread.

The later thread-author instance is the unit for estimating correction activation. The analysis estimates the probability that a participating author with observable user and thread characteristics produces later public correction after early thread conditions have already formed.

## Key Variables

The key variables translate the capacity-activation account into observable user and thread conditions. User-level structural position is the correction-capacity measure. Early audience structural heterogeneity, early correction norm, and hostile thread climate are local activation measures.

User-level structural position is measured with `user_cross_group_observed`, an indicator of author participation across more than one community-group proxy in the dataset. The indicator is the observable proxy for cross-group structural position. The measure does not observe private misinformation recognition.

Early audience structural heterogeneity is measured with `high_early_audience_structural_heterogeneity`, an indicator of high cross-group-user share among early authors in a thread. The high indicator marks eligible threads with a nonzero value at or above the 75th percentile. Eligible threads have at least five comments. The measure records whether the early local audience is structurally heterogeneous before later public correction is observed.

Early correction norm is measured with `early_correction_norm_presence`, an indicator of at least one predicted public correction in the early-comment window. The measure records correction visibility in the local thread before the later outcome period.

Hostile thread climate is measured with `high_thread_hostility_climate`, an indicator of high dictionary-based hostility rate in the thread. The high indicator marks eligible threads with a nonzero value at or above the 75th percentile. Eligible threads have at least five comments. The measure records observable hostile language. Sanction risk and social accountability remain outside direct observation.

The control variables include early discursive heterogeneity, thread activity, user activity, and community-group fixed effects. Early discursive heterogeneity is based on cue-category entropy in the early-comment window.

## Observational Models

The observational analysis estimates associations between user position, thread conditions, and later public correction. The main binary model estimates the probability that a later thread-author instance produces at least one public correction. Standard errors are clustered by submission thread because thread-author instances within the same discussion are correlated.

The main heterogeneity model uses the following specification:

```text
later_corrected_in_thread ~
user_cross_group_observed * high_early_audience_structural_heterogeneity
+ early_correction_norm_presence * high_thread_hostility_climate
+ high_early_discursive_heterogeneity
+ log_thread_comments + log_user_comments
+ C(community_group_proxy)
```

The specification follows the capacity-activation account. Cross-group position and early audience structural heterogeneity represent different levels of heterogeneity. Early correction norm and hostile thread climate represent local activation conditions. Thread and user activity adjust for general participation intensity.

The score-based model provides a threshold-sensitivity check with continuous correction scores. The score-based check reduces dependence on a binary correction label and addresses uncertainty in automated correction detection.

The observational models identify associations between observable thread conditions and later public correction behavior. The estimates are interpreted as associational evidence.

## Empirically Calibrated Agent-Based Model

The agent-based model examines how fitted individual correction probabilities accumulate into system-level correction supply. Each empirical thread-author instance is represented as an agent. The agent's probability of producing later public correction is calibrated from the main heterogeneity logit model.

Scenario analysis holds the empirical population fixed and changes observable conditions across simulated scenarios. For each scenario, the calibrated probability is computed for every empirical agent, and public correction behavior is simulated through Monte Carlo draws. The main simulation outcomes are the simulated correction rate and the number of activated threads. An activated thread is a thread with at least one later public correction.

The simulation scenarios change observable conditions such as cross-group position, early audience structural heterogeneity, early correction norm, and hostile thread climate. The main condition map varies early correction norm and hostile thread climate in a 2 x 2 design. Each scenario uses 500 Monte Carlo draws. The condition-map design evaluates changes in correction activation across local thread conditions under the fitted model.

The scenario analysis links micro-level correction probabilities to macro-level correction supply. The empirical Reddit population remains fixed across scenarios. Simulated scenario differences are interpreted as calibrated scenario evidence for the capacity-activation account.
