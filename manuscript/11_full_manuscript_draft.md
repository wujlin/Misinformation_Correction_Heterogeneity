# From Correction Capacity to Correction Activation: Network Heterogeneity and Public Misinformation Correction on Reddit

## Abstract

Misinformation correction research often examines whether corrective messages reduce misperceptions after exposure. The article examines an earlier supply problem: when users with correction capacity produce visible public correction. The empirical setting is Reddit discussions about COVID-19 vaccination, with 165,061 comments from 10,220 threads. Public correction is measured as a relation-aware behavior. A response counts as correction when the response targets and corrects a specific prior claim. An independent audit evaluates the pair-level detector. Predicted corrections are then aggregated to thread-author instances. Observational models show that cross-group users have a higher estimated probability of later public correction. Early audience structural heterogeneity has a positive but less precise association. Local thread conditions shape correction activation. Early correction norm is associated with a higher probability of later public correction. Hostile thread climate is associated with a lower probability of later public correction. An empirically calibrated agent-based model uses 89,251 observed thread-author instances as agents to examine system-level correction supply. In scenario analysis, correction activation is higher when early correction norm is present and hostile thread climate is low. Correction activation is lower when early correction norm is absent and hostile thread climate is high. The article develops a supply-side account of misinformation correction, a relation-aware measurement strategy, and a computational framework for linking individual correction probabilities to system-level correction activation.

## Introduction

Public misinformation correction depends on visible correction supply. Research on misinformation correction often evaluates correction effects after exposure. Correction-effectiveness research explains belief updating, source credibility, and post-correction persistence (e.g., Lewandowsky et al., 2012; Chan et al., 2017; Walter and Murphy, 2018; Ecker et al., 2022). Public online discussion raises an earlier communication problem. Corrective information sometimes exists in the wider information environment. A local thread still remains uncorrected. The question is when public correction becomes visible in the discussion environment.

Correction supply is the visible production of public corrections within a discussion system. A supply-side perspective treats correction first as public behavior. Corrective messages have effects only after correction becomes available inside a thread. A discussion remains vulnerable when corrections are absent, delayed, concentrated in already receptive spaces, or suppressed by hostile interaction. The supply-effect distinction matters on social platforms. Users discuss, challenge, defend, and interpret misinformation through comment threads. Public correction is a behavioral and relational outcome: a user responds to a prior claim in a way that publicly challenges or corrects the claim.

Network heterogeneity links correction supply to more than one mechanism. The informational benefit is consistent with research on cross-cutting exposure and network diversity. Users connected across communities encounter a broader range of perspectives and evidence (Mutz, 2002, 2006). Public correction is also a visible social act. Users who speak across heterogeneous audiences face disagreement, social accountability, hostile replies, and uncertainty about audience interpretation. Research on context collapse, self-censorship, and the spiral of silence links visibility and audience composition to public expression (Noelle-Neumann, 1974; Marwick and boyd, 2011; Hampton et al., 2014). The term heterogeneity covers distinct mechanisms.

The capacity-activation framework makes the mechanism distinction explicit. Correction capacity refers to observable conditions that place a user closer to diverse informational cues or cross-community discussion. Cross-group participation is the observable proxy for such structural position. Correction activation refers to the conversion of correction capacity into visible correction within a local thread environment. Activation depends on user position and thread conditions. The relevant thread conditions include early correction norm, early audience structural heterogeneity, and hostile thread climate. The capacity-activation distinction turns a broad question about heterogeneity into a more precise question. The resulting question is how different forms of heterogeneity and local climate shape the conversion of correction capacity into public correction supply.

The empirical setting is Reddit discussions about COVID-19 vaccination. Reddit discussion threads connect claims, replies, users, and local conversational context. The dataset contains 165,061 comments from 10,220 threads. The analysis focuses on later thread-author instances, which link authors to threads after the early-comment window.

The measurement design treats public correction as a relation-aware behavior. A correction label requires more than corrective language or disagreement. The label is assigned when a response targets and corrects a specific prior claim. To scale the relational definition, the analysis constructs candidate claim-response pairs and uses a pair-level correction detector evaluated through independent audit evidence. The audit result supports thread-level behavioral analysis with explicit measurement uncertainty.

The empirical design connects observational evidence with calibrated simulation. Observational models estimate how user position and thread conditions are associated with later public correction. The models link cross-group position to higher later public correction. The association for early audience structural heterogeneity is positive but less precise. Local thread climate separates facilitation from inhibition: early correction norm is positive, while hostile thread climate is negative.

The agent-based model translates individual correction probabilities into system-level correction supply. The model uses 89,251 observed thread-author instances as agents. The scenario design uses the same empirical Reddit population while varying observable conditions. Scenario comparisons show that correction activation changes when early correction visibility and hostile thread climate are jointly varied.

The design makes three contributions to computational communication research on misinformation. The supply-side account explains why correction effects require visible correction supply in public discussion. The relation-aware measurement strategy treats public correction as a claim-response relation that matches the conversational structure of online correction. The layered account of heterogeneity separates correction capacity from correction activation. Cross-group structural position is used as the correction-capacity proxy. Early correction norm and hostile thread climate shape correction activation across threads.

The scope is observational. Trace data record public behavior. Private misinformation recognition, anticipated social accountability, and internal willingness remain outside direct observation. The empirical analysis studies actual public correction behavior and the observable conditions associated with that behavior. Scenario analysis with the agent-based model examines the aggregate patterns implied by fitted individual correction probabilities. The boundary clarifies the claim. Misinformation persists in public discussion when correction capacity is unevenly activated across local thread environments.

## Theory

### From Correction Effectiveness to Correction Supply

Correction supply is the behavioral condition for correction effectiveness. The correction-effects literature establishes the post-exposure part of the problem. A supply-side account begins one step earlier. Correction effects in public discussion depend on whether correction first becomes visible in the local thread environment.

Correction supply shifts attention from correction effects to correction behavior. Studies of social-media correction show that corrective messages reduce misperceptions after users encounter corrective messages (Bode and Vraga, 2015; Vraga and Bode, 2017). A thread receives little public correction when users stay silent, arrive late, or correct elsewhere. Correction supply links misinformation research to public expression and participation.

Public correction is a relational behavior. A user produces public correction when a response challenges or corrects a specific prior claim. The target relation matters because generic disagreement and factual talk often look similar when comments are labeled without target relations. A supply-side theory requires a behavioral denominator. The relevant question is which participating users produce visible correction after a local thread has formed.

A supply-side view changes how misinformation persistence is interpreted. Corrective messages sometimes fail after exposure. Correction supply sometimes remains scarce or unevenly distributed. The second pathway is the focus of the article. The theoretical question is when users with correction capacity produce visible correction in local thread environments.

### Network Heterogeneity and Correction Capacity

Network heterogeneity matters first for correction capacity. Users who participate across community groups encounter diverse information, disagreement, and corrective cues. Cross-cutting exposure research shows that heterogeneous networks increase contact with different perspectives (Mutz, 2002, 2006). Brokerage research links cross-boundary position to information access. The capacity account links cross-group structural position to correction-relevant information.

The empirical analysis uses cross-group structural position as an observable proxy for correction capacity. Cross-group users are observed in more than one community-group proxy in the Reddit dataset. Cross-group structural position approximates exposure to multiple discussion environments and more opportunities to encounter contested claims. The proxy is not a pure recognition measure; the proxy also reflects activity in politicized or contested discussions. Private misinformation recognition remains outside direct observation. The empirical claim is behavioral: the predicted pattern is a positive association between cross-group structural position and later public correction.

Correction capacity is defined for users. Correction capacity describes a user's position in the broader discussion ecology. The user-level concept differs from the structure of the local thread audience. The user-thread distinction clarifies how heterogeneity operates at different points in the correction process.

### Public Correction as Local Activation

Correction capacity becomes visible through correction activation. Public correction is a visible social act directed at a prior claim and exposed to other participants. The act exposes the user to agreement, appreciation, conflict, ridicule, or further argument. Research on the spiral of silence, context collapse, and self-censorship explains the public-expression problem. The expression literature links public expression to audience visibility and expected social response (Noelle-Neumann, 1974; Marwick and boyd, 2011; Hampton et al., 2014).

Local thread conditions shape the activation threshold for public correction. Early correction norm records whether correction has already appeared in the early part of the thread. Early correction norm is expected to make public correction appear legitimate and acceptable. Hostile thread climate measures observable hostile language in the discussion. Hostile thread climate is expected to raise the cost of visible correction and reduce later activation.

Early audience structural heterogeneity is another local activation condition. Early audience structural heterogeneity measures whether the early thread audience contains a high share of cross-group users. A structurally heterogeneous early audience provides more diverse cues and a more visible co-corrector pool. A structurally heterogeneous early audience also raises cross-community visibility. Because early audience structural heterogeneity combines diverse cues and cross-community visibility, early audience structural heterogeneity is defined as a thread-level activation condition.

The capacity-activation account separates informational access from public expression. Cross-group structural position represents correction capacity. Early correction norm, hostile thread climate, and early audience structural heterogeneity represent correction activation. The capacity-activation distinction identifies the tension in misinformation correction. User positions create exposure to correction opportunities. Local conditions shape whether correction becomes visible.

### Argument and Expectations

The argument has two parts: correction capacity and correction activation. Cross-group structural position increases correction capacity by placing users closer to diverse informational cues. Local thread conditions increase correction activation when correction is visible and socially supported. Local thread conditions reduce correction activation when public correction becomes costly.

The empirical expectations follow the capacity-activation sequence. The account implies a positive association between cross-group structural position and later public correction. The account also implies that early audience structural heterogeneity conditions the cross-group relationship. Early correction norm is expected to raise correction activation because correction has already become visible and legitimate. Hostile thread climate is expected to lower correction activation by raising the social cost of correction.

The simulation expectation connects the individual and system levels. The empirical analysis estimates associations between observable user and thread conditions and later public correction. The agent-based model applies the fitted probabilities to the observed thread-author population and changes local activation conditions. Scenario differences indicate the generative sufficiency of the capacity-activation account for thread-level correction activation. The combined design supports a bounded claim about correction supply in Reddit COVID-19 vaccination discussions.

## Methods

### Data

The data come from the public Reddit COVID-19 vaccine discussion dataset christinegu27/reddit_covidvaccine_data. The raw files contain Reddit comments and submission metadata from COVID-19 vaccine-related submissions. After preprocessing, the analytic corpus contains 165,061 comments from 10,220 submission threads across 12 subreddits and 58,278 observed authors. Reddit discussion structure links submissions, comments, replies, users, and local conversational context. The design separates early thread conditions from later user behavior and constructs thread-author instances in which users remain present in a discussion.

The main behavioral unit is the later thread-author instance. A thread-author instance represents one author in one submission thread. The behavioral analysis focuses on instances in which the author has at least one later comment after the early-comment window. The design creates a denominator for public correction behavior. The denominator includes visible correctors and participating authors who remain present in the thread without producing later public correction.

### Measuring Public Correction

Public correction is defined as a relation between a response comment and a prior claim. The relational definition differs from a comment-level label. A comment sometimes contains factual information, disagreement, or critical language without correcting the specific claim to which the comment responds. A short response functions as a correction when the response directly challenges a prior claim. The measurement task is to identify a correction relation between a response and a specific target claim.

To operationalize the relational definition, the analysis constructs candidate claim-response pairs from Reddit reply structure and thread context. Each pair contains a potential target claim and a response comment. A relation-aware detector then scores the correction relation between the response and the target claim. For comment-level aggregation, a response comment receives the public correction score from the highest-scoring correction relation among the response comment's candidate pairs. Comments without any candidate correction relation receive a score of zero.

An independent audit evaluates the correction detector. The final correction detector uses a pair-ensemble score to reduce dependence on a single model. The empirical models use predicted correction labels as measurement-informed estimates of public correction behavior. Public correction is a relational construct, and automated labels contain measurement error.

### Analytical Unit and Outcome

The analytical unit connects early thread conditions to later public correction behavior. For each submission thread, comments are ordered chronologically. The early-comment window contains the first ten comments and defines the initial discussion environment. Later comments provide the behavioral outcome period. The outcome is the author's production of at least one later public correction in that thread.

The later thread-author instance is the unit for estimating correction activation. The analysis estimates the probability that a participating author with observable user and thread characteristics produces later public correction after early thread conditions have already formed.

### Key Variables

The key variables translate the capacity-activation account into observable user and thread conditions. User-level structural position is the correction-capacity measure. Early audience structural heterogeneity, early correction norm, and hostile thread climate are local activation measures.

User-level structural position is measured with `user_cross_group_observed`, an indicator of author participation across more than one community-group proxy in the dataset. The indicator is the observable proxy for cross-group structural position. The measure does not observe private misinformation recognition.

Early audience structural heterogeneity is measured with `high_early_audience_structural_heterogeneity`, an indicator of high cross-group-user share among early authors in a thread. The high indicator marks eligible threads with a nonzero value at or above the 75th percentile. Eligible threads have at least five comments. The measure records whether the early local audience is structurally heterogeneous before later public correction is observed.

Early correction norm is measured with `early_correction_norm_presence`, an indicator of at least one predicted public correction in the early-comment window. The measure records correction visibility in the local thread before the later outcome period.

Hostile thread climate is measured with `high_thread_hostility_climate`, an indicator of high dictionary-based hostility rate in the thread. The high indicator marks eligible threads with a nonzero value at or above the 75th percentile. Eligible threads have at least five comments. The measure records observable hostile language. Sanction risk and social accountability remain outside direct observation.

The control variables include early discursive heterogeneity, thread activity, user activity, and community-group fixed effects. Early discursive heterogeneity is based on cue-category entropy in the early-comment window.

### Observational Models

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

### Empirically Calibrated Agent-Based Model

The agent-based model examines how fitted individual correction probabilities accumulate into system-level correction supply. Each empirical thread-author instance is represented as an agent. The agent's probability of producing later public correction is calibrated from the main heterogeneity logit model.

Scenario analysis holds the empirical population fixed and changes observable conditions across simulated scenarios. For each scenario, the calibrated probability is computed for every empirical agent, and public correction behavior is simulated through Monte Carlo draws. The main simulation outcomes are the simulated correction rate and the number of activated threads. An activated thread is a thread with at least one later public correction.

The simulation scenarios change observable conditions such as cross-group position, early audience structural heterogeneity, early correction norm, and hostile thread climate. The main condition map varies early correction norm and hostile thread climate in a 2 x 2 design. Each scenario uses 500 Monte Carlo draws. The condition-map design evaluates changes in correction activation across local thread conditions under the fitted model.

The scenario analysis links micro-level correction probabilities to macro-level correction supply. The empirical Reddit population remains fixed across scenarios. Simulated scenario differences are interpreted as calibrated scenario evidence for the capacity-activation account.

## Results

### Measurement Validation

The measurement analysis evaluates relation-aware detection for thread-level behavioral analysis. The relation-aware detector models correction as a pair-level relation. The pair-level design preserves the target-claim relation absent from standalone comment categories. In the independent audit used for the measurement analysis, the pair-ensemble detector reaches average precision of 0.726 and ROC-AUC of 0.850. The audit result supports aggregate behavioral analysis with explicit measurement caveats.

[Figure 1 about here]

Full-corpus coverage indicates why relation-aware measurement matters for downstream analysis. The measurement pipeline moves from 165,061 comments to 107,023 candidate claim-response pairs and 23,780 predicted public correction comments. The earlier comment-level detector identified 16,976 predicted correction comments. The larger count is consistent with the measurement design because some corrections become identifiable only when the response is evaluated against a specific prior claim.

### Cross-Group Position and Later Public Correction

[Figure 2 about here]

Cross-group users have a higher estimated probability of later public correction. In the main heterogeneity logit model, `user_cross_group_observed` has an odds ratio of 1.138 and p = 0.0104. The score-based model supports the same direction with a coefficient of 0.0216 and p < 0.001.

The cross-group association is a behavioral estimate, and private recognition remains outside direct observation. Cross-group participation is the observable correction-capacity measure. Users observed across community groups occupy more diverse informational contexts. The models account for user activity and thread activity when estimating the association. The trace data support the association between cross-group position and later public correction.

### Layered Heterogeneity

Early audience structural heterogeneity has a positive but less precise main association. In the binary logit model, high early audience structural heterogeneity has OR = 1.083 and p = 0.0888. In the score-based model, the coefficient is 0.0092 and p = 0.1102.

The interaction between cross-group position and early audience structural heterogeneity is positive in both outcome specifications. The binary-logit interaction has OR = 1.160 and p = 0.0892. The score-based interaction coefficient is 0.0234 with p = 0.0308. In the binary model, predicted correction probability rises from 14.8% to 15.8% for non-cross-group users and from 16.4% to 19.7% for cross-group users. In the score-based model, the corresponding predicted score rises from 0.180 to 0.189 for non-cross-group users. For cross-group users, the predicted score rises from 0.202 to 0.234.

The layered heterogeneity pattern separates user position from early audience structural heterogeneity. User-level structural position and thread-level early audience structural heterogeneity are distinct parts of the correction process. Cross-group users have a higher probability of later public correction overall. The predicted probability gap between cross-group and non-cross-group users is larger in structurally heterogeneous early thread environments. The binary-logit interaction is positive and less precise than the score-based interaction.

### Local Correction Norm and Hostile Thread Climate

Local thread climate shapes later public correction. Among the focal local-climate variables, early correction norm has the largest positive association. In the main heterogeneity logit model, `early_correction_norm_presence` has OR = 1.877 and p < 0.001. Hostile thread climate is negatively associated with correction, with OR = 0.854 and p = 0.0173.

The local-climate estimates support the correction activation argument. Public correction is more likely when correction has already become visible early in the thread. Hostile thread climate is associated with a lower probability of later public correction. The interaction between early correction norm and hostile thread climate is negative and imprecise in the binary calibration model. The simulation scenarios below evaluate the joint implications of early correction norm and hostile thread climate for aggregate correction activation.

### Simulation: From Individual Probability to Correction Activation

The agent-based model evaluates how fitted individual-level associations accumulate into system-level correction outcomes. The baseline simulation matches the observed correction rate of approximately 0.151 across 89,251 empirical thread-author instances. The key system-level outcome is the number of activated threads, defined as threads with at least one later public correction.

[Figure 3 about here]

Early correction norm and hostile thread climate jointly shape correction activation in the condition map. When early correction norm is present and hostile thread climate is low, the simulated correction rate reaches 19.1%, with about 2,913 activated threads. The increase is about 185 activated threads relative to the observed baseline. When early correction norm is absent and hostile thread climate is high, the simulated correction rate falls to 9.7%, with about 2,385 activated threads. The decrease is about 344 activated threads relative to the observed baseline.

[Figure 4 about here]

The broader scenario comparison separates correction-rate change from activated-thread change. The local activation scenarios show larger simulated shifts than scenarios that change early audience structural heterogeneity alone. The all-cross-group scenario produces a simulated correction-rate increase of about 2.07 percentage points and about 98 additional activated threads. The high early audience structural heterogeneity scenario produces a simulated correction-rate increase of about 0.85 percentage points and about 44 additional activated threads.

The local-climate scenarios show the largest simulated changes in correction supply. The no-early-correction-norm scenario produces a correction-rate decrease of about 4.40 percentage points and about 252 fewer activated threads. The universal hostile thread climate scenario produces a correction-rate decrease of about 2.09 percentage points and about 118 fewer activated threads. The contrast supports the interpretation of correction activation as a thread-level process.

### Result Synthesis

The results support a capacity-activation account of public misinformation correction. The cross-group association provides the correction-capacity result. Early correction norm and hostile thread climate provide the correction-activation result. Early audience structural heterogeneity connects the two layers by changing the size of the cross-group gap. The simulation translates the fitted associations into thread-level correction supply.

## Discussion

### Capacity, Activation, and Correction Supply

Public misinformation correction is first a supply problem and then a question of effects. The findings locate correction supply in two observable places: users positioned across community groups and local threads where correction is visible and hostile thread climate is low. Cross-group structural position is the observable indicator of correction capacity. Early correction norm and hostile thread climate identify whether correction capacity becomes public behavior.

The theoretical implication is that network heterogeneity is layered. User-level structural heterogeneity refers to cross-group position and correction capacity. Thread-level audience structural heterogeneity describes the local audience environment. Early correction norm and hostile thread climate describe the discussion conditions in which correction becomes visible. The heterogeneity layers operate at different points in the correction process.

The agent-based model adds a system-level interpretation. The model keeps the empirical Reddit population fixed and changes observable conditions. Activation is highest when early correction norm is present and hostile thread climate is low. Activation is lowest when hostile thread climate is high and early correction norm is absent. The scenario results show the aggregate correction supply implied by fitted user-level probabilities.

### Correction Supply as a Behavioral Outcome

The supply-side account defines public correction as a behavioral outcome. Correction-effects research asks whether corrections reduce misperceptions after exposure. Social-media correction research shows why corrective responses matter once users encounter corrective responses. A supply-side account asks whether corrections become publicly available in the discussion environment. The distinction matters because public threads receive few corrections even when corrective information exists elsewhere.

The behavioral outcome precedes correction effects. Later public correction records whether users produce visible correction inside a thread. The outcome allows misinformation persistence to be studied as public correction scarcity and uneven activation. The account moves the empirical focus from belief change after exposure to the public availability of correction.

Relation-aware measurement identifies public correction as a claim-response behavior. Public correction is measured as a response that targets a specific prior claim. The relation-aware design separates correction from generic disagreement, factual talk, or negative sentiment. The detector aligns the measurement task with the conversational structure of Reddit threads.

### Layered Network Heterogeneity

The layered heterogeneity account separates structural position from local audience context. Cross-cutting exposure research motivates the correction-capacity side of the account. Expression research motivates the correction-activation side. The capacity-activation distinction connects cross-cutting exposure research and expression research through public correction behavior.

The empirical pattern locates cross-group position on the correction-capacity side of the argument. Early audience structural heterogeneity shows a positive and less precise relationship in the binary model, with support from the score-based and descriptive analyses. The layered pattern treats early audience structural heterogeneity as a contextual condition distinct from user position.

The layered account avoids treating network heterogeneity as a single variable. Cross-group structural position, early audience structural heterogeneity, early correction norm, and hostile thread climate perform different analytical roles. The account treats network heterogeneity as a family of conditions linked to different parts of the correction process.

### Relation-Aware Measurement and Generative Simulation

The computational design integrates relation-aware detection, observational network analysis, and empirically calibrated simulation. The detector provides a scalable measure of public correction as a claim-response relation. The observational models link measured public correction to user position and thread conditions. The agent-based model uses the fitted associations to simulate system-level correction supply.

The simulation follows the generative logic of agent-based modeling. In generative logic, explanation means showing how micro-level rules produce a macro-level pattern (Epstein, 1999, 2006). Each agent represents an empirical thread-author instance. Scenario comparisons change observable conditions. The empirical population remains fixed. The empirical-population design preserves the observed distribution of users and threads.

The simulation adds calibrated scenario evidence. Early correction norm has a larger simulated association than early audience structural heterogeneity alone. Hostile thread climate is associated with lower correction activation and offsets part of the benefit of early correction norm in simulated scenarios. The scenario pattern locates correction supply in both interaction climate and the presence of users with correction capacity.

### Platform and Community Implications

Public correction is an interactional supply problem for platforms and communities. More users with correction capacity in a discussion are associated with higher correction supply. Local conditions still shape correction activation. The results point to early and visible correction opportunities as a design margin.

The first design implication concerns early correction visibility. When correction appears early, later users receive a visible cue that correction is legitimate in that thread. One platform design option is to make high-quality early corrections easier to find. Community moderation offers another route: norms that recognize corrective participation without public shaming.

The second design implication concerns hostile thread climate. Hostile language is associated with reduced later public correction and lower simulated activation. The results locate hostile thread climate as a condition under which visible correction becomes less likely. The implication connects misinformation governance to broader moderation questions about civility, sanctions, and participation.

### Limitations

The first boundary concerns observable public behavior on Reddit. Trace data capture visible correction behavior, local thread conditions, and user participation. Private recognition, internal confidence, and anticipated social accountability remain outside direct observation. The claims concern visible correction behavior and observable thread conditions.

Measurement uncertainty is the second boundary. Independent audit evidence supports aggregate analysis. Predicted correction labels remain estimates. The relation-aware design addresses one measurement problem by linking responses to target claims. Further validation is needed to improve label precision across topics and platforms.

Associational inference is the third boundary. Cross-group position, early audience structural heterogeneity, early correction norm, and hostile thread climate are observed conditions. Unobserved user traits and thread selection are possible sources of the observed associations. The model estimates are interpreted as evidence about observable behavioral patterns.

Simulation scope is the fourth boundary. The agent-based model provides scenario analysis under fitted assumptions. The scenario results support generative sufficiency under the capacity-activation account. The appropriate interpretation is calibrated scenario exploration. Causal tests require platform experiments, survey measures, or field interventions.

### Conclusion

The findings point to uneven conversion from correction capacity to correction activation. Reddit COVID-19 vaccination discussions show that users with correction capacity contribute to broader correction supply when correction is already visible and hostile thread climate is low. Early correction norm marks correction as visible and legitimate. Hostile thread climate marks an environment where correction carries higher expected social cost. The implication is that misinformation persistence arises from uneven correction supply, even when users with correction capacity are present in the discussion system.

## References

References are generated from `references.bib` during LaTeX assembly.
