# Heterogeneity-Targeted Annotation Sample

## Purpose

The heterogeneity model shows a near-significant association:

```text
high_early_audience_structural_heterogeneity:
  odds ratio = 1.12
  p = 0.080
```

This effect should not be treated as a coefficient to tune. The defensible next step is to reduce measurement error in the public-correction dependent variable around the strata that identify this effect.

The targeted annotation sample therefore focuses on comments from threads with and without high early audience structural heterogeneity. It oversamples high-heterogeneity threads while retaining a low-heterogeneity control group.

## Output

The final targeted sample is:

```text
outputs/heterogeneity_targeted_annotation_sample_deberta_20260626T124000Z
```

The main files are:

```text
annotation_sample_blind.csv
annotation_sample_with_metadata.csv
tables/sample_strata_counts.csv
metrics/run_summary.json
```

The sample excludes the existing 2,760 combined Qwen-assisted labels:

```text
outputs/llm_qwen_public_correction_combined_2760_20260625T062000Z/llm_annotations.csv
```

## Sampling Design

The sample contains 1,200 new comments:

```text
high early audience structural heterogeneity = 720
low early audience structural heterogeneity = 480
```

The sample is also stratified by:

```text
early correction norm presence
current DeBERTa predicted label
DeBERTa score bin
community group
```

The score-bin distribution is:

```text
very_low = 150
low_mid = 150
near_negative = 150
near_positive = 600
very_high = 150
```

The sample intentionally emphasizes `near_positive` rows because those cases are most likely to affect thresholded public-correction outcomes after additional annotation and retraining.

## Why This Sample Matters

The current heterogeneity effect may be attenuated by correction-label noise. If comments in high-heterogeneity threads are systematically under-detected or over-detected, the estimated coefficient for early audience heterogeneity can move after better labels are added.

This sample can support two checks:

```text
1. targeted measurement validation:
   Are public-correction labels less accurate in high early audience heterogeneity threads?

2. targeted retraining:
   After adding these labels, does the DeBERTa detector change the heterogeneity model result?
```

The expected analysis should compare the pre- and post-annotation heterogeneity model. The key question is not whether the p-value crosses 0.05, but whether the coefficient direction and magnitude remain stable after targeted measurement improvement.

## Qwen Annotation Command

When WSA and the local Qwen model are available, run:

```bash
python src/llm_annotate_public_correction.py \
  --input outputs/heterogeneity_targeted_annotation_sample_deberta_20260626T124000Z/annotation_sample_with_metadata.csv \
  --output-dir outputs/llm_qwen_public_correction_heterogeneity_targeted_20260626T124500Z \
  --model /path/to/local/qwen/model \
  --dtype bfloat16 \
  --device-map auto \
  --temperature 0.0 \
  --max-new-tokens 220 \
  --save-every 50 \
  --log-every 20 \
  --resume
```

The current local environment does not have `torch` or `transformers`, so this annotation step should run on WSA.

## After Annotation

After Qwen produces `llm_annotations.csv`, combine the previous and new labels:

```bash
python src/combine_llm_annotations.py \
  --inputs \
    outputs/llm_qwen_public_correction_combined_2760_20260625T062000Z/llm_annotations.csv \
    outputs/llm_qwen_public_correction_heterogeneity_targeted_20260626T124500Z/llm_annotations.csv \
  --output-dir outputs/llm_qwen_public_correction_combined_3960_heterogeneity_targeted_20260626T125000Z
```

Then retrain the detector and rerun:

```text
1. DeBERTa public-correction detector
2. full-comment prediction
3. correction misallocation tables
4. heterogeneity dynamic tables
5. heterogeneity logit model
```

## Interpretation Rule

If the effect becomes stronger after targeted labeling, the correct interpretation is:

```text
Additional targeted labels reduced measurement error in high-heterogeneity contexts, making the early audience heterogeneity association clearer.
```

If the effect remains weak, the correct interpretation is:

```text
The current trace-data proxy for audience heterogeneity does not strongly explain correction continuation beyond structural user heterogeneity and local correction norms.
```

Either outcome is useful. The sample is designed to test whether the near-significant effect is a measurement issue rather than to force a significant result.
