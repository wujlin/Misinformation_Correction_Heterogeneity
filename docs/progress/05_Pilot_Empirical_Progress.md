# Pilot Empirical Progress

## Current Purpose

The first empirical task is to determine whether the proposed correction-misallocation study can be supported by real Reddit data. The pilot does not test the full theory yet. It checks whether three empirical objects are observable: candidate public corrections, exposed-but-not-correcting users, and cross-community variation in user activity.

## Data Used

The current pilot uses `christinegu27/reddit_covidvaccine_data`, a public Reddit COVID-19 vaccine discussion dataset. The dataset contains 10,836 submissions and 165,061 comments from 12 subreddits, including `conspiracy`, `coronavirus`, `news`, `conservative`, `covidvaccinated`, `covid19`, and vaccine-related communities.

The dataset is useful for a feasibility test because it contains thread structure, author IDs, subreddit labels, parent comment IDs, and submission titles. The dataset is not sufficient for final user-history analysis because it does not contain complete Reddit-wide posting histories.

## First-Pass Results

The first-pass keyword retrieval identifies 6,697 candidate correction comments. These comments are not validated public corrections. They are retrieval candidates for manual annotation.

At the thread level, 2,961 out of 10,220 threads contain at least one candidate correction. This means public correction is frequent enough to construct a positive class for annotation and later classifier development.

The pilot also constructs 138,788 exposed-but-not-candidate-correcting author instances at the thread level. This result is important because the project requires a denominator, not only a list of visible correctors. Reddit thread participation allows the study to approximate users who were present in the discussion but did not produce a candidate correction.

At the user level, 58,278 non-deleted users are observed. Among users with at least two comments in the dataset, 3,634 are observed in more than one subreddit and 1,119 are observed in more than one community group. This supports a limited within-dataset proxy for structural heterogeneity.

## Preliminary Community Pattern

The pilot groups subreddits into three proxy categories:

- `skeptical_or_anti_institutional`
- `public_health_or_news`
- `vaccine_experience_or_health`

Candidate correction rates differ across these groups. The `vaccine_experience_or_health` group has the highest candidate correction comment rate. The `public_health_or_news` group has the lowest candidate correction comment rate. The `skeptical_or_anti_institutional` group is in between but contains the largest number of candidate corrections because it has much larger discussion volume.

This pattern should not be interpreted as a substantive finding yet. The current correction label is only a keyword flag, and the community grouping is a proxy. The pattern is useful because it suggests that the data contain enough variation to justify manual annotation and model-based analysis.

## Current Outputs

The exploratory run is stored locally at:

```text
outputs/pilot_covidvaccine_descriptive_20260624T151500Z
```

Key files:

- `metrics/run_summary.json`
- `tables/subreddit_profiles.csv`
- `tables/community_group_profiles.csv`
- `tables/thread_profiles_top.csv`
- `tables/user_profiles_top.csv`
- `annotation/annotation_sample.csv`
- `annotation/annotation_codebook.md`

## Next Step

The next step is manual annotation of `annotation_sample.csv`. The annotation should validate whether the candidate retrieval flag can identify real public corrections with acceptable precision. After annotation, the project can train or evaluate a correction classifier and replace the keyword flag with a validated correction label.

The broader Watchful1/Pushshift archive remains useful for scaling the study. The current GitHub dataset is enough for feasibility analysis but not enough for final claims about complete user-level network structure.

## LLM-Assisted Annotation Update

Qwen3-8B was used on WSA to label the 360-comment annotation sample. The output is stored locally at:

```text
outputs/llm_qwen_public_correction_annotation_gpu0_20260625T003500Z
```

The model labeled 91 comments as public correction and 269 comments as not public correction. Among keyword-based candidate comments, 76 out of 180 were labeled as public correction. Among non-candidate comments, 15 out of 180 were labeled as public correction.

This result supports the current workflow. The keyword flag is useful for retrieval but too noisy to serve as the final dependent variable. The next step is to use the LLM-assisted labels for classifier development and then validate a subset manually.
