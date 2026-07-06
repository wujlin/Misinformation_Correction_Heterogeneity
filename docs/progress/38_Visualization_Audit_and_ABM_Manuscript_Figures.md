# 38. Visualization Audit and ABM Manuscript Figures

## Purpose

This round reviews whether previous analysis stages already produced manuscript-level visualizations and generates a publication-style ABM figure set.

The aim is not to make the ABM visually decorative. The aim is to show the information that the ABM adds beyond the observational models:

> fixed empirical Reddit population, changed observable conditions, and simulated macro-level correction supply.

## Visualization Audit

Before this round, the repository had only one ABM figure pair:

- `outputs/abm_empirical_calibrated_no_anti_20260701T075000Z/figures/abm_scenario_correction_rate_change.pdf`
- `outputs/abm_empirical_calibrated_no_anti_20260701T075000Z/figures/abm_scenario_correction_rate_change.png`

The earlier detector, annotation, misallocation, thread-climate, logit, and score-model stages were mainly stored as tables, metrics, and written summaries. They did not yet have systematic manuscript-level figures.

The audit table is saved at:

- `outputs/manuscript_abm_figures_20260701T083000Z/existing_figure_audit.csv`

## New Figure Run

Figure output directory:

- `outputs/manuscript_abm_figures_20260701T083000Z`

Generation script:

- `src/visualize_abm_manuscript_figures.py`

Run command:

```bash
python3 src/visualize_abm_manuscript_figures.py \
  --output-dir outputs/manuscript_abm_figures_20260701T083000Z
```

The run uses the calibrated ABM output:

- `outputs/abm_empirical_calibrated_no_anti_20260701T075000Z`

## Figure Set

### Figure 1. Empirical-Population ABM Architecture

Files:

- `figures/fig1_abm_empirical_population_architecture.pdf`
- `figures/fig1_abm_empirical_population_architecture.png`

This figure explains how the simulation is built from observed Reddit discussions, pair-level correction detection, empirical thread-author agents, and calibrated scenario simulations.

Best use:

- Methods figure;
- appendix overview;
- presentation slide.

This figure should not be used as the main results figure because it explains model construction rather than reporting findings.

### Figure 2. Calibration Forest Plot

Files:

- `figures/fig2_abm_calibration_forest.pdf`
- `figures/fig2_abm_calibration_forest.png`

This figure shows the no-anti logit coefficients used to calibrate agent correction probabilities. It supports the claim that simulation probabilities are empirically calibrated rather than hand-assigned.

Best use:

- Methods/results bridge;
- appendix if the main text already reports the model table.

### Figure 3. Correction Activation Condition Map

Files:

- `figures/fig3_abm_correction_activation_condition_map.pdf`
- `figures/fig3_abm_correction_activation_condition_map.png`

This is the most informative ABM result figure.

The figure shows the 2 x 2 condition map between early correction norm and hostility climate. Cell color reports simulated correction rate. Cell text reports correction rate, activated threads, and change in activated threads relative to the observed baseline.

Best use:

- main ABM result figure.

The figure supports a precise mechanism statement:

> correction activation is strongest when an early correction norm is present and hostility is low, and weakest when early correction norm is absent and hostility is high.

### Figure 4. Counterfactual Activation Shift

Files:

- `figures/fig4_abm_counterfactual_activation_shift.pdf`
- `figures/fig4_abm_counterfactual_activation_shift.png`

This figure compares scenario-level changes relative to the observed baseline. Panel A shows correction-rate change. Panel B shows activated-thread change.

Best use:

- main or secondary ABM result figure.

This figure is useful because it turns correction-rate changes into a system-level communication outcome: how many threads become correction-active.

### Figure S1. Monte Carlo Uncertainty

Files:

- `figures/figS1_abm_monte_carlo_uncertainty.pdf`
- `figures/figS1_abm_monte_carlo_uncertainty.png`

This figure shows the distribution of simulated correction rates across 500 Monte Carlo draws for selected scenarios.

Best use:

- appendix;
- robustness or simulation-stochasticity check.

The figure should be described as Monte Carlo stochasticity, not full measurement uncertainty.

## Recommended Manuscript Use

The main text should not include every figure. The cleanest arrangement is:

- Main Figure: `fig3_abm_correction_activation_condition_map`
- Main or secondary Figure: `fig4_abm_counterfactual_activation_shift`
- Methods or appendix: `fig1_abm_empirical_population_architecture`
- Appendix: `fig2_abm_calibration_forest`
- Appendix: `figS1_abm_monte_carlo_uncertainty`

This arrangement keeps the main manuscript focused on the ABM's distinct contribution: how calibrated individual correction probabilities accumulate into different levels of correction activation under counterfactual observable contexts.

## Wording Rules

Use:

> simulated scenario difference

Avoid:

> causal intervention effect

Use:

> activated threads

Avoid:

> corrected misinformation environments

Use:

> Monte Carlo stochasticity

Avoid:

> total uncertainty

Use:

> the fitted mechanism is sufficient to generate different levels of correction supply

Avoid:

> the ABM proves the mechanism
