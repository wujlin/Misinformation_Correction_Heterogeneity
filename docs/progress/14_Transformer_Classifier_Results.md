# Transformer Classifier Results

## Purpose

This step moves from lightweight text classifiers to a transformer classifier after the expanded Qwen-assisted labels were manually checked and found to be broadly consistent with human judgment. The label source should therefore be described as human-audited LLM-assisted labels rather than unaudited model labels.

The main question is whether a stronger correction detector changes the empirical conclusion. The transformer improves public-correction detection substantially, but the core thread-climate interpretation remains stable.

## Model Setup

The transformer run fine-tunes:

```text
distilroberta-base
```

The run uses:

```text
labels = outputs/llm_qwen_public_correction_combined_2760_20260625T062000Z/llm_annotations.csv
usable binary labels = 2,755
negative labels = 1,988
positive labels = 767
feature mode = text_only
max length = 256
epochs = 4
class weight = balanced
threshold = selected on validation F1
```

The output directory is:

```text
outputs/transformer_correction_distilroberta_textonly_20260626T101000Z
```

The script is:

```text
src/train_transformer_correction_classifier.py
```

## Predictive Performance

The transformer improves the correction detector compared with the previous text-only word-char logistic regression.

Previous lightweight classifier:

```text
text_only + word_char_logreg_balanced
CV positive F1 = 0.594
CV ROC-AUC = 0.804
CV average precision = 0.632
```

Transformer classifier:

```text
validation positive F1 = 0.677
validation ROC-AUC = 0.864
validation average precision = 0.706

test positive F1 = 0.733
test precision = 0.676
test recall = 0.800
test ROC-AUC = 0.894
test average precision = 0.732
```

These numbers are not an external validation result because the test split comes from the same human-audited LLM-assisted label pool. They are still useful for model selection because they show that the transformer captures public-correction language better than the lightweight text model.

## Full Prediction Result

Applied to the full COVID vaccine comment dataset, the transformer predicts more public corrections:

```text
comments = 165,061
threads = 10,220
predicted public corrections = 18,953
threads with predicted public correction = 5,428
```

Compared with the best-threshold lightweight model:

```text
predicted public corrections:
  14,246 -> 18,953

threads with predicted public correction:
  4,069 -> 5,428

high-participation no-correction threads:
  510 -> 218
```

This change matters substantively. Some apparent correction absence in the lightweight model was likely caused by missed correction language. The correction-misallocation claim remains present, but its magnitude should be reduced when using the transformer detector.

## Thread Climate Results

The transformer-based thread-climate run is:

```text
outputs/thread_climate_dynamic_transformer_distilroberta_textonly_20260626T102000Z
```

The main descriptive quantities are:

```text
later predicted public corrections = 10,207
threads with later predicted correction = 2,197
high-participation no-correction threads = 218
threads with sanction-to-correction cue = 343
```

The descriptive contrasts remain consistent with the earlier thread-climate interpretation:

```text
low hostility:
  non-cross correction rate = 0.117
  cross correction rate = 0.159

high hostility:
  non-cross correction rate = 0.078
  cross correction rate = 0.107
```

Cross-group users still show higher descriptive correction rates, but the gap is smaller in high-hostility threads. This supports a moderated local-climate interpretation rather than a simple cross-group suppression claim.

Early correction norm remains important:

```text
without early correction:
  non-cross correction rate = 0.059
  cross correction rate = 0.073

with early correction:
  non-cross correction rate = 0.152
  cross correction rate = 0.208
```

The strongest descriptive pattern is therefore not that cross-group users disappear. The stronger pattern is that visible early correction changes the local environment in which later correction occurs.

## Logit Result

The transformer-based later-correction logit is:

```text
outputs/thread_climate_logit_transformer_distilroberta_textonly_20260626T102500Z
```

The model converged:

```text
observations = 89,251
outcome mean = 0.106
pseudo R2 = 0.057
standard errors = clustered by thread
```

The main coefficients are:

```text
early correction norm:
  odds ratio = 2.69
  p < 0.001

hostility climate:
  odds ratio = 0.84
  p = 0.019

anti-institutional climate:
  odds ratio = 1.46
  p < 0.001

cross-group user:
  odds ratio = 1.19
  p = 0.092

cross-group x hostility:
  odds ratio = 0.76
  p = 0.203

cross-group x early correction norm:
  odds ratio = 1.02
  p = 0.882

cross-group x hostility x early norm:
  odds ratio = 1.60
  p = 0.066
```

The controlled model supports the same core interpretation as the lightweight-model reruns. Early correction norm is positively associated with later correction. Hostility is negatively associated with later correction. Anti-institutional climate is positively associated with later correction, likely because contested misinformation environments create more correction opportunities.

The cross-group mechanism remains secondary. The cross-group main effect is weakly positive rather than suppressive, and the interaction terms do not provide a clean suppression result. It should not be written as the central empirical finding.

## Updated Interpretation

The transformer results strengthen the measurement layer and refine the substantive claim.

First, public correction is more common than the lightweight classifier suggested. The transformer detects substantially more correction comments and reduces the number of high-participation threads with no predicted correction. This means that correction misallocation exists, but the earlier magnitude was partly affected by model under-detection.

Second, the thread-climate mechanism is stable across detector choices. Early visible correction remains strongly associated with later correction, and hostile climate remains negatively associated with later correction. This supports the claim that public correction depends on local correction-supportive conditions.

Third, the current evidence does not support a strong cross-group suppression thesis. Cross-group users are often more active in correction, and the formal model does not show a stable inhibition pattern. The paper should therefore not claim that structurally heterogeneous users are systematically silenced.

The current main contribution should be framed as:

```text
Misinformation persistence is partly a local correction-environment problem. Public correction becomes more likely when correction is already visible in the thread, and less likely when the discussion climate is hostile. A stronger transformer detector shows that public correction is more common than the lightweight model suggested, but correction still depends on local thread conditions rather than only on the presence of knowledgeable or cross-community users.
```

## Next Step

The next modeling step should compare one or two stronger transformer variants rather than adding unrelated features. A useful sequence is:

```text
1. run roberta-base with the same split and output format;
2. optionally run deberta-v3-base if model download is stable;
3. keep distilroberta-base as the fast baseline;
4. choose the final detector based on held-out performance and downstream stability;
5. rerun the main figures and tables with the selected detector.
```

The current distilroberta-base run is already strong enough to replace the lightweight classifier for exploratory downstream analysis.
