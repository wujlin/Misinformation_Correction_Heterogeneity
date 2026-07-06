# Figure Caption and Alignment Notes

## Purpose

This note records the current figure-text alignment for the detector, observational, and ABM figure sets. It provides draft captions for manuscript assembly.

## Current Main Figure Set

Main candidate figures:

- `fig1_detector_validation_and_coverage.pdf`
- `fig2_observational_mechanism_results.pdf`
- `fig3_abm_correction_activation_condition_map.pdf`
- `fig4_abm_counterfactual_activation_shift.pdf`

Appendix candidate figures:

- `fig1_abm_empirical_population_architecture.pdf`
- `fig2_abm_calibration_forest.pdf`
- `figS1_abm_monte_carlo_uncertainty.pdf`

## Detector Evaluation Figure

File:

- `outputs/manuscript_validation_mechanism_figures_20260701T093000Z/figures/fig1_detector_validation_and_coverage.pdf`

Visible content:

- Panel A reports independent-audit metrics from the pair-ensemble detector.
- Average precision is 0.726.
- ROC-AUC is 0.850.
- F1 at threshold 0.5 is 0.678.
- Precision at threshold 0.5 is 0.668.
- Recall at threshold 0.5 is 0.688.
- Panel B reports corpus coverage.
- The full corpus contains 165,061 comments.
- The pair-candidate pool covers 88,689 comments and 107,023 candidate claim-response pairs.
- The relation-aware detector identifies 23,780 predicted public correction comments.
- The earlier comment-level detector identifies 16,976 predicted correction comments.

Draft caption:

> Figure 1. Detector evaluation and full-corpus coverage. Panel A reports independent-audit metrics for the relation-aware public correction detector used in thread-level behavioral analysis. Panel B reports the full comment corpus, candidate claim-response pairs, predicted public correction comments, and earlier comment-level correction labels.

Recommended placement:

- Main Results, Measurement Validation subsection.
- This figure supports the measurement claim before the substantive models.

## Observational Mechanism Figure

File:

- `outputs/manuscript_validation_mechanism_figures_20260701T093000Z/figures/fig2_observational_mechanism_results.pdf`

Visible content:

- Panel A reports focal odds ratios from the main heterogeneity logit model.
- Cross-group user, early correction norm, high hostile thread climate, and high early discursive heterogeneity have intervals that exclude 1.
- High early audience structural heterogeneity and the cross-group by audience-heterogeneity interaction are positive and less precise in the binary logit.
- Panel B reports predicted correction probabilities for cross-group and non-cross-group users under low and high early audience structural heterogeneity.
- Panel C reports the same scenario pattern with the score-based correction outcome.
- The cross-group advantage is larger when early audience structural heterogeneity is high.

Draft caption:

> Figure 2. Observational evidence for correction capacity and layered heterogeneity. Panel A reports focal odds ratios from the main heterogeneity logit model. Values above 1 indicate a higher probability of later public correction. Horizontal lines show 95% confidence intervals. Blue markers indicate p < 0.05. Panel B reports model-predicted correction probabilities by cross-group position and early audience structural heterogeneity. Panel C reports the same scenario comparison using the score-based correction outcome.

Recommended placement:

- Main Results, Cross-Group Position and Layered Heterogeneity subsections.
- This figure connects user-level structural position with thread-level audience structure.

## Current ABM Figure Set

Main ABM candidate figures:

- `fig3_abm_correction_activation_condition_map.pdf`
- `fig4_abm_counterfactual_activation_shift.pdf`

Appendix ABM candidate figures:

- `fig1_abm_empirical_population_architecture.pdf`
- `fig2_abm_calibration_forest.pdf`
- `figS1_abm_monte_carlo_uncertainty.pdf`

## Figure 1

File:

- `outputs/manuscript_abm_figures_20260701T083000Z/figures/fig1_abm_empirical_population_architecture.pdf`

Visible content:

- The figure shows the empirical-population ABM workflow.
- The workflow starts from 165,061 observed Reddit comments.
- A relation-aware correction detector produces pair-level correction scores.
- The empirical agent population contains 89,251 thread-authors.
- The calibrated ABM runs 13 contexts with 500 Monte Carlo draws.
- Observable conditions include cross-group position, audience structure, correction norm, and hostile thread climate.
- Macro correction supply is measured by correction rate and activated threads.

Draft caption:

> Figure 1. Empirical-population ABM design. The model starts from observed Reddit COVID-19 vaccination discussions, applies a relation-aware correction detector, constructs 89,251 empirical thread-author agents, and simulates correction behavior across calibrated discussion contexts. Observable conditions include cross-group position, audience structure, early correction norm, and hostile thread climate. The macro outcomes are simulated correction rate and activated threads.

Recommended placement:

- Appendix or Methods.
- The figure is useful for explaining the ABM workflow, but Results currently needs Figure 3 and Figure 4 more directly.

## Figure 2

File:

- `outputs/manuscript_abm_figures_20260701T083000Z/figures/fig2_abm_calibration_forest.pdf`

Visible content:

- The figure shows odds ratios from the calibrated heterogeneity logit.
- Values above 1 indicate higher correction probability.
- Early correction norm has the largest positive association.
- Cross-group user and high early discursive heterogeneity are positive.
- High hostile thread climate is below 1.
- Some interaction and audience-heterogeneity estimates are less precise.

Draft caption:

> Figure 2. Calibration model for the empirical-population ABM. Points show odds ratios from the calibrated heterogeneity logit model, and horizontal lines show uncertainty intervals. Values above 1 indicate a higher probability of later public correction. Early correction norm has the largest positive association, while high hostile thread climate is associated with a lower probability of later public correction.

Recommended placement:

- Appendix or Results support.
- The main text already reports the key odds ratios for cross-group position, early correction norm, and hostile thread climate.

## Figure 3

File:

- `outputs/manuscript_abm_figures_20260701T083000Z/figures/fig3_abm_correction_activation_condition_map.pdf`

Visible content:

- The figure is a 2 x 2 condition map.
- The x-axis is early correction norm: absent or present.
- The y-axis is hostile thread climate: low or high.
- Cell color indicates simulated correction rate.
- Cell text reports correction rate, activated-thread count, and activated-thread change from observed baseline.
- The highest activation occurs when early correction norm is present and hostile thread climate is low.
- The lowest activation occurs when early correction norm is absent and hostile thread climate is high.

Draft caption:

> Figure 3. Correction activation under early correction norm and hostile thread climate. The heatmap shows simulated correction rates across four local thread contexts. Each cell reports the simulated correction rate, activated-thread count, and activated-thread change from the observed baseline.

Recommended placement:

- Main Results.
- This figure directly supports the correction-activation argument.

## Figure 4

File:

- `outputs/manuscript_abm_figures_20260701T083000Z/figures/fig4_abm_counterfactual_activation_shift.pdf`

Visible content:

- Panel A shows correction-rate change in percentage points.
- Panel B shows activated-thread change.
- Blue bars indicate increases relative to observed baseline.
- Red bars indicate decreases relative to observed baseline.
- Early correction norm with low hostile thread climate has the largest positive shift.
- No early correction norm with high hostile thread climate has the largest negative shift.
- Universal early correction norm and all-cross-group scenarios also increase correction supply.
- No early correction norm and universal hostile thread climate reduce correction supply.

Draft caption:

> Figure 4. Scenario shifts in correction supply relative to the observed baseline. Panel A reports simulated correction-rate changes in percentage points. Panel B reports changes in activated threads. Blue bars indicate increases relative to the observed baseline, and red bars indicate decreases.

Recommended placement:

- Main Results.
- This figure supports the claim that local activation conditions have larger system-level consequences than early audience structural heterogeneity alone.

## Figure S1

File:

- `outputs/manuscript_abm_figures_20260701T083000Z/figures/figS1_abm_monte_carlo_uncertainty.pdf`

Visible content:

- The figure shows simulated correction-rate distributions across 500 Monte Carlo draws.
- Scenarios are ordered from low correction rate to high correction rate.
- The observed baseline sits between universal hostile thread climate and all-cross-group scenarios.
- Early correction norm with low hostile thread climate has the highest distribution.
- No early correction norm with high hostile thread climate has the lowest distribution.

Draft caption:

> Figure S1. Monte Carlo uncertainty in selected ABM scenarios. Violin distributions show simulated correction rates across 500 Monte Carlo draws. Black points indicate scenario means. The scenario ordering is stable across draws: high hostile-thread-climate conditions without early correction norm produce the lowest correction rates, and low hostile-thread-climate conditions with early correction norm produce the highest correction rates.

Recommended placement:

- Appendix.
- This figure supports simulation stability. The main substantive argument rests on Figure 3 and Figure 4.

## Current Main-Text Alignment

Results currently uses Figure 1, Figure 2, Figure 3, and Figure 4.

- Figure 1 supports the measurement-validation claim.
- Figure 2 supports the cross-group and layered-heterogeneity claims.
- Figure 3 supports the claim that early correction norm and hostile thread climate jointly shape correction activation.
- Figure 4 supports the claim that local activation conditions have larger system-level consequences than changing early audience structural heterogeneity alone.

Remaining figure tasks for manuscript assembly:

- Keep LaTeX captions synchronized with the current generated figure labels.
- Re-check detector and observational figure labels after final journal-template placement.
- Decide whether the ABM architecture and calibration figures stay in the appendix or become Methods/Results figures after the full manuscript layout is assembled.
