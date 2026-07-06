# Manuscript Spine

## Working Title

From Correction Capacity to Correction Activation: Network Heterogeneity and Public Misinformation Correction on Reddit

## One-Sentence Claim

Public misinformation correction involves two linked questions: whether corrections work after they appear, and whether correction-capable users publicly activate correction in the discussion environments where correction is needed.

## Core Argument

This paper studies public correction as a supply-side communication behavior. Prior work has shown that corrections can reduce misperceptions and that heterogeneous networks can expose users to more diverse information. The present study asks a different question: when does correction capacity become public correction supply?

The argument has three steps.

First, network heterogeneity contains multiple constructs. User-level structural heterogeneity captures whether users participate across communities and may therefore encounter more diverse informational cues. Thread-level audience structural heterogeneity captures the local discussion environment in which a corrective response becomes visible.

Second, public correction depends on local activation conditions. A cross-group user may have higher correction capacity, but public correction becomes more likely when early correction norms are visible and less likely when hostile thread climate is high.

Third, misinformation persistence can emerge from a mismatch between correction capacity and correction activation. Correction-capable users may exist, while correction supply remains unevenly distributed across threads when the local discussion climate limits visible correction.

## Research Question

How do user-level structural position and thread-level discussion conditions shape public misinformation correction in online discussions?

## Empirical Setting

The empirical setting is Reddit discussions about COVID-19 vaccination. The dataset contains 165,061 comments. Public correction is measured through a relation-aware pair-level detector that identifies whether a response comment corrects a specific prior claim.

## Measurement Contribution

Public correction is measured as a relation-aware behavior. A corrective comment is a response that targets a specific prior claim. The relation-aware detector operationalizes this distinction and reduces the risk of treating generic disagreement as correction.

## Mechanism Contribution

The paper distinguishes correction capacity from correction activation.

- Correction capacity is associated with user-level structural position, especially cross-group participation.
- Correction activation is associated with local discussion conditions, especially early correction norm and hostile thread climate.

The capacity-activation distinction replaces the broad claim that heterogeneity is simply good or bad. The results show that different forms of heterogeneity operate at different levels of the correction process.

## Method Contribution

The paper combines relation-aware correction detection, observational network analysis, and empirically calibrated agent-based modeling.

The observational analysis estimates associations between observed network and thread conditions and later public correction. The agent-based model then fixes the empirical Reddit population and changes observable conditions to examine how individual correction probabilities accumulate into system-level correction supply.

## Main Evidence

### Detector

The latest independent audit shows that the relation-aware correction detector reaches average precision around 0.72-0.73 and ROC-AUC around 0.85. The detector supports downstream behavioral analysis with explicit measurement uncertainty.

### Observational Models

The later-correction model uses 89,251 later thread-author instances.

Key results:

- Cross-group users have a higher estimated probability of later public correction: OR = 1.138, p = 0.0104.
- Early audience structural heterogeneity is positive but less precise: OR = 1.083, p = 0.0888.
- The interaction between cross-group position and early audience structural heterogeneity is clearer in the score-based model: coefficient = 0.0234, p = 0.0308.
- Early correction norm is the largest positive contextual signal.
- Hostile thread climate is negatively associated with later public correction.

### ABM Results

The empirically calibrated simulation uses 89,251 empirical thread-author agents and 500 Monte Carlo draws per scenario.

Key scenario differences relative to observed baseline:

- all cross-group position: correction rate +2.07 percentage points and +98 activated threads;
- high early audience structural heterogeneity: +0.85 percentage points and +44 activated threads;
- no early correction norm: -4.40 percentage points and -252 activated threads;
- universal hostile thread climate: -2.09 percentage points and -118 activated threads;
- early correction norm with low hostile thread climate: +3.92 percentage points and +185 activated threads;
- no early correction norm with high hostile thread climate: -5.41 percentage points and -344 activated threads.

## Figure Plan

Main text:

- Figure 1: Relation-aware measurement and empirical design.
- Figure 2: Observational mechanism results.
- Figure 3: ABM correction activation condition map.
- Figure 4: ABM counterfactual activation shift.

Appendix:

- Detector audit and measurement validation.
- Calibration forest plot.
- Monte Carlo stochasticity.
- Robustness tables.

## Boundary of the Claim

The study observes public correction behavior and observable conditions associated with that behavior. Private misinformation recognition and anticipated social accountability remain outside direct observation. The simulation shows generative sufficiency under the fitted probability model. The simulation is interpreted as scenario evidence under fitted assumptions.

## Target Journal Positioning

For JCMC, the manuscript should be positioned as a computational communication study of public correction supply. The central contribution is the distinction between correction capacity and correction activation, measured through relation-aware correction detection and tested through empirical-population simulation.
