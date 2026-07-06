# Model and Methods

## 1. Conceptual Model

The proposed model is an epistemic-expressive model of public correction.

The model argues that information checking behavior is shaped by two mechanisms:

```text
Network structural heterogeneity
-> diverse informational cues
-> private misinformation recognition

Audience attribute heterogeneity
-> anticipated social accountability
-> public correction inhibition
```

The model does not require a fixed temporal sequence. Recognition and expression can interact dynamically. The analytical distinction is still necessary because it separates cognitive recognition from public expression.

## 2. Main Variables

### 2.1 Independent variables

Network structural heterogeneity:

- Whether a user connects multiple communities.
- Whether a user occupies a brokerage position.
- Whether a user receives information from structurally diverse neighbors.

Audience attribute heterogeneity:

- Whether the user's audience contains people with different stances.
- Whether the user's audience combines different relationship types.
- Whether the user perceives the audience as socially mixed or conflict-prone.

### 2.2 Mechanism variables

Private recognition:

- Whether the user recognizes misinformation.
- How confident the user is in that recognition.
- Whether the user has encountered corrective information.

Anticipated social accountability:

- Expected conflict.
- Expected social punishment.
- Concern about being perceived as partisan, aggressive, or overly serious.
- Concern about damaging relationships.

### 2.3 Outcome variables

Public correction:

- Publicly correcting misinformation.
- Replying with a correction.
- Posting a counterclaim.
- Sharing corrective information.

Correction inhibition:

- Recognizing misinformation but remaining publicly silent.
- Choosing private correction instead of public correction.
- Avoiding engagement despite confidence in the information.

Misinformation persistence:

- Continued visibility of misinformation.
- Low correction diffusion.
- Persistence of misperceptions in simulated populations.

## 3. Potential Hypotheses

H1: Network structural heterogeneity is positively associated with private misinformation recognition.

H2: Audience attribute heterogeneity is positively associated with anticipated social accountability.

H3: Anticipated social accountability is negatively associated with public correction.

H4: Audience attribute heterogeneity weakens the association between private recognition and public correction.

H5: Networks with high structural heterogeneity but high audience attribute heterogeneity may produce a larger gap between private recognition and public correction.

These hypotheses should be refined after deciding the empirical context and data structure.

## 4. Network Analysis Plan

Network analysis will be used to define the user's position and audience structure.

Possible network types:

- Following network
- Reply network
- Retweet or repost network
- Mention network
- Discussion-thread interaction network

Possible measures:

- Degree centrality
- Betweenness centrality
- Ego-network diversity
- Cross-community tie ratio
- Modularity-based community membership
- Brokerage and constraint
- Attribute diversity among neighbors or visible audience

The key is to avoid using network measures only as descriptive statistics. The measures should map onto the theoretical mechanisms:

- Structural heterogeneity maps onto information exposure and private recognition.
- Attribute heterogeneity maps onto social accountability and public correction inhibition.

## 5. Agent-Based Modeling Plan

The ABM should simulate how micro-level recognition and correction decisions produce macro-level misinformation persistence.

### 5.1 Agents

Each agent can have:

- Factual knowledge
- Misinformation exposure
- Correction exposure
- Recognition probability
- Confidence
- Audience heterogeneity
- Social accountability sensitivity
- Correction threshold

### 5.2 Decision rule

A simple decision rule can be:

```text
Public correction occurs when:

recognition confidence + perceived correction efficacy
>
anticipated social accountability + conflict cost
```

This rule can be refined through survey or experimental evidence.

### 5.3 Network generation

The model can compare different network generation mechanisms:

- High homophily network
- Moderate heterogeneity network
- High heterogeneity network
- Modular network with brokers
- Network with context collapse

The simulation can test how different structures affect:

- Recognition rate
- Public correction rate
- Recognition-correction gap
- Misinformation persistence
- Correction diffusion

## 6. Role of LLM Agents

LLM agents should not become the theoretical core. Their role is methodological.

Possible uses:

- Simulating heterogeneous user personas.
- Generating context-sensitive correction decisions.
- Representing different levels of confidence, conflict avoidance, and social accountability concern.
- Testing how behavioral rules change under different audience structures.

LLM agent behavior must be constrained, calibrated, and validated. The model should not treat free-form LLM outputs as empirical evidence by themselves.

## 7. Empirical Strategy Options

### Option A: Survey experiment plus simulation

Use survey experiment to estimate how audience heterogeneity affects social accountability and correction intention. Use these parameters to calibrate ABM.

### Option B: Observational network data plus survey

Collect a networked discussion dataset and measure users' positions. Combine with survey measures of recognition, correction willingness, and perceived audience heterogeneity.

### Option C: Fully simulated design

Use ABM and LLM agents to explore theoretical mechanisms. This option is useful for early-stage model development, but it is weaker for publication unless validated with human data.

## 8. Current Best Positioning

The strongest positioning is:

> This study explains why heterogeneity can improve misinformation recognition while inhibiting public correction. It shows how network structure and audience composition jointly shape the gap between private recognition and public correction.

This positioning keeps the project close to communication research and avoids turning it into a purely technical simulation paper.
