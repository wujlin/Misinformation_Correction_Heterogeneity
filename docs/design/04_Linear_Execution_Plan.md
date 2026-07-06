# Linear Execution Plan

## 1. Current Research Position

The project should now be framed as a study of correction misallocation on Reddit.

The central question is:

> Do public corrections appear where misinformation correction is most needed, or are they concentrated in communities that are already skeptical of the misinformation?

The project should not claim that trace data can prove private recognition. The observable target is actual public correction behavior among exposed users.

## 2. Core Argument

The core argument is that misinformation correction may fail because correction supply is misallocated across communities.

Correction demand is high in rumor-supportive communities because misinformation is more likely to be accepted or defended there. However, correction supply may be higher in rumor-skeptical communities where correction is socially easier but less needed.

This creates the main empirical pattern:

```text
high correction demand
-> low correction supply
```

The key mechanism is local normative cost. Public correction in a rumor-supportive community means speaking against the local majority. Public correction in a rumor-skeptical community means speaking with the local majority.

## 3. Research Design Overview

The study should proceed in four layers:

1. Pilot data validation.
2. Main trace-data analysis.
3. Sub-analyses on cross-community travel and correction threshold.
4. ABM counterfactual experiment.

The first layer decides whether the project is feasible. The later layers should not be built before the pilot confirms that correction behavior can be reliably detected.

## 4. Layer 1: Pilot Data Validation

### 4.1 Platform

Use Reddit as the main platform.

Reddit is useful because thread participation allows a partial construction of the denominator:

```text
exposed-but-silent users
= users who participated in the thread but did not post public correction
```

This does not prove that these users privately recognized misinformation, but it provides a stronger behavioral denominator than many other platforms.

### 4.2 Topic

Start with COVID, vaccine, and health misinformation.

These topics are suitable because fact-checking references and public health sources can help establish misinformation claims and correction references.

Potential ground-truth sources:

- Snopes
- PolitiFact
- FactCheck.org
- CDC
- WHO
- Reuters Fact Check

### 4.3 Pilot Sample

The pilot should collect:

- 20-30 misinformation claims.
- 200-500 Reddit threads.
- 1,000-2,000 comments for manual annotation.
- User-level posting histories when available.

### 4.4 Pilot Questions

The pilot must answer four feasibility questions:

1. Are there enough threads containing identifiable misinformation claims?
2. Is public correction frequent enough to model statistically?
3. Can correction be reliably identified through manual coding and text classification?
4. Can user-level cross-community participation be reconstructed?

### 4.5 Pilot Go/No-Go Criteria

Continue to the main study only if:

- Public correction is not too rare.
- The correction classifier reaches acceptable precision and recall.
- User history provides enough information to measure brokerage or structural heterogeneity.
- Threads contain enough exposed-but-silent users to construct the denominator.

If these conditions fail, the project should either narrow the topic or shift to a different empirical context.

## 5. Layer 2: Main Trace-Data Analysis

### 5.1 Unit of Analysis

Use the following unit:

```text
user x thread x misinformation claim
```

The outcome is whether an exposed user publicly corrected misinformation in a thread.

### 5.2 Outcome Variable

Public correction is coded as 1 when a user publicly posts a reply or comment that:

- identifies a claim as false, misleading, unsupported, or debunked;
- provides a fact-checking source;
- cites scientific or official evidence;
- directly challenges the misinformation claim with corrective information.

Users who participate in the same thread but do not post correction are coded as exposed-but-silent.

### 5.3 Key Independent Variables

Correction capacity:

- Brokerage position.
- Cross-community participation.
- Subreddit diversity entropy.
- Participation in both rumor-supportive and rumor-skeptical communities.

Local normative cost:

- Rumor-supportive climate in the thread or subreddit.
- Pre-existing share of misinformation-supportive comments.
- Local stance distribution before the user's comment opportunity.

### 5.4 Main Model

The main statistical model should test:

```text
Public correction
~ correction capacity
+ local normative cost
+ correction capacity x local normative cost
+ controls
+ user/thread/subreddit random effects
```

The interaction term is the main test.

The expected pattern is:

```text
correction capacity increases public correction overall,
but this advantage decreases or reverses in rumor-supportive communities.
```

### 5.5 Controls

Potential controls include:

- User activity level.
- Account age when available.
- Prior subreddit participation volume.
- Thread popularity.
- Comment depth.
- Time since thread creation.
- Topic category.
- Whether prior correction already appeared in the thread.
- Subreddit size and moderation intensity when available.

## 6. Layer 3: Sub-Analyses

### 6.1 Sub-Analysis B: Cross-Community Travel

This analysis asks whether corrections travel from rumor-skeptical communities to rumor-supportive communities.

Observable signals:

- Reuse of fact-checking links.
- Reuse of debunking claims.
- Similar correction language appearing across subreddits.
- Broker users carrying correction content across communities.

Purpose:

This analysis supports the correction misallocation claim by showing whether correction remains trapped in communities where misinformation is already contested.

### 6.2 Sub-Analysis C: Collective Correction Threshold

This analysis asks whether the first correction lowers the cost of later corrections.

Key question:

> Does an early correction trigger additional corrections, and does this effect vary by local rumor-supportive climate?

Expected pattern:

- In rumor-skeptical communities, one correction may trigger more corrections.
- In rumor-supportive communities, one correction may not be enough to start a correction cascade.

Purpose:

This analysis links correction misallocation to collective action dynamics.

## 7. Layer 4: ABM Counterfactual Experiment

### 7.1 Purpose

The ABM should not be used as evidence that the psychological mechanism is true.

The ABM should be used for:

1. Generative sufficiency.
2. Counterfactual analysis.

The question is:

> Are correction capacity and local normative cost sufficient to generate the correction misallocation observed in Reddit data?

### 7.2 Agent Rule

A simple agent rule can be:

```text
P(public correction)
= f(correction capacity,
    local normative cost,
    prior corrections,
    individual correction threshold)
```

### 7.3 Calibration

Parameters should be calibrated from the trace-data model whenever possible.

Do not use ABM to invent unobserved psychological parameters without empirical anchoring.

### 7.4 Counterfactuals

The ABM can test:

1. What if local normative cost in rumor-supportive communities is reduced?
2. What if a small number of co-correctors are introduced into rumor-supportive communities?
3. What if the first correction is made more visible?
4. What if broker users have a lower correction threshold?

### 7.5 Outcomes

Simulation outcomes:

- Public correction rate.
- Correction misallocation index.
- Correction diffusion across communities.
- Misinformation persistence.
- Cascade depth and duration.

## 8. Role of LLM Agents

LLM agents are optional.

They should only be used if real Reddit text can ground the agent's information environment.

Valid use:

- Feed actual thread content to constrained agents.
- Ask agents to classify or respond under predefined correction thresholds.
- Compare LLM-generated behavior with observed aggregate patterns.

Invalid use:

- Prompt agents to behave as socially accountable users and then treat the result as evidence.
- Use LLM agents without calibration.
- Make LLM agents the theoretical contribution.

If grounding and validation are weak, use a parameterized ABM instead.

## 9. Contribution After Redesign

The theoretical contribution is:

> The study shifts misinformation correction research from correction effectiveness to correction allocation.

Existing studies ask whether correction works. This project asks whether corrections occur in the communities where they are most needed.

The methodological contribution is:

> The study combines correction detection, denominator construction, network analysis, and generative simulation to explain actual public correction behavior in Reddit misinformation discussions.

## 10. Paper Structure

### Introduction

- Public correction can reduce misinformation, but corrections may not appear where they are needed.
- Reddit enables measurement of both correction and exposed-but-silent users.
- The paper studies correction misallocation.

### Theory

- Misinformation correction and observed correction.
- Cross-cutting exposure and brokerage.
- Spiral of silence and local normative climate.
- Correction misallocation framework.

### Data and Measurement

- Misinformation claim selection.
- Reddit thread collection.
- Manual annotation and correction classifier.
- Network and community measures.
- Denominator construction.

### Main Results

- Correction distribution across community climates.
- Brokerage and public correction.
- Brokerage x local normative cost interaction.
- Correction misallocation index.

### Sub-Analyses

- Cross-community travel of corrections.
- Collective correction threshold.

### ABM Counterfactuals

- Model construction and calibration.
- Generative sufficiency.
- Counterfactual interventions.

### Discussion

- Correction supply-demand mismatch.
- Implications for platform design and community moderation.
- Limits of trace data.
- Why simulation supports plausibility rather than causal proof.

## 11. Immediate Next Steps

1. Select 20-30 health misinformation claims.
2. Identify relevant subreddits.
3. Test data access and collection.
4. Build an annotation codebook for public correction.
5. Label a pilot sample.
6. Estimate correction prevalence and classifier reliability.
7. Decide whether Reddit is feasible for the full study.
