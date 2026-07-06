# Research Logic and Discussion Record

## 1. Starting Point

The initial research interest was to find a strong computational communication topic that can combine network analysis, agent-based modeling, and possibly LLM agents. The topic should have a real-world problem, a clear mechanism, and a contribution beyond a descriptive pattern.

The selection criteria became:

- The mechanism should not be reducible to a volume effect.
- The finding should have a counterintuitive direction.
- Network analysis and ABM should explain the mechanism, not only visualize the data.
- LLM agents should be methodologically useful but should not replace theory.

## 2. Directions Considered and Rejected

### 2.1 AI-generated fake news diffusion

This direction was considered but rejected as too broad. The field is crowded, and simply saying that AI-generated misinformation spreads or is harmful does not provide a strong contribution.

### 2.2 Platform correction mechanism

This direction was also set aside because platform correction systems are often difficult to observe. The mechanism depends on black-box moderation, platform-specific rules, and limited data access.

### 2.3 Perceived majority and source independence

The idea was to study how AI-generated opinions create perceived majority. Several mechanisms were discussed, such as source independence, semantic synchrony, and majority perception.

The weakness was that many hypotheses became intuitive or already familiar. For example, if users see more similar opinions in their local information environment, they are likely to perceive stronger support. Backfire through coordination cues is also a well-studied mechanism.

### 2.4 Public comments, textual diversity, and attention allocation

Another direction focused on mass public participation. The idea was that textual diversity may overstate substantive opinion diversity, especially when repeated arguments are paraphrased into many different forms.

This direction had some real-world context, including mass comments, duplicate comments, and public comment processing. However, the stronger claim became difficult to separate from a volume effect. If one argument has more narrative variants because it has more comments, then its higher visibility is not a distinct mechanism.

The direction may still work as a computational public administration or text-as-data problem, but it is not currently the strongest candidate for a communication journal.

## 3. Current Direction

The current direction focuses on misinformation correction and network heterogeneity.

The key problem is not simply whether correction works. Existing research suggests that public correction and observed correction can reduce misperceptions. The more basic question is why correction does not happen even when users privately recognize misinformation.

The current research object is the gap between private recognition and public correction.

## 4. Core Mechanism

The project now uses an epistemic-expressive model of public correction.

The model avoids describing the process as two temporal stages. Instead, it distinguishes two analytically different mechanisms:

- Epistemic mechanism:
  What users know, see, and recognize.

- Expressive mechanism:
  Whether users are willing to publicly act on that recognition.

This distinction is important because silence can mean different things. A user may remain silent because the user does not recognize misinformation, or because the user recognizes it but expects public correction to create social cost.

## 5. Network Heterogeneity

The project distinguishes two forms of heterogeneity.

### 5.1 Network structural heterogeneity

Network structural heterogeneity refers to the structure of a user's network position. It captures whether the user connects multiple communities, receives information from diverse network neighborhoods, or occupies a brokerage position.

Possible measures:

- Ego-network community diversity
- Cross-community tie ratio
- Betweenness centrality
- Brokerage position
- Burt's constraint
- Effective number of communities in the ego network

Expected role:

Network structural heterogeneity may improve exposure to diverse informational cues and increase misinformation recognition.

### 5.2 Audience attribute heterogeneity

Audience attribute heterogeneity refers to the attributes of the audience visible to a user. It captures whether the user's audience differs in stance, identity, relationship type, expertise, or group membership.

Possible measures:

- Ideological diversity of audience
- Relationship diversity of audience
- Identity diversity of audience
- Strong-tie and weak-tie mixture
- Perceived audience disagreement

Expected role:

Audience attribute heterogeneity may increase anticipated social accountability, conflict risk, and expression concern, which may suppress public correction.

## 6. Why This Direction Is More Promising

This direction is stronger because it contains a real tension:

> Heterogeneity may help users recognize misinformation while making them less willing to publicly correct it.

This is not a simple volume effect. It also creates a clear social psychological mechanism. The same online network condition can produce informational benefit and expressive inhibition.

The project can explain misinformation persistence as a networked gap between private recognition and public correction.
