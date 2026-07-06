# Manuscript Outline

## Title

From Correction Capacity to Correction Activation: Network Heterogeneity and Public Misinformation Correction on Reddit

## Abstract

Role: state the problem, empirical design, main findings, contribution, and causal boundary.

Core movement:

1. Misinformation correction research often studies correction effects after corrections appear.
2. The present study examines whether correction-capable users publicly activate correction.
3. The study measures public correction as a relation between a response and a prior claim.
4. Reddit COVID-19 vaccination discussions provide thread-author instances for analysis.
5. Cross-group users have a higher estimated probability of correction, while local correction norm and hostile thread climate shape activation.
6. Empirically calibrated ABM shows how these associations accumulate into system-level correction supply.

## 1. Introduction

Question answered:

> Why should misinformation correction be studied as a supply-side public behavior and as an effect of corrective messages?

Paragraph roles:

1. Define the public correction problem: corrections matter after they become visible.
2. Explain the gap in existing correction research: correction effectiveness vs correction supply.
3. Introduce network heterogeneity as a double-edged condition, but avoid claiming private recognition.
4. Define correction capacity and correction activation.
5. State empirical setting and measurement approach.
6. Preview main findings.
7. State contributions.

## 2. Theory

### 2.1 From Correction Effectiveness to Correction Supply

Question answered:

> What is missing when misinformation correction research focuses mainly on whether corrections work?

Core claim:

Correction effectiveness and correction supply are distinct problems. A correction may be persuasive after it is visible, but public discussions can still fail when few users produce corrections or when corrections appear only in already receptive environments.

Likely references:

- misinformation correction effects;
- corrective information and social correction;
- misinformation persistence.

### 2.2 Network Heterogeneity and Correction Capacity

Question answered:

> Why might structurally heterogeneous users be more likely to correct?

Core claim:

User-level structural heterogeneity can increase exposure to diverse informational cues and discussion contexts. In this paper, cross-group participation is treated as an observable proxy for correction capacity. Private recognition remains outside direct observation.

Likely references:

- cross-cutting exposure;
- network heterogeneity;
- brokerage and information access.

### 2.3 Public Correction as Local Activation

Question answered:

> Why might correction capacity fail to become visible correction?

Core claim:

Public correction is a visible social act. Local discussion conditions shape whether correction becomes visible. Early correction norm may signal that correction is acceptable. Hostile thread climate may increase the expressive cost of correction.

Likely references:

- spiral of silence;
- context collapse;
- social accountability;
- collective action or threshold models.

### 2.4 Argument and Expectations

Question answered:

> What should be observed if the capacity-activation argument is plausible?

Expectations:

1. Cross-group users should be more likely to produce later public correction.
2. Early audience structural heterogeneity should strengthen or condition this relationship.
3. Early correction norm should be associated with more later correction.
4. Hostile thread climate should be associated with less later correction.
5. In simulation, early correction norm with low hostile thread climate should increase correction activation, while high hostile thread climate without early correction norm should reduce correction activation.

## 3. Data and Measurement

### 3.1 Reddit COVID-19 Vaccination Discussions

Question answered:

> What empirical setting is used and why is it suitable?

Content:

- COVID-19 vaccination Reddit discussion dataset;
- 165,061 comments;
- 10,220 threads;
- user-thread participation allows construction of exposed or participating denominators;
- Reddit is suitable because thread structure links claims, replies, users, and local discussion context.

### 3.2 Relation-Aware Public Correction Detection

Question answered:

> How is public correction measured?

Content:

- public correction as a relation between a response and a prior claim;
- pair candidate construction;
- pair-level detector;
- independent audit performance;
- downstream comment-level correction score.

Boundary:

The detector estimates public correction and introduces measurement uncertainty. The manuscript treats predicted correction as a measurement-informed estimate.

### 3.3 Agent and Thread Variables

Question answered:

> What are the main analytical units and variables?

Content:

- unit: later thread-author instance;
- outcome: whether the author produces later public correction in the thread;
- user-level variable: cross-group observed;
- thread-level variables: early audience structural heterogeneity, early correction norm, hostility, discursive heterogeneity;
- controls: user activity, thread activity, community group proxy.

## 4. Empirical Strategy

### 4.1 Observational Models

Question answered:

> How are associations between observable conditions and later public correction estimated?

Content:

- binary logit for later correction;
- score-based OLS as a threshold-sensitivity check;
- clustered standard errors by thread;
- no causal identification claim.

### 4.2 Empirically Calibrated ABM

Question answered:

> What does ABM add beyond observational models?

Content:

- agents are empirical thread-author instances;
- correction probability is calibrated from the main heterogeneity logit;
- simulation fixes the empirical population and changes observable conditions;
- output: correction rate and activated threads;
- role: generative sufficiency and scenario exploration under fitted assumptions.

## 5. Results

### 5.1 Measurement Validation

Question answered:

> Does the correction detector support downstream behavioral analysis?

Content:

- audit average precision around 0.72-0.73;
- ROC-AUC around 0.85;
- measurement uncertainty acknowledged.

### 5.2 Cross-Group Position and Later Public Correction

Question answered:

> Are cross-group users more likely to correct?

Content:

- cross-group OR = 1.138, p = 0.0106;
- score model supports the direction.

### 5.3 Layered Heterogeneity

Question answered:

> Does audience structural heterogeneity condition correction?

Content:

- main effect positive and smaller;
- score-model interaction clearer;
- interpret binary-logit interaction as positive and less precise.

### 5.4 Correction Norm and Hostile Thread Climate

Question answered:

> Which local discussion conditions shape correction activation?

Content:

- early correction norm largest positive contextual signal;
- hostility negative;
- norm with hostility weakens activation.

### 5.5 ABM Scenario Results

Question answered:

> How do individual associations accumulate into system-level correction supply?

Content:

- Figure 3 condition map;
- Figure 4 counterfactual activation shift;
- supportive context increases activated threads;
- hostile contexts without early correction norm reduce activated threads.

## 6. Discussion

Question answered:

> What does the study change in how we understand misinformation correction?

Core claims:

1. Public correction should be studied as correction supply and correction effectiveness.
2. Network heterogeneity should be decomposed into user position and local audience context.
3. Correction-capable users may produce uneven correction activation across local discussion environments.
4. Platform design and community governance should consider early correction visibility and hostile sanction climate.

Boundary:

- private recognition remains outside direct observation;
- audience heterogeneity is structurally proxied;
- Reddit COVID-19 vaccination discussion has platform and topic boundaries;
- ABM is calibrated scenario exploration under fitted assumptions.

## 7. Conclusion

Question answered:

> What is the final takeaway?

Core sentence:

Misinformation persistence can arise because corrections fail after exposure and because correction capacity is unevenly activated across public discussion environments.
