# 39. Validation and Mechanism Manuscript Figures

## Purpose

This round creates manuscript-level figures for measurement validation and observational mechanism results.

The figure set follows the current manuscript boundary:

> anti-institutional climate is frozen out of the main analysis, control set, and robustness discussion.

## No-Anti Observational Rerun

The observational models were rerun after adding an explicit `--exclude-anti-institutional` option.

Updated scripts:

- `src/fit_thread_climate_models.py`
- `src/fit_thread_climate_score_models.py`

New model outputs:

- Logit: `outputs/thread_climate_logit_no_anti_latest_pair_ensemble_20260701T092000Z`
- Score-based OLS: `outputs/thread_climate_score_ols_no_anti_latest_pair_ensemble_20260701T092500Z`

Both run summaries record:

- `anti_institutional_included = false`
- `nobs = 89,251`

## Main Observational Results

The no-anti logit keeps the main direction of the previous results.

| Predictor | Estimate | p-value |
|---|---:|---:|
| Cross-group user | OR = 1.138 | 0.0104 |
| High early audience structural heterogeneity | OR = 1.083 | 0.0888 |
| Cross-group x high early audience structural heterogeneity | OR = 1.160 | 0.0892 |
| Early correction norm | OR = 1.877 | < 0.001 |
| High hostility | OR = 0.854 | 0.0173 |
| High early discursive heterogeneity | OR = 1.188 | < 0.001 |

The score-based OLS gives clearer support for the layered heterogeneity interaction.

| Predictor | Estimate | p-value |
|---|---:|---:|
| Cross-group user | 0.0216 | < 0.001 |
| High early audience structural heterogeneity | 0.0092 | 0.110 |
| Cross-group x high early audience structural heterogeneity | 0.0234 | 0.0308 |
| Early correction norm | 0.0779 | < 0.001 |
| Norm x hostility | -0.0291 | < 0.001 |
| High early discursive heterogeneity | 0.0258 | < 0.001 |

## Figure Run

Figure output directory:

- `outputs/manuscript_validation_mechanism_figures_20260701T093000Z`

Generation script:

- `src/visualize_validation_mechanism_figures.py`

Run command:

```bash
python src/visualize_validation_mechanism_figures.py
```

## Figure Set

### Figure 1. Detector Validation and Corpus Coverage

Files:

- `figures/fig1_detector_validation_and_coverage.pdf`
- `figures/fig1_detector_validation_and_coverage.png`

Panel A reports audit3 detector metrics:

- AP = 0.726
- ROC-AUC = 0.850
- F1 at threshold 0.5 = 0.678
- Precision at threshold 0.5 = 0.668
- Recall at threshold 0.5 = 0.688

Panel B reports corpus coverage:

- 165,061 comments
- 88,689 comments with pair candidates
- 107,023 candidate claim-response pairs
- 23,780 predicted public correction comments
- 16,976 legacy comment-model predicted corrections

### Figure 2. Observational Mechanism Results

Files:

- `figures/fig2_observational_mechanism_results.pdf`
- `figures/fig2_observational_mechanism_results.png`

Panel A reports focal no-anti logit odds ratios.

Panel B reports predicted correction probability by cross-group position and early audience structural heterogeneity:

| Early audience structural heterogeneity | Non-cross | Cross-group |
|---|---:|---:|
| Low | 14.8% | 16.4% |
| High | 15.8% | 19.7% |

Panel C reports the score-based version:

| Early audience structural heterogeneity | Non-cross | Cross-group |
|---|---:|---:|
| Low | 18.0% | 20.2% |
| High | 18.9% | 23.4% |

## Manuscript Alignment

The Results section now follows this figure order:

1. Measurement validation: Figure 1
2. Cross-group position and layered heterogeneity: Figure 2
3. ABM condition map: Figure 3
4. ABM counterfactual shifts: Figure 4

The main claim remains:

> Cross-group position is associated with correction capacity. Correction activation depends on local thread conditions, especially early correction norm and hostility. Early audience structural heterogeneity conditions how strongly cross-group position converts into later public correction.
