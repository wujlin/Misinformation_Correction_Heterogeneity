# LLM-Assisted Annotation Progress

## Purpose

This step uses Qwen3-8B to conduct a first pass of model-assisted annotation on the 360-comment pilot sample. The purpose is to evaluate whether the keyword-based `candidate_correction` flag is a useful retrieval aid for public correction, not to replace human validation.

## Run

The annotation was run on WSA using GPU0 only. GPU1 was already occupied by another task, so GPU0 was selected through `CUDA_VISIBLE_DEVICES=0`.

Remote output:

```text
/home/jinlin/projects/Misinformation_Correction_Heterogeneity/outputs/llm_qwen_public_correction_annotation_gpu0_20260625T003500Z
```

Local synced output:

```text
outputs/llm_qwen_public_correction_annotation_gpu0_20260625T003500Z
```

Model and settings:

- Model: `Qwen/Qwen3-8B`
- Environment: WSA `dpl`
- GPU: GPU0
- dtype: `bfloat16`
- temperature: `0`
- max new tokens: `120`
- rows: `360`
- elapsed time: about `540` seconds

## Main Result

Qwen labels:

```text
public correction = 91
not public correction = 269
```

The keyword-based retrieval flag has a useful but imperfect relationship with the Qwen label:

```text
candidate_correction = 1: 76 / 180 labeled as public correction
candidate_correction = 0: 15 / 180 labeled as public correction
```

This implies two preliminary points. First, the keyword flag is useful for enriching public-correction cases. Second, the keyword flag misses some correction comments, so it should not be used as the final dependent variable.

## Community Pattern

Qwen-labeled public correction rates in the balanced annotation sample:

```text
public_health_or_news: 22 / 120
skeptical_or_anti_institutional: 26 / 120
vaccine_experience_or_health: 43 / 120
```

The `vaccine_experience_or_health` group has the highest public-correction rate in this model-assisted sample. This should be treated as an annotation-stage signal rather than a substantive empirical finding, because the sample is balanced by retrieval status and community group.

## Interpretation Boundary

These are LLM-assisted labels, not human ground truth. The labels are useful for checking the codebook, estimating the noise in the keyword flag, and preparing a classifier. A human-validated subset is still needed before paper-level claims about correction behavior.

## Next Step

The next empirical step is to train or evaluate a lightweight correction classifier using:

- comment body;
- submission title;
- subreddit;
- keyword flag;
- Qwen-assisted label.

The classifier should then be applied to the full comment dataset and compared against a human-validated subset.
